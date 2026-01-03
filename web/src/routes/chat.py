"""Chat API routes with SSE streaming."""
import asyncio
import json
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

import grpc
import sys
import os

from ..services.chat_service import ChatService
from ..dependencies.container import get_container

router = APIRouter()

# 全局变量
_grpc_stub = None
_agent_pb2 = None
_agent_pb2_grpc = None

# SSE 事件类型常量
class SSEEventType:
    SESSION_ID = "session_id"
    REASONING_START = "reasoning_start"
    REASONING_CHUNK = "reasoning_chunk"
    REASONING_END = "reasoning_end"
    ANSWER_START = "answer_start"
    CHUNK = "chunk"
    ERROR = "error"
    DONE = "done"
    HEARTBEAT = "heartbeat"
    METADATA = "metadata"


def _ensure_proto_imported():
    """Ensure proto modules are imported."""
    global _agent_pb2, _agent_pb2_grpc, _grpc_stub
    if _agent_pb2 is None:
        # 添加 agent 根目录到路径，使 proto 可以作为包被正确导入
        proto_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agent'))
        if proto_parent not in sys.path:
            sys.path.insert(0, proto_parent)

        # 导入 proto 模块（通过包导入方式）
        from proto import agent_pb2
        from proto import agent_pb2_grpc
        _agent_pb2 = agent_pb2
        _agent_pb2_grpc = agent_pb2_grpc


def init_grpc_stub(host: str = 'localhost', port: int = 50051):
    """Initialize gRPC stub (synchronous)."""
    global _grpc_stub
    if _grpc_stub is None:
        _ensure_proto_imported()
        # 使用同步channel
        channel = grpc.insecure_channel(f'{host}:{port}')
        _grpc_stub = _agent_pb2_grpc.AgentServiceStub(channel)
    return _grpc_stub


def get_grpc_stub():
    """Get the gRPC stub."""
    global _grpc_stub
    if _grpc_stub is None:
        raise RuntimeError("gRPC stub not initialized. Call init_grpc_stub() first.")
    return _grpc_stub


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None


def get_chat_service() -> ChatService:
    """Get the chat service from the container."""
    container = get_container()
    return container.resolve('ChatService')


def get_session_service():
    """Get the session service from the container."""
    container = get_container()
    return container.resolve('SessionService')


async def generate_chat_stream(message: str, session_id: str, request: Request = None) -> AsyncGenerator[str, None]:
    """Generate a chat response stream by calling the backend Agent gRPC service with true streaming.

    Features:
    - Heartbeat mechanism to prevent connection timeout
    - Request timeout protection (120 seconds)
    - Client disconnect detection
    """
    import logging
    logger = logging.getLogger(__name__)

    session_service = get_session_service()

    if not session_id:
        result = await session_service.create_session()
        session_id = result['session_id']

    yield f"data: {json.dumps({'type': SSEEventType.SESSION_ID, 'session_id': session_id})}\n\n"

    # 请求超时控制器
    timeout_seconds = 120
    task = None

    try:
        # 确保 proto 已导入
        _ensure_proto_imported()

        # 获取 gRPC stub 并调用流式服务
        logger.info(f"[Chat] 通过 gRPC StreamMessage 调用 Agent 服务...")
        stub = get_grpc_stub()

        request_msg = _agent_pb2.MessageRequest(
            session_id=session_id,
            user_input=message,
            model_id='',
            stream=True
        )

        # 使用 asyncio.to_thread 在线程池中执行同步 gRPC 流
        chunk_iterator = stub.StreamMessage(request_msg)

        # 最后一次心跳时间
        last_heartbeat = datetime.now()

        # 遍历 gRPC 流
        for chunk in chunk_iterator:
            # 检查客户端是否已断开连接
            if request and await request.is_disconnected():
                logger.info("[Chat] 客户端已断开连接，停止流式传输")
                break

            chunk_type = chunk.chunk_type
            content = chunk.content
            is_last = chunk.is_last

            logger.debug(f"[Chat] 收到流式 chunk: type={chunk_type}, is_last={is_last}")

            # 发送心跳（每30秒）
            elapsed_since_heartbeat = (datetime.now() - last_heartbeat).total_seconds()
            if elapsed_since_heartbeat >= 30:
                heartbeat_data = json.dumps({
                    'type': SSEEventType.HEARTBEAT,
                    'timestamp': datetime.now().isoformat()
                })
                yield f"data: {heartbeat_data}\n\n"
                last_heartbeat = datetime.now()

            if chunk_type == "thinking_start":
                yield f"data: {json.dumps({'type': SSEEventType.REASONING_START})}\n\n"
                await asyncio.sleep(0.01)  # 10ms 延迟确保数据分开发送
            elif chunk_type == "thinking_chunk":
                yield f"data: {json.dumps({'type': SSEEventType.REASONING_CHUNK, 'content': content})}\n\n"
                await asyncio.sleep(0.01)  # 10ms 延迟
            elif chunk_type == "thinking_end":
                yield f"data: {json.dumps({'type': SSEEventType.REASONING_END})}\n\n"
                await asyncio.sleep(0.01)
            elif chunk_type == "answer_start":
                yield f"data: {json.dumps({'type': SSEEventType.ANSWER_START})}\n\n"
                await asyncio.sleep(0.01)
            elif chunk_type == "answer":
                yield f"data: {json.dumps({'type': SSEEventType.CHUNK, 'content': content})}\n\n"
                await asyncio.sleep(0.01)  # 10ms 延迟确保每个chunk分开发送
            elif chunk_type == "error":
                yield f"data: {json.dumps({'type': SSEEventType.REASONING_CHUNK, 'content': f'处理出错: {content}'})}\n\n"
                yield f"data: {json.dumps({'type': SSEEventType.REASONING_END})}\n\n"
                yield f"data: {json.dumps({'type': SSEEventType.ANSWER_START})}\n\n"
                yield f"data: {json.dumps({'type': SSEEventType.CHUNK, 'content': '抱歉，处理您的请求时出现问题。'})}\n\n"
            elif chunk_type == "done":
                yield f"data: {json.dumps({'type': SSEEventType.DONE})}\n\n"
                break

            if is_last:
                break

        logger.info(f"[Chat] 流式响应完成")

    except grpc.RpcError as e:
        logger.error(f"[Chat] gRPC 调用失败: {e}")
        yield f"data: {json.dumps({'type': SSEEventType.REASONING_CHUNK, 'content': f'连接后端服务失败: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.REASONING_END})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.ANSWER_START})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.CHUNK, 'content': '抱歉，连接后端服务失败，请稍后重试。'})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.DONE})}\n\n"
    except asyncio.CancelledError:
        logger.info("[Chat] 请求被取消（客户端断开连接）")
        raise
    except Exception as e:
        logger.error(f"[Chat] 处理异常: {e}")
        yield f"data: {json.dumps({'type': SSEEventType.REASONING_CHUNK, 'content': f'处理异常: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.REASONING_END})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.ANSWER_START})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.CHUNK, 'content': '抱歉，处理您的请求时出现异常。'})}\n\n"
        yield f"data: {json.dumps({'type': SSEEventType.DONE})}\n\n"


@router.post("/chat/stream")
async def stream_chat(request: ChatRequest, fastapi_request: Request):
    """
    Stream a chat response using Server-Sent Events.
    Calls the backend Agent gRPC service for intelligent responses.

    Features:
    - Heartbeat every 30 seconds to prevent connection timeout
    - Client disconnect detection for resource cleanup
    - CORS and security headers
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=422, detail="消息不能为空")

    # 验证消息长度（防止过大请求）
    if len(request.message) > 5000:
        raise HTTPException(status_code=422, detail="消息长度不能超过5000字符")

    return StreamingResponse(
        generate_chat_stream(request.message, request.session_id or "", fastapi_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            # 安全相关头
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
    )
