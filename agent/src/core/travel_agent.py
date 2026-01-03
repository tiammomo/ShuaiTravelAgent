"""
ReAct 旅游助手 Agent
====================

基于 ReAct (Reasoning and Acting) 模式的旅游智能体实现。
"""

import json
import sys
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

# 添加父目录到路径以支持外部导入
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_SRC_DIR = os.path.dirname(CURRENT_DIR)
if AGENT_SRC_DIR not in sys.path:
    sys.path.insert(0, AGENT_SRC_DIR)

# 使用绝对导入替代相对导入
from core.react_agent import ReActAgent, ToolInfo, Action, Thought, AgentState, ActionStatus
from config.config_manager import ConfigManager
from memory.manager import MemoryManager
from llm.client import LLMClient


def create_travel_tools(config_manager: ConfigManager) -> List[tuple]:
    """创建旅游助手工具列表"""
    from environment.travel_data import TravelData

    tools = []

    tools.append((
        ToolInfo(
            name="search_cities",
            description="根据用户兴趣、预算和季节偏好搜索匹配的城市",
            parameters={
                'type': 'object',
                'properties': {
                    'interests': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': '用户兴趣标签列表'
                    },
                    'budget_min': {'type': 'integer', 'description': '最低预算'},
                    'budget_max': {'type': 'integer', 'description': '最高预算'},
                    'season': {'type': 'string', 'description': '旅行季节'}
                }
            },
            required_params=[],
            category='travel',
            tags=['search', 'city', 'recommend']
        ),
        lambda interests=None, budget_min=None, budget_max=None, season=None:
            _search_cities(config_manager, interests, (budget_min, budget_max) if budget_min and budget_max else None, season)
    ))

    tools.append((
        ToolInfo(
            name="query_attractions",
            description="查询指定城市的景点信息",
            parameters={
                'type': 'object',
                'properties': {
                    'cities': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': '要查询的城市名称列表'
                    }
                },
                'required': ['cities']
            },
            required_params=['cities'],
            category='travel',
            tags=['query', 'attraction', 'scenic']
        ),
        lambda cities: _query_attractions(config_manager, cities)
    ))

    tools.append((
        ToolInfo(
            name="generate_route",
            description="为指定城市生成详细的旅游路线规划",
            parameters={
                'type': 'object',
                'properties': {
                    'city': {'type': 'string', 'description': '目标城市名称'},
                    'days': {'type': 'integer', 'description': '旅行天数，默认3天', 'default': 3}
                },
                'required': ['city']
            },
            required_params=['city'],
            category='travel',
            tags=['route', 'plan', 'schedule']
        ),
        lambda city, days=3: _generate_route(config_manager, city, days)
    ))

    tools.append((
        ToolInfo(
            name="calculate_budget",
            description="计算指定城市和天数的旅游预算",
            parameters={
                'type': 'object',
                'properties': {
                    'city': {'type': 'string', 'description': '目标城市'},
                    'days': {'type': 'integer', 'description': '旅行天数'}
                },
                'required': ['city', 'days']
            },
            required_params=['city', 'days'],
            category='travel',
            tags=['budget', 'cost', 'expense']
        ),
        lambda city, days: _calculate_budget(config_manager, city, days)
    ))

    tools.append((
        ToolInfo(
            name="get_city_info",
            description="获取指定城市的详细信息",
            parameters={
                'type': 'object',
                'properties': {
                    'city': {'type': 'string', 'description': '城市名称'}
                },
                'required': ['city']
            },
            required_params=['city'],
            category='travel',
            tags=['city', 'info', 'detail']
        ),
        lambda city: _get_city_info(config_manager, city)
    ))

    tools.append((
        ToolInfo(
            name="llm_chat",
            description="使用大语言模型进行对话回答",
            parameters={
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': '用户问题'},
                    'context': {'type': 'string', 'description': '对话上下文'}
                },
                'required': ['query']
            },
            required_params=['query'],
            category='ai',
            tags=['chat', 'llm', 'ai']
        ),
        lambda query, context="": _llm_chat(config_manager, query, context)
    ))

    tools.append((
        ToolInfo(
            name="generate_city_recommendation",
            description="根据用户需求生成个性化城市推荐",
            parameters={
                'type': 'object',
                'properties': {
                    'user_query': {'type': 'string', 'description': '用户原始需求'},
                    'available_cities': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': '可选城市列表'
                    }
                },
                'required': ['user_query', 'available_cities']
            },
            required_params=['user_query', 'available_cities'],
            category='ai',
            tags=['recommend', 'city', 'llm']
        ),
        lambda user_query, available_cities: _generate_recommendation(config_manager, user_query, available_cities)
    ))

    tools.append((
        ToolInfo(
            name="generate_route_plan",
            description="根据城市景点信息生成详细路线规划",
            parameters={
                'type': 'object',
                'properties': {
                    'city': {'type': 'string', 'description': '目标城市'},
                    'days': {'type': 'integer', 'description': '旅行天数'},
                    'preferences': {'type': 'string', 'description': '用户偏好'}
                },
                'required': ['city', 'days']
            },
            required_params=['city', 'days'],
            category='ai',
            tags=['route', 'plan', 'llm']
        ),
        lambda city, days, preferences="": _generate_route_plan(config_manager, city, days, preferences)
    ))

    return tools


def _search_cities(config_manager, interests: List[str] = None,
                   budget: tuple = None, season: str = None) -> Dict[str, Any]:
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.search_cities(interests, budget, season)


def _query_attractions(config_manager, cities: List[str]) -> Dict[str, Any]:
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.query_attractions(cities)


def _generate_route(config_manager, city: str, days: int) -> Dict[str, Any]:
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    result = env.get_city_info(city)
    if not result.get('success'):
        return result

    city_info = result.get('info', {})
    attractions = city_info.get('attractions', [])

    route_plan = []
    for i in range(min(days, len(attractions))):
        attr = attractions[i] if i < len(attractions) else {'name': '自由活动'}
        route_plan.append({
            'day': i + 1,
            'attractions': [attr['name']] if isinstance(attr, dict) else [attr],
            'schedule': f'游览{attr.get("name", "自由活动")}'
        })

    return {
        'success': True,
        'city': city,
        'route_plan': route_plan,
        'total_cost_estimate': {
            'tickets': sum(a.get('ticket', 0) for a in attractions[:days]),
            'total': sum(a.get('ticket', 0) for a in attractions[:days]) + city_info.get('avg_budget_per_day', 400) * days
        }
    }


def _calculate_budget(config_manager, city: str, days: int) -> Dict[str, Any]:
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.calculate_budget(city, days)


def _get_city_info(config_manager, city: str) -> Dict[str, Any]:
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.get_city_info(city)


def _llm_chat(config_manager, query: str, context: str = "") -> Dict[str, Any]:
    llm_config = config_manager.get_default_model_config()
    llm_client = LLMClient(llm_config)

    messages = [{"role": "user", "content": query}]
    if context:
        messages.insert(0, {"role": "system", "content": context})

    result = llm_client.chat(messages)

    if isinstance(result, dict):
        if result.get('success') and 'content' in result:
            return {'success': True, 'response': result['content']}
        elif 'error' in result:
            return {'success': False, 'response': result['error']}
    return result


def _generate_recommendation(config_manager, user_query: str,
                             available_cities: List[str]) -> Dict[str, Any]:
    llm_config = config_manager.get_default_model_config()
    llm_client = LLMClient(llm_config)
    return llm_client.generate_travel_recommendation(user_query, "", available_cities)


def _generate_route_plan(config_manager, city: str, days: int,
                         preferences: str = "") -> Dict[str, Any]:
    city_info = config_manager.get_city_info(city)
    if not city_info:
        return {'success': False, 'error': f'未找到城市: {city}'}

    attractions = city_info.get('attractions', [])
    llm_config = config_manager.get_default_model_config()
    llm_client = LLMClient(llm_config)
    return llm_client.generate_route_plan(city, days, attractions, preferences)


class ReActTravelAgent:
    """ReAct 旅游助手 Agent"""

    def __init__(self, config_path: str = "config/llm_config.yaml",
                 model_id: Optional[str] = None,
                 max_steps: int = 10):
        self.config_manager = ConfigManager(config_path)

        memory_config = self.config_manager.agent_config.get('max_working_memory', 10)
        self.memory_manager = MemoryManager(
            max_working_memory=memory_config
        )

        # Get model config using the new method
        if model_id:
            llm_config = self.config_manager.get_model_config(model_id)
        else:
            llm_config = self.config_manager.get_default_model_config()

        self.llm_client = LLMClient(llm_config)

        # 传递 llm_client 给 ReActAgent，使其能使用 LLM 进行思考
        self.react_agent = ReActAgent(
            name="TravelReActAgent",
            max_steps=max_steps,
            max_reasoning_depth=5,
            llm_client=self.llm_client
        )

        self._register_tools()
        self._register_callbacks()

    def _register_tools(self) -> None:
        tools = create_travel_tools(self.config_manager)
        for tool_info, executor in tools:
            self.react_agent.register_tool(tool_info, executor)

    def _register_callbacks(self) -> None:
        def on_thought(thought: Thought):
            self.memory_manager.add_message('assistant', f"[思考] {thought.content}")

        def on_action(action: Action):
            if action.status == ActionStatus.RUNNING:
                self.memory_manager.add_message('assistant', f"[行动] 执行工具: {action.tool_name}")
            elif action.status == ActionStatus.SUCCESS:
                self.memory_manager.add_message('assistant', f"[完成] {action.tool_name}")
            elif action.status == ActionStatus.FAILED:
                self.memory_manager.add_message('assistant', f"[失败] {action.tool_name}: {action.error}")

        self.react_agent.add_thought_callback(on_thought)
        self.react_agent.add_action_callback(on_action)

    async def process(self, user_input: str) -> Dict[str, Any]:
        """处理用户输入"""
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"[Agent] 开始处理用户输入: {user_input[:50]}...")

        try:
            self.memory_manager.add_message('user', user_input)

            context = {
                'user_query': user_input,
                'user_preference': self.memory_manager.get_user_preference()
            }

            result = await self.react_agent.run(user_input, context)
            logger.info(f"[Agent] ReAct 执行完成, success={result.get('success')}, steps={len(result.get('history', []))}")

            if result.get('success'):
                history = result.get('history', [])
                reasoning_text = self._build_reasoning_text(history)
                answer = self._extract_answer(history)
                logger.info(f"[Agent] 提取到答案: {answer[:100]}...")

                self.memory_manager.add_message('assistant', answer)

                return {
                    "success": True,
                    "answer": answer,
                    "reasoning": {
                        "text": reasoning_text,
                        "total_steps": len(history),
                        "tools_used": self._extract_tools_used(history)
                    },
                    "history": history
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', '处理失败'),
                    "reasoning": None,
                    "history": result.get('history', [])
                }

        except Exception as e:
            logger.error(f"[Agent] 处理异常: {e}")
            return {
                "success": False,
                "error": f"处理失败: {str(e)}",
                "reasoning": None
            }

    def process_sync(self, user_input: str) -> Dict[str, Any]:
        """同步处理用户输入（用于 gRPC 调用）"""
        import asyncio
        return asyncio.run(self.process(user_input))

    async def process_stream(self, user_input: str, answer_callback=None, done_callback=None):
        """流式处理用户输入，使用真正的token级别流式输出

        Args:
            user_input: 用户输入
            answer_callback: 回答内容回调函数，接收 (token: str)
            done_callback: 完成回调函数，接收 (result: Dict)
        """
        import logging
        import time as time_module
        logger = logging.getLogger(__name__)

        logger.info(f"[Agent] 开始流式处理用户输入: {user_input[:50]}...")
        start_time = time_module.time()

        try:
            self.memory_manager.add_message('user', user_input)

            context = {
                'user_query': user_input,
                'user_preference': self.memory_manager.get_user_preference()
            }

            # 先运行 ReAct agent 获取思考历史
            result = await self.react_agent.run(user_input, context)
            logger.info(f"[Agent] ReAct 执行完成, success={result.get('success')}, steps={len(result.get('history', []))}")

            if result.get('success'):
                history = result.get('history', [])
                reasoning_text = self._build_reasoning_text(history)
                answer = self._extract_answer(history)

                self.memory_manager.add_message('assistant', answer)

                # 使用流式 LLM 调用生成答案，实现真正的 token 级别流式
                # 构建消息
                system_prompt = """你是一个专业的旅游助手。请根据用户的问题，提供详细、准确的旅游建议和规划。回答要简洁明了，条理清晰。"""
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]

                logger.info(f"[Agent] 开始流式生成答案...")

                # 使用 LLM 客户端的流式方法
                if hasattr(self.llm_client, 'chat_stream'):
                    token_count = 0
                    accumulated_answer = ""

                    # 流式遍历 LLM 响应
                    for token in self.llm_client.chat_stream(messages, temperature=0.7):
                        token_count += 1
                        accumulated_answer += token

                        # 立即发送每个 token
                        if answer_callback:
                            answer_callback(token)

                        # 极短延迟，确保 token 独立发送
                        await asyncio.sleep(0.01)

                    answer = accumulated_answer
                    logger.info(f"[Agent] 流式生成完成, 共 {token_count} tokens")

                else:
                    # 回退到非流式
                    logger.warning("[Agent] LLM 客户端不支持流式，使用批量发送")
                    chunks = self._split_into_chunks(answer)
                    for chunk in chunks:
                        if answer_callback:
                            answer_callback(chunk)
                        await asyncio.sleep(0.02)

                elapsed = time_module.time() - start_time
                logger.info(f"[Agent] 总耗时: {elapsed:.2f}秒")

                final_result = {
                    "success": True,
                    "answer": answer,
                    "reasoning": {
                        "text": reasoning_text,
                        "total_steps": len(history),
                        "tools_used": self._extract_tools_used(history)
                    },
                    "history": history
                }

                if done_callback:
                    done_callback(final_result)

                return final_result
            else:
                final_result = {
                    "success": False,
                    "error": result.get('error', '处理失败'),
                    "reasoning": None,
                    "history": result.get('history', [])
                }
                if done_callback:
                    done_callback(final_result)
                return final_result

        except Exception as e:
            logger.error(f"[Agent] 处理异常: {e}")
            import traceback
            traceback.print_exc()
            error_result = {
                "success": False,
                "error": f"处理失败: {str(e)}",
                "reasoning": None
            }
            if done_callback:
                done_callback(error_result)
            return error_result

    def _split_into_chunks(self, text: str, chunk_size: int = 3) -> List[str]:
        """将文本拆分成小块用于流式输出

        Args:
            text: 输入文本
            chunk_size: 每个块的最大字符数（中文字符），默认3个
        Returns:
            文本块列表
        """
        if not text:
            return []

        chunks = []
        i = 0

        while i < len(text):
            # 找到下一个断点（标点或换行）
            chunk_end = min(i + 20, len(text))  # 最大20个字符

            # 从后往前找合适的断点
            for j in range(chunk_end, i, -1):
                char = text[j - 1]
                # 中文标点作为断点
                if char in '。！？；：、\n':
                    chunk_end = j
                    break
                # 英文标点也作为断点
                if char in '.!?:;,' and j > i + 3:
                    chunk_end = j
                    break

            # 确保至少返回一个字符
            if chunk_end <= i:
                chunk_end = min(i + 1, len(text))

            chunk = text[i:chunk_end]
            chunks.append(chunk)
            i = chunk_end

        # 如果分块太大，进一步拆分
        final_chunks = []
        for chunk in chunks:
            while len(chunk) > 15:  # 如果块太大，按更小单位拆分
                final_chunks.append(chunk[:8])  # 8个字符
                chunk = chunk[8:]
            if chunk:
                final_chunks.append(chunk)

        return final_chunks if final_chunks else [text]

    def _build_reasoning_text(self, history: List[Dict]) -> str:
        if not history:
            return "<thinking>\n[Timestamp: {timestamp}]\n\n[Intent Analysis]\nNo reasoning history available.\n\n[Context Evaluation]\nNo context available.\n\n[Response Planning]\nUnable to generate response.\n\n[Constraint Check]\nNo constraints checked.\n</thinking>".format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        intent_analysis = []
        context_evaluation = []
        response_planning = []
        constraint_check = []

        for i, step in enumerate(history):
            thought = step.get('thought', {})
            action = step.get('action', {})

            thought_type = thought.get('type', 'UNKNOWN')
            thought_content = thought.get('content', '')
            action_name = action.get('tool_name', '')
            action_status = action.get('status', 'PENDING')
            result = action.get('result', {})

            if thought_type == 'ANALYSIS':
                if thought_content:
                    intent_analysis.append(f"Step {i + 1}: {thought_content}")
            elif thought_type == 'PLANNING':
                if thought_content:
                    response_planning.append(f"Step {i + 1}: {thought_content}")
            elif thought_type == 'INFERENCE':
                if thought_content:
                    context_evaluation.append(f"Step {i + 1}: {thought_content}")
                if action_name and action_name != 'none':
                    status_str = 'SUCCESS' if action_status == 'SUCCESS' else 'FAILED' if action_status == 'FAILED' else 'RUNNING'
                    context_evaluation.append(f"  - Tool: {action_name} [{status_str}]")
            elif thought_type == 'REFLECTION':
                if thought_content:
                    constraint_check.append(f"Step {i + 1}: {thought_content}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        intent_section = "[Intent Analysis]\n"
        if intent_analysis:
            intent_section += "\n".join(intent_analysis)
        else:
            intent_section += f"User query analysis based on {len(history)} reasoning steps.\n"

        context_section = "[Context Evaluation]\n"
        if context_evaluation:
            context_section += "\n".join(context_evaluation)
        else:
            context_section += "No explicit context evaluation steps recorded."

        response_section = "[Response Planning]\n"
        if response_planning:
            response_section += "\n".join(response_planning)
        else:
            response_section += "Response generation based on tool execution results."

        constraint_section = "[Constraint Check]\n"
        if constraint_check:
            constraint_section += "\n".join(constraint_check)
        else:
            constraint_section += "All constraints satisfied.\n"
            constraint_section += f"- Total reasoning steps: {len(history)}\n"
            constraint_section += f"- Tools executed: {len(self._extract_tools_used(history))}\n"
            constraint_section += "- Response format: Standard text response"

        thinking_content = f"""[Timestamp: {timestamp}]

{intent_section}

{context_section}

{response_section}

{constraint_section}"""

        return f"<thinking>\n{thinking_content}\n</thinking>"

    def _extract_tools_used(self, history: List[Dict]) -> List[str]:
        tools = []
        for step in history:
            action = step.get('action', {})
            tool_name = action.get('tool_name', '')
            if tool_name and tool_name not in tools and tool_name != 'none':
                tools.append(tool_name)
        return tools

    def _extract_answer(self, history: List[Dict]) -> str:
        """提取最终回答，优先使用LLM生成活泼的回答"""
        # 收集所有工具执行结果
        tool_results = []
        has_successful_tools = False

        for step in reversed(history):
            action = step.get('action', {})
            if action.get('status') == 'SUCCESS':
                has_successful_tools = True
                result = action.get('result', {})
                tool_name = action.get('tool_name', '')
                if result:
                    tool_results.append({
                        'tool': tool_name,
                        'result': result
                    })

        # 如果有工具执行结果，使用LLM生成活泼的回答
        if has_successful_tools:
            return self._generate_answer(history)

        # 否则返回默认消息
        return '让我来帮你规划这次旅行吧！🎉'

    def _format_attractions_response(self, tool_result: Dict) -> str:
        """Format attractions data into a readable response."""
        lines = []

        # Handle both old format (cities key) and new format (data key)
        if 'cities' in tool_result:
            data = tool_result['cities']
        elif 'data' in tool_result:
            data = tool_result['data']
        else:
            data = tool_result

        if not data:
            return "未找到相关景点信息"

        for city, data_item in data.items():
            region = data_item.get('region', '') if isinstance(data_item, dict) else ''
            region_str = f" (来自{region}地区)" if region else ""
            lines.append(f"\n## {city}{region_str}")
            attractions = data_item.get('attractions', []) if isinstance(data_item, dict) else []
            if attractions:
                lines.append("\n### 景点推荐：")
                for i, attr in enumerate(attractions[:10], 1):
                    name = attr.get('name', '未知景点')
                    desc = attr.get('description', '')[:100]
                    ticket = attr.get('ticket', 0)
                    lines.append(f"{i}. **{name}**")
                    if desc:
                        lines.append(f"   - {desc}")
                    if ticket > 0:
                        lines.append(f"   - 门票: ¥{ticket}")
            else:
                lines.append("  暂无景点信息")

        return '\n'.join(lines) if lines else "未找到相关景点信息"

    def _generate_answer(self, history: List[Dict]) -> str:
        try:
            tool_results = []
            for step in history:
                action = step.get('action', {})
                if action.get('status') == 'SUCCESS' and action.get('result'):
                    tool_results.append({
                        'tool': action.get('tool_name', ''),
                        'result': action.get('result', {})
                    })

            system_prompt = """你是一个超级热情、活泼的AI旅游小伙伴！

【任务】
根据工具查询结果，生成结构化的旅游推荐信息。

【说话风格】
- 使用轻松活泼的语气，多用口语化表达
- 适当使用emoji表情符号增添趣味
- 用"小伙伴"、"亲"、"哇塞"等亲切称呼
- 适当加入旅行的氛围感描写
- 重点信息用**加粗**标记

【输出格式】
必须输出JSON格式，不要包含任何Markdown格式！JSON结构如下：
{
    "opening": "开场白，使用轻松活泼的语气",
    "cities": [
        {
            "name": "城市名",
            "emoji": "城市emoji",
            "days": "推荐天数",
            "budget": "预算描述",
            "season": "最佳旅行季节",
            "attractions": [
                {"name": "景点名", "type": "景点类型", "ticket": "门票价格", "description": "简短描述"}
            ]
        }
    ],
    "tips": "旅行小贴士"
}

【重要】
- 只输出JSON，不要输出任何Markdown语法
- 确保JSON格式正确，可以被json.loads()解析
- 每个城市至少推荐2-4个景点"""

            user_prompt = f"""我想要规划一次旅行，这是我的查询结果：
{json.dumps(tool_results, ensure_ascii=False, indent=2)}

请只输出JSON格式的结果，不要有任何其他内容。"""

            result = self.llm_client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], temperature=0.7)

            if result.get('success'):
                content = result.get('content', '')
                # 尝试解析JSON
                data = self._parse_json_response(content)
                if data:
                    return self._format_travel_response(data)
                return content
            return '处理完成'

        except Exception as e:
            return f'生成回答失败：{str(e)}'

    def _parse_json_response(self, content: str) -> dict:
        """解析LLM返回的JSON响应"""
        import re
        try:
            # 首先尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON块（可能有 markdown 代码块包裹）
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass

        # 尝试提取任何 JSON 对象
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        return None

    def _format_travel_response(self, data: dict) -> str:
        """将结构化数据格式化为规范的Markdown"""
        lines = []

        # 开场白
        opening = data.get('opening', '')
        if opening:
            lines.append(opening)
            lines.append('')

        # 城市推荐
        for i, city in enumerate(data.get('cities', [])):
            lines.append(f"## {city.get('emoji', '')} {city.get('name', '')}")
            lines.append('')

            # 城市基本信息
            lines.append(f"- **推荐天数**：{city.get('days', '3天')}")
            lines.append(f"- **预算**：约 **{city.get('budget', '待定')}/天**")
            lines.append(f"- **最佳旅行季节**：{city.get('season', '四季皆宜')}")
            lines.append('')

            # 必游景点
            lines.append('#### 必游景点：')
            attractions = city.get('attractions', [])
            for j, attr in enumerate(attractions, 1):
                ticket = attr.get('ticket', '免费')
                ticket_str = f"门票 **{ticket}**" if ticket not in ['免费', '0', 0] else '完全免费'
                lines.append(f"{j}. **{attr.get('name', '未知景点')}**（{attr.get('type', '景点')}）- {ticket_str}")
                desc = attr.get('description', '')
                if desc:
                    lines.append(f"   - {desc}")
                lines.append('')

            # 城市之间加空行（最后一个城市除外）
            if i < len(data.get('cities', [])) - 1:
                lines.append('')

        # 旅行小贴士
        tips = data.get('tips', '')
        if tips:
            lines.append('')
            lines.append('☀️ 旅行小贴士')
            lines.append('')
            lines.append(tips)

        return '\n'.join(lines)

    def get_conversation_history(self) -> list:
        return self.memory_manager.get_conversation_history()

    def clear_conversation(self) -> None:
        self.memory_manager.clear_conversation()
        self.react_agent.reset()
