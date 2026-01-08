# 日志规范文档

本文档定义了 ShuaiTravelAgent 项目的日志规范和最佳实践。

## 日志级别使用规范

| 级别 | 值 | 使用场景 |
|------|-----|---------|
| **DEBUG** | 10 | 变量值追踪、函数调用参数、SQL查询语句、API请求/响应详情、详细执行步骤 |
| **INFO** | 20 | 服务启动/关闭、请求开始和完成、关键业务流程节点、配置加载成功、用户登录/登出、数据同步完成 |
| **WARNING** | 30 | 性能下降（响应时间变长）、依赖服务不可用（降级运行）、配置项使用默认值、资源使用率接近阈值 |
| **ERROR** | 40 | API请求失败（4xx/5xx）、数据库操作失败、外部服务调用失败、文件读取/写入失败、认证/授权失败 |
| **CRITICAL** | 50 | 系统级故障、数据库连接完全失败、关键服务不可用、内存溢出 |

## 统一日志格式

### 控制台输出（标准格式）
```
[2024-01-15 14:30:45.123] INFO     | agent.core.travel_agent | User request received:我想去北京旅游
```

### 文件输出（详细格式，包含行号和函数名）
```
[2024-01-15 14:30:45.123] INFO     | agent.core.travel_agent:123 | process_request() | User request received:我想去北京旅游
```

### JSON 格式（日志聚合）
```json
{"timestamp": "2024-01-15 14:30:45.123", "level": "INFO", "logger": "agent.core.travel_agent", "message": "User request received", "module": "travel_agent", "function": "process_request", "line": 123}
```

## 使用方法

### 基础用法
```python
from config.logging_config import get_logger

logger = get_logger(__name__)
logger.info("用户请求 received", extra={"user_id": "123", "action": "query"})
logger.error("操作失败", extra={"error_code": "E001"})
```

### 性能日志装饰器
```python
from config.logging_config import log_performance

logger = get_logger(__name__)

@log_performance(logger, level=logging.INFO)
def process_request(request):
    # 函数逻辑
    return result
```

### API 请求日志
```python
from config.logging_config import log_api_request

log_api_request(
    logger=logger,
    method="POST",
    path="/api/chat",
    status_code=200,
    duration_ms=145.5,
    request_id="req-123"
)
```

### Agent 操作日志
```python
from config.logging_config import log_agent_action

log_agent_action(
    logger=logger,
    action="city_recommendation",
    session_id="sess-456",
    success=True,
    extra={"cities": ["北京", "上海", "杭州"]}
)
```

## 配置文件结构

日志配置位于 `agent/src/config/logging_config.py`，支持：

- **多输出目标**：控制台、文件、错误日志
- **日志轮转**：自动轮转，防止日志文件过大
- **多环境配置**：dev/test/prod
- **请求追踪**：X-Request-ID 支持

## 环境配置

```python
# 开发环境 - 最详细输出
setup_logging(level="DEBUG", env="dev")

# 测试环境 - 更详细输出
setup_logging(level="DEBUG", env="test")

# 生产环境 - 减少控制台输出，增加文件记录
setup_logging(level="INFO", env="prod")
```

## 日志文件

| 文件 | 级别 | 大小限制 | 保留数量 |
|------|------|---------|---------|
| logs/info.log | INFO+ | 10MB | 5 |
| logs/error.log | ERROR+ | 10MB | 10 |
| logs/all.log | DEBUG+ | 50MB | 3 |
