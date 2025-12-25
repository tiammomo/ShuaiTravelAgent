"""
决策/推理模块 (Reasoner)
职责：
1. 识别用户意图（城市推荐/景点查询/路线规划/一般对话）
2. 提取关键参数（预算、天数、兴趣等）
3. 生成执行计划
"""

import re
from typing import Dict, Any, Optional, List
from enum import Enum


class IntentType(Enum):
    """意图类型枚举"""
    CITY_RECOMMENDATION = "city_recommendation"  # 城市推荐
    ATTRACTION_QUERY = "attraction_query"  # 景点查询
    ROUTE_PLANNING = "route_planning"  # 路线规划
    GENERAL_CHAT = "general_chat"  # 一般对话
    PREFERENCE_UPDATE = "preference_update"  # 偏好更新


class Reasoner:
    """推理引擎：意图识别、参数提取、计划生成"""
    
    def __init__(self):
        """初始化推理引擎"""
        # 意图识别规则
        self.intent_patterns = {
            IntentType.CITY_RECOMMENDATION: [
                r'推荐.*城市',
                r'去哪.*玩',
                r'去哪.*旅游',
                r'想去.*地方',
                r'旅游.*推荐',
                r'哪里.*好玩',
                r'适合.*城市'
            ],
            IntentType.ATTRACTION_QUERY: [
                r'景点.*有哪些',
                r'.*有什么.*玩的',
                r'.*好玩的地方',
                r'.*著名景点',
                r'查看.*景点'
            ],
            IntentType.ROUTE_PLANNING: [
                r'路线.*规划',
                r'行程.*安排',
                r'怎么.*玩',
                r'制定.*计划',
                r'.*天.*怎么玩',
                r'详细.*路线'
            ],
            IntentType.PREFERENCE_UPDATE: [
                r'我.*喜欢',
                r'我.*偏好',
                r'预算.*是',
                r'打算.*天'
            ]
        }
    
    def recognize_intent(self, user_input: str) -> IntentType:
        """
        识别用户意图
        
        Args:
            user_input: 用户输入
            
        Returns:
            意图类型
        """
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input):
                    return intent
        
        return IntentType.GENERAL_CHAT
    
    def extract_parameters(self, user_input: str) -> Dict[str, Any]:
        """
        提取关键参数
        
        Args:
            user_input: 用户输入
            
        Returns:
            参数字典
        """
        params = {}
        
        # 提取城市名称
        cities = self._extract_cities(user_input)
        if cities:
            params['cities'] = cities
        
        # 提取天数
        days = self._extract_days(user_input)
        if days:
            params['days'] = days
        
        # 提取预算
        budget = self._extract_budget(user_input)
        if budget:
            params['budget'] = budget
        
        # 提取兴趣标签
        interests = self._extract_interests(user_input)
        if interests:
            params['interests'] = interests
        
        # 提取季节
        season = self._extract_season(user_input)
        if season:
            params['season'] = season
        
        return params
    
    def _extract_cities(self, text: str) -> List[str]:
        """提取城市名称"""
        # 常见城市列表（简化版）
        common_cities = [
            '北京', '上海', '杭州', '成都', '西安', '厦门',
            '广州', '深圳', '重庆', '南京', '苏州', '武汉'
        ]
        
        found_cities = []
        for city in common_cities:
            if city in text:
                found_cities.append(city)
        
        return found_cities
    
    def _extract_days(self, text: str) -> Optional[int]:
        """提取旅行天数"""
        # 匹配 "3天" "三天" 等模式
        match = re.search(r'(\d+|[一二三四五六七八九十]+)\s*天', text)
        if match:
            day_str = match.group(1)
            # 转换中文数字
            chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                           '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
            if day_str in chinese_nums:
                return chinese_nums[day_str]
            try:
                return int(day_str)
            except:
                pass
        return None
    
    def _extract_budget(self, text: str) -> Optional[tuple]:
        """提取预算范围"""
        # 匹配 "预算3000元" "3000-5000元" 等
        numbers = re.findall(r'\d+', text)
        if '预算' in text or '元' in text or '块' in text:
            if numbers:
                nums = [int(n) for n in numbers]
                if len(nums) >= 2:
                    return (min(nums), max(nums))
                elif len(nums) == 1:
                    return (0, nums[0])
        return None
    
    def _extract_interests(self, text: str) -> List[str]:
        """提取兴趣标签"""
        interest_keywords = {
            '历史': '历史文化',
            '文化': '历史文化',
            '古迹': '历史文化',
            '自然': '自然风光',
            '风景': '自然风光',
            '山水': '自然风光',
            '美食': '美食',
            '吃': '美食',
            '海边': '海滨度假',
            '海滨': '海滨度假',
            '沙滩': '海滨度假',
            '购物': '现代都市',
            '都市': '现代都市',
            '休闲': '休闲养生',
            '放松': '休闲养生'
        }
        
        found_interests = []
        for keyword, tag in interest_keywords.items():
            if keyword in text and tag not in found_interests:
                found_interests.append(tag)
        
        return found_interests
    
    def _extract_season(self, text: str) -> Optional[str]:
        """提取季节偏好"""
        seasons = ['春天', '夏天', '秋天', '冬天', '春季', '夏季', '秋季', '冬季']
        for season in seasons:
            if season in text:
                return season[:2] + '季'  # 统一为"春季"格式
        return None
    
    def generate_action_plan(self, intent: IntentType, 
                            params: Dict[str, Any],
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成执行计划
        
        Args:
            intent: 意图类型
            params: 提取的参数
            context: 上下文信息（记忆、会话状态等）
            
        Returns:
            执行计划
        """
        plan = {
            "intent": intent.value,
            "params": params,
            "actions": []
        }
        
        if intent == IntentType.CITY_RECOMMENDATION:
            plan['actions'] = [
                {
                    "type": "search_cities",
                    "params": {
                        "interests": params.get('interests', []),
                        "budget": params.get('budget'),
                        "season": params.get('season')
                    }
                },
                {
                    "type": "llm_recommendation",
                    "params": {
                        "user_query": context.get('user_query', ''),
                        "available_cities": []  # 将由环境模块填充
                    }
                }
            ]
        
        elif intent == IntentType.ATTRACTION_QUERY:
            cities = params.get('cities', [])
            if not cities and context.get('last_recommended_cities'):
                cities = context.get('last_recommended_cities', [])
            
            plan['actions'] = [
                {
                    "type": "query_attractions",
                    "params": {
                        "cities": cities
                    }
                }
            ]
        
        elif intent == IntentType.ROUTE_PLANNING:
            cities = params.get('cities', [])
            days = params.get('days', 3)
            
            if not cities and context.get('last_recommended_cities'):
                cities = context.get('last_recommended_cities', [])[:1]
            
            plan['actions'] = [
                {
                    "type": "generate_route",
                    "params": {
                        "city": cities[0] if cities else None,
                        "days": days
                    }
                }
            ]
        
        elif intent == IntentType.PREFERENCE_UPDATE:
            plan['actions'] = [
                {
                    "type": "update_preference",
                    "params": params
                }
            ]
        
        else:  # GENERAL_CHAT
            plan['actions'] = [
                {
                    "type": "llm_chat",
                    "params": {
                        "user_query": context.get('user_query', '')
                    }
                }
            ]
        
        return plan
    
    def validate_plan(self, plan: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证执行计划的有效性
        
        Args:
            plan: 执行计划
            
        Returns:
            (是否有效, 错误信息)
        """
        if not plan.get('actions'):
            return False, "执行计划为空"
        
        intent = plan.get('intent')
        
        # 验证路线规划必需参数
        if intent == IntentType.ROUTE_PLANNING.value:
            route_action = next((a for a in plan['actions'] if a['type'] == 'generate_route'), None)
            if route_action:
                if not route_action['params'].get('city'):
                    return False, "路线规划需要指定城市"
        
        return True, ""
