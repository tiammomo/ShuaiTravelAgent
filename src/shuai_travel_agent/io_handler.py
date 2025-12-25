"""
输入输出处理模块 (IO Handler)
职责：
1. 解析和验证用户输入
2. 格式化Agent输出结果
3. 提供结构化数据转换
4. 预留MCP协议适配接口
"""

import json
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime


class InputParser:
    """输入解析器：处理用户输入的解析和验证"""
    
    @staticmethod
    def parse_text(text: str) -> Dict[str, Any]:
        """
        解析文本输入
        
        Args:
            text: 用户输入文本
            
        Returns:
            解析结果
        """
        return {
            "type": "text",
            "content": text.strip(),
            "length": len(text.strip()),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def parse_json(json_str: str) -> Dict[str, Any]:
        """
        解析JSON输入
        
        Args:
            json_str: JSON字符串
            
        Returns:
            解析结果
        """
        try:
            data = json.loads(json_str)
            return {
                "type": "json",
                "content": data,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
        except json.JSONDecodeError as e:
            return {
                "type": "json",
                "content": None,
                "error": f"JSON解析失败: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    @staticmethod
    def validate_input(text: str, max_length: int = 500) -> tuple[bool, str]:
        """
        验证输入有效性
        
        Args:
            text: 输入文本
            max_length: 最大长度限制
            
        Returns:
            (是否有效, 错误信息)
        """
        if not text or not text.strip():
            return False, "输入不能为空"
        
        if len(text) > max_length:
            return False, f"输入长度超过限制({max_length}字符)"
        
        # 检查是否包含危险字符（防止注入攻击）
        dangerous_patterns = [
            r'<script.*?>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "输入包含不安全内容"
        
        return True, ""
    
    @staticmethod
    def extract_intent_keywords(text: str) -> List[str]:
        """
        提取意图关键词（用于日志记录）
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        keywords = []
        
        # 城市推荐关键词
        if re.search(r'推荐|去哪|旅游', text):
            keywords.append("city_recommendation")
        
        # 景点查询关键词
        if re.search(r'景点|好玩|游览', text):
            keywords.append("attraction_query")
        
        # 路线规划关键词
        if re.search(r'路线|规划|行程', text):
            keywords.append("route_planning")
        
        # 预算关键词
        if re.search(r'预算|花费|费用', text):
            keywords.append("budget_related")
        
        return keywords


class OutputFormatter:
    """输出格式化器：格式化各类输出结果"""
    
    @staticmethod
    def format_city_recommendation(data: Dict[str, Any]) -> str:
        """
        格式化城市推荐结果
        
        Args:
            data: 推荐数据
            
        Returns:
            格式化后的文本
        """
        output = []
        
        # 添加整体说明
        if data.get('explanation'):
            output.append(data['explanation'])
            output.append("")
        
        # 添加推荐城市列表
        recommendations = data.get('recommendations', [])
        if recommendations:
            output.append("推荐城市：")
            for i, rec in enumerate(recommendations, 1):
                city = rec.get('city', '未知')
                score = rec.get('match_score', 0)
                reason = rec.get('reason', '')
                
                output.append(f"\n{i}. {city} (匹配度: {score}%)")
                if reason:
                    output.append(f"   推荐理由: {reason}")
        
        return "\n".join(output) if output else "暂无推荐结果"
    
    @staticmethod
    def format_attractions(data: Dict[str, Any]) -> str:
        """
        格式化景点信息
        
        Args:
            data: 景点数据
            
        Returns:
            格式化后的文本
        """
        output = []
        
        for city, info in data.items():
            output.append(f"\n【{city}】")
            output.append(f"推荐游玩天数: {info.get('recommended_days', 3)}天")
            output.append(f"平均每日预算: {info.get('avg_budget_per_day', 0)}元")
            output.append("\n主要景点:")
            
            attractions = info.get('attractions', [])
            for i, attr in enumerate(attractions, 1):
                name = attr.get('name', '未知景点')
                attr_type = attr.get('type', '未分类')
                duration = attr.get('duration', 0)
                ticket = attr.get('ticket', 0)
                
                output.append(f"{i}. {name} - {attr_type}")
                output.append(f"   建议游玩: {duration}小时, 门票: {ticket}元")
        
        return "\n".join(output) if output else "暂无景点信息"
    
    @staticmethod
    def format_route_plan(data: Dict[str, Any]) -> str:
        """
        格式化路线规划
        
        Args:
            data: 路线规划数据
            
        Returns:
            格式化后的文本
        """
        output = []
        output.append("为您定制的旅游路线：\n")
        
        # 每日行程
        route_plan = data.get('route_plan', [])
        for day_plan in route_plan:
            day = day_plan.get('day', 0)
            attractions = day_plan.get('attractions', [])
            schedule = day_plan.get('schedule', '')
            tips = day_plan.get('tips', '')
            
            output.append(f"第{day}天:")
            if attractions:
                output.append(f"  景点: {', '.join(attractions)}")
            if schedule:
                output.append(f"  行程: {schedule}")
            if tips:
                output.append(f"  提示: {tips}")
            output.append("")
        
        # 费用估算
        cost = data.get('total_cost_estimate', {})
        if cost:
            output.append("费用估算:")
            if 'tickets' in cost:
                output.append(f"  门票: {cost['tickets']}元")
            if 'meals' in cost:
                output.append(f"  餐饮: {cost['meals']}元")
            if 'transportation' in cost:
                output.append(f"  交通: {cost['transportation']}元")
            if 'total' in cost:
                output.append(f"  总计: 约{cost['total']}元")
            output.append("")
        
        # 旅行建议
        tips = data.get('travel_tips', [])
        if tips:
            output.append("旅行建议:")
            for tip in tips:
                output.append(f"  • {tip}")
        
        return "\n".join(output) if output else "暂无路线规划"
    
    @staticmethod
    def format_error(error: str, error_type: str = "general") -> str:
        """
        格式化错误信息
        
        Args:
            error: 错误信息
            error_type: 错误类型
            
        Returns:
            格式化后的错误信息
        """
        error_messages = {
            "validation": "输入验证失败",
            "network": "网络连接错误",
            "timeout": "请求超时",
            "api": "API调用失败",
            "parsing": "结果解析失败",
            "general": "处理失败"
        }
        
        prefix = error_messages.get(error_type, "处理失败")
        return f"❌ {prefix}: {error}"
    
    @staticmethod
    def format_success(message: str) -> str:
        """
        格式化成功信息
        
        Args:
            message: 成功信息
            
        Returns:
            格式化后的成功信息
        """
        return f"✓ {message}"
    
    @staticmethod
    def format_json(data: Any, indent: int = 2) -> str:
        """
        格式化JSON输出
        
        Args:
            data: 数据对象
            indent: 缩进空格数
            
        Returns:
            JSON字符串
        """
        return json.dumps(data, ensure_ascii=False, indent=indent)
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
        """
        截断长文本
        
        Args:
            text: 文本
            max_length: 最大长度
            suffix: 后缀
            
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix


class ResponseBuilder:
    """响应构建器：构建标准化的API响应"""
    
    @staticmethod
    def build_success_response(data: Any, message: str = None, 
                               metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        构建成功响应
        
        Args:
            data: 响应数据
            message: 提示信息
            metadata: 元数据
            
        Returns:
            响应字典
        """
        response = {
            "success": True,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if message:
            response["message"] = message
        
        if metadata:
            response["metadata"] = metadata
        
        return response
    
    @staticmethod
    def build_error_response(error: str, error_code: str = None,
                            details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        构建错误响应
        
        Args:
            error: 错误信息
            error_code: 错误代码
            details: 错误详情
            
        Returns:
            响应字典
        """
        response = {
            "success": False,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        if error_code:
            response["error_code"] = error_code
        
        if details:
            response["details"] = details
        
        return response
    
    @staticmethod
    def build_chat_response(success: bool, response_text: str,
                           intent: str = None, data: Dict[str, Any] = None,
                           error: str = None) -> Dict[str, Any]:
        """
        构建聊天响应（用于API）
        
        Args:
            success: 是否成功
            response_text: 响应文本
            intent: 识别的意图
            data: 附加数据
            error: 错误信息
            
        Returns:
            响应字典
        """
        response = {
            "success": success,
            "response": response_text,
            "timestamp": datetime.now().isoformat()
        }
        
        if intent:
            response["intent"] = intent
        
        if data:
            response["data"] = data
        
        if error:
            response["error"] = error
        
        return response


class IOHandler:
    """IO处理器：整合输入解析和输出格式化功能"""
    
    def __init__(self):
        """初始化IO处理器"""
        self.input_parser = InputParser()
        self.output_formatter = OutputFormatter()
        self.response_builder = ResponseBuilder()
    
    def process_input(self, user_input: str, validate: bool = True) -> Dict[str, Any]:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入
            validate: 是否验证
            
        Returns:
            处理结果
        """
        # 验证输入
        if validate:
            valid, error_msg = self.input_parser.validate_input(user_input)
            if not valid:
                return self.response_builder.build_error_response(
                    error_msg,
                    error_code="INVALID_INPUT"
                )
        
        # 解析输入
        parsed = self.input_parser.parse_text(user_input)
        
        # 提取关键词
        keywords = self.input_parser.extract_intent_keywords(user_input)
        parsed['keywords'] = keywords
        
        return self.response_builder.build_success_response(parsed)
    
    def format_agent_result(self, result: Dict[str, Any]) -> str:
        """
        格式化Agent执行结果
        
        Args:
            result: Agent返回的结果
            
        Returns:
            格式化后的文本
        """
        if not result.get('success'):
            error = result.get('error', '未知错误')
            return self.output_formatter.format_error(error)
        
        intent = result.get('intent', '')
        data = result.get('data', {})
        
        # 根据意图类型格式化
        if intent == 'city_recommendation':
            return self.output_formatter.format_city_recommendation(data)
        
        elif intent == 'attraction_query':
            return self.output_formatter.format_attractions(data)
        
        elif intent == 'route_planning':
            return self.output_formatter.format_route_plan(data)
        
        else:
            # 默认返回response字段
            return result.get('response', '处理完成')
    
    def build_api_response(self, agent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建API响应（用于FastAPI）
        
        Args:
            agent_result: Agent处理结果
            
        Returns:
            API响应字典
        """
        success = agent_result.get('success', False)
        
        # 格式化响应文本
        if success:
            response_text = self.format_agent_result(agent_result)
        else:
            response_text = agent_result.get('error', '处理失败')
        
        return self.response_builder.build_chat_response(
            success=success,
            response_text=response_text,
            intent=agent_result.get('intent'),
            data=agent_result.get('data'),
            error=agent_result.get('error')
        )
    
    # ========== MCP协议扩展预留接口 ==========
    
    def encode_to_mcp_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        编码为MCP协议格式（预留接口）
        
        Args:
            data: 数据
            
        Returns:
            MCP格式数据
        """
        # TODO: 实现MCP协议格式转换
        # MCP消息格式示例：
        # {
        #     "jsonrpc": "2.0",
        #     "id": "xxx",
        #     "method": "tools/call",
        #     "params": {
        #         "name": "tool_name",
        #         "arguments": {...}
        #     }
        # }
        return data
    
    def decode_from_mcp_format(self, mcp_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从MCP协议格式解码（预留接口）
        
        Args:
            mcp_data: MCP格式数据
            
        Returns:
            解码后的数据
        """
        # TODO: 实现MCP协议格式解析
        return mcp_data
    
    def format_for_streaming(self, text: str, chunk_size: int = 50) -> List[str]:
        """
        格式化为流式输出（预留接口）
        
        Args:
            text: 文本
            chunk_size: 分块大小
            
        Returns:
            文本块列表
        """
        # 按句子分割
        sentences = re.split(r'([。！？\n])', text)
        chunks = []
        current_chunk = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
            
            if len(current_chunk) + len(sentence) + len(punctuation) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence + punctuation
            else:
                current_chunk += sentence + punctuation
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
