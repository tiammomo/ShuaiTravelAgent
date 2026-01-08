"""
语义工具匹配模块

提供基于语义相似度的工具匹配功能，支持智能选择最佳工具。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
import re
import logging

logger = logging.getLogger(__name__)


class MatchStrategy(Enum):
    """匹配策略"""
    EXACT = "exact"           # 精确匹配
    SEMANTIC = "semantic"     # 语义匹配
    KEYWORD = "keyword"       # 关键词匹配
    HYBRID = "hybrid"         # 混合匹配


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    description: str
    parameters: Dict = field(default_factory=dict)
    intent_tags: List[str] = field(default_factory=list)  # 支持的意图标签
    supported_entities: List[str] = field(default_factory=list)  # 支持的实体类型


@dataclass
class ToolMatch:
    """工具匹配结果"""
    tool: ToolInfo
    score: float
    match_type: str  # "exact", "semantic", "keyword", "fallback"
    matched_keywords: List[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool.name,
            "score": self.score,
            "match_type": self.match_type,
            "matched_keywords": self.matched_keywords,
            "reason": self.reason
        }


class SemanticToolMatcher:
    """语义工具匹配器"""

    # 意图到工具的映射规则
    INTENT_TOOL_MAP = {
        "city_recommendation": ["search_cities", "recommend_cities", "city_info"],
        "attraction_query": ["search_attractions", "attraction_detail", "city_attractions"],
        "route_planning": ["plan_route", "route_recommendation", "navigation"],
        "budget_query": ["budget_calculator", "cost_estimator", "price_query"],
        "food_recommendation": ["food_recommendation", "restaurant_search", "local_food"],
        "accommodation": ["hotel_search", "accommodation", "hotel_booking"],
        "transportation": ["transport_query", "ticket_booking", "traffic_info"],
        "season_query": ["weather_query", "season_info", "climate"],
        "nature_tour": ["nature_spots", "scenic_spots", "park_info"],
        "cultural_tour": ["museum_info", "historical_sites", "cultural_spots"],
        "family_tour": ["family_spots", "kid_friendly", "theme_park"],
        "honeymoon_tour": ["romantic_spots", "couple_activities", "honeymoon"],
        "adventure_tour": ["adventure_activities", "outdoor_spots", "hiking"],
        "general_chat": ["chat", "general_query", "default"],
    }

    # 关键词到工具的映射
    KEYWORD_TOOL_MAP = {
        "search_cities": ["搜索城市", "查找城市", "城市列表", "有哪些城市"],
        "recommend_cities": ["推荐城市", "城市推荐", "去哪里", "推荐些"],
        "city_info": ["城市信息", "城市介绍", "城市详情", "城市概况"],
        "search_attractions": ["搜索景点", "查找景点", "景点查询"],
        "attraction_detail": ["景点详情", "景点介绍", "景点门票", "门票价格"],
        "city_attractions": ["城市景点", "景点列表", "景点有哪些"],
        "plan_route": ["规划路线", "路线规划", "行程安排", "路线设计"],
        "budget_calculator": ["预算计算", "预算多少", "费用多少", "花钱"],
        "food_recommendation": ["美食推荐", "有什么好吃的", "当地美食", "小吃"],
        "hotel_search": ["酒店查询", "酒店推荐", "住宿", "订酒店"],
        "transport_query": ["交通查询", "怎么去", "交通方式", "出行方式"],
        "weather_query": ["天气预报", "天气情况", "气候"],
    }

    def __init__(self, strategy: MatchStrategy = MatchStrategy.HYBRID):
        self.strategy = strategy
        self._tools: Dict[str, ToolInfo] = {}
        self._user_preferences: Dict[str, List[str]] = {}  # 用户对工具的使用偏好
        self._usage_stats: Dict[str, int] = {}  # 工具使用统计

    def register_tool(self, tool: ToolInfo) -> bool:
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        self._tools[tool.name] = tool
        logger.info(f"已注册工具: {tool.name}")
        return True

    def register_tools(self, tools: List[ToolInfo]) -> int:
        """批量注册工具"""
        count = 0
        for tool in tools:
            if self.register_tool(tool):
                count += 1
        return count

    def get_available_tools(self) -> List[ToolInfo]:
        """获取所有已注册的工具"""
        return list(self._tools.values())

    def match_tools(self, intent: str, entities: Dict[str, List[str]] = None,
                    top_k: int = 3, context: Dict = None) -> List[ToolMatch]:
        """
        根据意图匹配工具

        Args:
            intent: 意图类型
            entities: 提取的实体
            top_k: 返回前 k 个匹配结果
            context: 上下文信息

        Returns:
            List[ToolMatch]: 匹配结果列表
        """
        matches: List[ToolMatch] = []
        entities = entities or {}

        # 1. 直接映射匹配
        direct_tools = self.INTENT_TOOL_MAP.get(intent, [])
        for tool_name in direct_tools:
            if tool_name in self._tools:
                tool = self._tools[tool_name]
                score = self._calculate_direct_score(tool, intent, entities)
                matches.append(ToolMatch(
                    tool=tool,
                    score=score,
                    match_type="direct",
                    reason=f"直接映射到意图 {intent}"
                ))

        # 2. 关键词匹配
        keyword_matches = self._match_by_keyword(intent, entities)
        matches.extend(keyword_matches)

        # 3. 语义匹配（如果配置了）
        if self.strategy in [MatchStrategy.SEMANTIC, MatchStrategy.HYBRID]:
            semantic_matches = self._match_by_semantic(intent, entities)
            matches.extend(semantic_matches)

        # 4. 兜底匹配 - 尝试所有工具
        if len(matches) == 0:
            fallback_matches = self._match_fallback(intent, entities)
            matches.extend(fallback_matches)

        # 5. 去重并排序
        unique_matches = self._deduplicate_matches(matches)

        # 6. 应用用户偏好
        unique_matches = self._apply_user_preferences(unique_matches, intent)

        # 7. 限制返回数量
        return sorted(unique_matches, key=lambda x: x.score, reverse=True)[:top_k]

    def _calculate_direct_score(self, tool: ToolInfo, intent: str,
                                 entities: Dict[str, List[str]]) -> float:
        """计算直接映射分数"""
        score = 0.8  # 基础分数

        # 检查实体匹配
        for entity_type, entity_values in entities.items():
            if entity_type in tool.supported_entities and entity_values:
                score += 0.05 * len(entity_values)

        return min(score, 1.0)

    def _match_by_keyword(self, intent: str, entities: Dict[str, List[str]]) -> List[ToolMatch]:
        """关键词匹配"""
        matches = []

        for tool_name, keywords in self.KEYWORD_TOOL_MAP.items():
            if tool_name not in self._tools:
                continue

            tool = self._tools[tool_name]
            matched_keywords = []

            # 检查工具名称是否包含在意图或关键词中
            for kw in keywords:
                if kw in intent:
                    matched_keywords.append(kw)

            # 检查描述
            desc = tool.description.lower()
            for kw in keywords:
                if kw.lower() in desc:
                    matched_keywords.append(kw)

            if matched_keywords:
                score = 0.5 + 0.1 * len(matched_keywords)
                matches.append(ToolMatch(
                    tool=tool,
                    score=min(score, 0.9),
                    match_type="keyword",
                    matched_keywords=matched_keywords,
                    reason=f"关键词匹配: {matched_keywords}"
                ))

        return matches

    def _match_by_semantic(self, intent: str,
                           entities: Dict[str, List[str]]) -> List[ToolMatch]:
        """
        语义匹配（简化版）

        注意：完整的语义匹配需要嵌入模型（如 sentence-transformers）
        这里提供基于规则和工具描述的简化实现
        """
        matches = []
        intent_words = intent.replace("_", " ").split()

        for tool in self._tools.values():
            score = 0.0
            matched_reasons = []

            # 1. 工具名称匹配
            tool_name_words = tool.name.replace("_", " ").replace("-", " ").split()
            for iw in intent_words:
                for tnw in tool_name_words:
                    if iw in tnw or tnw in iw:
                        score += 0.2
                        matched_reasons.append(f"名称匹配: {tnw}")
                        break

            # 2. 意图标签匹配
            for tag in tool.intent_tags:
                if tag in intent or intent in tag:
                    score += 0.3
                    matched_reasons.append(f"标签匹配: {tag}")
                    break

            # 3. 描述语义匹配
            desc = tool.description.lower()
            semantic_keywords = {
                "city": ["城市", "目的地", "城市"],
                "attraction": ["景点", "景区", "观光", "游览"],
                "food": ["美食", "餐饮", "吃", "小吃"],
                "route": ["路线", "行程", "规划", "安排"],
                "budget": ["预算", "费用", "花费", "价格"],
                "hotel": ["住宿", "酒店", "民宿", "住"],
                "transport": ["交通", "出行", "transport"],
                "weather": ["天气", "气候", "季节"],
            }

            for key, words in semantic_keywords.items():
                if key in intent:
                    for word in words:
                        if word in desc:
                            score += 0.15
                            matched_reasons.append(f"语义匹配: {word}")
                            break

            if score > 0.2:
                matches.append(ToolMatch(
                    tool=tool,
                    score=min(score, 0.85),
                    match_type="semantic",
                    matched_keywords=matched_reasons,
                    reason=f"; ".join(matched_reasons) if matched_reasons else "语义相似"
                ))

        return matches

    def _match_fallback(self, intent: str, entities: Dict[str, List[str]]) -> List[ToolMatch]:
        """兜底匹配 - 尝试所有工具"""
        matches = []

        for tool in self._tools.values():
            # 计算基础分数
            score = 0.3  # 兜底分数

            # 检查是否支持该意图类型
            if tool.intent_tags:
                for tag in tool.intent_tags:
                    if tag in intent or intent in tag:
                        score = 0.6
                        break

            if score > 0.3:
                matches.append(ToolMatch(
                    tool=tool,
                    score=score,
                    match_type="fallback",
                    reason="兜底匹配"
                ))

        return matches

    def _deduplicate_matches(self, matches: List[ToolMatch]) -> List[ToolMatch]:
        """去重匹配结果"""
        seen = set()
        unique = []

        for match in matches:
            tool_name = match.tool.name
            if tool_name not in seen:
                seen.add(tool_name)
                unique.append(match)

        return unique

    def _apply_user_preferences(self, matches: List[ToolMatch],
                                 intent: str) -> List[ToolMatch]:
        """应用用户偏好"""
        preferences = self._user_preferences.get(intent, [])

        for match in matches:
            if match.tool.name in preferences:
                match.score = min(match.score * 1.2, 1.0)  # 偏好提升

        return matches

    def record_tool_usage(self, tool_name: str, success: bool):
        """记录工具使用情况"""
        if tool_name not in self._usage_stats:
            self._usage_stats[tool_name] = {"success": 0, "total": 0}

        self._usage_stats[tool_name]["total"] += 1
        if success:
            self._usage_stats[tool_name]["success"] += 1

    def get_tool_stats(self, tool_name: str) -> Optional[Dict]:
        """获取工具使用统计"""
        return self._usage_stats.get(tool_name)

    def get_success_rate(self, tool_name: str) -> Optional[float]:
        """获取工具成功率"""
        stats = self._usage_stats.get(tool_name)
        if stats and stats["total"] > 0:
            return stats["success"] / stats["total"]
        return None

    def recommend_best_tool(self, matches: List[ToolMatch]) -> Optional[ToolMatch]:
        """推荐最佳工具（综合考虑分数和成功率）"""
        if not matches:
            return None

        best = None
        best_score = -1

        for match in matches:
            # 综合分数 = 匹配分数 * 0.8 + 成功率 * 0.2
            success_rate = self.get_success_rate(match.tool.name) or 0.5
            combined_score = match.score * 0.8 + success_rate * 0.2

            if combined_score > best_score:
                best_score = combined_score
                best = match

        return best


class ToolSelector:
    """工具选择器 - 提供高级工具选择功能"""

    def __init__(self, matcher: SemanticToolMatcher):
        self.matcher = matcher

    def select_tool_for_action(self, action_description: str,
                                available_tools: List[ToolInfo]) -> Optional[ToolInfo]:
        """
        根据动作描述选择工具

        Args:
            action_description: 动作描述
            available_tools: 可用工具列表

        Returns:
            最佳匹配的工具
        """
        # 注册可用工具
        for tool in available_tools:
            self.matcher.register_tool(tool)

        # 提取意图关键词
        intent = self._extract_intent_from_action(action_description)
        entities = self._extract_entities_from_action(action_description)

        # 匹配工具
        matches = self.matcher.match_tools(intent, entities, top_k=1)
        if matches:
            return matches[0].tool

        return None

    def _extract_intent_from_action(self, action: str) -> str:
        """从动作描述提取意图"""
        action_lower = action.lower()

        intent_patterns = {
            "search_cities": ["搜索城市", "查找城市", "城市列表"],
            "recommend_cities": ["推荐", "建议"],
            "attraction_query": ["景点", "好玩", "值得"],
            "route_planning": ["路线", "行程", "规划"],
            "budget_query": ["预算", "花费", "费用"],
            "food_recommendation": ["美食", "吃"],
            "accommodation": ["住宿", "酒店"],
            "transportation": ["交通", "怎么去"],
        }

        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if pattern in action:
                    return intent

        return "general_chat"

    def _extract_entities_from_action(self, action: str) -> Dict[str, List[str]]:
        """从动作描述提取实体"""
        entities = {
            "cities": [],
            "days": [],
            "budget": [],
        }

        # 简单的正则提取
        import re

        # 城市名（简单示例）
        city_match = re.search(r"([^\s]+?)城市", action)
        if city_match:
            entities["cities"].append(city_match.group(1))

        # 天数
        day_match = re.search(r"(\d+)\s*天", action)
        if day_match:
            entities["days"].append(day_match.group(1))

        return entities


# 全局匹配器实例
semantic_matcher = SemanticToolMatcher()
tool_selector = ToolSelector(semantic_matcher)
