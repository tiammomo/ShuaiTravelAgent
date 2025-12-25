"""
环境交互模块 (Environment)
职责：
1. 管理旅游知识库（城市、景点数据）
2. 提供数据查询接口
3. 执行工具调用
"""

from typing import Dict, Any, List, Optional


class Environment:
    """环境交互器：提供旅游数据查询和工具调用接口"""
    
    def __init__(self, config_manager):
        """
        初始化环境交互器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, callable]:
        """注册可用工具"""
        return {
            "search_cities": self.search_cities,
            "query_attractions": self.query_attractions,
            "calculate_budget": self.calculate_budget,
            "get_city_info": self.get_city_info
        }
    
    def search_cities(self, interests: List[str] = None,
                     budget: tuple = None,
                     season: str = None) -> Dict[str, Any]:
        """
        根据兴趣、预算、季节搜索城市
        
        Args:
            interests: 兴趣标签列表
            budget: 预算范围 (min, max)
            season: 季节
            
        Returns:
            搜索结果
        """
        all_cities = self.config_manager.get_all_cities()
        matched_cities = []
        
        for city_name in all_cities:
            city_info = self.config_manager.get_city_info(city_name)
            if not city_info:
                continue
            
            score = 0
            match_reasons = []
            
            # 兴趣匹配
            if interests:
                city_tags = city_info.get('tags', [])
                for interest in interests:
                    # 查找哪些城市有这个兴趣标签
                    if interest in city_tags or any(interest in tag for tag in city_tags):
                        score += 30
                        match_reasons.append(f"符合{interest}兴趣")
            
            # 预算匹配
            if budget:
                avg_budget = city_info.get('avg_budget_per_day', 0)
                if budget[0] <= avg_budget <= budget[1]:
                    score += 20
                    match_reasons.append("预算适合")
                elif avg_budget < budget[1]:
                    score += 10
            
            # 季节匹配
            if season:
                best_seasons = city_info.get('best_season', [])
                if season in best_seasons:
                    score += 15
                    match_reasons.append("季节适宜")
            
            # 如果没有任何条件，给予基础分
            if not interests and not budget and not season:
                score = 50
            
            if score > 0:
                matched_cities.append({
                    "city": city_name,
                    "score": score,
                    "info": city_info,
                    "match_reasons": match_reasons
                })
        
        # 按分数排序
        matched_cities.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            "success": True,
            "cities": matched_cities,
            "count": len(matched_cities)
        }
    
    def query_attractions(self, cities: List[str]) -> Dict[str, Any]:
        """
        查询城市的景点信息
        
        Args:
            cities: 城市名称列表
            
        Returns:
            景点信息
        """
        result = {}
        
        for city_name in cities:
            city_info = self.config_manager.get_city_info(city_name)
            if city_info:
                result[city_name] = {
                    "attractions": city_info.get('attractions', []),
                    "avg_budget_per_day": city_info.get('avg_budget_per_day', 0),
                    "recommended_days": city_info.get('recommended_days', 3)
                }
        
        return {
            "success": True,
            "data": result,
            "cities_count": len(result)
        }
    
    def calculate_budget(self, city: str, days: int, 
                        include_accommodation: bool = True,
                        include_transportation: bool = True) -> Dict[str, Any]:
        """
        计算旅游预算
        
        Args:
            city: 城市名称
            days: 旅行天数
            include_accommodation: 是否包含住宿
            include_transportation: 是否包含交通
            
        Returns:
            预算估算
        """
        city_info = self.config_manager.get_city_info(city)
        if not city_info:
            return {
                "success": False,
                "error": f"未找到城市: {city}"
            }
        
        avg_daily = city_info.get('avg_budget_per_day', 400)
        attractions = city_info.get('attractions', [])
        
        # 计算门票费用
        ticket_total = sum(a.get('ticket', 0) for a in attractions)
        
        # 基础预算（餐饮+市内交通）
        meal_cost = avg_daily * 0.4 * days  # 餐饮约占40%
        local_transport = avg_daily * 0.2 * days  # 市内交通约占20%
        
        budget = {
            "tickets": ticket_total,
            "meals": int(meal_cost),
            "local_transportation": int(local_transport)
        }
        
        # 住宿费用
        if include_accommodation:
            accommodation = avg_daily * 0.3 * days  # 住宿约占30%
            budget['accommodation'] = int(accommodation)
        
        # 往返交通
        if include_transportation:
            inter_city_transport = 1000  # 简化估算
            budget['inter_city_transportation'] = inter_city_transport
        
        budget['total'] = sum(budget.values())
        budget['days'] = days
        budget['avg_per_day'] = int(budget['total'] / days)
        
        return {
            "success": True,
            "city": city,
            "budget": budget
        }
    
    def get_city_info(self, city: str) -> Dict[str, Any]:
        """
        获取城市详细信息
        
        Args:
            city: 城市名称
            
        Returns:
            城市信息
        """
        city_info = self.config_manager.get_city_info(city)
        if city_info:
            return {
                "success": True,
                "city": city,
                "info": city_info
            }
        else:
            return {
                "success": False,
                "error": f"未找到城市: {city}"
            }
    
    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具调用
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            执行结果
        """
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具不存在: {tool_name}"
            }
        
        try:
            return self.tools[tool_name](**kwargs)
        except Exception as e:
            return {
                "success": False,
                "error": f"工具执行失败: {str(e)}"
            }
