"""
上下文决策引擎

提供基于上下文的智能决策功能，支持多轮对话和信息补全。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import json
import logging

from .intent_recognizer import IntentResult, IntentType, SentimentType
from .style_config import style_manager, ReplyStyle

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """决策类型"""
    FINAL_ANSWER = "final_answer"         # 直接给出答案
    CONTINUE = "continue"                 # 继续执行下一步
    ASK_CLARIFICATION = "ask_fallback"    # 询问澄清
    REFLECT = "reflect"                   # 反思/重试
    SKIP = "skip"                         # 跳过当前步骤
    ERROR = "error"                       # 错误处理


@dataclass
class Decision:
    """决策结果"""
    type: DecisionType
    content: str = ""                     # 决策内容（回复文本）
    next_actions: List[Dict] = field(default_factory=list)  # 下一步动作
    confidence: float = 0.0
    reason: str = ""
    style: Optional[str] = None           # 使用的风格
    data: Dict = field(default_factory=dict)  # 附加数据

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "next_actions": self.next_actions,
            "confidence": self.confidence,
            "reason": self.reason,
            "style": self.style,
            "data": self.data
        }


@dataclass
class ContextInfo:
    """上下文信息"""
    history: List[Dict] = field(default_factory=list)  # 对话历史
    current_step: int = 0
    max_steps: int = 5
    session_data: Dict = field(default_factory=dict)   # 会话数据
    user_profile: Dict = field(default_factory=dict)   # 用户画像


class DecisionEngine:
    """决策引擎"""

    def __init__(self):
        self._missing_entity_handlers: Dict[str, Callable] = {}
        self._response_generators: Dict[IntentType, Callable] = {}
        self._clarification_templates: Dict[str, str] = {}
        self._setup_default_templates()

    def _setup_default_templates(self):
        """设置默认的澄清模板"""
        self._clarification_templates = {
            "cities": "为了给你更精准的推荐，能告诉我你想去哪个城市或者地区吗？🏙️",
            "budget": "你的预算是多少呢？比如 2000元、5000左右？💰",
            "days": "你大概想玩几天呢？🗓️",
            "season": "你计划什么时间去旅行呢？比如 1月、春季、暑假？🌸",
            "people": "有几个人一起去呢？👨‍👩‍👧‍👦",
            "preferences": "你有什么特别的偏好吗？比如自然风光、历史文化、美食探索？🎯",
            "default": "为了更好地帮助你，能详细说说你的需求吗？😊"
        }

    def make_decision(self, intent: IntentResult, context: ContextInfo,
                      tool_results: List[Dict] = None) -> Decision:
        """
        根据意图和上下文做出决策

        Args:
            intent: 意图识别结果
            context: 上下文信息
            tool_results: 工具执行结果

        Returns:
            Decision: 决策结果
        """
        # 1. 检查是否需要澄清
        if intent.needs_more_info():
            return self._handle_missing_info(intent)

        # 2. 检查是否可以给出最终答案
        if tool_results and len(tool_results) > 0:
            if self._can_finalize(intent, tool_results, context):
                return self._generate_final_answer(intent, tool_results, context)

        # 3. 继续执行下一步
        if context.current_step < context.max_steps:
            return self._plan_next_action(intent, context, tool_results)

        # 4. 达到最大步数，强制给出答案
        return self._generate_final_answer(intent, tool_results or [], context, force=True)

    def _handle_missing_info(self, intent: IntentResult) -> Decision:
        """处理缺失信息"""
        missing = intent.missing_info

        # 选择最重要的缺失信息
        priority_order = ["cities", "days", "budget", "season", "people", "preferences"]
        key_to_ask = None

        for key in priority_order:
            if key in missing:
                key_to_ask = key
                break

        if key_to_ask is None:
            key_to_ask = "default"

        # 获取澄清模板
        template = self._clarification_templates.get(
            key_to_ask,
            self._clarification_templates["default"]
        )

        # 根据意图类型调整模板
        if intent.intent == IntentType.BUDGET_QUERY:
            template = "能告诉我你的大概预算是多少吗？这样我可以帮你找到更合适的方案！💰"
        elif intent.intent == IntentType.CITY_RECOMMENDATION:
            template = "你想去哪个城市或者地区玩呢？🏙️"

        # 根据用户情感选择风格
        style_key = {
            SentimentType.URGENT: ReplyStyle.CONCISE,
            SentimentType.EXCITED: ReplyStyle.PLAYFUL,
            SentimentType.HESITANT: ReplyStyle.WARM,
        }.get(intent.sentiment, ReplyStyle.WARM)

        style = style_manager.get_style_for_task(
            intent.intent.value,
            SentimentType(intent.sentiment.value)
        )

        return Decision(
            type=DecisionType.ASK_CLARIFICATION,
            content=template,
            confidence=0.9,
            reason=f"需要补充信息: {missing}",
            style=style.name,
            data={"missing_keys": missing, "ask_key": key_to_ask}
        )

    def _can_finalize(self, intent: IntentResult, tool_results: List[Dict],
                      context: ContextInfo) -> bool:
        """检查是否可以直接给出最终答案"""
        # 1. 如果是简单查询且有结果
        if intent.intent in [
            IntentType.ATTRACTION_QUERY,
            IntentType.BUDGET_QUERY,
            IntentType.SEASON_QUERY
        ]:
            return len(tool_results) >= 1

        # 2. 如果有足够的结果
        if intent.intent in [
            IntentType.CITY_RECOMMENDATION,
            IntentType.FOOD_RECOMMENDATION
        ]:
            return len(tool_results) >= 2

        # 3. 如果达到最小结果数量
        min_results = {
            IntentType.TRAVEL_PLANNING: 3,
            IntentType.ROUTE_PLANNING: 2,
            IntentType.ITINERARY_QUERY: 1,
        }.get(intent.intent, 1)

        return len(tool_results) >= min_results

    def _generate_final_answer(self, intent: IntentResult,
                                tool_results: List[Dict],
                                context: ContextInfo,
                                force: bool = False) -> Decision:
        """生成最终答案"""
        # 选择风格
        style = style_manager.get_style_for_task(
            intent.intent.value,
            SentimentType(intent.sentiment.value)
        )

        # 根据意图类型生成内容
        content_generator = self._response_generators.get(
            intent.intent,
            self._default_content_generator
        )

        try:
            content = content_generator(intent, tool_results, context)
            # 应用风格
            if style.use_fluent_language:
                content = style_manager.apply_style_to_response(
                    content, style,
                    {"purpose": self._get_purpose(intent)}
                )

            return Decision(
                type=DecisionType.FINAL_ANSWER,
                content=content,
                confidence=0.85 if not force else 0.6,
                reason="基于已有信息生成答案",
                style=style.name,
                data={"intent": intent.to_dict(), "tool_results_count": len(tool_results)}
            )

        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            return Decision(
                type=DecisionType.ERROR,
                content="抱歉，我遇到了一些问题，请稍后再试。😔",
                confidence=0.0,
                reason=f"生成错误: {str(e)}"
            )

    def _default_content_generator(self, intent: IntentResult,
                                    tool_results: List[Dict],
                                    context: ContextInfo) -> str:
        """默认内容生成器"""
        parts = []

        # 开场白
        if intent.intent == IntentType.CITY_RECOMMENDATION:
            parts.append("根据你的需求，我为你推荐以下城市！🌟")
        elif intent.intent == IntentType.ATTRACTION_QUERY:
            parts.append("找到了这些好玩的景点！🎉")
        elif intent.intent == IntentType.FOOD_RECOMMENDATION:
            parts.append("这些美食千万不要错过！🍜")
        else:
            parts.append("帮你整理好了！📋")

        # 处理工具结果
        for result in tool_results:
            if isinstance(result, dict):
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
                parts.append(result_str)
            else:
                parts.append(str(result))

        # 结束语
        parts.append("\n祝你的旅行愉快！✈️")

        return "\n".join(parts)

    def _plan_next_action(self, intent: IntentResult, context: ContextInfo,
                          tool_results: List[Dict] = None) -> Decision:
        """规划下一步动作"""
        # 根据意图类型决定下一步
        action_plan = self._get_action_plan(intent, context)

        return Decision(
            type=DecisionType.CONTINUE,
            content="",
            next_actions=action_plan,
            confidence=0.8,
            reason=f"第 {context.current_step + 1} 步: {action_plan[0].get('description', '执行搜索')}" if action_plan else "完成",
            data={"step": context.current_step + 1}
        )

    def _get_action_plan(self, intent: IntentResult,
                          context: ContextInfo) -> List[Dict]:
        """获取动作计划"""
        actions = []
        intent_entities = intent.entities

        if intent.intent == IntentType.CITY_RECOMMENDATION:
            # 需要搜索城市
            actions.append({
                "action": "search_cities",
                "params": {
                    "region": intent_entities.get("cities", ["全国"])[0] if intent_entities.get("cities") else None,
                    "season": intent_entities.get("season", [None])[0]
                },
                "description": "搜索符合条件的城市"
            })

        elif intent.intent == IntentType.ATTRACTION_QUERY:
            cities = intent_entities.get("cities", [])
            if cities:
                for city in cities[:2]:  # 限制数量
                    actions.append({
                        "action": "city_attractions",
                        "params": {"city": city},
                        "description": f"搜索 {city} 的景点"
                    })
            else:
                actions.append({
                    "action": "recommend_attractions",
                    "params": {},
                    "description": "推荐热门景点"
                })

        elif intent.intent == IntentType.FOOD_RECOMMENDATION:
            cities = intent_entities.get("cities", [])
            if cities:
                actions.append({
                    "action": "city_food",
                    "params": {"city": cities[0]},
                    "description": f"搜索 {cities[0]} 的美食"
                })
            else:
                actions.append({
                    "action": "popular_food",
                    "params": {},
                    "description": "推荐热门美食"
                })

        elif intent.intent == IntentType.BUDGET_QUERY:
            actions.append({
                "action": "budget_estimate",
                "params": {
                    "destination": intent_entities.get("cities", [None])[0],
                    "days": intent_entities.get("days", [None])[0],
                    "people": intent_entities.get("people", [None])[0]
                },
                "description": "估算旅行预算"
            })

        elif intent.intent == IntentType.TRAVEL_PLANNING:
            # 综合规划
            actions.append({
                "action": "search_cities",
                "params": {"criteria": intent_entities},
                "description": "搜索目的地城市"
            })
            actions.append({
                "action": "city_attractions",
                "params": {"city": intent_entities.get("cities", [None])[0]},
                "description": "获取城市景点信息"
            })
            actions.append({
                "action": "plan_route",
                "params": {
                    "days": intent_entities.get("days", [3])[0],
                    "interests": intent_entities.get("preferences", [])
                },
                "description": "规划行程路线"
            })

        else:
            # 默认使用通用搜索
            actions.append({
                "action": "general_search",
                "params": {"query": intent.original_query},
                "description": "执行搜索"
            })

        return actions

    def _get_purpose(self, intent: IntentResult) -> str:
        """获取回复目的"""
        purpose_map = {
            IntentType.CITY_RECOMMENDATION: "帮你找到最适合的目的地",
            IntentType.ATTRACTION_QUERY: "为你推荐好玩的景点",
            IntentType.FOOD_RECOMMENDATION: "带你品尝地道美食",
            IntentType.BUDGET_QUERY: "帮你规划预算",
            IntentType.ROUTE_PLANNING: "为你设计完美路线",
            IntentType.TRAVEL_PLANNING: "帮你规划整个旅程",
        }
        return purpose_map.get(intent.intent, "帮你解答问题")

    def register_content_generator(self, intent_type: IntentType,
                                    generator: Callable):
        """注册内容生成器"""
        self._response_generators[intent_type] = generator

    def register_clarification_template(self, key: str, template: str):
        """注册澄清模板"""
        self._clarification_templates[key] = template

    def register_missing_handler(self, entity_key: str, handler: Callable):
        """注册缺失信息处理器"""
        self._missing_entity_handlers[entity_key] = handler

    def create_context_info(self, history: List[Dict] = None,
                            session_data: Dict = None) -> ContextInfo:
        """创建上下文信息"""
        return ContextInfo(
            history=history or [],
            current_step=0,
            max_steps=5,
            session_data=session_data or {},
            user_profile={}
        )


# 全局决策引擎实例
decision_engine = DecisionEngine()
