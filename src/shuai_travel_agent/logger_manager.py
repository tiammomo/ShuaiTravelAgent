"""
日志记录模块 (Logger Manager)
=============================

提供统一的日志记录功能，跟踪系统从输入到输出的完整数据流转。

核心功能：
1. 多级别日志记录（DEBUG, INFO, WARNING, ERROR, CRITICAL）
2. 完整的数据流转追踪
3. 性能指标记录
4. 结构化日志输出（支持JSON格式）
5. 自动日志文件轮转
6. 请求唯一标识（Trace ID）

版本：1.0.0
"""

import json
import logging
import sys
import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps
import threading


class LogLevel:
    """日志级别常量"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class TraceContext:
    """Trace上下文管理"""

    def __init__(self):
        self._local = threading.local()
        self._global_trace_id = None

    def get_trace_id(self) -> str:
        """获取当前Trace ID"""
        if hasattr(self._local, 'trace_id') and self._local.trace_id:
            return self._local.trace_id
        return self._global_trace_id or str(uuid.uuid4())[:8]

    def set_trace_id(self, trace_id: str):
        """设置当前Trace ID"""
        self._local.trace_id = trace_id

    def clear(self):
        """清除当前Trace上下文"""
        if hasattr(self._local, 'trace_id'):
            del self._local.trace_id

    def start_trace(self) -> str:
        """开始一个新的Trace，返回Trace ID"""
        trace_id = str(uuid.uuid4())[:8]
        self.set_trace_id(trace_id)
        return trace_id

    def end_trace(self):
        """结束当前Trace"""
        self.clear()


# 全局Trace上下文
trace_context = TraceContext()


class LoggerManager:
    """
    日志管理器

    提供统一的日志记录接口，支持结构化日志和完整的数据流转追踪。

    使用示例：
    ```python
    logger = LoggerManager.get_logger(__name__)
    logger.input("用户输入", {"message": "推荐城市"})
    logger.info("开始处理")
    logger.output("最终结果", {"answer": "推荐北京、上海..."})
    ```
    """

    _instance = None
    _loggers: Dict[str, logging.Logger] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._log_dir = "logs"
        self._log_file = os.path.join(self._log_dir, "app.log")
        self._trace_log_file = os.path.join(self._log_dir, "trace.log")
        self._json_log_file = os.path.join(self._log_dir, "structured.log")

        # 确保日志目录存在
        os.makedirs(self._log_dir, exist_ok=True)

        # 配置根日志器
        self._setup_root_logger()

    def _setup_root_logger(self):
        """配置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # 清除现有处理器
        root_logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # 文件处理器（普通日志）
        file_handler = logging.FileHandler(self._log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Trace日志处理器
        trace_handler = logging.FileHandler(self._trace_log_file, encoding='utf-8')
        trace_handler.setLevel(logging.DEBUG)
        trace_formatter = logging.Formatter(
            '%(asctime)s - [%(trace_id)s] - %(name)s - %(levelname)s - %(message)s'
        )
        trace_handler.setFormatter(trace_formatter)
        root_logger.addHandler(trace_handler)

    @classmethod
    def get_logger(cls, name: str) -> 'LoggerManager':
        """获取指定名称的日志器"""
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = LoggerWrapper(logger)
        return cls._loggers[name]

    def get_trace_logger(self, name: str) -> 'TraceLogger':
        """获取带Trace功能的日志器"""
        return TraceLogger(name)


class LoggerWrapper:
    """
    日志包装器

    提供便捷的日志方法，同时包含结构化数据记录功能。
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def debug(self, msg: str, **kwargs):
        """DEBUG级别日志"""
        extra = self._build_extra(**kwargs)
        self._logger.debug(msg, extra=extra)

    def info(self, msg: str, **kwargs):
        """INFO级别日志"""
        extra = self._build_extra(**kwargs)
        self._logger.info(msg, extra=extra)

    def warning(self, msg: str, **kwargs):
        """WARNING级别日志"""
        extra = self._build_extra(**kwargs)
        self._logger.warning(msg, extra=extra)

    def error(self, msg: str, **kwargs):
        """ERROR级别日志"""
        extra = self._build_extra(**kwargs)
        self._logger.error(msg, extra=extra)

    def critical(self, msg: str, **kwargs):
        """CRITICAL级别日志"""
        extra = self._build_extra(**kwargs)
        self._logger.critical(msg, extra=extra)

    def exception(self, msg: str, exc_info=True, **kwargs):
        """异常日志"""
        extra = self._build_extra(**kwargs)
        self._logger.exception(msg, exc_info=exc_info, extra=extra)

    def _build_extra(self, **kwargs) -> Dict[str, Any]:
        """构建extra字段"""
        trace_id = trace_context.get_trace_id()
        return {
            'trace_id': trace_id,
            'timestamp': datetime.now().isoformat(),
            **{k: self._format_value(v) for k, v in kwargs.items()}
        }

    def _format_value(self, value: Any) -> Any:
        """格式化值为可记录的形式"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return value

    # ============ 业务日志方法 ============

    def input(self, source: str, data: Dict[str, Any]):
        """记录输入数据"""
        self.info(f"[INPUT] 来源: {source}", input_data=data)

    def output(self, destination: str, data: Dict[str, Any]):
        """记录输出数据"""
        self.info(f"[OUTPUT] 目标: {destination}", output_data=data)

    def process_start(self, component: str, task: str):
        """记录处理开始"""
        self.info(f"[PROCESS START] 组件: {component}", task=task)

    def process_end(self, component: str, duration_ms: float, result: str):
        """记录处理结束"""
        self.info(f"[PROCESS END] 组件: {component}, 耗时: {duration_ms:.2f}ms", result=result)

    def flow(self, from_component: str, to_component: str, data: Any):
        """记录数据流转"""
        self.info(f"[FLOW] {from_component} -> {to_component}", flow_data=data)

    def state_change(self, component: str, old_state: str, new_state: str):
        """记录状态变化"""
        self.info(f"[STATE CHANGE] {component}: {old_state} -> {new_state}")

    def tool_call(self, tool_name: str, params: Dict[str, Any]):
        """记录工具调用"""
        self.info(f"[TOOL CALL] {tool_name}", tool_params=params)

    def tool_result(self, tool_name: str, success: bool, result: Any):
        """记录工具结果"""
        status = "SUCCESS" if success else "FAILED"
        self.info(f"[TOOL RESULT] {tool_name}: {status}", tool_result=result)

    def thinking(self, thought_type: str, content: str, confidence: float = 0.0):
        """记录思考过程"""
        self.info(f"[THINKING] {thought_type}", thinking_content=content, confidence=confidence)

    def reasoning_step(self, step: int, thought: str, action: str = None):
        """记录推理步骤"""
        self.info(f"[REASONING STEP {step}]", thought_content=thought, action=action)

    def error_detail(self, error_type: str, error_msg: str, traceback: str = None):
        """记录错误详情"""
        self.error(f"[ERROR] {error_type}", error_message=error_msg, error_traceback=traceback)


class TraceLogger:
    """
    Trace日志器

    提供完整的请求追踪能力，记录从输入到输出的完整数据流转。
    """

    def __init__(self, name: str):
        self._name = name
        self._logger = logging.getLogger(f"trace.{name}")

    def trace_request(self, request_id: str, user_input: str, context: Dict[str, Any] = None):
        """记录请求开始"""
        self._logger.info(
            f"[TRACE REQUEST] 请求ID: {request_id}",
            trace_id=request_id,
            event="request_start",
            user_input=user_input,
            context=context or {}
        )
        return request_id

    def trace_input_parsing(self, request_id: str, raw_input: str, parsed_data: Dict[str, Any]):
        """记录输入解析"""
        self._logger.info(
            f"[TRACE INPUT] 请求ID: {request_id}",
            trace_id=request_id,
            event="input_parsing",
            raw_input=raw_input,
            parsed_data=parsed_data
        )

    def trace_agent_start(self, request_id: str, task: str):
        """记录Agent开始处理"""
        self._logger.info(
            f"[TRACE AGENT START] 请求ID: {request_id}",
            trace_id=request_id,
            event="agent_start",
            task=task
        )

    def trace_reasoning(self, request_id: str, step: int, thought_type: str, content: str, confidence: float):
        """记录推理过程"""
        self._logger.info(
            f"[TRACE REASONING] 请求ID: {request_id}, 步骤: {step}",
            trace_id=request_id,
            event="reasoning",
            step=step,
            thought_type=thought_type,
            content=content,
            confidence=confidence
        )

    def trace_action(self, request_id: str, action_name: str, params: Dict[str, Any], status: str):
        """记录行动执行"""
        self._logger.info(
            f"[TRACE ACTION] 请求ID: {request_id}, 行动: {action_name}",
            trace_id=request_id,
            event="action",
            action_name=action_name,
            params=params,
            status=status
        )

    def trace_tool_call(self, request_id: str, tool_name: str, params: Dict[str, Any]):
        """记录工具调用"""
        self._logger.info(
            f"[TRACE TOOL] 请求ID: {request_id}, 工具: {tool_name}",
            trace_id=request_id,
            event="tool_call",
            tool_name=tool_name,
            params=params
        )

    def trace_tool_result(self, request_id: str, tool_name: str, success: bool, result: Any):
        """记录工具结果"""
        self._logger.info(
            f"[TRACE TOOL RESULT] 请求ID: {request_id}, 工具: {tool_name}, 成功: {success}",
            trace_id=request_id,
            event="tool_result",
            tool_name=tool_name,
            success=success,
            result=result
        )

    def trace_agent_end(self, request_id: str, success: bool, answer: str = None, error: str = None):
        """记录Agent处理结束"""
        self._logger.info(
            f"[TRACE AGENT END] 请求ID: {request_id}, 成功: {success}",
            trace_id=request_id,
            event="agent_end",
            success=success,
            answer=answer,
            error=error
        )

    def trace_output_format(self, request_id: str, raw_output: str, formatted_output: str):
        """记录输出格式化"""
        self._logger.info(
            f"[TRACE OUTPUT] 请求ID: {request_id}",
            trace_id=request_id,
            event="output_format",
            raw_output=raw_output,
            formatted_output=formatted_output
        )

    def trace_request_end(self, request_id: str, total_duration_ms: float, success: bool):
        """记录请求完成"""
        self._logger.info(
            f"[TRACE REQUEST END] 请求ID: {request_id}, 总耗时: {total_duration_ms:.2f}ms, 成功: {success}",
            trace_id=request_id,
            event="request_end",
            total_duration_ms=total_duration_ms,
            success=success
        )

    def trace_error(self, request_id: str, error_type: str, error_msg: str, stack_trace: str = None):
        """记录错误"""
        self._logger.error(
            f"[TRACE ERROR] 请求ID: {request_id}, 错误: {error_type}",
            trace_id=request_id,
            event="error",
            error_type=error_type,
            error_msg=error_msg,
            stack_trace=stack_trace
        )


class StructuredLogger:
    """
    结构化JSON日志器

    用于生成符合特定格式的JSON日志，便于后续分析和处理。
    """

    def __init__(self, name: str = "structured"):
        self._name = name
        self._log_file = "logs/structured.log"

    def log(self, event_type: str, data: Dict[str, Any]):
        """记录结构化日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_context.get_trace_id(),
            "event_type": event_type,
            "data": data
        }

        with open(self._log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def log_request_start(self, request_id: str, input_data: Dict[str, Any]):
        """记录请求开始"""
        self.log("REQUEST_START", {
            "request_id": request_id,
            "input": input_data
        })

    def log_request_end(self, request_id: str, output_data: Dict[str, Any], success: bool, duration_ms: float):
        """记录请求结束"""
        self.log("REQUEST_END", {
            "request_id": request_id,
            "output": output_data,
            "success": success,
            "duration_ms": duration_ms
        })


def log_execution_time(logger_name: str = __name__):
    """函数执行时间装饰器"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = LoggerManager.get_logger(logger_name)
            start_time = time.time()
            logger.process_start(func.__name__, "function")
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.process_end(func.__name__, duration_ms, "success")
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.process_end(func.__name__, duration_ms, f"error: {str(e)}")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = LoggerManager.get_logger(logger_name)
            start_time = time.time()
            logger.process_start(func.__name__, "function")
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.process_end(func.__name__, duration_ms, "success")
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.process_end(func.__name__, duration_ms, f"error: {str(e)}")
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# 获取全局日志器实例的便捷函数
def get_logger(name: str) -> LoggerWrapper:
    """获取日志器实例"""
    return LoggerManager.get_logger(name)


def get_trace_logger(name: str) -> TraceLogger:
    """获取Trace日志器实例"""
    return LoggerManager.get_trace_logger(name)


def get_structured_logger(name: str = "structured") -> StructuredLogger:
    """获取结构化日志器实例"""
    return StructuredLogger(name)


def start_trace() -> str:
    """开始一个新的Trace"""
    return trace_context.start_trace()


def end_trace():
    """结束当前Trace"""
    trace_context.end_trace()


def with_trace(func):
    """带Trace上下文的函数装饰器"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_trace()
        try:
            return await func(*args, **kwargs)
        finally:
            end_trace()

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_trace()
        try:
            return func(*args, **kwargs)
        finally:
            end_trace()

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
