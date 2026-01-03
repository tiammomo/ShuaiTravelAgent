import re
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentState(Enum):
    IDLE = auto()
    REASONING = auto()
    ACTING = auto()
    OBSERVING = auto()
    EVALUATING = auto()
    COMPLETED = auto()
    ERROR = auto()

class ActionStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()

class ThoughtType(Enum):
    ANALYSIS = auto()
    PLANNING = auto()
    DECISION = auto()
    REFLECTION = auto()
    INFERENCE = auto()

@dataclass
class ToolInfo:
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str] = field(default_factory=list)
    timeout: int = 30
    category: str = "general"
    tags: List[str] = field(default_factory=list)

@dataclass
class Action:
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    status: ActionStatus = ActionStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: int = 0

    def mark_running(self) -> None:
        self.status = ActionStatus.RUNNING
        self.start_time = datetime.now()

    def mark_success(self, result: Dict[str, Any]) -> None:
        self.status = ActionStatus.SUCCESS
        self.result = result
        self.end_time = datetime.now()
        if hasattr(self, "start_time"):
            self.duration = int((self.end_time - self.start_time).total_seconds() * 1000)

    def mark_failed(self, error: str) -> None:
        self.status = ActionStatus.FAILED
        self.error = error
        self.end_time = datetime.now()
        if hasattr(self, "start_time"):
            self.duration = int((self.end_time - self.start_time).total_seconds() * 1000)

@dataclass
class Thought:
    id: str
    type: ThoughtType
    content: str
    confidence: float = 0.8
    reasoning_chain: List[str] = field(default_factory=list)
    decision: Optional[str] = None

@dataclass
class Observation:
    id: str
    source: str
    content: Any
    observation_type: str = "data"

@dataclass
class AgentStateData:
    task: str = ""
    goal: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    state: AgentState = AgentState.IDLE
    context: Dict[str, Any] = field(default_factory=dict)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._executors: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()

    async def register(self, tool_info: ToolInfo, executor: Callable) -> bool:
        async with self._lock:
            if tool_info.name in self._tools:
                logger.warning(f"工具已存在: {tool_info.name}")
                return False
            self._tools[tool_info.name] = tool_info
            self._executors[tool_info.name] = executor
            logger.info(f"工具注册成功: {tool_info.name}")
            return True

    def get_tool(self, tool_name: str) -> Optional[ToolInfo]:
        return self._tools.get(tool_name)

    def get_executor(self, tool_name: str) -> Optional[Callable]:
        return self._executors.get(tool_name)

    def list_tools(self) -> List[ToolInfo]:
        return list(self._tools.values())

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_info = self.get_tool(tool_name)
        if not tool_info:
            raise ValueError(f"工具不存在: {tool_name}")

        executor = self.get_executor(tool_name)
        if not executor:
            raise ValueError(f"工具执行函数未注册: {tool_name}")

        for param in tool_info.required_params:
            if param not in params:
                raise ValueError(f"缺少必需参数: {param}")

        timeout_duration = tool_info.timeout
        try:
            if asyncio.iscoroutinefunction(executor):
                result = await asyncio.wait_for(executor(**params), timeout=timeout_duration)
            else:
                result = await asyncio.to_thread(executor, **params)
            return result if isinstance(result, dict) else {"result": result}
        except asyncio.TimeoutError:
            raise TimeoutError(f"工具执行超时: {tool_name}")


class ShortTermMemory:
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._memory: deque = deque(maxlen=max_size)

    def add(self, content: Any, importance: float = 0.5) -> str:
        import uuid
        memory_id = str(uuid.uuid4())
        self._memory.append({
            "id": memory_id,
            "content": content,
            "importance": importance,
            "timestamp": datetime.now().isoformat()
        })
        return memory_id

    def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        return list(self._memory)[-limit:][::-1] if limit < len(self._memory) else list(self._memory)[::-1]

    def clear(self) -> None:
        self._memory.clear()

    def __len__(self) -> int:
        return len(self._memory)


class ThoughtEngine:
    """基于 LLM 的思考引擎"""

    def __init__(self, max_reasoning_depth: int = 5, llm_client=None):
        self.max_reasoning_depth = max_reasoning_depth
        self._thought_counter = 0
        self.llm_client = llm_client

    def _create_thought(self, thought_type: ThoughtType, content: str) -> Thought:
        self._thought_counter += 1
        return Thought(
            id=f"thought_{self._thought_counter}",
            type=thought_type,
            content=content,
            confidence=0.85
        )

    def _extract_task_entities(self, task: str) -> Dict[str, Any]:
        """使用 LLM 提取任务实体"""
        if self.llm_client:
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
                    content = result.get("content", "")
                    import json
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()

                    entities = json.loads(content)
                    logger.info(f"[ThoughtEngine] LLM提取实体: {entities}")
                    return entities
            except Exception as e:
                logger.error(f"[ThoughtEngine] LLM实体提取失败: {e}")

        return self._extract_entities_by_rules(task)

    def _extract_entities_by_rules(self, task: str) -> Dict[str, Any]:
        entities = {}
        days_match = re.search(r"(\d+)\s*天", task)
        entities["days"] = int(days_match.group(1)) if days_match else 3

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
                    entities["city"] = city
                    break

        budget_match = re.search(r"(\d+)\s*元", task)
        if budget_match:
            entities["budget"] = int(budget_match.group(1))

        return entities

    def analyze_task(self, task: str, context: Dict[str, Any]) -> Thought:
        if self.llm_client:
            return self._analyze_task_with_llm(task, context)
        else:
            return self._analyze_task_with_rules(task, context)

    def _analyze_task_with_llm(self, task: str, context: Dict[str, Any]) -> Thought:
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
                content = result.get("content", "")
                import json
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                analysis = json.loads(content)
                logger.info(f"[ThoughtEngine] LLM分析结果: {analysis}")

                thought = self._create_thought(ThoughtType.ANALYSIS, f"【任务分析】{analysis.get('reasoning', '')}")
                thought.decision = json.dumps([{
                    "step": i + 1,
                    "action": tool.get("name", ""),
                    "params": tool.get("parameters", {})
                } for i, tool in enumerate(analysis.get("tools", []))])
                thought.confidence = analysis.get("confidence", 0.85)
                return thought
        except Exception as e:
            logger.error(f"[ThoughtEngine] LLM分析失败: {e}")

        return self._analyze_task_with_rules(task, context)

    def _analyze_task_with_rules(self, task: str, context: Dict[str, Any]) -> Thought:
        entities = self._extract_entities_by_rules(task)
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["推荐", "建议", "哪些", "适合"]):
            task_type = "recommendation"
        elif any(kw in task_lower for kw in ["查询", "搜索", "有什么", "信息"]):
            task_type = "query"
        elif any(kw in task_lower for kw in ["规划", "计划", "路线", "行程", "安排", "攻略", "旅游", "旅行", "游玩", "出游", "出发"]):
            task_type = "planning"
        else:
            task_type = "general"

        task_type_cn = {
            "recommendation": "城市推荐",
            "query": "信息查询",
            "planning": "路线规划",
            "budget": "预算计算",
            "general": "一般对话"
        }.get(task_type, "一般对话")

        content = f"【任务分析】用户输入：「{task}」\n【意图识别】任务类型={task_type_cn}\n【提取信息】{entities}"
        thought = self._create_thought(ThoughtType.ANALYSIS, content)
        thought.confidence = 0.7
        return thought

    def plan_actions(self, task: str, tools: List[ToolInfo], constraints: Optional[List[str]] = None) -> Thought:
        if self.llm_client:
            return self._plan_actions_with_llm(task, tools, constraints)
        else:
            return self._plan_actions_with_rules(task, tools, constraints)

    def _plan_actions_with_llm(self, task: str, tools: List[ToolInfo], constraints: Optional[List[str]] = None) -> Thought:
        tool_descriptions = []
        for t in tools:
            params = t.parameters.get("properties", {})
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
                content = result.get("content", "")
                import json
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                plan = json.loads(content)
                logger.info(f"[ThoughtEngine] LLM规划结果: {plan}")

                steps = plan.get("steps", [])
                thought = self._create_thought(ThoughtType.PLANNING, f"【执行计划】{plan.get('reasoning', '')}")
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

    def _plan_actions_with_rules(self, task: str, tools: List[ToolInfo], constraints: Optional[List[str]] = None) -> Thought:
        steps = self._decompose_task_by_rules(task, tools)

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
        actions = []
        task_lower = task.lower()

        days_match = re.search(r"(\d+)\s*天", task)
        days = int(days_match.group(1)) if days_match else 3

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

        if any(kw in task_lower for kw in ["推荐", "建议", "哪些", "适合"]):
            recommend_tools = [t for t in tools if "recommend" in t.name.lower() or "search" in t.name.lower()]
            if recommend_tools:
                actions.append(Action(
                    id=f"action_{len(actions)}",
                    tool_name=recommend_tools[0].name,
                    parameters={"interests": [], "budget_min": None, "budget_max": None, "season": None}
                ))

        if city:
            city_info_tools = [t for t in tools if "city_info" in t.name.lower() or "attraction" in t.name.lower()]
            if city_info_tools:
                actions.append(Action(
                    id=f"action_{len(actions)}",
                    tool_name=city_info_tools[0].name,
                    parameters={"city": city}
                ))

        route_tools = [t for t in tools if "route" in t.name.lower() or "plan" in t.name.lower()]
        if route_tools and (any(kw in task_lower for kw in ["规划", "路线", "行程", "安排"]) or
                           any(kw in task_lower for kw in ["旅游", "旅行", "游玩", "出游", "出发"])):
            actions.append(Action(
                id=f"action_{len(actions)}",
                tool_name=route_tools[0].name,
                parameters={"city": city or "未知", "days": days}
            ))

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
        thought = self._create_thought(ThoughtType.REFLECTION, "反思行动结果")
        success = action_result.get("success", False)

        thought.reasoning_chain = [
            f"行动成功：{success}",
            f"改进建议：{'结果符合预期' if success else '建议检查参数或尝试其他工具'}"
        ]
        thought.confidence = 0.9 if success else 0.6

        return thought


class EvaluationEngine:
    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0
        }

    def evaluate_result(self, action: Action) -> Dict[str, Any]:
        evaluation = {
            "success": action.status == ActionStatus.SUCCESS,
            "duration": action.duration,
            "has_result": action.result is not None
        }

        self._metrics["total_tasks"] += 1
        if evaluation["success"]:
            self._metrics["successful_tasks"] += 1
        else:
            self._metrics["failed_tasks"] += 1

        return evaluation


class ReActAgent:
    def __init__(self, name: str = "ReActAgent", max_steps: int = 10,
                 max_reasoning_depth: int = 5, llm_client=None):
        self.name = name
        self.max_steps = max_steps

        self.tool_registry = ToolRegistry()
        self.thought_engine = ThoughtEngine(max_reasoning_depth, llm_client)
        self.evaluation_engine = EvaluationEngine()
        self.short_memory = ShortTermMemory()

        self.state = AgentStateData(max_steps=max_steps)
        self.current_state = AgentState.IDLE

        self.action_history: List[Action] = []
        self.thought_history: List[Thought] = []

        # 流式思考回调
        self._on_thought_callbacks: List[Callable] = []
        self._on_action_callbacks: List[Callable] = []

        # 实时思考流相关
        self._think_stream_callback = None  # 实时思考流回调
        self._think_start_time = None  # 思考开始时间

    def register_tool(self, tool_info: ToolInfo, executor: Callable) -> bool:
        if tool_info.name in self.tool_registry._tools:
            return False
        self.tool_registry._tools[tool_info.name] = tool_info
        self.tool_registry._executors[tool_info.name] = executor
        return True

    def add_thought_callback(self, callback: Callable) -> None:
        self._on_thought_callbacks.append(callback)

    def add_action_callback(self, callback: Callable) -> None:
        self._on_action_callbacks.append(callback)

    def set_think_stream_callback(self, callback: Callable[[str, float], None]) -> None:
        """设置实时思考流回调 - callback(thought_content, elapsed_seconds)"""
        self._think_stream_callback = callback

    def _notify_thought(self, thought: Thought) -> None:
        for callback in self._on_thought_callbacks:
            try:
                callback(thought)
            except Exception as e:
                logger.error(f"思考回调错误: {e}")

    def _notify_action(self, action: Action) -> None:
        for callback in self._on_action_callbacks:
            try:
                callback(action)
            except Exception as e:
                logger.error(f"行动回调错误: {e}")

    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.state.task = task
        self.state.context = context or {}
        self.state.current_step = 0
        self.state.history = []

        self.current_state = AgentState.REASONING
        self._think_start_time = None  # 重置

        logger.info(f"开始执行任务: {task}")

        try:
            while self.state.current_step < self.max_steps:
                # 首次思考时记录开始时间
                if self._think_start_time is None:
                    self._think_start_time = datetime.now()

                observation = await self._observe()
                thought = await self._think(observation)

                # 实时流式思考内容
                if self._think_stream_callback:
                    elapsed = (datetime.now() - self._think_start_time).total_seconds()
                    self._think_stream_callback(f"已思考（{elapsed:.1f}秒）\n\n{thought.content}", elapsed)

                if self._should_stop(thought):
                    break

                action = await self._act(thought)
                evaluation = await self._evaluate(action)

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
        self.current_state = AgentState.REASONING

        if self.state.current_step == 0:
            thought = self.thought_engine.analyze_task(
                self.state.task,
                self.state.context
            )

            # 始终生成执行计划，不管confidence高低
            plan_thought = self.thought_engine.plan_actions(
                self.state.task,
                self.tool_registry.list_tools()
            )
            thought.decision = plan_thought.decision
            thought.reasoning_chain.extend(plan_thought.reasoning_chain)
        else:
            last_action = self.action_history[-1] if self.action_history else None

            if last_action and last_action.status == ActionStatus.FAILED:
                thought = self.thought_engine.reflect(last_action.result or {})
                thought.content = f"""【执行失败】步骤 {self.state.current_step}

【失败原因】{last_action.error}
【当前状态】需要调整策略或检查参数
【后续行动】尝试其他工具或重新执行"""
            elif last_action and last_action.status == ActionStatus.SUCCESS:
                result = last_action.result
                tool_name = last_action.tool_name

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
                thought = self.thought_engine._create_thought(
                    ThoughtType.INFERENCE,
                    f"【继续执行】步骤 {self.state.current_step + 1}\n\n根据执行计划，继续执行下一步操作"
                )
                thought.reasoning_chain = [f"执行步骤 {self.state.current_step + 1}"]

        self.thought_history.append(thought)
        self._notify_thought(thought)

        return thought

    def _should_stop(self, thought: Thought) -> bool:
        if thought.type == ThoughtType.INFERENCE:
            last_action = self.action_history[-1] if self.action_history else None
            if last_action and last_action.tool_name in ["llm_chat", "generate_city_recommendation", "generate_route_plan"]:
                if last_action.status == ActionStatus.SUCCESS:
                    return True

        if thought.confidence > 0.9 and thought.decision:
            last_action = self.action_history[-1] if self.action_history else None
            if last_action and last_action.status == ActionStatus.SUCCESS:
                return True

        if self.state.current_step >= self.max_steps - 1:
            return True

        return False

    async def _act(self, thought: Thought) -> Action:
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
                params = decision.get("params", {})

                # 参数名映射：处理 LLM 生成的计划中参数名不匹配的问题
                param_mapping = {
                    'city': 'cities',  # city -> cities
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
        self.current_state = AgentState.EVALUATING
        return self.evaluation_engine.evaluate_result(action)

    def _update_state(self, action: Action, evaluation: Dict[str, Any]) -> None:
        self.state.current_step += 1
        if action.result:
            self.state.context["last_result"] = action.result
        self.state.updated_at = datetime.now()

    def _record_history(self, thought: Thought, action: Action, evaluation: Dict[str, Any]) -> None:
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
        self.state = AgentStateData(max_steps=self.max_steps)
        self.current_state = AgentState.IDLE
        self.action_history.clear()
        self.thought_history.clear()
        self.short_memory.clear()
