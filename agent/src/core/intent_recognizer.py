"""
意图识别模块

使用 LLM 进行细粒度意图识别，支持多种旅游相关意图类型。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型枚举"""
    # 旅行规划类
    TRAVEL_PLANNING = "travel_planning"           # 综合旅行规划
    CITY_RECOMMENDATION = "city_recommendation"   # 城市推荐
    ATTRACTION_QUERY = "attraction_query"         # 景点查询
    ROUTE_PLANNING = "route_planning"             # 路线规划
    ITINERARY_QUERY = "itinerary_query"           # 行程查询

    # 专项咨询类
    BUDGET_QUERY = "budget_query"                 # 预算咨询
    FOOD_RECOMMENDATION = "food_recommendation"   # 美食推荐
    ACCOMMODATION = "accommodation"               # 住宿咨询
    TRANSPORTATION = "transportation"             # 交通咨询
    SEASON_QUERY = "season_query"                 # 季节/天气咨询

    # 特定类型推荐
    NATURE_TOUR = "nature_tour"                   # 自然风光游
    CULTURAL_TOUR = "cultural_tour"               # 文化历史游
    FAMILY_TOUR = "family_tour"                   # 亲子游
    HONEYMOON_TOUR = "honeymoon_tour"             # 蜜月游
    ADVENTURE_TOUR = "adventure_tour"             # 探险游

    # 其他
    GENERAL_CHAT = "general_chat"                 # 一般对话
    GREETING = "greeting"                         # 问候
    COMPLAINT = "complaint"                       # 投诉/反馈


class SentimentType(Enum):
    """用户情感类型"""
    NEUTRAL = "neutral"
    EXCITED = "excited"
    URGENT = "urgent"
    HESITANT = "hesitant"
    CURIOUS = "curious"
    DISAPPOINTED = "disappointed"
    SATISFIED = "satisfied"


@dataclass
class Entity:
    """实体类"""
    value: str
    type: str
    confidence: float = 1.0


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: IntentType
    sub_intent: Optional[str] = None
    entities: Dict[str, List[str]] = field(default_factory=dict)
    sentiment: SentimentType = SentimentType.NEUTRAL
    confidence: float = 0.0
    priority: str = "normal"  # "high", "normal", "low"
    missing_info: List[str] = field(default_factory=list)
    original_query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "sub_intent": self.sub_intent,
            "entities": self.entities,
            "sentiment": self.sentiment.value,
            "confidence": self.confidence,
            "priority": self.priority,
            "missing_info": self.missing_info,
        }

    def needs_more_info(self) -> bool:
        """是否需要更多信息"""
        return len(self.missing_info) > 0

    def is_travel_related(self) -> bool:
        """是否是旅行相关意图"""
        return self.intent not in [IntentType.GENERAL_CHAT, IntentType.GREETING]


# 意图关键词映射
INTENT_KEYWORDS: Dict[IntentType, List[str]] = {
    IntentType.TRAVEL_PLANNING: ["规划", "计划", "安排", "攻略", "行程", "旅游", "旅行", "出游"],
    IntentType.CITY_RECOMMENDATION: ["推荐", "哪些城市", "去哪", "城市", "目的地"],
    IntentType.ATTRACTION_QUERY: ["景点", "好玩", "值得去", "网红", "打卡", "门票"],
    IntentType.ROUTE_PLANNING: ["路线", "路线规划", "路径", "怎么走", "顺序"],
    IntentType.ITINERARY_QUERY: ["几天", "日程", "时间安排", "每天"],
    IntentType.BUDGET_QUERY: ["预算", "花费", "多少钱", "费用", "消费"],
    IntentType.FOOD_RECOMMENDATION: ["美食", "好吃", "餐厅", "小吃", "特色菜", "吃什么"],
    IntentType.ACCOMMODATION: ["住宿", "酒店", "民宿", "宾馆", "住哪里"],
    IntentType.TRANSPORTATION: ["交通", "怎么去", "出行", "飞机", "火车", "高铁"],
    IntentType.SEASON_QUERY: ["季节", "什么时候", "天气", "最佳时间", "几月"],
    IntentType.NATURE_TOUR: ["自然", "风光", "风景", "山水", "海滩", "森林"],
    IntentType.CULTURAL_TOUR: ["文化", "历史", "古迹", "博物馆", "文物"],
    IntentType.FAMILY_TOUR: ["亲子", "小孩", "儿童", "家庭", "孩子"],
    IntentType.HONEYMOON_TOUR: ["蜜月", "情侣", "浪漫", "二人世界"],
    IntentType.ADVENTURE_TOUR: ["冒险", "刺激", "极限", "户外", "徒步"],
    IntentType.GREETING: ["你好", "hi", "hello", "在吗", "在不在"],
    IntentType.COMPLAINT: ["投诉", "不满意", "太差", "坑", "骗"],
}


class IntentRecognizer:
    """意图识别器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._fallback_keywords = INTENT_KEYWORDS

    def set_llm_client(self, llm_client):
        """设置 LLM 客户端"""
        self.llm_client = llm_client

    async def recognize(self, query: str, context: Dict = None) -> IntentResult:
        """
        识别用户意图

        Args:
            query: 用户输入
            context: 上下文信息（可选）

        Returns:
            IntentResult: 意图识别结果
        """
        # 优先使用 LLM 识别
        if self.llm_client:
            try:
                return await self._recognize_with_llm(query, context)
            except Exception as e:
                logger.warning(f"LLM 意图识别失败，回退到规则识别: {e}")

        # 回退到规则识别
        return self._recognize_with_rules(query)

    async def _recognize_with_llm(self, query: str,
                                   context: Dict = None) -> IntentResult:
        """使用 LLM 进行意图识别"""

        context_info = ""
        if context:
            context_info = f"\n上下文信息：{json.dumps(context, ensure_ascii=False, indent=2)}"

        system_prompt = f"""你是智能旅游助手的任务分析专家。

用户输入：{query}{context_info}

请分析用户意图，返回 JSON 格式：
{{
    "intent": "意图类型",
    "sub_intent": "子意图（可选）",
    "entities": {{
        "cities": ["提取的城市名"],
        "budget": "预算（如：2000元、5000左右）",
        "days": "天数（如：3天、一周）",
        "season": "季节/时间（如：1月、春季、暑假）",
        "people": "人数（如：2人、一家三口）",
        "preferences": ["偏好标签，如：自然风光、美食、历史]"]
    }},
    "sentiment": "用户情感（neutral/excited/urgent/hesitant/curious/disappointed/satisfied）",
    "confidence": 0.0-1.0,
    "priority": "优先级（high/normal/low）",
    "missing_info": ["缺少的关键信息列表"]
}}

意图类型说明：
- travel_planning: 综合旅行规划
- city_recommendation: 城市推荐
- attraction_query: 景点查询
- route_planning: 路线规划
- itinerary_query: 行程安排
- budget_query: 预算咨询
- food_recommendation: 美食推荐
- accommodation: 住宿咨询
- transportation: 交通咨询
- season_query: 季节咨询
- nature_tour: 自然风光游
- cultural_tour: 文化历史游
- family_tour: 亲子游
- honeymoon_tour: 蜜月游
- adventure_tour: 探险游
- general_chat: 一般对话
- greeting: 问候

只输出 JSON，不要其他内容。"""

        try:
            result = self.llm_client.chat(
                [{"role": "system", "content": system_prompt}],
                temperature=0.3
            )

            if result.get("success"):
                content = result.get("content", "")
                # 提取 JSON
                data = self._extract_json(content)
                if data:
                    return self._parse_llm_result(data, query)

        except Exception as e:
            logger.error(f"LLM 意图识别错误: {e}")

        # 识别失败，回退到规则
        return self._recognize_with_rules(query)

    def _recognize_with_rules(self, query: str) -> IntentResult:
        """使用规则进行意图识别"""
        query_lower = query.lower()

        # 1. 检测问候
        if any(kw in query for kw in ["你好", "hi", "hello", "在吗", "在不在"]):
            return IntentResult(
                intent=IntentType.GREETING,
                confidence=0.95,
                original_query=query
            )

        # 2. 检测投诉
        if any(kw in query for kw in ["投诉", "不满意", "太差", "坑", "骗"]):
            return IntentResult(
                intent=IntentType.COMPLAINT,
                confidence=0.9,
                priority="high",
                original_query=query
            )

        # 3. 多重意图检测
        intent_scores: Dict[IntentType, float] = {}

        for intent_type, keywords in self._fallback_keywords.items():
            if intent_type in [IntentType.GREETING, IntentType.COMPLAINT]:
                continue

            score = 0.0
            matched_keywords = []
            for kw in keywords:
                if kw in query:
                    score += 1.0
                    matched_keywords.append(kw)

            if score > 0:
                # 根据匹配数量和精确度调整分数
                intent_scores[intent_type] = min(score / 3.0, 1.0)

        # 4. 按分数排序，选择最高分
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            intent = best_intent[0]
            confidence = best_intent[1]
        else:
            intent = IntentType.GENERAL_CHAT
            confidence = 0.5

        # 5. 提取实体
        entities = self._extract_entities(query)

        # 6. 检测情感
        sentiment = self._detect_sentiment(query)

        # 7. 检测优先级
        priority = "high" if any(kw in query for kw in ["急", "马上", "尽快", "着急"]) else "normal"

        return IntentResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
            sentiment=sentiment,
            priority=priority,
            original_query=query
        )

    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """提取实体"""
        entities = {
            "cities": [],
            "budget": [],
            "days": [],
            "season": [],
            "people": [],
            "preferences": []
        }

        # 城市名检测（简单规则）
        city_keywords = ["去", "到", "在", "的城市", "旅游"]
        for kw in city_keywords:
            # 这里应该调用城市数据库进行匹配
            # 暂时返回空列表
            pass

        # 天数检测
        day_patterns = [r"(\d+)\s*天", r"(\d+)\s*夜", r"一周", r"半个月"]
        import re
        for pattern in day_patterns:
            match = re.search(pattern, query)
            if match:
                entities["days"].append(match.group(1) if match.lastindex else match.group(0))
                break

        # 预算检测
        budget_patterns = [r"(\d+)\s*元", r"(\d+)\s*千", r"(\d+)\s*万左右"]
        for pattern in budget_patterns:
            match = re.search(pattern, query)
            if match:
                entities["budget"].append(match.group(0))
                break

        # 人数检测
        people_patterns = [r"(\d+)\s*人", r"一家(\d+)", r"两口", r"三口"]
        for pattern in people_patterns:
            match = re.search(pattern, query)
            if match:
                entities["people"].append(match.group(0))
                break

        return entities

    def _detect_sentiment(self, query: str) -> SentimentType:
        """检测用户情感"""
        if any(kw in query for kw in ["太棒了", "太好了", "超级", "非常", "特别", "期待"]):
            return SentimentType.EXCITED
        if any(kw in query for kw in ["急", "马上", "尽快", "着急"]):
            return SentimentType.URGENT
        if any(kw in query for kw in ["大概", "也许", "可能", "不太确定"]):
            return SentimentType.HESITANT
        if any(kw in query for kw in ["为什么", "怎么", "能否", "能不能"]):
            return SentimentType.CURIOUS
        if any(kw in query for kw in ["谢谢", "感谢", "太好了", "满意"]):
            return SentimentType.SATISFIED
        if any(kw in query for kw in ["不行", "不好", "不满意"]):
            return SentimentType.DISAPPOINTED
        return SentimentType.NEUTRAL

    def _extract_json(self, content: str) -> Optional[Dict]:
        """从文本中提取 JSON"""
        import re
        try:
            # 尝试直接解析
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

    def _parse_llm_result(self, data: Dict, original_query: str) -> IntentResult:
        """解析 LLM 返回的结果"""
        try:
            intent_str = data.get("intent", "general_chat")
            intent = IntentType(intent_str) if intent_str in [e.value for e in IntentType] else IntentType.GENERAL_CHAT

            sentiment_str = data.get("sentiment", "neutral")
            sentiment = SentimentType(sentiment_str) if sentiment_str in [e.value for e in SentimentType] else SentimentType.NEUTRAL

            return IntentResult(
                intent=intent,
                sub_intent=data.get("sub_intent"),
                entities=data.get("entities", {}),
                sentiment=sentiment,
                confidence=data.get("confidence", 0.7),
                priority=data.get("priority", "normal"),
                missing_info=data.get("missing_info", []),
                original_query=original_query
            )
        except Exception as e:
            logger.error(f"解析 LLM 结果失败: {e}")
            return IntentResult(
                intent=IntentType.GENERAL_CHAT,
                confidence=0.5,
                original_query=original_query
            )


# 全局意图识别器实例
intent_recognizer = IntentRecognizer()
