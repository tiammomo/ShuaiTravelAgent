"""
ReAct (Reasoning and Acting) 智能体核心架构
============================================

架构设计理念：
--------------
ReAct模式是一种结合推理和行动的智能体架构，模拟人类解决问题的思维方式。
与传统的"思考后行动"模式不同，ReAct强调在行动中思考，通过观察环境反馈
来动态调整推理策略。

核心循环：Observation(观察) → Thought(思考) → Action(行动) → Feedback(反馈) → State Update(状态更新)

模块说明：
- ToolRegistry: 工具注册与管理
- ThoughtEngine: 思考生成与推理
- EvaluationEngine: 行动结果评估
- ShortTermMemory: 短期记忆（当前会话上下文）
- LongTermMemory: 长期记忆（历史经验学习）
- ReActAgent: 智能体主类，整合各模块实现完整推理循环

作者：AI Assistant
版本：2.0.0
"""

import re
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from collections import deque
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 枚举类型定义 ====================

class AgentState(Enum):
    """智能体状态枚举，表示推理循环的不同阶段"""
    IDLE = auto()           # 空闲状态，等待任务输入
    REASONING = auto()      # 推理中，进行思考和分析
    ACTING = auto()         # 行动中，执行工具调用
    OBSERVING = auto()      # 观察中，等待环境反馈
    EVALUATING = auto()     # 评估中，验证行动结果
    COMPLETED = auto()      # 任务完成
    ERROR = auto()          # 错误状态


class ActionStatus(Enum):
    """行动执行状态枚举"""
    PENDING = auto()        # 待执行
    RUNNING = auto()        # 执行中
    SUCCESS = auto()        # 成功完成
    FAILED = auto()         # 执行失败


class ThoughtType(Enum):
    """思考类型枚举，描述不同推理活动"""
    ANALYSIS = auto()       # 分析问题，理解任务目标
    PLANNING = auto()       # 制定计划，分解任务步骤
    DECISION = auto()       # 做出决策，选择行动方案
    REFLECTION = auto()     # 反思结果，评估行动效果
    INFERENCE = auto()      # 逻辑推理，推导中间结论


# ==================== 数据类定义 ====================

@dataclass
class ToolInfo:
    """
    工具信息数据类

    Attributes:
        name: 工具名称，唯一标识符
        description: 工具功能描述
        parameters: 参数模式定义（JSON Schema格式）
        required_params: 必需参数列表
        timeout: 超时时间（秒）
        category: 工具分类
        tags: 工具标签，用于搜索和筛选
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str] = field(default_factory=list)
    timeout: int = 30
    category: str = "general"
    tags: List[str] = field(default_factory=list)


@dataclass
class Action:
    """
    行动数据类，表示一个待执行或已执行的行动

    Attributes:
        id: 行动唯一标识
        tool_name: 调用的工具名称
        parameters: 工具参数
        status: 执行状态
        result: 执行结果
        error: 错误信息
        duration: 执行时长（毫秒）
    """
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    status: ActionStatus = ActionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: int = 0

    def mark_running(self) -> None:
        """标记为执行中，记录开始时间"""
        self.status = ActionStatus.RUNNING
        self.start_time = datetime.now()

    def mark_success(self, result: Dict[str, Any]) -> None:
        """标记为成功，记录结果和结束时间"""
        self.status = ActionStatus.SUCCESS
        self.result = result
        self.end_time = datetime.now()
        if hasattr(self, 'start_time'):
            self.duration = int((self.end_time - self.start_time).total_seconds() * 1000)

    def mark_failed(self, error: str) -> None:
        """标记为失败，记录错误信息"""
        self.status = ActionStatus.FAILED
        self.error = error
        self.end_time = datetime.now()
        if hasattr(self, 'start_time'):
            self.duration = int((self.end_time - self.start_time).total_seconds() * 1000)


@dataclass
class Thought:
    """
    思考数据类，表示一次推理活动

    Attributes:
        id: 思考唯一标识
        type: 思考类型
        content: 思考内容（推理过程描述）
        confidence: 置信度（0-1）
        reasoning_chain: 推理链（支持多步推理）
        decision: 最终决策
    """
    id: str
    type: ThoughtType
    content: str
    confidence: float = 0.8
    reasoning_chain: List[str] = field(default_factory=list)
    decision: Optional[str] = None


@dataclass
class Observation:
    """
    观察数据类，表示从环境或工具调用获取的观察结果

    Attributes:
        id: 观察唯一标识
        source: 观察来源
        content: 观察内容
        observation_type: 观察类型
    """
    id: str
    source: str
    content: Any
    observation_type: str = "data"


@dataclass
class AgentStateData:
    """智能体状态数据类，存储完整运行状态"""
    task: str = ""
    goal: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    state: AgentState = AgentState.IDLE
    context: Dict[str, Any] = field(default_factory=dict)


# ==================== 工具注册表 ====================

class ToolRegistry:
    """
    工具注册表

    管理所有可用工具的注册、查找和调用。支持动态注册和卸载工具。

    设计要点：
    - 线程安全：使用asyncio.Lock保证并发安全
    - 快速查找：使用字典索引加速工具查找
    - 类别管理：按类别组织工具
    """

    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}              # 工具名称 -> 工具信息
        self._executors: Dict[str, Callable] = {}          # 工具名称 -> 执行函数
        self._lock = asyncio.Lock()

    async def register(self, tool_info: ToolInfo, executor: Callable) -> bool:
        """
        注册工具

        Args:
            tool_info: 工具信息对象
            executor: 工具执行函数

        Returns:
            是否注册成功
        """
        async with self._lock:
            if tool_info.name in self._tools:
                logger.warning(f"工具已存在: {tool_info.name}")
                return False
            self._tools[tool_info.name] = tool_info
            self._executors[tool_info.name] = executor
            logger.info(f"工具注册成功: {tool_info.name}")
            return True

    def get_tool(self, tool_name: str) -> Optional[ToolInfo]:
        """获取工具信息"""
        return self._tools.get(tool_name)

    def get_executor(self, tool_name: str) -> Optional[Callable]:
        """获取工具执行函数"""
        return self._executors.get(tool_name)

    def list_tools(self) -> List[ToolInfo]:
        """列出所有工具"""
        return list(self._tools.values())

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            params: 工具参数

        Returns:
            执行结果

        Raises:
            ValueError: 工具不存在或缺少必需参数
            TimeoutError: 执行超时
        """
        tool_info = self.get_tool(tool_name)
        if not tool_info:
            raise ValueError(f"工具不存在: {tool_name}")

        executor = self.get_executor(tool_name)
        if not executor:
            raise ValueError(f"工具执行函数未注册: {tool_name}")

        # 验证必需参数
        for param in tool_info.required_params:
            if param not in params:
                raise ValueError(f"缺少必需参数: {param}")

        # 执行工具调用
        timeout_duration = tool_info.timeout
        try:
            if asyncio.iscoroutinefunction(executor):
                result = await asyncio.wait_for(executor(**params), timeout=timeout_duration)
            else:
                result = await asyncio.to_thread(executor, **params)
            return result if isinstance(result, dict) else {'result': result}
        except asyncio.TimeoutError:
            raise TimeoutError(f"工具执行超时: {tool_name}")


# ==================== 短期记忆模块 ====================

class ShortTermMemory:
    """
    短期记忆模块

    存储当前会话的上下文信息，支持FIFO淘汰策略。

    Attributes:
        max_size: 最大记忆容量
    """

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._memory: deque = deque(maxlen=max_size)

    def add(self, content: Any, importance: float = 0.5) -> str:
        """
        添加记忆

        Args:
            content: 记忆内容
            importance: 重要性分数（0-1）

        Returns:
            记忆ID
        """
        import uuid
        memory_id = str(uuid.uuid4())
        self._memory.append({
            'id': memory_id,
            'content': content,
            'importance': importance,
            'timestamp': datetime.now().isoformat()
        })
        return memory_id

    def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近记忆"""
        return list(self._memory)[-limit:][::-1] if limit < len(self._memory) else list(self._memory)[::-1]

    def clear(self) -> None:
        """清空记忆"""
        self._memory.clear()

    def __len__(self) -> int:
        return len(self._memory)


# ==================== 思考引擎 ====================

class ThoughtEngine:
    """
    思考引擎

    负责生成和管理思考过程，支持任务分析、计划制定、决策生成等功能。

    Attributes:
        max_reasoning_depth: 最大推理深度
    """

    def __init__(self, max_reasoning_depth: int = 5):
        self.max_reasoning_depth = max_reasoning_depth
        self._thought_counter = 0

    def _create_thought(self, thought_type: ThoughtType, content: str) -> Thought:
        """
        创建思考对象

        Args:
            thought_type: 思考类型
            content: 思考内容

        Returns:
            思考对象
        """
        self._thought_counter += 1
        return Thought(
            id=f"thought_{self._thought_counter}",
            type=thought_type,
            content=content,
            confidence=0.85
        )

    def _extract_task_entities(self, task: str) -> Dict[str, Any]:
        """
        从任务中提取实体信息（城市、天数、预算等）

        Args:
            task: 任务描述

        Returns:
            提取的实体字典
        """
        import re
        entities = {}

        # 提取天数
        days_match = re.search(r'(\d+)\s*天', task)
        entities['days'] = int(days_match.group(1)) if days_match else 3

        # 提取城市 - 多种模式匹配
        city_patterns = [
            r'(?:去|在|到|城市)(.+?)(?:的?路线|旅游|游玩|旅行)?',
            r'(.+?)的?路线',
            r'(.+?)景点',
            r'(?:推荐|适合).*?城市[：:]\s*(.+)',
        ]
        for pattern in city_patterns:
            city_match = re.search(pattern, task)
            if city_match:
                city = city_match.group(1).strip()
                # 过滤非城市内容
                if city and not any(kw in city for kw in ['推荐', '建议', '哪些', '什么']):
                    entities['city'] = city
                    break

        # 提取预算
        budget_match = re.search(r'(\d+)\s*元', task)
        if budget_match:
            entities['budget'] = int(budget_match.group(1))

        # 提取兴趣标签
        interest_keywords = {
            '历史': ['历史', '古迹', '文物'],
            '自然': ['自然', '风景', '山水', '公园'],
            '美食': ['美食', '小吃', '特色菜'],
            '购物': ['购物', '商场', '免税'],
            '亲子': ['亲子', '儿童', '小孩'],
            '海滨': ['海滨', '海滩', '海岛', '沙滩']
        }
        entities['interests'] = []
        for interest, keywords in interest_keywords.items():
            if any(kw in task for kw in keywords):
                entities['interests'].append(interest)

        # 提取季节
        season_match = re.search(r'(春夏秋冬)季', task)
        if season_match:
            entities['season'] = season_match.group(1)

        return entities

    def analyze_task(self, task: str, context: Dict[str, Any]) -> Thought:
        """
        分析任务，理解任务目标和约束

        Args:
            task: 任务描述
            context: 上下文信息

        Returns:
            分析思考
        """
        task_type = self._classify_task(task)
        task_type_cn = {
            "recommendation": "城市推荐",
            "query": "信息查询",
            "planning": "路线规划",
            "budget": "预算计算",
            "general": "一般对话"
        }.get(task_type, "一般对话")

        # 提取实体信息
        entities = self._extract_task_entities(task)
        entity_info = f" | 提取信息: {entities}" if entities else ""

        content = f"【任务分析】用户输入：「{task}」\n【意图识别】任务类型={task_type_cn}{entity_info}"
        thought = self._create_thought(ThoughtType.ANALYSIS, content)

        # 构建详细推理链
        thought.reasoning_chain = [
            f"1. 解析用户原始输入：{task}",
            f"2. 识别用户意图：{task_type_cn}",
        ]

        # 根据任务类型添加不同的推理步骤
        if task_type == "recommendation":
            thought.reasoning_chain.append(f"3. 需要筛选符合用户偏好的城市")
            if entities.get('interests'):
                thought.reasoning_chain.append(f"4. 用户兴趣偏好：{', '.join(entities['interests'])}")
        elif task_type == "planning":
            thought.reasoning_chain.append(f"3. 需要规划具体行程路线")
            if entities.get('city'):
                thought.reasoning_chain.append(f"4. 目标城市：{entities['city']}")
            if entities.get('days'):
                thought.reasoning_chain.append(f"5. 行程天数：{entities['days']}天")
        elif task_type == "query":
            thought.reasoning_chain.append(f"3. 需要查询城市/景点详细信息")

        thought.reasoning_chain.append(f"准备调用相应工具执行任务")

        return thought

    def _classify_task(self, task: str) -> str:
        """分类任务类型"""
        task_lower = task.lower()
        if any(kw in task_lower for kw in ['推荐', '建议', '哪些']):
            return "recommendation"
        elif any(kw in task_lower for kw in ['查询', '搜索', '有什么']):
            return "query"
        elif any(kw in task_lower for kw in ['规划', '计划', '路线', '行程']):
            return "planning"
        return "general"

    def plan_actions(self, task: str, tools: List[ToolInfo],
                     constraints: Optional[List[str]] = None) -> Thought:
        """
        制定行动计划

        Args:
            task: 任务描述
            available_tools: 可用工具列表
            constraints: 约束条件

        Returns:
            计划思考
        """
        steps = self._decompose_task(task, tools)
        step_names = [s.tool_name for s in steps]

        # 生成详细的工具选择说明
        tool_details = []
        for i, step in enumerate(steps, 1):
            tool_info = next((t for t in tools if t.name == step.tool_name), None)
            desc = tool_info.description if tool_info else "未知工具"
            tool_details.append(f"  {i}. {step.tool_name}: {desc}")

        content = f"""【执行计划】根据任务分析结果，制定以下执行方案：

【步骤规划】共{len(steps)}个执行步骤

【工具选择理由】"""
        if steps:
            for i, step in enumerate(steps, 1):
                params_str = ', '.join(f"{k}={v}" for k, v in step.parameters.items())
                content += f"\n  选择 {step.tool_name}，参数：({params_str})"
        else:
            content += "\n  无需工具调用，直接生成回答"

        thought = self._create_thought(ThoughtType.PLANNING, content)
        thought.confidence = 0.9

        # 构建推理链
        thought.reasoning_chain = [
            f"任务分解完成：共{len(steps)}个执行步骤",
        ]
        if step_names:
            thought.reasoning_chain.append(f"工具调用序列：{' → '.join(step_names)}")
        else:
            thought.reasoning_chain.append("无需工具调用")

        thought.reasoning_chain.append("准备按计划执行各步骤")

        # 序列化决策
        if steps:
            thought.decision = json.dumps([{
                'step': i + 1,
                'action': s.tool_name,
                'params': s.parameters
            } for i, s in enumerate(steps)])

        return thought

    def _decompose_task(self, task: str, tools: List[ToolInfo]) -> List[Action]:
        """
        分解任务为行动步骤

        Args:
            task: 任务描述
            tools: 可用工具列表

        Returns:
            行动列表
        """
        import re
        actions = []
        task_lower = task.lower()

        # 检测任务中的实体
        days_match = re.search(r'(\d+)\s*天', task)
        days = int(days_match.group(1)) if days_match else 3

        # 城市信息提取
        city_match = re.search(r'(?:去|在|到|城市)(.+?)(?:的?路线|旅游|游玩)?', task)
        city = city_match.group(1).strip() if city_match else None
        if not city:
            city_match = re.search(r'(.+?)的?路线', task)
            city = city_match.group(1).strip() if city_match else None

        # 搜索相关工具 - 城市推荐/查询
        recommend_tools = [t for t in tools if 'recommend' in t.name.lower() or 'search' in t.name.lower()]
        if recommend_tools and any(kw in task_lower for kw in ['推荐', '建议', '哪些', '适合']):
            actions.append(Action(
                id=f"action_{len(actions)}",
                tool_name=recommend_tools[0].name,
                parameters={'user_query': task, 'available_cities': []}
            ))

        # 城市信息工具
        city_info_tools = [t for t in tools if 'city_info' in t.name.lower() or 'attraction' in t.name.lower()]
        if city_info_tools and city:
            actions.append(Action(
                id=f"action_{len(actions)}",
                tool_name=city_info_tools[0].name,
                parameters={'city': city}
            ))

        # 路线规划工具
        route_tools = [t for t in tools if 'route' in t.name.lower() or 'plan' in t.name.lower()]
        if route_tools and any(kw in task_lower for kw in ['规划', '路线', '行程', '安排']):
            actions.append(Action(
                id=f"action_{len(actions)}",
                tool_name=route_tools[0].name,
                parameters={'city': city, 'days': days}
            ))

        # 预算计算工具
        budget_tools = [t for t in tools if 'budget' in t.name.lower()]
        if budget_tools and any(kw in task_lower for kw in ['预算', '花费', '费用', '多少钱']):
            actions.append(Action(
                id=f"action_{len(actions)}",
                tool_name=budget_tools[0].name,
                parameters={'city': city, 'days': days}
            ))

        # LLM对话工具（兜底）
        if not actions:
            llm_tools = [t for t in tools if 'llm_chat' in t.name.lower()]
            if llm_tools:
                actions.append(Action(
                    id=f"action_{len(actions)}",
                    tool_name=llm_tools[0].name,
                    parameters={'query': task}
                ))

        return actions

    def reflect(self, action_result: Dict[str, Any]) -> Thought:
        """
        反思行动结果

        Args:
            action_result: 行动结果

        Returns:
            反思思考
        """
        thought = self._create_thought(ThoughtType.REFLECTION, "反思行动结果")
        success = action_result.get('success', False)

        thought.reasoning_chain = [
            f"行动成功：{success}",
            f"改进建议：{'结果符合预期' if success else '建议检查参数或尝试其他工具'}"
        ]
        thought.confidence = 0.9 if success else 0.6

        return thought


# ==================== 评估引擎 ====================

class EvaluationEngine:
    """
    评估引擎

    负责评估行动结果和智能体性能。

    Attributes:
        _metrics: 性能指标字典
    """

    def __init__(self):
        self._metrics: Dict[str, Any] = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0
        }

    def evaluate_result(self, action: Action) -> Dict[str, Any]:
        """
        评估行动结果

        Args:
            action: 行动对象

        Returns:
            评估结果
        """
        evaluation = {
            'success': action.status == ActionStatus.SUCCESS,
            'duration': action.duration,
            'has_result': action.result is not None
        }

        # 更新指标
        self._metrics['total_tasks'] += 1
        if evaluation['success']:
            self._metrics['successful_tasks'] += 1
        else:
            self._metrics['failed_tasks'] += 1

        return evaluation


# ==================== ReAct 智能体主类 ====================

class ReActAgent:
    """
    ReAct智能体主类

    整合思考、行动、记忆、评估模块，实现完整的ReAct推理循环。

    使用示例：
    ```python
    agent = ReActAgent(name="TravelAgent")
    agent.register_tool(tool_info, tool_function)
    result = await agent.run("推荐一些旅游城市")
    ```

    核心流程：
    1. 接收任务输入
    2. 分析任务并生成计划
    3. 执行行动（工具调用）
    4. 观察结果
    5. 评估并反思
    6. 更新状态
    7. 决定是否继续或结束
    """

    def __init__(self, name: str = "ReActAgent", max_steps: int = 10,
                 max_reasoning_depth: int = 5):
        """
        初始化ReAct智能体

        Args:
            name: 智能体名称
            max_steps: 最大执行步骤数
            max_reasoning_depth: 最大推理深度
        """
        self.name = name
        self.max_steps = max_steps

        # 初始化组件
        self.tool_registry = ToolRegistry()
        self.thought_engine = ThoughtEngine(max_reasoning_depth)
        self.evaluation_engine = EvaluationEngine()
        self.short_memory = ShortTermMemory()

        # 状态管理
        self.state = AgentStateData(max_steps=max_steps)
        self.current_state = AgentState.IDLE

        # 历史记录
        self.action_history: List[Action] = []
        self.thought_history: List[Thought] = []

        # 回调函数
        self._on_thought_callbacks: List[Callable] = []
        self._on_action_callbacks: List[Callable] = []

    def register_tool(self, tool_info: ToolInfo, executor: Callable) -> bool:
        """
        注册工具

        Args:
            tool_info: 工具信息
            executor: 工具执行函数

        Returns:
            是否注册成功
        """
        # 直接同步注册
        if tool_info.name in self.tool_registry._tools:
            return False
        self.tool_registry._tools[tool_info.name] = tool_info
        self.tool_registry._executors[tool_info.name] = executor
        return True

    def add_thought_callback(self, callback: Callable) -> None:
        """添加思考回调"""
        self._on_thought_callbacks.append(callback)

    def add_action_callback(self, callback: Callable) -> None:
        """添加行动回调"""
        self._on_action_callbacks.append(callback)

    def _notify_thought(self, thought: Thought) -> None:
        """通知思考事件"""
        for callback in self._on_thought_callbacks:
            try:
                callback(thought)
            except Exception as e:
                logger.error(f"思考回调错误: {e}")

    def _notify_action(self, action: Action) -> None:
        """通知行动事件"""
        for callback in self._on_action_callbacks:
            try:
                callback(action)
            except Exception as e:
                logger.error(f"行动回调错误: {e}")

    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行任务

        核心方法：启动ReAct推理循环，执行任务直到完成或达到最大步骤。

        Args:
            task: 任务描述
            context: 初始上下文

        Returns:
            执行结果
        """
        # 初始化任务状态
        self.state.task = task
        self.state.context = context or {}
        self.state.current_step = 0
        self.state.history = []

        old_state = self.current_state
        self.current_state = AgentState.REASONING
        self._notify_state_change = lambda o, n: None  # 简化回调

        logger.info(f"开始执行任务: {task}")

        try:
            # ReAct主循环
            while self.state.current_step < self.max_steps:
                # 步骤1: 观察
                observation = await self._observe()

                # 步骤2: 思考
                thought = await self._think(observation)

                # 步骤3: 判断是否停止
                if self._should_stop(thought):
                    break

                # 步骤4: 行动
                action = await self._act(thought)

                # 步骤5: 评估
                evaluation = await self._evaluate(action)

                # 步骤6: 更新状态
                self._update_state(action, evaluation)

                # 步骤7: 记录历史
                self._record_history(thought, action, evaluation)

            # 任务完成
            self.current_state = AgentState.COMPLETED
            return self._build_result()

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            self.current_state = AgentState.ERROR
            return {
                'success': False,
                'error': str(e),
                'task': task,
                'steps_completed': self.state.current_step
            }

    async def _observe(self) -> Observation:
        """
        观察阶段：获取环境信息和之前行动的结果

        Returns:
            观察结果
        """
        self.current_state = AgentState.OBSERVING

        last_action = self.action_history[-1] if self.action_history else None

        return Observation(
            id=f"obs_{self.state.current_step}",
            source="environment",
            content={
                'last_action': last_action.result if last_action else None,
                'step': self.state.current_step
            }
        )

    async def _think(self, observation: Observation) -> Thought:
        """
        思考阶段：基于观察结果进行推理

        Args:
            observation: 观察结果

        Returns:
            思考结果
        """
        self.current_state = AgentState.REASONING

        # 第一步：任务分析和计划
        if self.state.current_step == 0:
            thought = self.thought_engine.analyze_task(
                self.state.task,
                self.state.context
            )

            if thought.confidence > 0.7:
                plan_thought = self.thought_engine.plan_actions(
                    self.state.task,
                    self.tool_registry.list_tools()
                )
                thought.decision = plan_thought.decision
                thought.reasoning_chain.extend(plan_thought.reasoning_chain)
        else:
            # 后续步骤：基于结果反思和推理
            last_action = self.action_history[-1] if self.action_history else None

            if last_action and last_action.status == ActionStatus.FAILED:
                thought = self.thought_engine.reflect(last_action.result or {})
                thought.content = f"""【执行失败】步骤 {self.state.current_step}

【失败原因】{last_action.error}
【当前状态】需要调整策略或检查参数
【后续行动】尝试其他工具或重新执行"""
            elif last_action and last_action.status == ActionStatus.SUCCESS:
                # 行动成功，分析结果
                result = last_action.result
                tool_name = last_action.tool_name

                # 根据不同工具生成不同的思考内容
                result_info = ""
                if isinstance(result, dict):
                    if result.get('success') and 'cities' in result:
                        cities = result.get('cities', [])
                        result_info = f"获取到 {len(cities)} 个推荐城市：{', '.join(cities[:5])}"
                    elif result.get('success') and 'route_plan' in result:
                        route_days = len(result.get('route_plan', []))
                        result_info = f"路线规划完成，共 {route_days} 天行程"
                    elif 'response' in result:
                        result_info = f"LLM生成回答：{result['response'][:80]}..."
                    elif 'info' in result:
                        result_info = "城市详细信息获取成功"
                    else:
                        result_info = f"工具执行成功，结果类型：{type(result).__name__}"
                else:
                    result_info = f"执行结果：{str(result)[:80]}"

                thought = self.thought_engine._create_thought(
                    ThoughtType.INFERENCE,
                    f"【执行成功】步骤 {self.state.current_step} 完成\n\n【工具】{tool_name}\n【结果】{result_info}"
                )
                thought.reasoning_chain = [
                    f"步骤 {self.state.current_step} 执行状态：成功",
                    f"工具 {tool_name} 返回结果",
                    f"结果摘要：{result_info[:50]}...",
                    f"评估是否需要继续执行或生成最终回答"
                ]
                thought.confidence = 0.95
            else:
                thought = self.thought_engine._create_thought(
                    ThoughtType.INFERENCE,
                    f"【继续执行】步骤 {self.state.current_step + 1}\n\n根据执行计划，继续执行下一步操作"
                )
                thought.reasoning_chain = [f"执行步骤 {self.state.current_step + 1}"]

        self.thought_history.append(thought)
        self._notify_thought(thought)

        return thought

    def _should_stop(self, thought: Thought) -> bool:
        """
        判断是否应该停止执行

        Args:
            thought: 当前思考

        Returns:
            是否应该停止
        """
        # LLM工具执行成功后停止
        if thought.type == ThoughtType.INFERENCE:
            last_action = self.action_history[-1] if self.action_history else None
            if last_action and last_action.tool_name in ['llm_chat', 'generate_city_recommendation', 'generate_route_plan']:
                if last_action.status == ActionStatus.SUCCESS:
                    return True

        # 置信度高且有决策，已执行成功则停止
        if thought.confidence > 0.9 and thought.decision:
            last_action = self.action_history[-1] if self.action_history else None
            if last_action and last_action.status == ActionStatus.SUCCESS:
                return True

        # 达到最大步骤
        if self.state.current_step >= self.max_steps - 1:
            return True

        return False

    async def _act(self, thought: Thought) -> Action:
        """
        行动阶段：根据思考结果执行工具调用

        Args:
            thought: 思考结果

        Returns:
            行动结果
        """
        self.current_state = AgentState.ACTING

        action = self._extract_action(thought)

        if action:
            action.mark_running()
            self.action_history.append(action)
            self._notify_action(action)

            try:
                result = await self.tool_registry.execute(
                    action.tool_name,
                    action.parameters
                )
                action.mark_success(result)
                logger.info(f"工具执行成功: {action.tool_name}")
            except Exception as e:
                action.mark_failed(str(e))
                logger.error(f"工具执行失败: {action.tool_name}: {e}")
        else:
            # 无需执行操作
            action = Action(
                id=f"action_{len(self.action_history)}",
                tool_name="none",
                parameters={},
                status=ActionStatus.SUCCESS
            )
            action.mark_success({'message': '无操作需要执行'})
            self.action_history.append(action)

        return action

    def _extract_action(self, thought: Thought) -> Optional[Action]:
        """
        从思考中提取行动

        Args:
            thought: 思考结果

        Returns:
            行动对象
        """
        if not thought.decision:
            return None

        try:
            if isinstance(thought.decision, str):
                decisions = json.loads(thought.decision)
            else:
                decisions = thought.decision if isinstance(thought.decision, list) else []

            if not decisions:
                return None

            current_step = self.state.current_step
            if current_step < len(decisions):
                decision = decisions[current_step]
                return Action(
                    id=f"action_{len(self.action_history)}",
                    tool_name=decision.get('action', ''),
                    parameters=decision.get('params', {})
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        return None

    async def _evaluate(self, action: Action) -> Dict[str, Any]:
        """
        评估阶段：评估行动结果

        Args:
            action: 行动结果

        Returns:
            评估结果
        """
        self.current_state = AgentState.EVALUATING
        return self.evaluation_engine.evaluate_result(action)

    def _update_state(self, action: Action, evaluation: Dict[str, Any]) -> None:
        """
        更新智能体状态

        Args:
            action: 行动结果
            evaluation: 评估结果
        """
        self.state.current_step += 1
        if action.result:
            self.state.context['last_result'] = action.result
        self.state.updated_at = datetime.now()

    def _record_history(self, thought: Thought, action: Action,
                        evaluation: Dict[str, Any]) -> None:
        """
        记录执行历史

        Args:
            thought: 思考结果
            action: 行动结果
            evaluation: 评估结果
        """
        # 将Action对象转换为字典（保留result用于答案提取）
        action_dict = {
            'id': action.id,
            'tool_name': action.tool_name,
            'status': action.status.name,
            'duration': action.duration,
            'result': action.result,  # 保留结果用于答案提取
            'error': action.error
        }

        self.state.history.append({
            'step': self.state.current_step,
            'thought': {
                'id': thought.id,
                'type': thought.type.name,
                'content': thought.content,
                'confidence': thought.confidence,
                'decision': thought.decision
            },
            'action': action_dict,
            'evaluation': evaluation,
            'timestamp': datetime.now().isoformat()
        })

    def _build_result(self) -> Dict[str, Any]:
        """
        构建最终执行结果

        Returns:
            执行结果字典
        """
        successful_steps = sum(
            1 for step in self.state.history
            if step.get('evaluation', {}).get('success', False)
        )

        return {
            'success': self.current_state == AgentState.COMPLETED,
            'task': self.state.task,
            'steps_completed': len(self.state.history),
            'successful_steps': successful_steps,
            'total_duration': sum(
                step.get('action', {}).get('duration', 0)
                for step in self.state.history
            ),
            'history': self.state.history
        }

    def reset(self) -> None:
        """重置智能体状态"""
        self.state = AgentStateData(max_steps=self.max_steps)
        self.current_state = AgentState.IDLE
        self.action_history.clear()
        self.thought_history.clear()
        self.short_memory.clear()
