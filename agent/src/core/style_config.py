"""
动态风格配置模块

提供多种回复风格配置，支持根据任务类型和用户情感动态选择风格。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import random


class ReplyStyle(Enum):
    """回复风格枚举"""
    ENTHUSIASTIC = "enthusiastic"   # 热情活泼
    WARM = "warm"                    # 温暖亲切
    PROFESSIONAL = "professional"    # 专业正式
    PLAYFUL = "playful"              # 俏皮可爱
    CONCISE = "concise"              # 简洁明了


class UserSentiment(Enum):
    """用户情感枚举"""
    NEUTRAL = "neutral"      # 中性
    EXCITED = "excited"      # 兴奋
    URGENT = "urgent"        # 急迫
    HESITANT = "hesitant"    # 犹豫
    SATISFIED = "satisfied"  # 满意


@dataclass
class StyleConfig:
    """风格配置"""
    name: str
    emoji_density: str  # "high", "medium", "low"
    greetings: List[str]
    closings: List[str]
    temperature: float
    max_response_length: int
    use_emojis: bool = True
    use_fluent_language: bool = True
    use_interaction: bool = True  # 互动性

    def get_greeting(self) -> str:
        """获取随机问候语"""
        return random.choice(self.greetings) if self.greetings else ""

    def get_closing(self) -> str:
        """获取随机结束语"""
        return random.choice(self.closings) if self.closings else ""

    def get_emoji_count(self, base_count: int = 3) -> int:
        """根据密度获取emoji数量"""
        density_map = {"high": 1.5, "medium": 1.0, "low": 0.5}
        multiplier = density_map.get(self.emoji_density, 1.0)
        return int(base_count * multiplier)


# 预定义风格配置
STYLE_CONFIGS: Dict[ReplyStyle, StyleConfig] = {
    ReplyStyle.ENTHUSIASTIC: StyleConfig(
        name="热情活泼",
        emoji_density="high",
        greetings=[
            "哇塞！小伙伴你问对人啦！🌟",
            "哇！这个问题太棒了！✨",
            "嘿嘿，超级开心你问我！🚀",
            "呀！这是个超棒的问题！💫",
            "小伙伴你好呀！🎉"
        ],
        closings=[
            "祝你的旅行超级精彩！🌈",
            "期待你的完美旅程！✈️",
            "祝你玩得开心到飞起！🎊",
            "有任何问题随时来找我哦～💪"
        ],
        temperature=0.85,
        max_response_length=1500
    ),

    ReplyStyle.WARM: StyleConfig(
        name="温暖亲切",
        emoji_density="medium",
        greetings=[
            "很高兴帮你规划这次旅行～😊",
            "好的呀，让我来帮你看看！🌸",
            "没问题，我来帮你找找看！🍀",
            "好的，我来为你精心推荐！💝"
        ],
        closings=[
            "希望这些建议对你有帮助～🌷",
            "祝你旅途愉快，一切顺利！🍀",
            "期待你的旅行故事哦～📸",
            "有任何问题随时问我～💌"
        ],
        temperature=0.7,
        max_response_length=1200
    ),

    ReplyStyle.PROFESSIONAL: StyleConfig(
        name="专业正式",
        emoji_density="low",
        greetings=[
            "您好，我来为您介绍。",
            "根据您的需求，我推荐以下方案。",
            "您好，以下是我的推荐。",
            "好的，为您整理如下。"
        ],
        closings=[
            "祝您旅途愉快。",
            "如需进一步咨询，欢迎随时联系。",
            "祝您出行顺利。",
            "感谢您的咨询。"
        ],
        temperature=0.5,
        max_response_length=1000
    ),

    ReplyStyle.PLAYFUL: StyleConfig(
        name="俏皮可爱",
        emoji_density="high",
        greetings=[
            "嘿！旅行小达人来啦～🎈",
            "哇哦！这个问题我超爱！🍭",
            "叮咚～您的旅行小助手已上线！🧸",
            "嘿嘿，ready 出发！🚀",
            "呀呼～来啦来啦！🎪"
        ],
        closings=[
            "好啦，就这些啦～记得拍照发圈哦！📷",
            "冲冲冲！期待你的旅行大片！🎬",
            "祝你玩得开心鸭～🦆",
            "溜啦溜啦，有问题再找我玩～🎨"
        ],
        temperature=0.9,
        max_response_length=1400
    ),

    ReplyStyle.CONCISE: StyleConfig(
        name="简洁明了",
        emoji_density="low",
        greetings=[
            "好的。",
            "推荐以下城市。"
        ],
        closings=[
            "祝你旅途愉快。",
            "如有其他问题，请随时咨询。"
        ],
        temperature=0.4,
        max_response_length=800
    )
}

# 任务类型到风格的映射
TASK_STYLE_MAP: Dict[str, ReplyStyle] = {
    "city_recommendation": ReplyStyle.ENTHUSIASTIC,
    "attraction_query": ReplyStyle.WARM,
    "route_planning": ReplyStyle.PROFESSIONAL,
    "food_recommendation": ReplyStyle.PLAYFUL,
    "budget_query": ReplyStyle.PROFESSIONAL,
    "general_chat": ReplyStyle.WARM,
}

# 情感调整系数
SENTIMENT_ADJUSTMENTS: Dict[UserSentiment, Dict] = {
    UserSentiment.URGENT: {"temperature": -0.2, "max_length": 0.8},
    UserSentiment.EXCITED: {"temperature": 0.1, "emoji_density": "high"},
    UserSentiment.HESITANT: {"temperature": -0.1, "use_interaction": True},
    UserSentiment.SATISFIED: {"temperature": 0.05, "use_interaction": True},
}

# 旅行相关 Emoji 集合
TRAVEL_EMOJIS = {
    "general": ["🌟", "✨", "💫", "🌈", "🌸", "🍀"],
    "city": ["🏙️", "🌆", "🌃", "🏮", "🗼", "🏯"],
    "nature": ["🏔️", "🌊", "🌴", "🌺", "🦋", "🌻"],
    "food": ["🍜", "🥘", "🍤", "🍵", "🥮", "🍡"],
    "transport": ["✈️", "🚄", "🚌", "🚢", "🚲", "🚗"],
    "activity": ["📸", "🎭", "⛷️", "🏊", "🧘", "🎣"],
    "emotion": ["😊", "😍", "🤗", "🥰", "😄", "🎉"],
}


class StyleManager:
    """风格管理器"""

    def __init__(self, default_style: ReplyStyle = ReplyStyle.WARM):
        self.default_style = default_style
        self._user_preferences: Dict[str, ReplyStyle] = {}

    def get_style_for_task(self, task_type: str,
                           sentiment: UserSentiment = UserSentiment.NEUTRAL) -> StyleConfig:
        """根据任务类型和情感获取风格配置"""
        # 1. 获取基础风格
        base_style = STYLE_CONFIGS.get(
            TASK_STYLE_MAP.get(task_type, self.default_style),
            STYLE_CONFIGS[self.default_style]
        )

        # 2. 根据情感调整
        adjustment = SENTIMENT_ADJUSTMENTS.get(sentiment, {})

        # 3. 创建调整后的配置
        config_dict = {
            "name": base_style.name,
            "emoji_density": adjustment.get("emoji_density", base_style.emoji_density),
            "greetings": base_style.greetings,
            "closings": base_style.closings,
            "temperature": base_style.temperature + adjustment.get("temperature", 0),
            "max_response_length": int(base_style.max_response_length *
                                       adjustment.get("max_length", 1.0)),
            "use_emojis": base_style.use_emojis,
            "use_fluent_language": base_style.use_fluent_language,
            "use_interaction": adjustment.get("use_interaction", base_style.use_interaction)
        }

        return StyleConfig(**config_dict)

    def get_emoji(self, category: str = "general") -> str:
        """获取随机emoji"""
        emojis = TRAVEL_EMOJIS.get(category, TRAVEL_EMOJIS["general"])
        return random.choice(emojis)

    def get_emojis(self, categories: List[str], count: int = 3) -> str:
        """获取多个emoji"""
        all_emojis = []
        for cat in categories:
            all_emojis.extend(TRAVEL_EMOJIS.get(cat, []))
        return "".join(random.sample(all_emojis, min(count, len(all_emojis))))

    def format_opening(self, style: StyleConfig, context: str = "") -> str:
        """格式化开场白"""
        greeting = style.get_greeting()
        if context:
            return f"{greeting} {context}"
        return greeting

    def format_closing(self, style: StyleConfig, extra: str = "") -> str:
        """格式化结束语"""
        closing = style.get_closing()
        if extra:
            return f"{extra} {closing}"
        return closing

    def apply_style_to_response(self, response: str, style: StyleConfig,
                                 context: dict = None) -> str:
        """根据风格调整回复内容"""
        # 1. 添加开场白
        if style.use_interaction and context:
            opening = self.format_opening(style, context.get("purpose", ""))
            response = f"{opening}\n\n{response}"

        # 2. 添加结束语
        if style.use_interaction:
            closing = self.format_closing(style)
            response = f"{response}\n\n{closing}"

        # 3. 根据需要添加emoji
        if style.use_emojis and style.emoji_density != "low":
            # 在适当位置插入emoji
            lines = response.split("\n")
            for i, line in enumerate(lines):
                if line.strip() and random.random() < 0.3:
                    emoji = self.get_emoji()
                    lines[i] = f"{emoji} {line}"
            response = "\n".join(lines)

        return response


# 全局风格管理器实例
style_manager = StyleManager()
