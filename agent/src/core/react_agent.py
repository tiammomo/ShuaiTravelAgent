"""
================================================================================
ReAct Agent 核心实现模块
================================================================================

本模块实现了基于 ReAct (Reasoning and Acting) 模式的智能体架构。

ReAct 模式概述：
ReAct 是一种结合推理和行动的人工智能范式，智能体通过以下循环来处理任务：
1. Think (思考) - 分析当前状态，决定下一步行动
2. Act (行动) - 执行工具调用，获取结果
3. Observe (观察) - 收集行动结果，作为下一步的输入
4. Evaluate (评估) - 评估行动效果，决定是否继续

核心组件：
- AgentState: 智能体状态枚举（空闲、推理、行动、观察、评估、完成、错误）
- ActionStatus: 行动状态枚举（待命、执行中、成功、失败）
- ThoughtType: 思考类型枚举（分析、规划、决策、反思、推理）
- ToolInfo: 工具信息数据结构
- Action: 行动数据结构
- Thought: 思考数据结构
- Observation: 观察数据结构
- ToolRegistry: 工具注册表，管理所有可用工具
- ShortTermMemory: 短期记忆管理器
- ThoughtEngine: 思考引擎，负责生成思考和规划
- EvaluationEngine: 评估引擎，负责评估行动结果
- ReActAgent: 主智能体类，协调各组件工作

使用示例：
```python
agent = ReActAgent(name="TravelAgent", max_steps=10, llm_client=llm_client)
result = await agent.run("规划北京三日游行程")
```

================================================================================
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

# 导入新的意图识别模块
try:
    from core.intent_recognizer import intent_recognizer, IntentRecognizer, IntentResult, IntentType
except ImportError:
    intent_recognizer = None
    IntentResult = None
    IntentType = None

# 配置日志级别，确保在生产环境中可以灵活调整
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_json_from_markdown(content: str) -> str:
    """
    从 Markdown 代码块中提取 JSON 内容。

    LLM 返回的结果通常包含在 ```json 或 ``` 代码块中，
    此函数负责提取纯 JSON 字符串以便后续解析。

    Args:
        content: 原始内容，可能包含 ```json 或 ``` 包裹的 JSON

    Returns:
        提取后的纯 JSON 字符串。如果代码块不存在，则返回原内容。

    Examples:
        >>> extract_json_from_markdown("```json\\n{\\"a\\":1}\\n```")
        '{"a":1}'
        >>> extract_json_from_markdown("hello")
        'hello'
    """
    if "```json" in content:
        # 提取 ```json 代码块中的内容
        return content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        # 提取 ``` 代码块中的内容
        return content.split("```")[1].split("```")[0].strip()
    return content


class AgentState(Enum):
    """
    智能体状态枚举

    定义智能体在整个生命周期中可能处于的各种状态。
    状态转换遵循 ReAct 循环流程。
    """
    IDLE = auto()       # 空闲状态，等待新任务
    REASONING = auto()  # 推理状态，正在分析任务和制定计划
    ACTING = auto()     # 行动状态，正在执行工具调用
    OBSERVING = auto()  # 观察状态，正在收集行动结果
    EVALUATING = auto() # 评估状态，正在评估行动效果
    COMPLETED = auto()  # 完成状态，任务执行完毕
    ERROR = auto()      # 错误状态，执行过程中发生异常


class ActionStatus(Enum):
    """
    行动状态枚举

    表示单个行动的执行状态。
    """
    PENDING = auto()   # 待命状态，行动已创建但尚未执行
    RUNNING = auto()   # 执行中状态，行动正在运行
    SUCCESS = auto()   # 成功状态，行动正常完成
    FAILED = auto()    # 失败状态，行动执行出错


class ThoughtType(Enum):
    """
    思考类型枚举

    表示智能体在处理任务过程中产生的不同类型的思考。
    """
    ANALYSIS = auto()   # 分析型思考，用于理解任务和提取信息
    PLANNING = auto()   # 规划型思考，用于制定执行计划
    DECISION = auto()   # 决策型思考，用于做出最终决策
    REFLECTION = auto() # 反思型思考，用于回顾和总结
    INFERENCE = auto()  # 推理型思考，用于从结果中得出结论


@dataclass
class ToolInfo:
    """
    工具信息数据类

    用于描述一个可执行工具的元数据，包括工具名称、功能描述、
    参数规范、必填参数等信息。

    Attributes:
        name: 工具唯一标识名称
        description: 工具功能描述，供 LLM 理解工具用途
        parameters: OpenAI 风格的参数规范字典
        required_params: 必填参数名称列表
        timeout: 工具执行超时时间（秒），默认30秒
        category: 工具分类，如 "search"、"planning" 等
        tags: 工具标签列表，用于搜索和过滤
    """
    name: str                           # 工具名称
    description: str                    # 工具功能描述
    parameters: Dict[str, Any]          # 参数规范（OpenAI格式）
    required_params: List[str] = field(default_factory=list)  # 必填参数
    timeout: int = 30                   # 超时时间（秒）
    category: str = "general"           # 工具分类
    tags: List[str] = field(default_factory=list)  # 工具标签


@dataclass
class Action:
    """
    行动数据类

    表示智能体执行的一个具体行动，包含工具调用信息、
    执行状态、执行结果等。

    Attributes:
        id: 行动唯一标识
        tool_name: 要执行的工具名称
        parameters: 传递给工具的参数字典
        status: 当前执行状态
        result: 执行结果（成功时）
        error: 错误信息（失败时）
        duration: 执行耗时（毫秒）
        start_time: 开始时间（动态添加）
        end_time: 结束时间（动态添加）

    Examples:
        >>> action = Action(
        ...     id="action_0",
        ...     tool_name="search_cities",
        ...     parameters={"interests": ["美食"], "budget": 2000}
        ... )
        >>> action.mark_running()
    """
    id: str                             # 行动唯一标识
    tool_name: str                      # 工具名称
    parameters: Dict[str, Any]          # 执行参数
    status: ActionStatus = ActionStatus.PENDING  # 执行状态
    result: Optional[Dict[str, Any]] = None      # 执行结果
    error: Optional[str] = None          # 错误信息
    duration: int = 0                    # 执行耗时（毫秒）

    def mark_running(self) -> None:
        """
        标记行动开始执行

        将状态设置为 RUNNING，并记录开始时间。
        """
        self.status = ActionStatus.RUNNING
        self.start_time = datetime.now()

    def mark_success(self, result: Dict[str, Any]) -> None:
        """
        标记行动执行成功

        Args:
            result: 工具执行返回的结果字典
        """
        self.status = ActionStatus.SUCCESS
        self.result = result
        self.end_time = datetime.now()
        # 计算执行耗时（毫秒）
        if hasattr(self, "start_time"):
            self.duration = int((self.end_time - self.start_time).total_seconds() * 1000)

    def mark_failed(self, error: str) -> None:
        """
        标记行动执行失败

        Args:
            error: 错误描述信息
        """
        self.status = ActionStatus.FAILED
        self.error = error
        self.end_time = datetime.now()
        if hasattr(self, "start_time"):
            self.duration = int((self.end_time - self.start_time).total_seconds() * 1000)


@dataclass
class Thought:
    """
    思考数据类

    表示智能体在某个时刻产生的思考，包含思考内容、置信度等信息。

    Attributes:
        id: 思考唯一标识
        type: 思考类型（分析、规划、决策、反思、推理）
        content: 思考内容文本
        confidence: 置信度（0-1之间），越高表示越确定
        reasoning_chain: 推理链，记录推理过程
        decision: 决策结果，JSON 格式的行动计划
    """
    id: str                             # 思考标识
    type: ThoughtType                   # 思考类型
    content: str                        # 思考内容
    confidence: float = 0.8             # 置信度
    reasoning_chain: List[str] = field(default_factory=list)  # 推理链
    decision: Optional[str] = None      # 决策/行动计划


@dataclass
class Observation:
    """
    观察数据类

    表示智能体从环境中获取的观察结果，通常是上一个行动的执行结果。

    Attributes:
        id: 观察唯一标识
        source: 观察来源，如 "environment"、"action" 等
        content: 观察内容，可以是任意类型
        observation_type: 观察类型，如 "data"、"result"、"error" 等
    """
    id: str                             # 观察标识
    source: str                         # 来源
    content: Any                        # 内容
    observation_type: str = "data"      # 观察类型


@dataclass
class AgentStateData:
    """
    智能体状态数据类

    存储智能体当前执行任务的完整状态信息。

    Attributes:
        task: 当前任务描述
        goal: 任务目标（可选）
        history: 执行历史记录
        current_step: 当前执行步骤（0-based）
        max_steps: 最大执行步骤数
        state: 当前状态枚举值
        context: 上下文信息字典
    """
    task: str = ""                                      # 当前任务
    goal: Optional[str] = None                          # 任务目标
    history: List[Dict[str, Any]] = field(default_factory=list)  # 执行历史
    current_step: int = 0                               # 当前步骤
    max_steps: int = 10                                 # 最大步骤
    state: AgentState = AgentState.IDLE                 # 当前状态
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文


class ToolRegistry:
    """
    工具注册表

    负责管理智能体的所有可用工具，提供工具注册、查询、执行等功能。

    核心功能：
    - 工具注册：将工具信息及其执行函数注册到注册表
    - 工具查询：根据名称获取工具信息或执行函数
    - 工具执行：安全地执行工具调用，包含超时控制

    Thread Safety:
        使用 asyncio.Lock 保证并发安全

    Examples:
        >>> registry = ToolRegistry()
        >>> await registry.register(tool_info, executor_func)
        >>> result = await registry.execute("tool_name", {"param": "value"})
    """

    def __init__(self):
        # 工具名称 -> 工具信息字典
        self._tools: Dict[str, ToolInfo] = {}
        # 工具名称 -> 执行函数字典
        self._executors: Dict[str, Callable] = {}
        # 并发安全锁
        self._lock = asyncio.Lock()

    async def register(self, tool_info: ToolInfo, executor: Callable) -> bool:
        """
        注册工具

        Args:
            tool_info: 工具信息对象
            executor: 工具执行函数（可以是 sync 或 async 函数）

        Returns:
            bool: 注册成功返回 True，工具已存在返回 False
        """
        async with self._lock:
            # 检查工具是否已存在
            if tool_info.name in self._tools:
                logger.warning(f"工具已存在: {tool_info.name}")
                return False
            # 注册工具信息和执行函数
            self._tools[tool_info.name] = tool_info
            self._executors[tool_info.name] = executor
            logger.info(f"工具注册成功: {tool_info.name}")
            return True

    def get_tool(self, tool_name: str) -> Optional[ToolInfo]:
        """
        获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            ToolInfo: 工具信息对象，不存在返回 None
        """
        return self._tools.get(tool_name)

    def get_executor(self, tool_name: str) -> Optional[Callable]:
        """
        获取工具执行函数

        Args:
            tool_name: 工具名称

        Returns:
            Callable: 执行函数，不存在返回 None
        """
        return self._executors.get(tool_name)

    def list_tools(self) -> List[ToolInfo]:
        """
        列出所有已注册的工具

        Returns:
            List[ToolInfo]: 工具信息列表
        """
        return list(self._tools.values())

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具调用

        执行指定的工具调用，包含参数验证和超时控制。

        Args:
            tool_name: 要执行的工具名称
            params: 传递给工具的参数

        Returns:
            Dict[str, Any]: 工具执行结果

        Raises:
            ValueError: 工具不存在或缺少必需参数
            TimeoutError: 工具执行超时
        """
        tool_info = self.get_tool(tool_name)
        if not tool_info:
            raise ValueError(f"工具不存在: {tool_name}")

        executor = self.get_executor(tool_name)
        if not executor:
            raise ValueError(f"工具执行函数未注册: {tool_name}")

        # 验证必填参数
        for param in tool_info.required_params:
            if param not in params:
                raise ValueError(f"缺少必需参数: {param}")

        timeout_duration = tool_info.timeout
        try:
            # 判断执行函数是否为异步函数
            if asyncio.iscoroutinefunction(executor):
                # 异步函数：使用 asyncio.wait_for 控制超时
                result = await asyncio.wait_for(executor(**params), timeout=timeout_duration)
            else:
                # 同步函数：使用 to_thread 在线程池中执行
                result = await asyncio.to_thread(executor, **params)
            # 确保返回值为字典类型
            return result if isinstance(result, dict) else {"result": result}
        except asyncio.TimeoutError:
            raise TimeoutError(f"工具执行超时: {tool_name}")


class ShortTermMemory:
    """
    短期记忆管理器

    使用双端队列（deque）实现固定大小的短期记忆存储。
    当记忆数量超过最大容量时，自动删除最旧的记忆。

    Attributes:
        max_size: 最大记忆容量，默认20条

    Examples:
        >>> memory = ShortTermMemory(max_size=10)
        >>> memory.add("用户想去北京", importance=0.8)
        >>> recent = memory.get_recent(5)
    """

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        # 使用 deque 实现自动淘汰旧数据
        self._memory: deque = deque(maxlen=max_size)

    def add(self, content: Any, importance: float = 0.5) -> str:
        """
        添加记忆

        Args:
            content: 记忆内容
            importance: 重要性分数（0-1），用于后续优先级排序

        Returns:
            str: 生成的记忆 ID
        """
        import uuid
        # 生成唯一 ID
        memory_id = str(uuid.uuid4())
        # 存储记忆及元数据
        self._memory.append({
            "id": memory_id,
            "content": content,
            "importance": importance,
            "timestamp": datetime.now().isoformat()
        })
        return memory_id

    def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的记忆

        Args:
            limit: 获取数量限制

        Returns:
            List[Dict]: 最近的记忆列表（按时间倒序）
        """
        if limit < len(self._memory):
            return list(self._memory)[-limit:][::-1]
        return list(self._memory)[::-1]

    def clear(self) -> None:
        """清空所有记忆"""
        self._memory.clear()

    def __len__(self) -> int:
        """返回当前记忆数量"""
        return len(self._memory)


class ThoughtEngine:
    """
    思考引擎

    负责生成和分析智能体的思考内容，支持两种模式：
    1. LLM 模式：使用大语言模型进行深度分析和规划
    2. 规则模式：使用预定义规则进行简单推理

    核心功能：
    - 任务实体提取：从用户输入中提取关键信息（城市、天数、预算等）
    - 任务分析：分析用户意图，决定使用哪些工具
    - 行动规划：制定执行步骤和参数
    - 结果反思：反思行动结果，改进策略

    Attributes:
        max_reasoning_depth: 最大推理深度
        llm_client: LLM 客户端实例
    """

    def __init__(self, max_reasoning_depth: int = 5, llm_client=None):
        self.max_reasoning_depth = max_reasoning_depth
        self._thought_counter = 0
        self.llm_client = llm_client

    def _create_thought(self, thought_type: ThoughtType, content: str) -> Thought:
        """
        创建思考对象

        Args:
            thought_type: 思考类型
            content: 思考内容

        Returns:
            Thought: 新创建的思考对象
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
        使用 LLM 提取任务实体

        从用户输入中提取：
        - city: 目的地城市
        - days: 旅行天数
        - budget: 预算
        - interests: 兴趣标签
        - season: 出行季节
        - departure_date: 出发日期
        - task_type: 任务类型

        Args:
            task: 用户输入的原始任务描述

        Returns:
            Dict: 提取的实体字典，如果 LLM 调用失败则返回空字典
        """
        if self.llm_client:
            # 构建系统提示词，明确要求提取的结构化信息
            system_prompt = """你是一个旅游助手，专门从用户输入中提取关键信息。

请从用户输入中提取以下信息，以JSON格式返回：
- city: 用户想去的城市或地区（如果没有明确目的地则为null）
- days: 旅行天数（数字）
- budget: 预算金额（数字，单位元）
- interests: 用户兴趣标签列表（如美食、历史、自然风光等）
- season: 出行季节（如有提及）
- departure_date: 出发日期（如有提及）
- task_type: 任务类型（recommendation/planning/query/budget/general）

只返回JSON格式，不要其他内容。"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户输入：{task}"}
            ]

            try:
                result = self.llm_client.chat(messages, temperature=0.3)
                if result.get("success"):
                    # 提取 JSON 并解析
                    content = extract_json_from_markdown(result.get("content", ""))
                    entities = json.loads(content)
                    logger.info(f"[ThoughtEngine] LLM提取实体: {entities}")
                    return entities
            except Exception as e:
                logger.error(f"[ThoughtEngine] LLM实体提取失败: {e}")

        # LLM 失败时使用规则回退
        return self._extract_entities_by_rules(task)

    def _extract_entities_by_rules(self, task: str) -> Dict[str, Any]:
        """
        使用规则提取任务实体

        当 LLM 不可用时，使用正则表达式等规则提取基本信息。

        Args:
            task: 用户输入的任务描述

        Returns:
            Dict: 提取的实体字典
        """
        entities = {}
        # 提取天数：匹配 "X天" 或 "X 天" 格式
        days_match = re.search(r"(\d+)\s*天", task)
        entities["days"] = int(days_match.group(1)) if days_match else 3

        # 城市名提取模式列表（按优先级排序）
        city_patterns = [
            r"^(.+?)\s+计划",           # "北京计划..."
            r"^(.+?)\s+想要",           # "北京想要..."
            r"(?:去|在|到)(.+?)(?:旅游|游玩|旅行)?",  # "去北京旅游"
            r"(.+?)的?攻略",            # "北京攻略"
        ]
        for pattern in city_patterns:
            city_match = re.search(pattern, task)
            if city_match:
                city = city_match.group(1).strip()
                # 排除包含"推荐"等关键词的情况
                if city and not any(kw in city for kw in ["推荐", "建议", "哪些", "什么"]):
                    entities["city"] = city
                    break

        # 提取预算：匹配 "X元" 格式
        budget_match = re.search(r"(\d+)\s*元", task)
        if budget_match:
            entities["budget"] = int(budget_match.group(1))

        return entities

    def analyze_task(self, task: str, context: Dict[str, Any]) -> Thought:
        """
        分析任务

        根据任务描述和上下文，分析用户意图并决定使用哪些工具。

        Args:
            task: 用户任务描述
            context: 上下文信息（如用户偏好等）

        Returns:
            Thought: 分析结果思考对象
        """
        if self.llm_client:
            return self._analyze_task_with_llm(task, context)
        else:
            return self._analyze_task_with_rules(task, context)

    def _analyze_task_with_llm(self, task: str, context: Dict[str, Any]) -> Thought:
        """
        使用 LLM 分析任务

        构建详细的系统提示词，让 LLM 理解任务并选择合适的工具。

        Args:
            task: 用户任务描述
            context: 上下文信息

        Returns:
            Thought: 分析结果
        """
        system_prompt = """你是一个专业的旅游助手，负责分析用户的旅游需求。

可用工具：
- search_cities: 根据兴趣、预算搜索城市
- query_attractions: 查询城市景点
- get_city_info: 获取城市详情
- generate_route_plan: 生成详细路线规划
- llm_chat: 一般对话

请分析用户输入，判断意图，并决定使用哪些工具。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""用户输入：{task}

请分析这个请求，以JSON格式返回intent、reasoning、tools和confidence。只返回JSON格式。"""}
        ]

        try:
            result = self.llm_client.chat(messages, temperature=0.3)
            if result.get("success"):
                raw_content = result.get("content", "")
                logger.debug(f"[ThoughtEngine] LLM原始响应: {raw_content[:200]}...")
                content = extract_json_from_markdown(raw_content)
                logger.debug(f"[ThoughtEngine] 提取JSON: {content[:200]}...")

                # 尝试解析 JSON
                try:
                    analysis = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(f"[ThoughtEngine] JSON解析失败，尝试修复: {content[:100]}...")
                    # 尝试修复常见的 JSON 问题
                    content_fixed = content.replace("'", '"')
                    analysis = json.loads(content_fixed)

                # 确保 analysis 是字典
                if not isinstance(analysis, dict):
                    logger.error(f"[ThoughtEngine] LLM返回类型错误: {type(analysis)}, 内容: {analysis}")
                    raise ValueError(f"Expected dict, got {type(analysis)}")

                logger.info(f"[ThoughtEngine] LLM分析结果: {analysis}")

                # 创建分析型思考
                thought = self._create_thought(
                    ThoughtType.ANALYSIS,
                    f"【任务分析】{analysis.get('reasoning', '')}"
                )
                # 将工具列表转换为决策格式
                thought.decision = json.dumps([{
                    "step": i + 1,
                    "action": tool.get("name") if isinstance(tool, dict) else str(tool),
                    "params": tool.get("parameters", {}) if isinstance(tool, dict) else {}
                } for i, tool in enumerate(analysis.get("tools", []))])
                thought.confidence = analysis.get("confidence", 0.85)
                return thought
        except Exception as e:
            logger.error(f"[ThoughtEngine] LLM分析失败: {e}")

        return self._analyze_task_with_rules(task, context)

    def _analyze_task_with_rules(self, task: str, context: Dict[str, Any]) -> Thought:
        """
        使用规则分析任务

        优先尝试使用 LLM 进行意图识别，如果不可用则回退到规则匹配。

        Args:
            task: 用户任务描述
            context: 上下文信息

        Returns:
            Thought: 分析结果
        """
        # 尝试使用新的意图识别模块
        if intent_recognizer:
            try:
                import asyncio
                # 如果是异步方法
                if hasattr(intent_recognizer, '_recognize_with_llm'):
                    # 使用同步方法或创建事件循环
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        intent_result = loop.run_until_complete(
                            intent_recognizer.recognize(task, context)
                        )
                        loop.close()

                        # 类型检查
                        from core.intent_recognizer import IntentResult
                        if not isinstance(intent_result, IntentResult):
                            logger.warning(f"意图识别返回类型错误: {type(intent_result)}, 回退到规则匹配")
                            return self._analyze_task_with_keywords(task, context)

                        return self._convert_intent_to_thought(intent_result, task)
                    except Exception as e:
                        logger.warning(f"异步意图识别失败: {e}, 回退到规则匹配")
            except Exception as e:
                logger.warning(f"意图识别模块使用失败: {e}")

        # 回退到原始规则匹配
        return self._analyze_task_with_keywords(task, context)

    def _analyze_task_with_keywords(self, task: str, context: Dict[str, Any]) -> Thought:
        """
        使用关键词匹配分析任务

        Args:
            task: 用户任务描述
            context: 上下文信息

        Returns:
            Thought: 分析结果
        """
        entities = self._extract_entities_by_rules(task)
        task_lower = task.lower()

        # 根据关键词判断任务类型
        if any(kw in task_lower for kw in ["推荐", "建议", "哪些", "适合"]):
            task_type = "recommendation"
        elif any(kw in task_lower for kw in ["查询", "搜索", "有什么", "信息"]):
            task_type = "query"
        elif any(kw in task_lower for kw in ["规划", "计划", "路线", "行程", "安排", "攻略", "旅游", "旅行", "游玩", "出游", "出发"]):
            task_type = "planning"
        else:
            task_type = "general"

        # 任务类型中英对照
        task_type_cn = {
            "recommendation": "城市推荐",
            "query": "信息查询",
            "planning": "路线规划",
            "budget": "预算计算",
            "general": "一般对话"
        }.get(task_type, "一般对话")

        # 构建分析内容
        content = f"【任务分析】用户输入：「{task}」\n【意图识别】任务类型={task_type_cn}\n【提取信息】{entities}"
        thought = self._create_thought(ThoughtType.ANALYSIS, content)
        thought.confidence = 0.7
        return thought

    def _convert_intent_to_thought(self, intent_result: IntentResult, task: str) -> Thought:
        """
        将 IntentResult 转换为 Thought

        Args:
            intent_result: 意图识别结果
            task: 用户任务描述

        Returns:
            Thought: 思考结果
        """
        # 意图类型映射
        intent_type_map = {
            IntentType.CITY_RECOMMENDATION: "城市推荐",
            IntentType.ATTRACTION_QUERY: "景点查询",
            IntentType.ROUTE_PLANNING: "路线规划",
            IntentType.ITINERARY_QUERY: "行程查询",
            IntentType.BUDGET_QUERY: "预算咨询",
            IntentType.FOOD_RECOMMENDATION: "美食推荐",
            IntentType.ACCOMMODATION: "住宿咨询",
            IntentType.TRANSPORTATION: "交通咨询",
            IntentType.TRAVEL_PLANNING: "旅行规划",
            IntentType.GENERAL_CHAT: "一般对话",
        }

        type_name = intent_type_map.get(intent_result.intent, "一般对话")

        # 构建分析内容
        content_parts = [
            f"【任务分析】用户输入：「{task}」",
            f"【意图识别】任务类型={type_name}",
            f"【意图置信度】{intent_result.confidence:.2f}",
            f"【用户情感】{intent_result.sentiment.value}",
            f"【提取实体】{intent_result.entities}"
        ]

        if intent_result.missing_info:
            content_parts.append(f"【缺失信息】{intent_result.missing_info}")

        content = "\n".join(content_parts)
        thought = self._create_thought(ThoughtType.ANALYSIS, content)
        thought.confidence = intent_result.confidence

        # 将决策信息存入 thought
        if intent_result.needs_more_info():
            thought.decision = json.dumps({
                "action": "ask_clarification",
                "missing_info": intent_result.missing_info
            })

        return thought

    def plan_actions(self, task: str, tools: List[ToolInfo],
                     constraints: Optional[List[str]] = None) -> Thought:
        """
        规划行动步骤

        根据任务和可用工具，制定执行计划。

        Args:
            task: 用户任务描述
            tools: 可用工具列表
            constraints: 约束条件列表（可选）

        Returns:
            Thought: 规划结果思考
        """
        if self.llm_client:
            return self._plan_actions_with_llm(task, tools, constraints)
        else:
            return self._plan_actions_with_rules(task, tools, constraints)

    def _plan_actions_with_llm(self, task: str, tools: List[ToolInfo],
                                constraints: Optional[List[str]] = None) -> Thought:
        """
        使用 LLM 规划行动

        将工具列表发送给 LLM，让其制定详细的执行步骤。

        Args:
            task: 用户任务描述
            tools: 可用工具列表
            constraints: 约束条件

        Returns:
            Thought: 规划结果
        """
        # 构建工具描述列表
        tool_descriptions = []
        for t in tools:
            params = t.parameters.get("properties", {})
            # 格式化参数描述
            param_str = ", ".join([f"{k}({v.get('type', 'string')})" for k, v in params.items()])
            tool_descriptions.append(f"- {t.name}: {t.description} (参数: {param_str})")

        system_prompt = f"""你是 ReAct 智能体，负责规划行动步骤。

用户任务：{task}

可用工具：
{chr(10).join(tool_descriptions)}

请规划执行步骤。返回JSON格式：
{{
  "reasoning": "选择理由",
  "steps": [
    {{"action": "工具名", "params": {{"参数名": "参数值"}}, "reasoning": "为什么选这个工具"}}
  ]
}}"""

        try:
            result = self.llm_client.chat([{"role": "system", "content": system_prompt}], temperature=0.3)
            if result.get("success"):
                content = extract_json_from_markdown(result.get("content", ""))
                plan = json.loads(content)
                logger.info(f"[ThoughtEngine] LLM规划结果: {plan}")

                steps = plan.get("steps", [])
                thought = self._create_thought(
                    ThoughtType.PLANNING,
                    f"【执行计划】{plan.get('reasoning', '')}"
                )
                # 转换为统一格式
                thought.decision = json.dumps([{
                    "step": s.get("step", i + 1),
                    "action": s.get("action") or s.get("tool", ""),
                    "params": s.get("params") or s.get("parameters", {})
                } for i, s in enumerate(steps)])
                thought.confidence = 0.9
                return thought
        except Exception as e:
            logger.error(f"[ThoughtEngine] LLM规划失败: {e}")

        return self._plan_actions_with_rules(task, tools, constraints)

    def _plan_actions_with_rules(self, task: str, tools: List[ToolInfo],
                                  constraints: Optional[List[str]] = None) -> Thought:
        """
        使用规则规划行动

        根据任务类型和关键词匹配，选择合适的工具组合。

        Args:
            task: 用户任务描述
            tools: 可用工具列表
            constraints: 约束条件

        Returns:
            Thought: 规划结果
        """
        steps = self._decompose_task_by_rules(task, tools)

        # 构建规划内容
        content = f"""【执行计划】根据任务分析结果，制定以下执行方案：

【步骤规划】共{len(steps)}个执行步骤

【工具选择理由】"""
        if steps:
            for i, step in enumerate(steps, 1):
                params_str = ", ".join(f"{k}={v}" for k, v in step.parameters.items())
                content += f"\n  选择 {step.tool_name}，参数：({params_str})"
        else:
            content += "\n  无需工具调用，直接生成回答"

        thought = self._create_thought(ThoughtType.PLANNING, content)
        thought.confidence = 0.9

        # 构建推理链
        thought.reasoning_chain = [
            f"任务分解完成：共{len(steps)}个执行步骤",
        ]
        if any(s.tool_name for s in steps):
            step_names = [s.tool_name for s in steps]
            thought.reasoning_chain.append(f"工具调用序列：{' → '.join(step_names)}")
        else:
            thought.reasoning_chain.append("无需工具调用")

        thought.reasoning_chain.append("准备按计划执行各步骤")

        if steps:
            thought.decision = json.dumps([{
                "step": i + 1,
                "action": s.tool_name,
                "params": s.parameters
            } for i, s in enumerate(steps)])

        return thought

    def _decompose_task_by_rules(self, task: str, tools: List[ToolInfo]) -> List[Action]:
        """
        使用规则分解任务

        根据任务描述中的关键词，识别需要的工具调用。

        Args:
            task: 用户任务描述
            tools: 可用工具列表

        Returns:
            List[Action]: 分解后的行动列表
        """
        actions = []
        task_lower = task.lower()

        # 提取天数
        days_match = re.search(r"(\d+)\s*天", task)
        days = int(days_match.group(1)) if days_match else 3

        # 提取城市
        city = None
        city_patterns = [
            r"^(.+?)\s+计划",
            r"^(.+?)\s+想要",
            r"(?:去|在|到)(.+?)(?:旅游|游玩|旅行)?",
            r"(.+?)的?攻略",
        ]
        for pattern in city_patterns:
            city_match = re.search(pattern, task)
            if city_match:
                city = city_match.group(1).strip()
                if city and not any(kw in city for kw in ["推荐", "建议", "哪些", "什么"]):
                    break

        # 根据任务类型选择工具
        # 1. 推荐类任务 -> 搜索工具
        if any(kw in task_lower for kw in ["推荐", "建议", "哪些", "适合"]):
            recommend_tools = [t for t in tools if "recommend" in t.name.lower() or "search" in t.name.lower()]
            if recommend_tools:
                actions.append(Action(
                    id=f"action_{len(actions)}",
                    tool_name=recommend_tools[0].name,
                    parameters={"interests": [], "budget_min": None, "budget_max": None, "season": None}
                ))

        # 2. 城市相关任务 -> 城市信息工具
        if city:
            city_info_tools = [t for t in tools if "city_info" in t.name.lower() or "attraction" in t.name.lower()]
            if city_info_tools:
                actions.append(Action(
                    id=f"action_{len(actions)}",
                    tool_name=city_info_tools[0].name,
                    parameters={"city": city}
                ))

        # 3. 规划类任务 -> 路线规划工具
        route_tools = [t for t in tools if "route" in t.name.lower() or "plan" in t.name.lower()]
        if route_tools and (any(kw in task_lower for kw in ["规划", "路线", "行程", "安排"]) or
                           any(kw in task_lower for kw in ["旅游", "旅行", "游玩", "出游", "出发"])):
            actions.append(Action(
                id=f"action_{len(actions)}",
                tool_name=route_tools[0].name,
                parameters={"city": city or "未知", "days": days}
            ))

        # 4. 默认 -> LLM 对话工具
        if not actions:
            llm_tools = [t for t in tools if "llm_chat" in t.name.lower()]
            if llm_tools:
                actions.append(Action(
                    id=f"action_{len(actions)}",
                    tool_name=llm_tools[0].name,
                    parameters={"query": task}
                ))

        logger.info(f"[ReAct] 生成 {len(actions)} 个动作: {[a.tool_name for a in actions]}")
        return actions

    def reflect(self, action_result: Dict[str, Any]) -> Thought:
        """
        反思行动结果

        根据上一个行动的执行结果，生成反思性思考。

        Args:
            action_result: 行动结果字典

        Returns:
            Thought: 反思思考
        """
        thought = self._create_thought(ThoughtType.REFLECTION, "反思行动结果")
        success = action_result.get("success", False)

        thought.reasoning_chain = [
            f"行动成功：{success}",
            f"改进建议：{'结果符合预期' if success else '建议检查参数或尝试其他工具'}"
        ]
        thought.confidence = 0.9 if success else 0.6

        return thought


class EvaluationEngine:
    """
    评估引擎

    负责评估行动执行结果，收集统计信息。

    Attributes:
        _metrics: 评估指标字典，包含 total_tasks、successful_tasks、failed_tasks
    """

    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "total_tasks": 0,      # 总任务数
            "successful_tasks": 0, # 成功任务数
            "failed_tasks": 0      # 失败任务数
        }

    def evaluate_result(self, action: Action) -> Dict[str, Any]:
        """
        评估行动结果

        Args:
            action: 已执行的行动对象

        Returns:
            Dict: 评估结果，包含 success、duration、has_result
        """
        evaluation = {
            "success": action.status == ActionStatus.SUCCESS,
            "duration": action.duration,
            "has_result": action.result is not None
        }

        # 更新统计指标
        self._metrics["total_tasks"] += 1
        if evaluation["success"]:
            self._metrics["successful_tasks"] += 1
        else:
            self._metrics["failed_tasks"] += 1

        return evaluation


class ReActAgent:
    """
    ReAct 智能体主类

    协调各组件工作，实现完整的 ReAct 推理-行动循环。

    核心流程：
    1. 接收任务，初始化状态
    2. 进入推理循环：
       - Think: 分析当前状态，生成思考
       - Act: 执行工具调用
       - Observe: 收集执行结果
       - Evaluate: 评估执行效果
    3. 判断是否继续或停止
    4. 返回执行结果

    Attributes:
        name: 智能体名称
        max_steps: 最大执行步骤数
        tool_registry: 工具注册表
        thought_engine: 思考引擎
        evaluation_engine: 评估引擎
        short_memory: 短期记忆
        state: 当前状态数据
        current_state: 当前状态枚举值
        action_history: 行动历史
        thought_history: 思考历史

    Examples:
        >>> agent = ReActAgent(name="TravelAgent", max_steps=10)
        >>> agent.register_tool(tool_info, executor_func)
        >>> result = await agent.run("规划北京三日游")
    """

    def __init__(self, name: str = "ReActAgent", max_steps: int = 10,
                 max_reasoning_depth: int = 5, llm_client=None):
        self.name = name
        self.max_steps = max_steps

        # 初始化核心组件
        self.tool_registry = ToolRegistry()
        self.thought_engine = ThoughtEngine(max_reasoning_depth, llm_client)
        self.evaluation_engine = EvaluationEngine()
        self.short_memory = ShortTermMemory()

        # 初始化状态
        self.state = AgentStateData(max_steps=max_steps)
        self.current_state = AgentState.IDLE

        # 历史记录
        self.action_history: List[Action] = []
        self.thought_history: List[Thought] = []

        # 事件回调列表
        self._on_thought_callbacks: List[Callable] = []
        self._on_action_callbacks: List[Callable] = []

        # 实时思考流回调
        self._think_stream_callback = None
        self._think_start_time = None

    def register_tool(self, tool_info: ToolInfo, executor: Callable) -> bool:
        """
        注册工具

        Args:
            tool_info: 工具信息
            executor: 执行函数

        Returns:
            bool: 注册成功返回 True
        """
        if tool_info.name in self.tool_registry._tools:
            return False
        self.tool_registry._tools[tool_info.name] = tool_info
        self.tool_registry._executors[tool_info.name] = executor
        return True

    def add_thought_callback(self, callback: Callable) -> None:
        """
        添加思考回调

        Args:
            callback: 回调函数，接收 Thought 对象
        """
        self._on_thought_callbacks.append(callback)

    def add_action_callback(self, callback: Callable) -> None:
        """
        添加行动回调

        Args:
            callback: 回调函数，接收 Action 对象
        """
        self._on_action_callbacks.append(callback)

    def set_think_stream_callback(self, callback: Callable[[str, float], None]) -> None:
        """
        设置实时思考流回调

        用于流式输出思考内容。

        Args:
            callback: 回调函数，参数为 (思考内容, 已耗时秒数)
        """
        self._think_stream_callback = callback

    def _notify_thought(self, thought: Thought) -> None:
        """
        通知思考事件

        调用所有注册的思考回调。

        Args:
            thought: 产生的思考对象
        """
        for callback in self._on_thought_callbacks:
            try:
                callback(thought)
            except Exception as e:
                logger.error(f"思考回调错误: {e}")

    def _notify_action(self, action: Action) -> None:
        """
        通知行动事件

        调用所有注册的行动回调。

        Args:
            action: 执行的行动对象
        """
        for callback in self._on_action_callbacks:
            try:
                callback(action)
            except Exception as e:
                logger.error(f"行动回调错误: {e}")

    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行任务

        启动 ReAct 循环，执行任务直到完成或达到最大步骤数。

        Args:
            task: 用户任务描述
            context: 上下文信息（如用户偏好等）

        Returns:
            Dict: 执行结果，包含 success、history、steps_completed 等
        """
        self.state.task = task
        self.state.context = context or {}
        self.state.current_step = 0
        self.state.history = []

        self.current_state = AgentState.REASONING
        self._think_start_time = None  # 重置思考开始时间

        logger.info(f"开始执行任务: {task}")

        try:
            # ReAct 主循环
            while self.state.current_step < self.max_steps:
                # 记录本步骤的开始时间
                step_start_time = datetime.now()

                # 观察 -> 思考 -> 行动 -> 评估
                observation = await self._observe()
                thought = await self._think(observation)

                # 实时流式输出思考内容（使用步骤耗时）
                if self._think_stream_callback:
                    step_elapsed = (datetime.now() - step_start_time).total_seconds()
                    logger.info(f"[ThinkStream] 步骤{self.state.current_step + 1}回调已触发, elapsed={step_elapsed:.2f}s")
                    self._think_stream_callback(
                        f"步骤{self.state.current_step + 1}耗时: {step_elapsed:.1f}秒\n\n{thought.content}",
                        step_elapsed
                    )
                else:
                    logger.warning(f"[ThinkStream] 步骤{self.state.current_step + 1}回调为None")

                # 检查是否应该停止
                if self._should_stop(thought):
                    break

                action = await self._act(thought)
                evaluation = await self._evaluate(action)

                # 更新状态和记录历史
                self._update_state(action, evaluation)
                self._record_history(thought, action, evaluation)

            self.current_state = AgentState.COMPLETED
            return self._build_result()

        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            self.current_state = AgentState.ERROR
            return {
                "success": False,
                "error": str(e),
                "task": task,
                "steps_completed": self.state.current_step
            }

    async def _observe(self) -> Observation:
        """
        观察阶段

        收集环境信息，通常是上一个行动的结果。

        Returns:
            Observation: 观察对象
        """
        self.current_state = AgentState.OBSERVING

        last_action = self.action_history[-1] if self.action_history else None

        return Observation(
            id=f"obs_{self.state.current_step}",
            source="environment",
            content={
                "last_action": last_action.result if last_action else None,
                "step": self.state.current_step
            }
        )

    async def _think(self, observation: Observation) -> Thought:
        """
        思考阶段

        根据当前状态和观察结果，生成思考和行动计划。

        Args:
            observation: 观察对象

        Returns:
            Thought: 思考对象，包含决策
        """
        self.current_state = AgentState.REASONING

        if self.state.current_step == 0:
            # 第一步：分析任务并制定计划
            thought = self.thought_engine.analyze_task(
                self.state.task,
                self.state.context
            )

            # 始终生成执行计划
            plan_thought = self.thought_engine.plan_actions(
                self.state.task,
                self.tool_registry.list_tools()
            )
            thought.decision = plan_thought.decision
            thought.reasoning_chain.extend(plan_thought.reasoning_chain)
        else:
            # 后续步骤：根据结果决定下一步
            last_action = self.action_history[-1] if self.action_history else None

            if last_action and last_action.status == ActionStatus.FAILED:
                # 执行失败：反思并调整策略
                thought = self.thought_engine.reflect(last_action.result or {})
                thought.content = f"""【执行失败】步骤 {self.state.current_step}

【失败原因】{last_action.error}
【当前状态】需要调整策略或检查参数
【后续行动】尝试其他工具或重新执行"""
            elif last_action and last_action.status == ActionStatus.SUCCESS:
                # 执行成功：分析结果，决定是否继续
                result = last_action.result
                tool_name = last_action.tool_name

                # 提取结果摘要
                result_info = ""
                if isinstance(result, dict):
                    if result.get("success") and "cities" in result:
                        cities = result.get("cities", [])
                        city_names = [c.get("city", str(c)) for c in cities[:5]]
                        result_info = f"获取到 {len(cities)} 个推荐城市：{', '.join(city_names)}"
                    elif result.get("success") and "route_plan" in result:
                        route_days = len(result.get("route_plan", []))
                        result_info = f"路线规划完成，共 {route_days} 天行程"
                    elif "response" in result:
                        result_info = f"LLM生成回答：{result['response'][:80]}..."
                    elif "info" in result:
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
                    f"评估是否需要继续执行或生成最终回答"
                ]
                thought.confidence = 0.95
            else:
                # 继续执行下一步
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

        停止条件：
        1. 执行了最终工具（LLM回答、城市推荐、路线规划）且成功
        2. 高置信度且有决策，且上一个行动成功
        3. 已达到最大步骤数

        Args:
            thought: 当前思考对象

        Returns:
            bool: 是否应该停止
        """
        # 条件1: 执行了最终工具且成功
        if thought.type == ThoughtType.INFERENCE:
            last_action = self.action_history[-1] if self.action_history else None
            if last_action and last_action.tool_name in ["llm_chat", "generate_city_recommendation", "generate_route_plan"]:
                if last_action.status == ActionStatus.SUCCESS:
                    return True

        # 条件2: 高置信度且有决策
        if thought.confidence > 0.9 and thought.decision:
            last_action = self.action_history[-1] if self.action_history else None
            if last_action and last_action.status == ActionStatus.SUCCESS:
                return True

        # 条件3: 达到最大步骤数
        if self.state.current_step >= self.max_steps - 1:
            return True

        return False

    async def _act(self, thought: Thought) -> Action:
        """
        行动阶段

        根据思考决策执行工具调用。

        Args:
            thought: 思考对象，包含决策信息

        Returns:
            Action: 执行结果行动对象
        """
        self.current_state = AgentState.ACTING

        action = self._extract_action(thought)

        if action:
            # 执行工具调用
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
            # 无需执行工具
            action = Action(
                id=f"action_{len(self.action_history)}",
                tool_name="none",
                parameters={},
                status=ActionStatus.SUCCESS
            )
            action.mark_success({"message": "无操作需要执行"})
            self.action_history.append(action)

        return action

    def _extract_action(self, thought: Thought) -> Optional[Action]:
        """
        从思考中提取行动

        解析思考的决策字段，生成具体的行动对象。

        Args:
            thought: 思考对象

        Returns:
            Action: 行动对象，解析失败返回 None
        """
        if not thought.decision:
            return None

        try:
            # 解析决策 JSON
            if isinstance(thought.decision, str):
                decisions = json.loads(thought.decision)
            else:
                decisions = thought.decision if isinstance(thought.decision, list) else []

            if not decisions:
                return None

            # 获取当前步骤对应的决策
            current_step = self.state.current_step
            if current_step < len(decisions):
                decision = decisions[current_step]
                params = decision.get("params", {})

                # 参数名映射：处理 LLM 生成的计划中参数名不匹配的问题
                # 例如：city -> cities, destination -> cities
                param_mapping = {
                    'city': 'cities',
                    'destination': 'cities',
                    'location': 'cities',
                }
                mapped_params = {}
                for k, v in params.items():
                    mapped_key = param_mapping.get(k, k)
                    # 如果参数期望是数组，但提供的是单个值，转换为数组
                    if mapped_key == 'cities' and isinstance(v, str):
                        v = [v]
                    mapped_params[mapped_key] = v

                return Action(
                    id=f"action_{len(self.action_history)}",
                    tool_name=decision.get("action", ""),
                    parameters=mapped_params
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        return None

    async def _evaluate(self, action: Action) -> Dict[str, Any]:
        """
        评估阶段

        评估行动执行结果。

        Args:
            action: 已执行的行动对象

        Returns:
            Dict: 评估结果
        """
        self.current_state = AgentState.EVALUATING
        return self.evaluation_engine.evaluate_result(action)

    def _update_state(self, action: Action, evaluation: Dict[str, Any]) -> None:
        """
        更新智能体状态

        Args:
            action: 执行的行动
            evaluation: 评估结果
        """
        self.state.current_step += 1
        if action.result:
            self.state.context["last_result"] = action.result
        self.state.updated_at = datetime.now()

    def _record_history(self, thought: Thought, action: Action,
                        evaluation: Dict[str, Any]) -> None:
        """
        记录执行历史

        将思考、行动、评估结果保存到历史记录中。

        Args:
            thought: 思考对象
            action: 行动对象
            evaluation: 评估结果
        """
        action_dict = {
            "id": action.id,
            "tool_name": action.tool_name,
            "status": action.status.name,
            "duration": action.duration,
            "result": action.result,
            "error": action.error
        }

        self.state.history.append({
            "step": self.state.current_step,
            "thought": {
                "id": thought.id,
                "type": thought.type.name,
                "content": thought.content,
                "confidence": thought.confidence,
                "decision": thought.decision
            },
            "action": action_dict,
            "evaluation": evaluation,
            "timestamp": datetime.now().isoformat()
        })

    def _build_result(self) -> Dict[str, Any]:
        """
        构建执行结果

        Returns:
            Dict: 包含 success、history、steps_completed 等的 result 字典
        """
        successful_steps = sum(
            1 for step in self.state.history
            if step.get("evaluation", {}).get("success", False)
        )

        return {
            "success": self.current_state == AgentState.COMPLETED,
            "task": self.state.task,
            "steps_completed": len(self.state.history),
            "successful_steps": successful_steps,
            "total_duration": sum(
                step.get("action", {}).get("duration", 0)
                for step in self.state.history
            ),
            "history": self.state.history
        }

    def reset(self) -> None:
        """
        重置智能体状态

        清空历史记录、记忆和状态，准备接受新任务。
        """
        self.state = AgentStateData(max_steps=self.max_steps)
        self.current_state = AgentState.IDLE
        self.action_history.clear()
        self.thought_history.clear()
        self.short_memory.clear()
