"""
gRPC 服务器
"""

# 添加 agent 根目录到路径，这样可以使用绝对导入
import sys
import os
AGENT_ROOT = os.path.dirname(os.path.dirname(__file__))  # agent/
if AGENT_ROOT not in sys.path:
    sys.path.insert(0, AGENT_ROOT)

import grpc
from concurrent import futures
import json
import logging
import asyncio
import queue
import threading
from typing import Iterator
from datetime import datetime

from proto import agent_pb2, agent_pb2_grpc

from core.travel_agent import ReActTravelAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsyncThoughtStreamer:
    """异步思考流式输出器 - 用于实时传递思考过程（异步版本）"""

    def __init__(self):
        self._queue = asyncio.Queue()
        self._done = False
        self._answer_started = False

    async def put_thought(self, content: str, elapsed: float) -> None:
        """放入思考内容"""
        await self._queue.put({"type": "thinking", "content": content, "elapsed": elapsed})

    async def put_answer_chunk(self, chunk: str) -> None:
        """放入答案内容块（用于token级别流式）"""
        await self._queue.put({"type": "answer_chunk", "content": chunk})

    async def put_answer(self, content: str) -> None:
        """放入完整答案内容"""
        await self._queue.put({"type": "answer", "content": content})

    async def put_done(self) -> None:
        """标记完成"""
        self._done = True
        await self._queue.put(None)  # 放入 None 作为完成标记

    async def put_error(self, error: str) -> None:
        """放入错误"""
        await self._queue.put({"type": "error", "content": error})

    async def get(self) -> dict:
        """获取下一个内容块"""
        if self._done and self._queue.empty():
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            return None

    def is_done(self) -> bool:
        return self._done and self._queue.empty()


class ThoughtStreamer:
    """思考流式输出器 - 用于实时传递思考过程"""

    def __init__(self):
        self._queue = queue.Queue()
        self._done = False

    def put_thought(self, content: str, elapsed: float) -> None:
        """放入思考内容"""
        self._queue.put({"type": "thinking", "content": content, "elapsed": elapsed})

    def put_answer_chunk(self, chunk: str) -> None:
        """放入答案内容块（用于token级别流式）"""
        self._queue.put({"type": "answer_chunk", "content": chunk})

    def put_answer(self, content: str) -> None:
        """放入完整答案内容"""
        self._queue.put({"type": "answer", "content": content})

    def put_done(self) -> None:
        """标记完成"""
        self._done = True

    def put_error(self, error: str) -> None:
        """放入错误"""
        self._queue.put({"type": "error", "content": error})

    def get(self, timeout: float = None):
        """获取下一个内容块"""
        if self._done and self._queue.empty():
            return None
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_done(self) -> bool:
        return self._done and self._queue.empty()


class AgentServicer:
    """Agent 服务实现"""

    _instances = {}  # 存储每个请求的流式器
    _thread_pool = None  # 线程池

    def __init__(self, config_path: str = "config/llm_config.yaml"):
        self.config_path = config_path
        self.agent = ReActTravelAgent(config_path=config_path)
        logger.info("Agent 服务已初始化")

    @classmethod
    def get_thread_pool(cls):
        """获取线程池，单例模式"""
        if cls._thread_pool is None:
            cls._thread_pool = futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="agent_worker")
            logger.info("Agent 线程池已初始化")
        return cls._thread_pool

    @classmethod
    def cleanup_instance(cls, request_id: str):
        """安全清理实例，防止内存泄漏"""
        if request_id in cls._instances:
            del cls._instances[request_id]
            logger.debug(f"[Stream-{request_id}] 实例已清理")

    def ProcessMessage(self, request, context):
        """处理消息（非流式）"""
        try:
            result = self.agent.process_sync(request.user_input)
            return self._build_response(result, context)
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return self._build_error_response(str(e), context)

    def StreamMessage(self, request, context) -> Iterator:
        """处理消息（流式）- 使用线程和队列实现真正流式"""
        import uuid
        import time as time_module
        request_id = str(uuid.uuid4())[:8]

        logger.info(f"[Stream-{request_id}] 开始处理流式请求: {request.user_input[:50]}...")

        try:
            user_input = request.user_input

            # 发送思考开始信号
            yield agent_pb2.StreamChunk(chunk_type="thinking_start", content="", is_last=False)

            answer_started = False
            chunk_count = 0
            thinking_sent = False

            # 创建同步队列
            answer_queue = queue.Queue()
            thinking_queue = queue.Queue()
            done_event = threading.Event()
            error_holder = {"error": None}

            # 回调函数
            def on_think(content, elapsed):
                thinking_queue.put((content, elapsed))

            def on_answer_chunk(chunk):
                answer_queue.put(chunk)

            def on_done(result):
                if not result.get("success"):
                    error_holder["error"] = result.get("error", "未知错误")
                done_event.set()

            # 设置回调
            self.agent.react_agent.set_think_stream_callback(on_think)

            # 在线程中运行 agent
            def run_agent():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        self.agent.process_stream(
                            user_input,
                            answer_callback=on_answer_chunk,
                            done_callback=on_done
                        )
                    )
                    loop.close()
                except Exception as e:
                    logger.error(f"[Stream-{request_id}] agent 错误: {e}")
                    error_holder["error"] = str(e)
                    done_event.set()

            # 启动 agent 线程
            thread = threading.Thread(target=run_agent, daemon=True)
            thread.start()

            # 主循环：使用阻塞方式读取队列
            # 这确保了当队列为空时会阻塞，直到 agent 放入新数据
            while True:
                # 首先检查思考队列（带超时）
                try:
                    content, elapsed = thinking_queue.get(timeout=0.05)
                    thinking_text = f"[已思考 {elapsed:.1f}秒]\n\n{content}"
                    yield agent_pb2.StreamChunk(chunk_type="thinking_chunk", content=thinking_text, is_last=False)
                    thinking_sent = True
                except queue.Empty:
                    pass

                # 检查答案队列
                try:
                    chunk = answer_queue.get(timeout=0.05)
                    if not answer_started:
                        if thinking_sent:
                            yield agent_pb2.StreamChunk(chunk_type="thinking_end", content="", is_last=False)
                        yield agent_pb2.StreamChunk(chunk_type="answer_start", content="", is_last=False)
                        answer_started = True
                    chunk_count += 1
                    yield agent_pb2.StreamChunk(chunk_type="answer", content=chunk, is_last=False)
                    time_module.sleep(0.02)
                except queue.Empty:
                    pass

                # 检查是否完成
                if done_event.is_set():
                    # 继续读取剩余数据
                    while not answer_queue.empty():
                        try:
                            chunk = answer_queue.get_nowait()
                            if not answer_started:
                                if thinking_sent:
                                    yield agent_pb2.StreamChunk(chunk_type="thinking_end", content="", is_last=False)
                                yield agent_pb2.StreamChunk(chunk_type="answer_start", content="", is_last=False)
                                answer_started = True
                            chunk_count += 1
                            yield agent_pb2.StreamChunk(chunk_type="answer", content=chunk, is_last=False)
                            time_module.sleep(0.02)
                        except queue.Empty:
                            break
                    break

            # 清理
            self.agent.react_agent.set_think_stream_callback(None)

            # 检查错误
            if error_holder["error"]:
                if not answer_started:
                    yield agent_pb2.StreamChunk(chunk_type="thinking_end", content="", is_last=False)
                yield agent_pb2.StreamChunk(chunk_type="error", content=error_holder["error"], is_last=True)
                AgentServicer.cleanup_instance(request_id)
                return

            # 发送完成信号
            yield agent_pb2.StreamChunk(chunk_type="done", content="", is_last=True)
            AgentServicer.cleanup_instance(request_id)
            logger.info(f"[Stream-{request_id}] 流式响应完成 (共 {chunk_count} 个分块)")

        except Exception as e:
            logger.error(f"[Stream-{request_id}] 流式处理异常: {e}")
            yield agent_pb2.StreamChunk(chunk_type="error", content=str(e), is_last=True)
            AgentServicer.cleanup_instance(request_id)

    def _build_response(self, result, context):
        """构建响应"""
        if result.get("success", False):
            reasoning = result.get("reasoning", {})
            history = result.get("history", [])
            return agent_pb2.MessageResponse(
                success=True,
                answer=result.get("answer", ""),
                reasoning=agent_pb2.ReasoningInfo(
                    text=reasoning.get("text", ""),
                    total_steps=reasoning.get("total_steps", 0),
                    tools_used=reasoning.get("tools_used", [])
                ),
                history=[
                    agent_pb2.HistoryStep(
                        step=step.get("step", 0),
                        thought=agent_pb2.ThoughtInfo(
                            id=step.get("thought", {}).get("id", ""),
                            type=step.get("thought", {}).get("type", ""),
                            content=step.get("thought", {}).get("content", ""),
                            confidence=step.get("thought", {}).get("confidence", 0.0),
                            decision=step.get("thought", {}).get("decision", "")
                        ),
                        action=agent_pb2.ActionInfo(
                            id=step.get("action", {}).get("id", ""),
                            tool_name=step.get("action", {}).get("tool_name", ""),
                            status=step.get("action", {}).get("status", ""),
                            duration=step.get("action", {}).get("duration", 0)
                        ),
                        evaluation=agent_pb2.EvaluationInfo(
                            success=step.get("evaluation", {}).get("success", False),
                            duration=step.get("evaluation", {}).get("duration", 0)
                        )
                    )
                    for step in history
                ]
            )
        else:
            return agent_pb2.MessageResponse(
                success=False,
                error=result.get("error", "未知错误")
            )

    def _build_error_response(self, error: str, context):
        """构建错误响应"""
        return agent_pb2.MessageResponse(
            success=False,
            error=error
        )

    def HealthCheck(self, request, context):
        """健康检查"""
        return agent_pb2.HealthResponse(healthy=True, version="1.0.0", status="running")


def serve(config_path: str = "config/config.json", port: int = 50051):
    """启动 gRPC 服务器"""
    # 使用同步服务器
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # 添加服务
    agent_servicer = AgentServicer(config_path)
    # 注册 gRPC 服务
    agent_pb2_grpc.add_AgentServiceServicer_to_server(agent_servicer, server)

    server.add_insecure_port(f'[::]:{port}')
    server.start()

    logger.info(f"Agent gRPC 服务器已启动，端口: {port}")
    return server


if __name__ == '__main__':
    import argparse

    # Get project root (parent of agent/)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    parser = argparse.ArgumentParser(description='ShuaiTravelAgent gRPC Server')
    parser.add_argument('--config', type=str,
                        default=os.path.join(project_root, 'config', 'llm_config.yaml'),
                        help='Path to config file')
    parser.add_argument('--port', type=int, default=50051,
                        help='Port to listen on')
    args = parser.parse_args()

    config_path = args.config

    print(f"[*] Starting Agent gRPC Server...")
    print(f"    Config: {config_path}")
    print(f"    Port: {args.port}")
    print()

    server = serve(config_path, args.port)
    print(f"[OK] Agent gRPC Server started on port {args.port}")
    print("    Press Ctrl+C to stop")
    server.wait_for_termination()
