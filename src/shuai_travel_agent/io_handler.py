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
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from .logger_manager import LoggerManager, get_logger, get_trace_logger, trace_context


class InputParser:
    """输入解析器：处理用户输入的解析和验证"""

    _logger = LoggerManager.get_logger("io_handler.input_parser")

    @staticmethod
    def parse_text(text: str) -> Dict[str, Any]:
        """
        解析文本输入

        Args:
            text: 用户输入文本

        Returns:
            解析结果
        """
        trace_id = trace_context.get_trace_id()
        InputParser._logger.info(
            f"[{trace_id}] 解析文本输入",
            input_length=len(text),
            input_preview=text[:100] if text else ""
        )

        result = {
            "type": "text",
            "content": text.strip(),
            "length": len(text.strip()),
            "timestamp": datetime.now().isoformat()
        }

        InputParser._logger.debug(
            f"[{trace_id}] 文本解析完成",
            parsed_result=result
        )

        return result

    @staticmethod
    def parse_json(json_str: str) -> Dict[str, Any]:
        """
        解析JSON输入

        Args:
            json_str: JSON字符串

        Returns:
            解析结果
        """
        trace_id = trace_context.get_trace_id()
        InputParser._logger.info(
            f"[{trace_id}] 解析JSON输入",
            input_length=len(json_str)
        )

        try:
            data = json.loads(json_str)
            result = {
                "type": "json",
                "content": data,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
            InputParser._logger.debug(
                f"[{trace_id}] JSON解析成功",
                parsed_keys=list(data.keys()) if isinstance(data, dict) else []
            )
            return result
        except json.JSONDecodeError as e:
            result = {
                "type": "json",
                "content": None,
                "error": f"JSON解析失败: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
            InputParser._logger.error(
                f"[{trace_id}] JSON解析失败",
                error=str(e)
            )
            return result

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
        trace_id = trace_context.get_trace_id()
        InputParser._logger.info(
            f"[{trace_id}] 验证输入",
            input_length=len(text),
            max_length=max_length
        )

        if not text or not text.strip():
            InputParser._logger.warning(f"[{trace_id}] 输入为空")
            return False, "输入不能为空"

        if len(text) > max_length:
            InputParser._logger.warning(
                f"[{trace_id}] 输入长度超过限制",
                input_length=len(text),
                max_length=max_length
            )
            return False, f"输入长度超过限制({max_length}字符)"

        # 检查是否包含危险字符（防止注入攻击）
        dangerous_patterns = [
            r'<script.*?>',
            r'javascript:',
            r'on\w+\s*=',
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                InputParser._logger.warning(
                    f"[{trace_id}] 检测到危险字符",
                    pattern=pattern
                )
                return False, "输入包含不安全内容"

        InputParser._logger.debug(f"[{trace_id}] 输入验证通过")
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
        trace_id = trace_context.get_trace_id()
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

        InputParser._logger.debug(
            f"[{trace_id}] 意图关键词提取完成",
            keywords=keywords
        )

        return keywords


class OutputFormatter:
    """输出格式化器：格式化各类输出结果"""

    _logger = LoggerManager.get_logger("io_handler.output_formatter")

    @staticmethod
    def format_city_recommendation(data: Dict[str, Any]) -> str:
        """
        格式化城市推荐结果

        Args:
            data: 推荐数据

        Returns:
            格式化后的文本
        """
        trace_id = trace_context.get_trace_id()
        OutputFormatter._logger.info(
            f"[{trace_id}] 格式化城市推荐结果",
            data_keys=list(data.keys()) if data else []
        )

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

        result = "\n".join(output) if output else "暂无推荐结果"
        OutputFormatter._logger.debug(
            f"[{trace_id}] 城市推荐格式化完成",
            result_length=len(result),
            city_count=len(recommendations)
        )

        return result

    @staticmethod
    def format_attractions(data: Dict[str, Any]) -> str:
        """
        格式化景点信息

        Args:
            data: 景点数据

        Returns:
            格式化后的文本
        """
        trace_id = trace_context.get_trace_id()
        OutputFormatter._logger.info(
            f"[{trace_id}] 格式化景点信息",
            cities=list(data.keys()) if data else []
        )

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

        result = "\n".join(output) if output else "暂无景点信息"
        OutputFormatter._logger.debug(
            f"[{trace_id}] 景点信息格式化完成",
            result_length=len(result)
        )

        return result

    @staticmethod
    def format_route_plan(data: Dict[str, Any]) -> str:
        """
        格式化路线规划

        Args:
            data: 路线规划数据

        Returns:
            格式化后的文本
        """
        trace_id = trace_context.get_trace_id()
        OutputFormatter._logger.info(
            f"[{trace_id}] 格式化路线规划",
            data_keys=list(data.keys()) if data else []
        )

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

        result = "\n".join(output) if output else "暂无路线规划"
        OutputFormatter._logger.debug(
            f"[{trace_id}] 路线规划格式化完成",
            result_length=len(result),
            days=len(route_plan)
        )

        return result

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
        trace_id = trace_context.get_trace_id()
        error_messages = {
            "validation": "输入验证失败",
            "network": "网络连接错误",
            "timeout": "请求超时",
            "api": "API调用失败",
            "parsing": "结果解析失败",
            "general": "处理失败"
        }

        prefix = error_messages.get(error_type, "处理失败")
        result = f"❌ {prefix}: {error}"

        OutputFormatter._logger.warning(
            f"[{trace_id}] 错误格式化",
            error_type=error_type,
            error_message=error
        )

        return result

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

    _logger = LoggerManager.get_logger("io_handler.response_builder")

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
        trace_id = trace_context.get_trace_id()
        ResponseBuilder._logger.info(
            f"[{trace_id}] 构建成功响应",
            has_message=bool(message),
            has_metadata=bool(metadata)
        )

        response = {
            "success": True,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

        if message:
            response["message"] = message

        if metadata:
            response["metadata"] = metadata

        ResponseBuilder._logger.debug(
            f"[{trace_id}] 成功响应构建完成",
            response_keys=list(response.keys())
        )

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
        trace_id = trace_context.get_trace_id()
        ResponseBuilder._logger.warning(
            f"[{trace_id}] 构建错误响应",
            error_code=error_code,
            error_message=error[:200] if error else ""
        )

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
        trace_id = trace_context.get_trace_id()
        ResponseBuilder._logger.info(
            f"[{trace_id}] 构建聊天响应",
            success=success,
            intent=intent,
            response_length=len(response_text) if response_text else 0
        )

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

        ResponseBuilder._logger.debug(
            f"[{trace_id}] 聊天响应构建完成",
            response_keys=list(response.keys())
        )

        return response


class IOHandler:
    """IO处理器：整合输入解析和输出格式化功能"""

    _logger = LoggerManager.get_logger("io_handler")

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
        trace_id = trace_context.get_trace_id()
        IOHandler._logger.input(
            "用户输入",
            {
                "trace_id": trace_id,
                "input_preview": user_input[:100] + "..." if len(user_input) > 100 else user_input,
                "input_length": len(user_input),
                "validate": validate
            }
        )

        start_time = time.time()

        # 验证输入
        if validate:
            valid, error_msg = self.input_parser.validate_input(user_input)
            if not valid:
                IOHandler._logger.flow(
                    "InputParser",
                    "ResponseBuilder",
                    {"status": "validation_failed", "error": error_msg}
                )
                return self.response_builder.build_error_response(
                    error_msg,
                    error_code="INVALID_INPUT"
                )

        # 解析输入
        parsed = self.input_parser.parse_text(user_input)

        # 提取关键词
        keywords = self.input_parser.extract_intent_keywords(user_input)
        parsed['keywords'] = keywords

        duration_ms = (time.time() - start_time) * 1000
        IOHandler._logger.flow(
            "InputParser",
            "ResponseBuilder",
            {"status": "success", "keywords": keywords, "duration_ms": duration_ms}
        )

        IOHandler._logger.process_end(
            "IOHandler.process_input",
            duration_ms,
            "success"
        )

        return self.response_builder.build_success_response(parsed)

    def format_agent_result(self, result: Dict[str, Any]) -> str:
        """
        格式化Agent执行结果

        Args:
            result: Agent返回的结果

        Returns:
            格式化后的文本
        """
        trace_id = trace_context.get_trace_id()
        IOHandler._logger.flow(
            "Agent",
            "OutputFormatter",
            {
                "trace_id": trace_id,
                "success": result.get('success', False),
                "has_data": 'data' in result
            }
        )

        if not result.get('success'):
            error = result.get('error', '未知错误')
            IOHandler._logger.warning(
                f"[{trace_id}] Agent执行失败",
                error=error
            )
            return self.output_formatter.format_error(error)

        intent = result.get('intent', '')
        data = result.get('data', {})

        # 根据意图类型格式化
        if intent == 'city_recommendation':
            formatted = self.output_formatter.format_city_recommendation(data)
        elif intent == 'attraction_query':
            formatted = self.output_formatter.format_attractions(data)
        elif intent == 'route_planning':
            formatted = self.output_formatter.format_route_plan(data)
        else:
            # 默认返回response字段
            formatted = result.get('response', '处理完成')

        IOHandler._logger.output(
            "OutputFormatter",
            {
                "trace_id": trace_id,
                "intent": intent,
                "formatted_length": len(formatted)
            }
        )

        return formatted

    def build_api_response(self, agent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建API响应（用于FastAPI）

        Args:
            agent_result: Agent处理结果

        Returns:
            API响应字典
        """
        trace_id = trace_context.get_trace_id()
        IOHandler._logger.info(
            f"[{trace_id}] 构建API响应",
            success=agent_result.get('success', False)
        )

        success = agent_result.get('success', False)

        # 格式化响应文本
        if success:
            response_text = self.format_agent_result(agent_result)
        else:
            response_text = agent_result.get('error', '处理失败')

        response = self.response_builder.build_chat_response(
            success=success,
            response_text=response_text,
            intent=agent_result.get('intent'),
            data=agent_result.get('data'),
            error=agent_result.get('error')
        )

        IOHandler._logger.output(
            "ResponseBuilder",
            {
                "trace_id": trace_id,
                "response_keys": list(response.keys()),
                "success": success
            }
        )

        return response
    
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
