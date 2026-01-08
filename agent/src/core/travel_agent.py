"""
================================================================================
ReAct 旅游助手 Agent - 核心实现模块
================================================================================

本模块实现了基于 ReAct (Reasoning and Acting) 模式的旅游智能体。

功能概述：
- 提供完整的旅游相关工具集（城市搜索、景点查询、路线规划、预算计算等）
- 集成 LLM 进行自然语言理解和回答生成
- 支持同步和流式两种处理模式
- 维护对话历史和用户偏好

ReAct 模式流程：
1. 接收用户输入，分析意图
2. 选择合适的工具执行
3. 收集工具执行结果
4. 使用 LLM 生成最终回答

核心组件：
- create_travel_tools: 旅游工具工厂函数
- 工具执行函数: _search_cities, _query_attractions, _generate_route 等
- ReActTravelAgent: 旅游助手主类

使用示例：
```python
agent = ReActTravelAgent(config_path="config/llm_config.yaml")
result = await agent.process("北京三日游推荐")
```

================================================================================
"""

import json
import sys
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

# 添加父目录到路径以支持外部导入
# 这解决了模块间相对导入的问题，确保可以正确找到 core、config 等模块
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_SRC_DIR = os.path.dirname(CURRENT_DIR)
if AGENT_SRC_DIR not in sys.path:
    sys.path.insert(0, AGENT_SRC_DIR)

# 使用绝对导入替代相对导入，提高代码可读性和可维护性
from core.react_agent import ReActAgent, ToolInfo, Action, Thought, AgentState, ActionStatus
from core.style_config import style_manager, ReplyStyle, StyleConfig
from core.intent_recognizer import intent_recognizer, IntentRecognizer, IntentResult, IntentType, SentimentType
from core.decision_engine import decision_engine, DecisionEngine, Decision, DecisionType, ContextInfo
from config.config_manager import ConfigManager
from memory.manager import MemoryManager
from llm.client import LLMClient
from enum import Enum


class ChatMode(Enum):
    """对话模式枚举"""
    DIRECT = "direct"       # 直接调用 LLM
    REACT = "react"         # ReAct 推理模式
    PLAN = "plan"           # 规划后执行模式


def create_travel_tools(config_manager: ConfigManager) -> List[tuple]:
    """
    创建旅游助手工具列表

    该函数是旅游工具的工厂方法，负责创建所有可用的旅游相关工具。
    每个工具由两部分组成：
    1. ToolInfo: 工具的元数据描述（名称、参数、分类等）
    2. executor: 工具的实际执行函数

    工具列表包括：
    - search_cities: 根据条件搜索匹配的城市
    - query_attractions: 查询城市景点信息
    - generate_route: 生成旅游路线规划
    - calculate_budget: 计算旅游预算
    - get_city_info: 获取城市详细信息
    - llm_chat: LLM 对话回答
    - generate_city_recommendation: 生成城市推荐
    - generate_route_plan: 生成详细路线计划

    Args:
        config_manager: 配置管理器实例，用于获取城市数据等信息

    Returns:
        List[tuple]: 工具元组列表，每个元素为 (ToolInfo, executor_func)

    Examples:
        >>> tools = create_travel_tools(config_manager)
        >>> for tool_info, executor in tools:
        ...     agent.register_tool(tool_info, executor)
    """
    from environment.travel_data import TravelData

    tools = []

    # ========== 工具1: 城市搜索 ==========
    # 根据用户兴趣、预算和季节偏好搜索匹配的城市
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
                        'description': '用户兴趣标签列表，如 ["美食", "历史", "自然风光"]'
                    },
                    'budget_min': {'type': 'integer', 'description': '最低预算金额（元）'},
                    'budget_max': {'type': 'integer', 'description': '最高预算金额（元）'},
                    'season': {'type': 'string', 'description': '旅行季节，如 "春季", "夏季"'}
                }
            },
            required_params=[],  # 所有参数都是可选的
            category='travel',
            tags=['search', 'city', 'recommend']
        ),
        # 执行函数：调用内部函数处理搜索逻辑
        lambda interests=None, budget_min=None, budget_max=None, season=None:
            _search_cities(config_manager, interests, (budget_min, budget_max) if budget_min and budget_max else None, season)
    ))

    # ========== 工具2: 景点查询 ==========
    # 查询指定城市的景点信息
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
                'required': ['cities']  # cities 是必填参数
            },
            required_params=['cities'],
            category='travel',
            tags=['query', 'attraction', 'scenic']
        ),
        lambda cities: _query_attractions(config_manager, cities)
    ))

    # ========== 工具3: 路线生成 ==========
    # 为指定城市生成详细的旅游路线规划
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
                'required': ['city']  # city 是必填参数
            },
            required_params=['city'],
            category='travel',
            tags=['route', 'plan', 'schedule']
        ),
        lambda city, days=3: _generate_route(config_manager, city, days)
    ))

    # ========== 工具4: 预算计算 ==========
    # 计算指定城市和天数的旅游预算
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
                'required': ['city', 'days']  # city 和 days 都是必填参数
            },
            required_params=['city', 'days'],
            category='travel',
            tags=['budget', 'cost', 'expense']
        ),
        lambda city, days: _calculate_budget(config_manager, city, days)
    ))

    # ========== 工具5: 城市信息 ==========
    # 获取指定城市的详细信息
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

    # ========== 工具6: LLM 对话 ==========
    # 使用大语言模型进行对话回答
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

    # ========== 工具7: 城市推荐 ==========
    # 根据用户需求生成个性化城市推荐
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

    # ========== 工具8: 路线规划 ==========
    # 根据城市景点信息生成详细路线规划
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


# ==============================================================================
# 工具执行函数
# 这些函数是工具的具体实现，由 create_travel_tools 中定义的 lambda 调用
# ==============================================================================

def _search_cities(config_manager, interests: List[str] = None,
                   budget: tuple = None, season: str = None) -> Dict[str, Any]:
    """
    搜索匹配的城市

    根据用户的兴趣标签、预算范围和出行季节，从数据库中搜索匹配的城市。

    Args:
        config_manager: 配置管理器
        interests: 用户兴趣标签列表，如 ["美食", "历史文化"]
        budget: 预算范围元组 (最低, 最高)，如 (1000, 5000)
        season: 出行季节，如 "春季", "夏季"

    Returns:
        Dict: 包含搜索结果的字典，格式为 {'success': bool, 'cities': [...]}

    Examples:
        >>> result = _search_cities(None, ["美食"], (1000, 3000), "春季")
        >>> if result['success']:
        ...     for city in result['cities']:
        ...         print(city['name'])
    """
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.search_cities(interests, budget, season)


def _query_attractions(config_manager, cities: List[str]) -> Dict[str, Any]:
    """
    查询城市景点信息

    获取指定城市的景点列表和相关详细信息。

    Args:
        config_manager: 配置管理器
        cities: 要查询的城市名称列表

    Returns:
        Dict: 包含景点信息的字典，格式为 {'success': bool, 'data': {...}}

    Examples:
        >>> result = _query_attractions(None, ["北京", "上海"])
        >>> if result['success']:
        ...     for city, info in result['data'].items():
        ...         print(f"{city}: {len(info.get('attractions', []))} 个景点")
    """
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.query_attractions(cities)


def _generate_route(config_manager, city: str, days: int) -> Dict[str, Any]:
    """
    生成旅游路线规划

    根据城市信息和旅行天数，自动生成每日的景点游览路线。

    算法逻辑：
    1. 获取城市基本信息
    2. 提取城市景点列表
    3. 按天数分配景点，生成每日路线
    4. 计算预估费用

    Args:
        config_manager: 配置管理器
        city: 目标城市名称
        days: 旅行天数

    Returns:
        Dict: 路线规划结果，包含：
        - success: 是否成功
        - city: 城市名称
        - route_plan: 每日路线列表
        - total_cost_estimate: 费用估算

    Examples:
        >>> result = _generate_route(None, "北京", 3)
        >>> if result['success']:
        ...     for day in result['route_plan']:
        ...         print(f"第{day['day']}天: {day['schedule']}")
    """
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    result = env.get_city_info(city)
    if not result.get('success'):
        return result

    city_info = result.get('info', {})
    attractions = city_info.get('attractions', [])

    # 生成路线计划
    # 策略：每天分配一个主要景点，按顺序循环
    route_plan = []
    for i in range(min(days, len(attractions))):
        attr = attractions[i] if i < len(attractions) else {'name': '自由活动'}
        route_plan.append({
            'day': i + 1,
            'attractions': [attr['name']] if isinstance(attr, dict) else [attr],
            'schedule': f'游览{attr.get("name", "自由活动")}'
        })

    # 计算费用估算
    # 门票费用 + 每日平均花费
    return {
        'success': True,
        'city': city,
        'route_plan': route_plan,
        'total_cost_estimate': {
            'tickets': sum(a.get('ticket', 0) for a in attractions[:days]),
            'total': sum(a.get('ticket', 0) for a in attractions[:days]) +
                     city_info.get('avg_budget_per_day', 400) * days
        }
    }


def _calculate_budget(config_manager, city: str, days: int) -> Dict[str, Any]:
    """
    计算旅游预算

    根据城市物价水平和旅行天数，计算预计花费。

    Args:
        config_manager: 配置管理器
        city: 目标城市
        days: 旅行天数

    Returns:
        Dict: 预算计算结果，包含各项目的费用明细
    """
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.calculate_budget(city, days)


def _get_city_info(config_manager, city: str) -> Dict[str, Any]:
    """
    获取城市详细信息

    获取指定城市的完整信息，包括区域、标签、季节、预算、景点等。

    Args:
        config_manager: 配置管理器
        city: 城市名称

    Returns:
        Dict: 城市详细信息，包含：
        - success: 是否成功
        - city: 城市名称
        - info: 详细信息字典
    """
    from environment.travel_data import TravelData
    env = TravelData(config_manager)
    return env.get_city_info(city)


def _llm_chat(config_manager, query: str, context: str = "") -> Dict[str, Any]:
    """
    LLM 对话回答

    使用大语言模型生成回答，处理用户的一般性问题。

    Args:
        config_manager: 配置管理器
        query: 用户问题
        context: 对话上下文（可选）

    Returns:
        Dict: LLM 回答结果，格式为 {'success': bool, 'response': str}
    """
    llm_config = config_manager.get_default_model_config()
    llm_client = LLMClient(llm_config)

    messages = [{"role": "user", "content": query}]
    # 如果有上下文，添加到系统消息中
    if context:
        messages.insert(0, {"role": "system", "content": context})

    result = llm_client.chat(messages)

    # 标准化返回格式
    if isinstance(result, dict):
        if result.get('success') and 'content' in result:
            return {'success': True, 'response': result['content']}
        elif 'error' in result:
            return {'success': False, 'response': result['error']}
    return result


def _generate_recommendation(config_manager, user_query: str,
                             available_cities: List[str]) -> Dict[str, Any]:
    """
    生成城市推荐

    根据用户需求和可用城市列表，使用 LLM 生成个性化推荐。

    Args:
        config_manager: 配置管理器
        user_query: 用户原始需求描述
        available_cities: 可选城市列表

    Returns:
        Dict: 推荐结果，包含推荐的城市列表和理由
    """
    llm_config = config_manager.get_default_model_config()
    llm_client = LLMClient(llm_config)
    return llm_client.generate_travel_recommendation(user_query, "", available_cities)


def _generate_route_plan(config_manager, city: str, days: int,
                         preferences: str = "") -> Dict[str, Any]:
    """
    生成详细路线计划

    使用 LLM 根据城市景点信息生成详细的每日行程规划。

    Args:
        config_manager: 配置管理器
        city: 目标城市
        days: 旅行天数
        preferences: 用户偏好描述

    Returns:
        Dict: 详细路线计划
    """
    city_info = config_manager.get_city_info(city)
    if not city_info:
        return {'success': False, 'error': f'未找到城市: {city}'}

    attractions = city_info.get('attractions', [])
    llm_config = config_manager.get_default_model_config()
    llm_client = LLMClient(llm_config)
    return llm_client.generate_route_plan(city, days, attractions, preferences)


# ==============================================================================
# ReAct 旅游助手主类
# ==============================================================================

class ReActTravelAgent:
    """
    ReAct 旅游助手 Agent

    该类是旅游助手的核心入口，协调以下组件工作：
    1. ReActAgent: 负责推理和工具调用的循环
    2. MemoryManager: 负责对话历史的存储和管理
    3. LLMClient: 负责与大语言模型通信
    4. ConfigManager: 负责配置信息的读取

    处理流程：
    1. 接收用户输入
    2. 调用 ReActAgent 执行推理循环
    3. 收集工具执行结果
    4. 使用 LLM 生成最终回答
    5. 返回结构化结果

    Attributes:
        config_manager: 配置管理器实例
        memory_manager: 对话历史管理器
        llm_client: LLM 客户端实例
        react_agent: ReAct 智能体实例

    Examples:
        >>> agent = ReActTravelAgent(config_path="config/llm_config.yaml")
        >>> result = await agent.process("北京三日游推荐")
        >>> print(result["answer"])
    """

    def __init__(self, config_path: str = "config/llm_config.yaml",
                 model_id: Optional[str] = None,
                 max_steps: int = 10):
        """
        初始化旅游助手

        Args:
            config_path: 配置文件路径
            model_id: 使用的模型 ID，为 None 则使用默认模型
            max_steps: ReAct 循环的最大执行步骤数
        """
        # 初始化配置管理器
        self.config_manager = ConfigManager(config_path)

        # 初始化记忆管理器
        # max_working_memory 控制短期工作记忆的大小
        memory_config = self.config_manager.agent_config.get('max_working_memory', 10)
        self.memory_manager = MemoryManager(
            max_working_memory=memory_config
        )

        # 获取模型配置并初始化 LLM 客户端
        if model_id:
            llm_config = self.config_manager.get_model_config(model_id)
        else:
            llm_config = self.config_manager.get_default_model_config()

        self.llm_client = LLMClient(llm_config)

        # 传递 llm_client 给 ReActAgent，使其能使用 LLM 进行思考
        # 这是 ReAct 模式的关键：让智能体能够自主思考和规划
        self.react_agent = ReActAgent(
            name="TravelReActAgent",
            max_steps=max_steps,
            max_reasoning_depth=5,
            llm_client=self.llm_client
        )

        # 注册工具和回调
        self._register_tools()
        self._register_callbacks()

    def _register_tools(self) -> None:
        """
        注册旅游工具到 ReActAgent

        将 create_travel_tools 创建的所有工具注册到 ReActAgent 的工具注册表中。
        """
        tools = create_travel_tools(self.config_manager)
        for tool_info, executor in tools:
            self.react_agent.register_tool(tool_info, executor)

    def _register_callbacks(self) -> None:
        """
        注册事件回调函数

        用于将 ReActAgent 的思考和行动事件同步到记忆管理器中，
        以便维护完整的对话历史。
        """
        def on_thought(thought: Thought):
            """思考事件回调：将思考内容添加到记忆"""
            self.memory_manager.add_message('assistant', f"[思考] {thought.content}")

        def on_action(action: Action):
            """行动事件回调：根据状态记录不同消息"""
            if action.status == ActionStatus.RUNNING:
                self.memory_manager.add_message('assistant', f"[行动] 执行工具: {action.tool_name}")
            elif action.status == ActionStatus.SUCCESS:
                self.memory_manager.add_message('assistant', f"[完成] {action.tool_name}")
            elif action.status == ActionStatus.FAILED:
                self.memory_manager.add_message('assistant', f"[失败] {action.tool_name}: {action.error}")

        self.react_agent.add_thought_callback(on_thought)
        self.react_agent.add_action_callback(on_action)

    async def process(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户输入（非流式版本）

        这是主要的处理入口，接收用户输入，执行完整的 ReAct 循环，
        并返回结构化的处理结果。

        Args:
            user_input: 用户的输入文本

        Returns:
            Dict: 处理结果，包含：
            - success: 是否成功
            - answer: 生成的回答
            - reasoning: 推理过程信息
            - history: 执行历史

        Examples:
            >>> result = await agent.process("云南旅游推荐")
            >>> if result["success"]:
            ...     print(result["answer"])
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"[Agent] 开始处理用户输入: {user_input[:50]}...")

        try:
            # 1. 将用户输入添加到对话历史
            self.memory_manager.add_message('user', user_input)

            # 2. 构建上下文信息
            context = {
                'user_query': user_input,
                'user_preference': self.memory_manager.get_user_preference()
            }

            # 3. 执行 ReAct 推理循环
            result = await self.react_agent.run(user_input, context)
            logger.info(f"[Agent] ReAct 执行完成, success={result.get('success')}, steps={len(result.get('history', []))}")

            if result.get('success'):
                # 4. 提取结果
                history = result.get('history', [])
                reasoning_text = self._build_reasoning_text(history)
                answer = self._extract_answer(history)
                logger.info(f"[Agent] 提取到答案: {answer[:100]}...")

                # 5. 添加助手回答到历史
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
        """
        同步处理用户输入

        用于 gRPC 调用等需要同步接口的场景。
        内部通过 asyncio.run() 包装异步的 process 方法。

        Args:
            user_input: 用户输入文本

        Returns:
            Dict: 处理结果，同 process 方法的返回格式
        """
        import asyncio
        return asyncio.run(self.process(user_input))

    async def process_stream(self, user_input: str, answer_callback=None, done_callback=None, thinking_callback=None):
        """
        流式处理用户输入

        使用真正的 token 级别流式输出，提供更好的用户体验。
        特点：
        - 实时输出：每个 token 生成后立即通过回调发送
        - 真正的流式：使用 LLM 客户端的 chat_stream 方法
        - 回调机制：通过回调函数实现数据推送

        Args:
            user_input: 用户输入
            answer_callback: 回答内容回调函数，接收单个 token (str)
            done_callback: 完成回调函数，接收最终结果 (Dict)
            thinking_callback: 思考内容回调函数，接收思考内容 (str) 和耗时 (float)

        Returns:
            Dict: 最终处理结果

        Examples:
            >>> async def on_token(token):
            ...     print(token, end="", flush=True)
            >>> async def on_done(result):
            ...     print("\\n完成!")
            >>> await agent.process_stream("北京旅游", answer_callback=on_token, done_callback=on_done)
        """
        import logging
        import time as time_module
        logger = logging.getLogger(__name__)

        logger.info(f"[Agent] 开始流式处理用户输入: {user_input[:50]}...")
        start_time = time_module.time()

        try:
            # 添加用户输入到历史
            self.memory_manager.add_message('user', user_input)

            context = {
                'user_query': user_input,
                'user_preference': self.memory_manager.get_user_preference()
            }

            # 先运行 ReAct agent 获取思考历史
            # 设置思考流式回调
            if hasattr(self.react_agent, 'set_think_stream_callback') and thinking_callback:
                self.react_agent.set_think_stream_callback(thinking_callback)

            result = await self.react_agent.run(user_input, context)
            logger.info(f"[Agent] ReAct 执行完成, success={result.get('success')}, steps={len(result.get('history', []))}")

            if result.get('success'):
                history = result.get('history', [])
                reasoning_text = self._build_reasoning_text(history)
                answer = self._extract_answer(history)

                self.memory_manager.add_message('assistant', answer)

                # 构建 LLM 消息
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

                    # 遍历流式响应
                    for token in self.llm_client.chat_stream(messages, temperature=0.7):
                        token_count += 1
                        accumulated_answer += token

                        # 立即发送每个 token
                        if answer_callback:
                            answer_callback(token)

                        # 短暂延迟，确保前端有足够时间处理
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
        """
        将文本拆分成小块用于流式输出

        当 LLM 不支持流式输出时，使用此方法进行模拟流式。
        拆分策略：
        1. 优先在标点符号处断开
        2. 控制每块最大长度
        3. 确保中英文都能正确处理

        Args:
            text: 输入文本
            chunk_size: 每个块的最大字符数（中文字符），默认3个

        Returns:
            文本块列表

        Examples:
            >>> chunks = agent._split_into_chunks("你好世界！再见。")
            >>> print(chunks)  # ['你好', '世界', '！', '再见', '。']
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
        """
        构建推理过程文本

        将 ReAct 执行历史格式化为可读的推理过程描述。

        Args:
            history: ReAct 执行历史列表

        Returns:
            str: 格式化后的推理过程文本（Markdown 格式）
        """
        if not history:
            return "<thinking>\n[Timestamp: {timestamp}]\n\n[Intent Analysis]\nNo reasoning history available.\n\n[Context Evaluation]\nNo context available.\n\n[Response Planning]\nUnable to generate response.\n\n[Constraint Check]\nNo constraints checked.\n</thinking>".format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

        intent_analysis = []
        context_evaluation = []
        response_planning = []
        constraint_check = []

        # 遍历历史，按类型分类
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

        # 构建各部分内容
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
        """
        提取使用的工具列表

        从执行历史中收集所有被调用的工具名称。

        Args:
            history: 执行历史列表

        Returns:
            List[str]: 使用的工具名称列表（去重）
        """
        tools = []
        for step in history:
            action = step.get('action', {})
            tool_name = action.get('tool_name', '')
            if tool_name and tool_name not in tools and tool_name != 'none':
                tools.append(tool_name)
        return tools

    def _extract_answer(self, history: List[Dict]) -> str:
        """
        提取最终回答

        从执行历史中提取最终的回答内容。
        策略：
        1. 收集所有成功的工具执行结果
        2. 使用 LLM 生成活泼、结构化的回答

        Args:
            history: 执行历史列表

        Returns:
            str: 最终回答文本
        """
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

        # 如果有工具执行结果，使用 LLM 生成活泼的回答
        if has_successful_tools:
            return self._generate_answer(history)

        # 否则返回默认消息
        return '让我来帮你规划这次旅行吧！🎉'

    def _format_attractions_response(self, tool_result: Dict) -> str:
        """
        格式化景点响应数据

        将景点查询结果格式化为可读的文本。

        Args:
            tool_result: 工具返回的原始结果

        Returns:
            str: 格式化后的景点描述文本
        """
        lines = []

        # 兼容新旧两种数据格式
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

    def _generate_answer(self, history: List[Dict], intent: IntentResult = None) -> str:
        """
        使用 LLM 生成最终回答

        根据工具执行结果和用户意图，生成结构化、风格化的回答。

        Args:
            history: 执行历史列表
            intent: 意图识别结果（可选）

        Returns:
            str: 生成的回答文本
        """
        try:
            tool_results = []
            for step in history:
                action = step.get('action', {})
                if action.get('status') == 'SUCCESS' and action.get('result'):
                    tool_results.append({
                        'tool': action.get('tool_name', ''),
                        'result': action.get('result', {})
                    })

            # 获取风格配置
            if intent:
                # 安全获取 sentiment
                sentiment_value = intent.sentiment.value if hasattr(intent.sentiment, 'value') else str(intent.sentiment) if intent.sentiment else 'neutral'
                sentiment = SentimentType(sentiment_value) if sentiment_value in [e.value for e in SentimentType] else SentimentType.NEUTRAL
                style = style_manager.get_style_for_task(intent.intent.value, sentiment)
            else:
                style = style_manager.get_style_for_task("general_chat", SentimentType.NEUTRAL)

            # 根据风格调整温度
            temperature = style.temperature

            # 构建风格化的系统提示词
            system_prompt = self._build_style_prompt(style, intent)

            user_prompt = f"""我想要规划一次旅行，这是我的查询结果：
{json.dumps(tool_results, ensure_ascii=False, indent=2)}

请只输出JSON格式的结果，不要有任何其他内容。"""

            result = self.llm_client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], temperature=temperature)

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

    def _build_style_prompt(self, style: StyleConfig, intent: IntentResult = None) -> str:
        """
        根据风格配置构建系统提示词

        Args:
            style: 风格配置
            intent: 意图识别结果

        Returns:
            str: 系统提示词
        """
        # 根据风格选择问候语和角色设定
        role_greetings = {
            "热情活泼": "你是一个超级热情、活泼的AI旅游小伙伴！",
            "温暖亲切": "你是一个贴心、温暖的AI旅游助手！",
            "专业正式": "你是一位专业、可靠的AI旅游顾问。",
            "俏皮可爱": "你是一个可爱又热情的旅行小达人！",
            "简洁明了": "你是一个简洁高效的AI旅游助手。"
        }

        role = role_greetings.get(style.name, "你是一个AI旅游助手")

        # 根据风格选择语气关键词
        tone_keywords = {
            "热情活泼": "使用轻松活泼的语气，多用口语化表达。适当使用emoji表情符号增添趣味。用'小伙伴'、'亲'、'哇塞'等亲切称呼。",
            "温暖亲切": "使用温柔亲切的语气，像朋友一样聊天。适当表达关心和理解。让对话氛围轻松愉快。",
            "专业正式": "使用专业、清晰的语言。提供准确、有用的信息。保持礼貌和专业的态度。",
            "俏皮可爱": "使用俏皮可爱的语气，可以适当用一些有趣的网络用语。多多使用可爱的emoji。",
            "简洁明了": "使用简洁、直接的语言。不说废话，直奔主题。高效传递信息。"
        }

        tone = tone_keywords.get(style.name, "使用友好的语气")

        # 构建提示词
        prompt = f"""{role}

【任务】
根据工具查询结果，生成结构化的旅游推荐信息。

【说话风格】
- {tone}
- 适当加入旅行的氛围感描写
- 重点信息用**加粗**标记

【输出格式】
必须输出JSON格式，不要包含任何Markdown格式！JSON结构如下：
{{
    "opening": "开场白，使用轻松活泼的语气",
    "cities": [
        {{
            "name": "城市名",
            "emoji": "城市emoji",
            "days": "推荐天数",
            "budget": "预算描述",
            "season": "最佳旅行季节",
            "attractions": [
                {{"name": "景点名", "type": "景点类型", "ticket": "门票价格", "description": "简短描述"}}
            ]
        }}
    ],
    "tips": "旅行小贴士"
}}

【重要】
- 只输出JSON，不要输出任何Markdown语法
- 确保JSON格式正确，可以被json.loads()解析
- 每个城市至少推荐2-4个景点"""

        return prompt

    def _parse_json_response(self, content: str) -> dict:
        """
        解析 LLM 返回的 JSON 响应

        LLM 有时会在 JSON 外面包裹 markdown 代码块或添加额外文本，
        此函数负责提取纯 JSON 内容。

        Args:
            content: LLM 返回的原始内容

        Returns:
            dict: 解析后的 JSON 对象，解析失败返回 None
        """
        import re
        try:
            # 首先尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 代码块
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
        """
        格式化旅游响应

        将 LLM 生成的 JSON 数据格式化为规范的 Markdown 文本。

        Args:
            data: 结构化数据字典

        Returns:
            str: 格式化后的 Markdown 文本
        """
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

            # 城市之间加空行
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
        """
        获取对话历史

        Returns:
            list: 对话消息列表
        """
        return self.memory_manager.get_conversation_history()

    def clear_conversation(self) -> None:
        """
        清除对话历史

        清空记忆管理器和 ReActAgent 的状态，准备接受新会话。
        """
        self.memory_manager.clear_conversation()
        self.react_agent.reset()

    # ==========================================================================
    # 多模式对话处理
    # ==========================================================================

    async def process_with_mode(
        self,
        user_input: str,
        mode: ChatMode = ChatMode.REACT,
        answer_callback=None,
        done_callback=None,
        thinking_callback=None
    ) -> Dict[str, Any]:
        """
        根据指定模式处理用户输入

        支持三种对话模式：
        1. Direct Mode: 直接调用 LLM，快速响应简单问题
        2. ReAct Mode: 推理与行动交替，适合需要工具调用的场景
        3. Plan Mode: 先规划后执行，适合复杂任务

        Args:
            user_input: 用户输入
            mode: 对话模式
            answer_callback: 答案回调
            done_callback: 完成回调
            thinking_callback: 思考回调

        Returns:
            Dict: 处理结果
        """
        import logging
        import time as time_module
        logger = logging.getLogger(__name__)

        logger.info(f"[Agent] 开始处理 (mode={mode.value}): {user_input[:50]}...")
        start_time = time_module.time()

        # 添加用户输入到历史
        self.memory_manager.add_message('user', user_input)

        context = {
            'user_query': user_input,
            'user_preference': self.memory_manager.get_user_preference()
        }

        # 根据模式处理
        if mode == ChatMode.DIRECT:
            result = await self._process_direct_mode(user_input, answer_callback, done_callback, thinking_callback)
        elif mode == ChatMode.PLAN:
            result = await self._process_plan_mode(user_input, context, answer_callback, done_callback, thinking_callback)
        else:
            # 默认使用 ReAct 模式
            result = await self._process_react_mode(user_input, context, answer_callback, done_callback, thinking_callback)

        elapsed = time_module.time() - start_time
        logger.info(f"[Agent] 处理完成 (mode={mode.value}), 耗时: {elapsed:.2f}秒")

        return result

    async def _process_direct_mode(
        self,
        user_input: str,
        answer_callback=None,
        done_callback=None,
        thinking_callback=None
    ) -> Dict[str, Any]:
        """
        直接调用 LLM 模式

        特点：
        - 快速响应，无工具调用
        - 适合简单对话和一般问题
        - 不展示思考过程
        """
        import logging
        import asyncio
        logger = logging.getLogger(__name__)

        # 发送思考开始
        if thinking_callback:
            thinking_callback("【直接模式】直接生成回答...\n\n", 0.0)

        # 构建消息
        messages = [
            {"role": "system", "content": "你是一个专业的旅游助手。"},
            {"role": "user", "content": user_input}
        ]

        # 流式生成回答
        if hasattr(self.llm_client, 'chat_stream') and answer_callback:
            accumulated_answer = ""
            token_count = 0

            for token in self.llm_client.chat_stream(messages, temperature=0.7):
                token_count += 1
                accumulated_answer += token
                answer_callback(token)
                await asyncio.sleep(0.01)

            answer = accumulated_answer
            logger.info(f"[Agent] 直接模式完成, {token_count} tokens")
        else:
            # 非流式
            result = self.llm_client.chat(messages, temperature=0.7)
            answer = result.get('content', '抱歉，我没有理解您的意思。')

        # 添加助手回答到历史
        self.memory_manager.add_message('assistant', answer)

        result = {
            "success": True,
            "answer": answer,
            "mode": "direct",
            "reasoning": {
                "text": "<thinking>\n[Direct Mode]\n直接调用 LLM 生成回答\n</thinking>",
                "total_steps": 0,
                "tools_used": []
            },
            "history": []
        }

        # 调用完成回调
        if done_callback:
            done_callback(result)

        return result

    async def _process_plan_mode(
        self,
        user_input: str,
        context: Dict,
        answer_callback=None,
        done_callback=None,
        thinking_callback=None
    ) -> Dict[str, Any]:
        """
        规划后执行模式

        特点：
        1. 先使用 LLM 生成完整的执行计划
        2. 再逐步执行计划中的步骤
        3. 最后生成最终回答

        适合复杂任务，如多日行程规划
        """
        import logging
        import asyncio
        import json as json_util
        logger = logging.getLogger(__name__)

        step_times = []

        # Step 1: 生成执行计划
        if thinking_callback:
            thinking_callback("【规划模式】正在生成执行计划...\n\n", 0.0)

        plan_start = asyncio.get_event_loop()
        plan_prompt = f"""用户请求: {user_input}

请制定一个详细的执行计划，以 JSON 格式返回：
{{
    "steps": [
        {{
            "step": 1,
            "action": "工具名称",
            "params": {{"参数": "值"}},
            "description": "步骤描述"
        }}
    ],
    "estimated_time": "预计总时间"
}}"

只返回 JSON，不要其他内容。"""

        plan_result = self.llm_client.chat([
            {"role": "system", "content": "你是一个专业的旅游规划助手。"},
            {"role": "user", "content": plan_prompt}
        ], temperature=0.3)

        if not plan_result.get('success'):
            return {
                "success": False,
                "error": "规划生成失败",
                "mode": "plan"
            }

        plan_content = plan_result.get('content', '{}')
        try:
            # 尝试直接解析 JSON
            plan_data = json_util.loads(plan_content)
            logger.info(f"[Plan] 直接解析成功: {plan_data}")
        except json_util.JSONDecodeError:
            # 如果解析失败，尝试提取 JSON
            logger.warning(f"[Plan] 直接解析失败，尝试提取: {plan_content[:200]}...")
            plan_data = self._extract_json_from_plan(plan_content)
            logger.info(f"[Plan] 提取结果: {plan_data}")

        steps = plan_data.get('steps', [])
        if not steps:
            logger.warning(f"[Plan] steps 为空，原始内容: {plan_content[:500]}...")
            # 尝试更宽松的解析
            if 'steps' in plan_content:
                import re
                # 匹配整个 steps 数组中的每个步骤对象
                step_pattern = re.compile(r'\{\s*"action"\s*:\s*"([^"]+)"\s*,\s*"params"\s*:\s*(\{[^}]*\})\s*,\s*"description"\s*:\s*"([^"]+)"\s*\}')
                step_matches = step_pattern.findall(plan_content)

                if step_matches:
                    logger.info(f"[Plan] 找到步骤: {step_matches}")
                    steps = []
                    for action, params_str, description in step_matches:
                        try:
                            params = json_util.loads(params_str) if params_str else {}
                        except:
                            params = {}
                        steps.append({
                            "action": action,
                            "params": params,
                            "description": description
                        })
                else:
                    # 尝试只提取 action
                    step_items = re.findall(r'"action"\s*:\s*"([^"]+)"', plan_content)
                    if step_items:
                        logger.info(f"[Plan] 只找到 action: {step_items}")
                        steps = [{"action": s, "params": {}, "description": s} for i, s in enumerate(step_items)]

        step_elapsed = (asyncio.get_event_loop().time() - plan_start.time()) if hasattr(plan_start, 'time') else 0
        step_times.append(("规划", step_elapsed))

        if thinking_callback:
            thinking_callback(f"【规划模式】计划生成完成，共 {len(steps)} 个步骤\n\n", step_elapsed)

        # Step 2: 执行计划
        history = []
        reasoning_text = "[规划模式执行]\n\n"

        for i, step in enumerate(steps):
            step_num = i + 1
            action_name = step.get('action', '')
            params = step.get('params', {})
            description = step.get('description', '')

            step_start = asyncio.get_event_loop()

            if thinking_callback:
                thinking_callback(f"【规划模式】执行步骤 {step_num}/{len(steps)}: {description}\n\n", 0.0)

            reasoning_text += f"步骤 {step_num}: {description}\n"

            # 查找并执行工具
            result = {'success': False}
            if action_name and action_name != 'none':
                tool = self.react_agent.tool_registry.get_tool(action_name)
                if tool:
                    try:
                        result = await tool.execute(**params) if hasattr(tool, 'execute') else tool(params)
                        reasoning_text += f"  - 执行: {action_name}\n"
                        reasoning_text += f"  - 结果: {str(result)[:100]}...\n"
                    except Exception as e:
                        reasoning_text += f"  - 错误: {str(e)}\n"
                        result = {'success': False, 'error': str(e)}

            step_elapsed = (asyncio.get_event_loop().time() - step_start.time()) if hasattr(step_start, 'time') else 0
            step_times.append((action_name, step_elapsed))

            history.append({
                'step': step_num,
                'action': action_name,
                'params': params,
                'result': result,
                'description': description
            })

        # Step 3: 生成最终回答
        if thinking_callback:
            thinking_callback("【规划模式】正在生成最终回答...\n\n", 0.0)

        # 收集工具执行结果
        tool_results = [h.get('result', {}) for h in history if h.get('result', {}).get('success')]

        if tool_results:
            answer = self._generate_answer_from_results(user_input, tool_results)
        else:
            # 直接使用 LLM 生成回答
            final_prompt = f"""用户请求: {user_input}

执行计划已完成。请根据以下信息生成最终回答：
{json_util.dumps(history, ensure_ascii=False, indent=2)}

请提供详细、结构化的回答。"""
            final_result = self.llm_client.chat([
                {"role": "system", "content": "你是一个专业的旅游助手。"},
                {"role": "user", "content": final_prompt}
            ], temperature=0.7)
            answer = final_result.get('content', '抱歉，处理过程中出现问题。')

        # 通过 answer_callback 发送最终回答给前端
        if answer_callback:
            answer_callback(answer)

        self.memory_manager.add_message('assistant', answer)

        # 构建推理文本
        reasoning_text += "\n执行完成。"
        full_reasoning = f"""<thinking>
[规划模式]
{reasoning_text}

[步骤耗时]
{chr(10).join([f"- {name}: {t:.2f}秒" for name, t in step_times])}
</thinking>"""

        result = {
            "success": True,
            "answer": answer,
            "mode": "plan",
            "reasoning": {
                "text": full_reasoning,
                "total_steps": len(steps),
                "tools_used": [h.get('action') for h in history if h.get('action')]
            },
            "history": history,
            "plan": steps
        }

        # 调用完成回调
        if done_callback:
            done_callback(result)

        return result

    def _extract_json_from_plan(self, content: str) -> Dict:
        """从计划文本中提取 JSON"""
        import re
        import json as json_util
        json_match = re.search(r'\{[^{}]*\}', content)
        if json_match:
            try:
                return json_util.loads(json_match.group())
            except json_util.JSONDecodeError:
                pass
        return {}

    def _generate_answer_from_results(self, user_input: str, results: List[Dict]) -> str:
        """根据工具执行结果生成回答"""
        import json
        prompt = f"""用户请求: {user_input}

工具执行结果:
{json.dumps(results, ensure_ascii=False, indent=2)}

请根据以上结果，生成一个结构清晰、内容丰富的旅游回答。"""
        result = self.llm_client.chat([
            {"role": "system", "content": "你是一个专业的旅游助手。"},
            {"role": "user", "content": prompt}
        ], temperature=0.7)
        return result.get('content', '处理完成')

    async def _process_react_mode(
        self,
        user_input: str,
        context: Dict,
        answer_callback=None,
        done_callback=None,
        thinking_callback=None
    ) -> Dict[str, Any]:
        """
        ReAct 推理模式

        特点：
        - 思考 → 行动 → 观察 → 评估循环
        - 支持动态工具调用
        - 展示完整的推理过程
        """
        import logging
        import asyncio
        import time as time_module
        logger = logging.getLogger(__name__)

        # 设置思考流式回调
        if hasattr(self.react_agent, 'set_think_stream_callback') and thinking_callback:
            self.react_agent.set_think_stream_callback(thinking_callback)

        # 执行 ReAct 循环
        result = await self.react_agent.run(user_input, context)
        logger.info(f"[Agent] ReAct 执行完成, success={result.get('success')}")

        if result.get('success'):
            history = result.get('history', [])
            reasoning_text = self._build_reasoning_text(history)
            answer = self._extract_answer(history)

            self.memory_manager.add_message('assistant', answer)

            # 构建 LLM 消息生成最终回答
            system_prompt = "你是一个专业的旅游助手。请根据用户的问题，提供详细、准确的旅游建议和规划。"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            # 流式生成最终回答
            if hasattr(self.llm_client, 'chat_stream') and answer_callback:
                token_count = 0
                accumulated_answer = ""

                for token in self.llm_client.chat_stream(messages, temperature=0.7):
                    token_count += 1
                    accumulated_answer += token
                    answer_callback(token)
                    await asyncio.sleep(0.01)

                answer = accumulated_answer
                logger.info(f"[Agent] ReAct 流式生成完成, {token_count} tokens")

            return {
                "success": True,
                "answer": answer,
                "mode": "react",
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
                "mode": "react",
                "reasoning": None,
                "history": result.get('history', [])
            }
