# Tests Directory

## Test Files

### test_sse_streaming.py
SSE 流式传输核心测试用例：
- `TestSSEStreaming` - 测试 SSE 连接、响应格式、token 流式、会话持久化
- `TestSSEEventTypes` - 测试 SSE 事件类型（answer_start, chunk, done）

### test_e2e_streaming.py
端到端集成测试：
- `TestEndToEndStreaming` - 完整流式管道测试、连续请求测试
- `TestStreamingPerformance` - 性能测试（首 token 延迟、吞吐量）

### test_response.md
测试响应样例文件

## Running Tests

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_sse_streaming.py -v

# 运行特定测试类
pytest tests/test_sse_streaming.py::TestSSEStreaming -v

# 运行特定测试方法
pytest tests/test_sse_streaming.py::TestSSEStreaming::test_token_streaming -v

# 生成测试报告
pytest tests/ --html=report.html
```

## Test Requirements

- Web API 服务器运行在端口 8000
- gRPC 服务器运行在端口 50051
- Python 3.10+
- pytest-asyncio
- httpx
