"""
Agent主体类
职责：
1. 协调各模块工作
2. 执行完整的感知-推理-行动循环
3. 管理Agent生命周期
"""

from typing import Dict, Any, Optional
from .config_manager import ConfigManager
from .memory_manager import MemoryManager
from .llm_client import LLMClient
from .reasoner import Reasoner, IntentType
from .environment import Environment


class TravelAgent:
    """旅游助手Agent：协调各模块完成旅游推荐和规划"""

    def __init__(self, config_path: str = "config/config.json", model_config: Optional[str] = None):
        """
        初始化Agent

        Args:
            config_path: 配置文件路径
            model_config: 可选的模型ID，如果提供则使用指定模型
        """
        # 初始化各模块
        self.config_manager = ConfigManager(config_path)

        memory_config = self.config_manager.get_config('memory', {})
        self.memory_manager = MemoryManager(
            max_working_memory=memory_config.get('max_working_memory', 10),
            max_long_term_memory=memory_config.get('max_long_term_memory', 50)
        )

        # 如果指定了模型ID，使用指定模型的配置
        llm_config = self.config_manager.get_llm_config(model_config)
        self.llm_client = LLMClient(llm_config)
        
        self.reasoner = Reasoner()
        self.environment = Environment(self.config_manager)
        
        # Agent状态
        self.running = False
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户输入（核心循环：Perception → Reasoning → Action）
        
        Args:
            user_input: 用户输入
            
        Returns:
            处理结果
        """
        try:
            # === 1. 感知阶段 ===
            # 添加用户消息到记忆
            self.memory_manager.add_message('user', user_input)
            
            # === 2. 推理阶段 ===
            # 意图识别
            intent = self.reasoner.recognize_intent(user_input)
            
            # 参数提取
            params = self.reasoner.extract_parameters(user_input)
            
            # 生成执行计划
            context = {
                'user_query': user_input,
                'last_recommended_cities': self.memory_manager.get_session_state('last_recommended_cities', []),
                'user_preference': self.memory_manager.get_user_preference()
            }
            plan = self.reasoner.generate_action_plan(intent, params, context)
            
            # 验证计划
            valid, error_msg = self.reasoner.validate_plan(plan)
            if not valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "intent": intent.value
                }
            
            # === 3. 行动阶段 ===
            result = self._execute_plan(plan, user_input)
            
            # 添加助手回复到记忆
            if result.get('success') and result.get('response'):
                self.memory_manager.add_message('assistant', result['response'])
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "error": f"处理失败: {str(e)}"
            }
    
    def _execute_plan(self, plan: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """
        执行计划
        
        Args:
            plan: 执行计划
            user_input: 用户输入
            
        Returns:
            执行结果
        """
        intent = plan['intent']
        actions = plan['actions']
        
        if intent == IntentType.CITY_RECOMMENDATION.value:
            return self._handle_city_recommendation(actions, user_input)
        
        elif intent == IntentType.ATTRACTION_QUERY.value:
            return self._handle_attraction_query(actions)
        
        elif intent == IntentType.ROUTE_PLANNING.value:
            return self._handle_route_planning(actions, user_input)
        
        elif intent == IntentType.PREFERENCE_UPDATE.value:
            return self._handle_preference_update(actions)
        
        else:  # GENERAL_CHAT
            return self._handle_general_chat(user_input)
    
    def _handle_city_recommendation(self, actions: list, user_input: str) -> Dict[str, Any]:
        """处理城市推荐"""
        # 步骤1：搜索匹配城市
        search_action = next((a for a in actions if a['type'] == 'search_cities'), None)
        if search_action:
            search_result = self.environment.execute_tool('search_cities', **search_action['params'])
            
            if not search_result.get('success'):
                return search_result
            
            matched_cities = search_result.get('cities', [])
            available_cities = [c['city'] for c in matched_cities[:10]]  # 限制10个
        else:
            available_cities = self.config_manager.get_all_cities()
        
        # 步骤2：调用LLM生成推荐
        context = self.memory_manager.get_context_summary()
        llm_result = self.llm_client.generate_travel_recommendation(
            user_input,
            context,
            available_cities
        )
        
        if not llm_result.get('success'):
            return llm_result
        
        # 解析推荐结果
        recommendations = llm_result.get('recommendations', {})
        recommended_cities = [r['city'] for r in recommendations.get('recommendations', [])]
        
        # 更新会话状态
        self.memory_manager.update_session_state('last_recommended_cities', recommended_cities)
        
        return {
            "success": True,
            "intent": "city_recommendation",
            "data": recommendations,
            "response": self._format_city_recommendation(recommendations)
        }
    
    def _handle_attraction_query(self, actions: list) -> Dict[str, Any]:
        """处理景点查询"""
        query_action = next((a for a in actions if a['type'] == 'query_attractions'), None)
        if not query_action:
            return {"success": False, "error": "缺少查询参数"}
        
        cities = query_action['params'].get('cities', [])
        if not cities:
            return {"success": False, "error": "请先选择或推荐城市"}
        
        result = self.environment.execute_tool('query_attractions', cities=cities)
        
        if result.get('success'):
            result['response'] = self._format_attractions(result.get('data', {}))
        
        return result
    
    def _handle_route_planning(self, actions: list, user_input: str) -> Dict[str, Any]:
        """处理路线规划"""
        route_action = next((a for a in actions if a['type'] == 'generate_route'), None)
        if not route_action:
            return {"success": False, "error": "缺少规划参数"}
        
        city = route_action['params'].get('city')
        days = route_action['params'].get('days', 3)
        
        if not city:
            return {"success": False, "error": "请先指定城市"}
        
        # 获取城市景点信息
        city_info = self.config_manager.get_city_info(city)
        if not city_info:
            return {"success": False, "error": f"未找到城市: {city}"}
        
        attractions = city_info.get('attractions', [])
        user_preference = self.memory_manager.get_context_summary()
        
        # 调用LLM生成路线规划
        result = self.llm_client.generate_route_plan(
            city, days, attractions, user_preference
        )
        
        if result.get('success'):
            route_plan = result.get('route_plan', {})
            self.memory_manager.update_session_state('current_plan', route_plan)
            result['response'] = self._format_route_plan(route_plan)
        
        return result
    
    def _handle_preference_update(self, actions: list) -> Dict[str, Any]:
        """处理偏好更新"""
        update_action = next((a for a in actions if a['type'] == 'update_preference'), None)
        if update_action:
            params = update_action['params']
            current_pref = self.memory_manager.get_user_preference()
            
            # 合并更新
            if params.get('budget'):
                current_pref['budget_range'] = params['budget']
            if params.get('days'):
                current_pref['travel_days'] = params['days']
            if params.get('interests'):
                current_pref['interest_tags'].extend(params['interests'])
            
            self.memory_manager.set_user_preference(current_pref)
        
        return {
            "success": True,
            "response": "好的，我已记录您的偏好！"
        }
    
    def _handle_general_chat(self, user_input: str) -> Dict[str, Any]:
        """处理一般对话"""
        # 获取对话历史
        history = self.memory_manager.get_messages_for_llm(limit=5)
        context = self.memory_manager.get_context_summary()
        
        result = self.llm_client.chat_with_context(history, context)
        
        if result.get('success'):
            result['response'] = result.get('content', '')
        
        return result
    
    def _format_city_recommendation(self, recommendations: Dict[str, Any]) -> str:
        """格式化城市推荐结果"""
        output = []
        output.append(recommendations.get('explanation', ''))
        output.append("\n推荐城市：")
        
        for i, rec in enumerate(recommendations.get('recommendations', []), 1):
            output.append(f"\n{i}. {rec['city']} (匹配度: {rec['match_score']}%)")
            output.append(f"   {rec['reason']}")
        
        return "\n".join(output)
    
    def _format_attractions(self, data: Dict[str, Any]) -> str:
        """格式化景点信息"""
        output = []
        
        for city, info in data.items():
            output.append(f"\n【{city}】")
            output.append(f"推荐游玩天数：{info['recommended_days']}天")
            output.append(f"平均每日预算：{info['avg_budget_per_day']}元")
            output.append("\n主要景点：")
            
            for i, attr in enumerate(info['attractions'], 1):
                output.append(f"{i}. {attr['name']} - {attr['type']}")
                output.append(f"   建议游玩：{attr['duration']}小时，门票：{attr['ticket']}元")
        
        return "\n".join(output)
    
    def _format_route_plan(self, route_plan: Dict[str, Any]) -> str:
        """格式化路线规划"""
        output = []
        output.append("为您定制的旅游路线：\n")
        
        for day_plan in route_plan.get('route_plan', []):
            output.append(f"第{day_plan['day']}天：")
            output.append(f"  景点：{', '.join(day_plan['attractions'])}")
            output.append(f"  行程：{day_plan['schedule']}")
            if day_plan.get('tips'):
                output.append(f"  提示：{day_plan['tips']}")
            output.append("")
        
        # 费用估算
        cost = route_plan.get('total_cost_estimate', {})
        if cost:
            output.append("费用估算：")
            output.append(f"  门票：{cost.get('tickets', 0)}元")
            output.append(f"  餐饮：{cost.get('meals', 0)}元")
            output.append(f"  交通：{cost.get('transportation', 0)}元")
            output.append(f"  总计：约{cost.get('total', 0)}元")
        
        # 旅行建议
        tips = route_plan.get('travel_tips', [])
        if tips:
            output.append("\n旅行建议：")
            for tip in tips:
                output.append(f"  • {tip}")
        
        return "\n".join(output)
    
    def get_conversation_history(self) -> list:
        """获取对话历史"""
        return self.memory_manager.get_conversation_history()
    
    def clear_conversation(self) -> None:
        """清空当前会话"""
        self.memory_manager.clear_conversation()
