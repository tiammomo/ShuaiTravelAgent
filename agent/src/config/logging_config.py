"""
================================================================================
统一日志配置模块
================================================================================

提供标准化的日志配置，支持：
- 统一日志格式（时间戳、级别、模块、线程、消息）
- 多输出目标（控制台、文件、错误日志）
- 日志轮转（防止日志文件过大）
- 多环境配置（开发、测试、生产）
- 请求追踪（X-Request-ID）

使用示例：
    from config.logging_config import setup_logging, get_logger

    logger = get_logger(__name__)
    setup_logging(level="INFO", log_dir="logs")

    logger.info("用户操作", extra={"user_id": "123"})

================================================================================
"""

import os
import sys
import json
import logging
import logging.config
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps


# =============================================================================
# 日志级别定义
# =============================================================================

class LogLevel:
    """
    日志级别常量

    使用场景：
    - DEBUG: 调试信息，开发环境详细追踪
    - INFO: 正常运行信息，记录关键业务流程
    - WARNING: 警告信息，不影响程序运行但值得关注
    - ERROR: 错误信息，操作失败但系统仍可运行
    - CRITICAL: 严重错误，系统级故障
    """

    DEBUG = logging.DEBUG      # 10
    INFO = logging.INFO        # 20
    WARNING = logging.WARNING  # 30
    ERROR = logging.ERROR      # 40
    CRITICAL = logging.CRITICAL  # 50


# 日志级别名称映射
LOG_LEVEL_MAP = {
    "DEBUG": LogLevel.DEBUG,
    "INFO": LogLevel.INFO,
    "WARNING": LogLevel.WARNING,
    "WARN": LogLevel.WARNING,
    "ERROR": LogLevel.ERROR,
    "CRITICAL": LogLevel.CRITICAL,
}


# =============================================================================
# 日志格式配置
# =============================================================================

# 标准格式（控制台输出）- 增强时间戳可见性
STANDARD_FORMAT = (
    "[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s"
)

# 详细格式（文件输出，包含行号和函数名）
DETAILED_FORMAT = (
    "[%(asctime)s] %(levelname)-8s | %(name)s:%(lineno)d | %(funcName)s() | %(message)s"
)

# JSON 格式（用于日志聚合和分析）
JSON_FORMAT = (
    "%(asctime)s | %(message)s"
)


class JSONFormatter(logging.Formatter):
    """
    JSON 格式化器

    将日志输出为 JSON 格式，便于日志聚合和分析。
    包含所有标准字段以及 extra 中传递的额外字段。
    """

    def format(self, record: logging.LogRecord) -> str:
        """将日志记录格式化为 JSON 字符串"""
        # 使用时间戳格式
        timestamp = datetime.fromtimestamp(record.created)
        log_data = {
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.threadName,
            "process": record.processName,
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加 extra 中的自定义字段
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """
    控制台彩色格式化器

    为不同日志级别添加不同的颜色，便于快速识别。
    """

    # 颜色定义
    COLORS = {
        "DEBUG": "\033[36m",    # 青色
        "INFO": "\033[32m",     # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",    # 红色
        "CRITICAL": "\033[35m", # 紫色
        "RESET": "\033[0m",     # 重置
    }

    def format(self, record: logging.LogRecord) -> str:
        """添加颜色后格式化日志"""
        # 获取原始格式
        message = super().format(record)

        # 添加颜色
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Windows 兼容（不支持 ANSI 颜色）
        if sys.platform == "win32":
            return message

        return f"{color}{message}{reset}"


# =============================================================================
# 统一日志配置
# =============================================================================

DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "()": "config.logging_config.ColoredConsoleFormatter",
            "fmt": STANDARD_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": DETAILED_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "()": "config.logging_config.JSONFormatter",
        },
    },
    "filters": {
        "request_id_filter": {
            "()": "config.logging_config.RequestIdFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "console_error": {
            "class": "logging.StreamHandler",
            "level": "ERROR",
            "formatter": "standard",
            "stream": "ext://sys.stderr",
        },
        "file_info": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "detailed",
            "filename": "logs/info.log",
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
        },
        "file_error": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": "logs/error.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
        },
        "file_all": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "logs/all.log",
            "maxBytes": 50 * 1024 * 1024,  # 50MB
            "backupCount": 3,
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "agent": {
            "level": "INFO",
            "handlers": ["console", "file_info", "file_error"],
            "propagate": False,
        },
        "agent.core": {
            "level": "DEBUG",
            "handlers": ["console", "file_info"],
            "propagate": False,
        },
        "agent.tools": {
            "level": "INFO",
            "handlers": ["console", "file_info"],
            "propagate": False,
        },
        "web": {
            "level": "INFO",
            "handlers": ["console", "file_info", "file_error"],
            "propagate": False,
        },
        "web.routes": {
            "level": "DEBUG",
            "handlers": ["console", "file_info"],
            "propagate": False,
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file_error"],
    },
}


# =============================================================================
# 请求追踪过滤器
# =============================================================================

class RequestIdFilter(logging.Filter):
    """
    请求 ID 过滤器

    为日志添加请求追踪 ID，便于追踪分布式请求。
    """

    def __init__(self):
        super().__init__()
        self.request_id = "global"

    def filter(self, record: logging.LogRecord) -> bool:
        """添加 request_id 到日志记录"""
        record.request_id = getattr(record, "request_id", self.request_id)
        return True


# 全局请求 ID 上下文
_request_id_context = {"request_id": "global"}


def set_request_id(request_id: str) -> None:
    """设置当前请求的 ID"""
    _request_id_context["request_id"] = request_id


def get_request_id() -> str:
    """获取当前请求的 ID"""
    return _request_id_context["request_id"]


# =============================================================================
# 日志级别使用规范
# =============================================================================

LOG_LEVEL_GUIDELINES = {
    "DEBUG": [
        "变量值追踪",
        "函数调用参数",
        "SQL 查询语句",
        "API 请求/响应详情",
        "详细的执行步骤",
    ],
    "INFO": [
        "服务启动/关闭",
        "请求开始和完成",
        "关键业务流程节点",
        "配置加载成功",
        "用户登录/登出",
        "数据同步完成",
    ],
    "WARNING": [
        "性能下降（响应时间变长）",
        "依赖服务不可用（降级运行）",
        "配置项使用默认值",
        "资源使用率接近阈值",
    ],
    "ERROR": [
        "API 请求失败（4xx/5xx）",
        "数据库操作失败",
        "外部服务调用失败",
        "文件读取/写入失败",
        "认证/授权失败",
    ],
    "CRITICAL": [
        "系统级故障",
        "数据库连接完全失败",
        "关键服务不可用",
        "内存溢出",
    ],
}


# =============================================================================
# 核心功能函数
# =============================================================================

def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    env: str = "dev",
    config: Optional[Dict] = None,
) -> None:
    """
    设置统一日志配置

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        log_dir: 日志文件目录
        env: 环境（dev/test/prod）
        config: 自定义配置（覆盖默认配置）
    """
    # 创建日志目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 获取配置
    if config is None:
        config = DEFAULT_LOGGING_CONFIG.copy()

    # 根据环境调整配置
    if env == "prod":
        # 生产环境：减少控制台输出，增加文件记录
        config["handlers"]["console"]["level"] = "INFO"
        config["handlers"]["console"]["formatter"] = "standard"
    elif env == "test":
        # 测试环境：更详细的输出
        config["handlers"]["console"]["level"] = "DEBUG"
    else:
        # 开发环境：最详细输出
        config["handlers"]["console"]["level"] = "DEBUG"

    # 设置日志级别
    numeric_level = LOG_LEVEL_MAP.get(level.upper(), logging.INFO)
    config["root"]["level"] = numeric_level
    config["handlers"]["file_info"]["level"] = numeric_level

    # 更新文件路径
    if "handlers" in config:
        for handler_name, handler_config in config.get("handlers", {}).items():
            if isinstance(handler_config, dict) and "filename" in handler_config:
                handler_config["filename"] = os.path.join(
                    log_dir, handler_config["filename"].split("/")[-1]
                )

    # 应用配置
    try:
        logging.config.dictConfig(config)
    except Exception as e:
        # 配置失败时使用基本配置
        logging.basicConfig(
            level=numeric_level,
            format=STANDARD_FORMAT,
            stream=sys.stdout,
        )
        logging.warning(f"Failed to apply advanced logging config: {e}")


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    获取标准化的 logger 实例

    Args:
        name: logger 名称（通常使用 __name__）
        level: 日志级别

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    numeric_level = LOG_LEVEL_MAP.get(level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    return logger


# =============================================================================
# 性能日志装饰器
# =============================================================================

def log_performance(
    logger: logging.Logger,
    level: int = logging.INFO,
    include_args: bool = False,
    include_result: bool = False,
):
    """
    性能日志装饰器

    自动记录函数的执行时间

    Args:
        logger: 用于记录性能日志的 logger
        level: 日志级别
        include_args: 是否记录函数参数
        include_result: 是否记录函数返回值

    Example:
        @log_performance(logger)
        def my_function(arg1, arg2):
            # 函数逻辑
            return result
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            start_time = time.time()
            result = None
            error = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                extra = {
                    "function": func.__name__,
                    "duration_ms": round(duration_ms, 2),
                }

                if include_args:
                    extra["args"] = str(args)
                    extra["kwargs"] = str(kwargs)

                if include_result and result is not None:
                    extra["result"] = str(result)[:1000]  # 限制长度

                if error:
                    extra["error"] = error
                    logger.log(
                        level,
                        f"Function {func.__name__} failed in {duration_ms:.2f}ms",
                        extra=extra,
                    )
                else:
                    logger.log(
                        level,
                        f"Function {func.__name__} completed in {duration_ms:.2f}ms",
                        extra=extra,
                    )

        return wrapper

    return decorator


# =============================================================================
# 业务日志辅助函数
# =============================================================================

def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str = None,
    extra: Dict = None,
):
    """
    记录 API 请求日志

    Args:
        logger: logger 实例
        method: HTTP 方法
        path: 请求路径
        status_code: 响应状态码
        duration_ms: 执行时间（毫秒）
        request_id: 请求 ID
        extra: 额外信息
    """
    log_extra = {
        "event": "api_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "request_id": request_id or get_request_id(),
    }

    if extra:
        log_extra.update(extra)

    # 根据状态码确定日志级别
    if status_code >= 500:
        logger.error(f"API {method} {path} - {status_code}", extra=log_extra)
    elif status_code >= 400:
        logger.warning(f"API {method} {path} - {status_code}", extra=log_extra)
    else:
        logger.info(f"API {method} {path} - {status_code}", extra=log_extra)


def log_agent_action(
    logger: logging.Logger,
    action: str,
    session_id: str = None,
    success: bool = True,
    error: str = None,
    extra: Dict = None,
):
    """
    记录 Agent 操作日志

    Args:
        logger: logger 实例
        action: 操作名称
        session_id: 会话 ID
        success: 是否成功
        error: 错误信息
        extra: 额外信息
    """
    log_extra = {
        "event": "agent_action",
        "action": action,
        "session_id": session_id,
        "success": success,
    }

    if error:
        log_extra["error"] = error

    if extra:
        log_extra.update(extra)

    if success:
        logger.info(f"Agent action: {action}", extra=log_extra)
    else:
        logger.error(f"Agent action failed: {action} - {error}", extra=log_extra)


# =============================================================================
# 初始化
# =============================================================================

# 默认 logger
default_logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # 测试日志配置
    setup_logging(level="DEBUG", env="dev")

    logger = get_logger(__name__)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
