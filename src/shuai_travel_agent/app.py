"""
FastAPI Web服务模块
==================

提供HTTP API接口，支持会话管理和聊天功能。

核心功能：
1. 聊天接口 - SSE流式响应
2. 会话管理 - 创建、查询、删除会话
3. 模型管理 - 获取可用模型、设置会话模型
4. 健康检查 - 系统状态检查

版本：2.0.0
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import json
import asyncio
from datetime import datetime

from .agent import ReActTravelAgent
from .config_manager import ConfigManager

# 创建FastAPI应用
app = FastAPI(
    title="旅游助手API",
    description="基于ReAct模式的旅游推荐系统",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局会话存储
sessions: Dict[str, Dict[str, Any]] = {}

# 会话超时时间（秒）
SESSION_TIMEOUT = 86400


# ==================== 数据模型 ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[str] = None


class UpdateSessionNameRequest(BaseModel):
    """更新会话名称请求"""
    name: str


class SetSessionModelRequest(BaseModel):
    """设置会话模型请求"""
    model_id: str


# ==================== 辅助函数 ====================

def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, ReActTravelAgent]:
    """
    获取或创建会话

    Args:
        session_id: 会话ID，为None时创建新会话

    Returns:
        (session_id, agent实例)
    """
    if not session_id or session_id not in sessions:
        import uuid
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            'agent': ReActTravelAgent(),
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'message_count': 0,
            'name': None,
            'model_id': 'default'
        }
    else:
        sessions[session_id]['last_active'] = datetime.now().isoformat()

    return session_id, sessions[session_id]['agent']


def clean_expired_sessions() -> None:
    """清理过期会话"""
    current_time = datetime.now()
    expired = [
        sid for sid, data in sessions.items()
        if (current_time - datetime.fromisoformat(data['last_active'])).total_seconds() > SESSION_TIMEOUT
    ]
    for sid in expired:
        del sessions[sid]


# ==================== API端点 ====================

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式聊天接口

    使用SSE（Server-Sent Events）实现流式响应，
    先流式输出思考过程，再流式输出回答内容。

    消息类型说明：
    - session_id: 会话ID
    - reasoning_start: 思考过程开始
    - reasoning_chunk: 思考过程内容（逐块传输）
    - reasoning_end: 思考过程结束
    - answer_start: 正式回答开始
    - chunk: 回答内容（逐字符传输）
    - done: 传输完成
    - error: 错误信息

    Args:
        request: 聊天请求

    Returns:
        SSE流式响应
    """
    session_id, agent = get_or_create_session(request.session_id)

    async def event_generator():
        try:
            # 发送会话ID
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            # 执行ReAct处理（异步等待）
            result = await agent.process(request.message)

            if not result.get('success'):
                yield f"data: {json.dumps({'type': 'error', 'content': result.get('error', '处理失败')}, ensure_ascii=False)}\n\n"
                return

            # 提取结果
            answer = result.get('answer', '')
            reasoning = result.get('reasoning', {})
            reasoning_text = reasoning.get('text', '')
            tools_used = reasoning.get('tools_used', [])
            total_steps = reasoning.get('total_steps', 0)

            # 发送元数据（包含思考过程的基本信息）
            yield f"data: {json.dumps({
                'type': 'metadata',
                'has_reasoning': bool(reasoning_text),
                'tools_used': tools_used,
                'total_steps': total_steps,
                'reasoning_length': len(reasoning_text) if reasoning_text else 0,
                'answer_length': len(answer) if answer else 0
            }, ensure_ascii=False)}\n\n"

            # 如果有思考过程，先流式输出思考过程
            if reasoning_text:
                # 发送思考过程开始信号
                yield f"data: {json.dumps({'type': 'reasoning_start'}, ensure_ascii=False)}\n\n"

                # 流式传输思考过程（按行分割，每行作为一块）
                import re
                # 按行分割思考过程，但保留格式
                lines = reasoning_text.split('\n')
                for line in lines:
                    if line.strip():  # 跳过空行
                        yield f"data: {json.dumps({
                            'type': 'reasoning_chunk',
                            'content': line
                        }, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.02)  # 控制思考过程的输出速度

                # 发送思考过程结束信号
                yield f"data: {json.dumps({'type': 'reasoning_end'}, ensure_ascii=False)}\n\n"

            # 发送回答开始信号
            yield f"data: {json.dumps({'type': 'answer_start'}, ensure_ascii=False)}\n\n"

            # 流式传输回答内容（逐字符）
            for char in answer:
                yield f"data: {json.dumps({'type': 'chunk', 'content': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)  # 控制回答的输出速度

            # 更新会话状态
            sessions[session_id]['message_count'] += 1
            sessions[session_id]['last_active'] = datetime.now().isoformat()

            # 发送结束信号
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/session/new")
async def create_session():
    """
    创建新会话

    Returns:
        新会话信息
    """
    import uuid
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'agent': ReActTravelAgent(),
        'created_at': datetime.now().isoformat(),
        'last_active': datetime.now().isoformat(),
        'message_count': 0,
        'name': None
    }
    return {"success": True, "session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    """
    获取会话列表

    Returns:
        会话列表
    """
    clean_expired_sessions()

    session_list = [{
        "session_id": sid,
        "created_at": data['created_at'],
        "last_active": data['last_active'],
        "message_count": data['message_count'],
        "name": data.get('name')
    } for sid, data in sessions.items()]

    session_list.sort(key=lambda x: x['last_active'], reverse=True)

    return {"success": True, "sessions": session_list}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话

    Args:
        session_id: 会话ID

    Returns:
        删除结果
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    del sessions[session_id]
    return {"success": True, "message": "会话已删除"}


@app.put("/api/session/{session_id}/name")
async def update_session_name(session_id: str, request: UpdateSessionNameRequest):
    """
    更新会话名称

    Args:
        session_id: 会话ID
        request: 更新请求

    Returns:
        更新结果
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    sessions[session_id]['name'] = request.name
    return {"success": True, "message": "名称已更新", "name": request.name}


@app.post("/api/clear")
async def clear_conversation(session_id: Optional[str] = None):
    """
    清空对话历史

    Args:
        session_id: 会话ID

    Returns:
        清空结果
    """
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    sessions[session_id]['agent'].clear_conversation()
    sessions[session_id]['message_count'] = 0
    return {"success": True, "message": "对话已清空"}


# ==================== 模型管理接口 ====================

@app.get("/api/models")
async def get_available_models():
    """
    获取可用模型列表

    Returns:
        模型列表
    """
    try:
        config_manager = ConfigManager("config/config.json")
        models = config_manager.get_available_models()
        return {"success": True, "models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/session/{session_id}/model")
async def set_session_model(session_id: str, request: SetSessionModelRequest):
    """
    设置会话使用的模型

    Args:
        session_id: 会话ID
        request: 模型设置请求

    Returns:
        设置结果
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 验证模型
    try:
        config_manager = ConfigManager("config/config.json")
        config_manager.get_model_config(request.model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="模型不存在")

    # 创建新Agent实例
    try:
        new_agent = ReActTravelAgent(model_config=request.model_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建Agent失败: {str(e)}")

    sessions[session_id]['agent'] = new_agent
    sessions[session_id]['model_id'] = request.model_id

    return {"success": True, "message": "模型已切换", "model_id": request.model_id}


@app.get("/api/session/{session_id}/model")
async def get_session_model(session_id: str):
    """
    获取会话当前模型

    Args:
        session_id: 会话ID

    Returns:
        模型信息
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "success": True,
        "model_id": sessions[session_id].get('model_id', 'default')
    }


# ==================== 健康检查 ====================

@app.get("/api/health")
async def health_check():
    """
    健康检查

    Returns:
        系统状态
    """
    return {
        "status": "healthy",
        "agent": "ReActTravelAgent",
        "version": "2.0.0"
    }


# ==================== 城市信息接口 ====================

@app.get("/api/cities")
async def get_cities():
    """
    获取支持的城市列表

    Returns:
        城市列表
    """
    try:
        config_manager = ConfigManager("config/config.json")
        cities = config_manager.get_all_cities()
        return {"success": True, "cities": cities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/city/{city_name}")
async def get_city_info(city_name: str):
    """
    获取城市详细信息

    Args:
        city_name: 城市名称

    Returns:
        城市信息
    """
    try:
        config_manager = ConfigManager("config/config.json")
        city_info = config_manager.get_city_info(city_name)
        if city_info:
            return {"success": True, "city": city_name, "info": city_info}
        raise HTTPException(status_code=404, detail=f"城市不存在: {city_name}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 启动函数 ====================

def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    启动Web服务器

    Args:
        host: 绑定地址
        port: 监听端口
        reload: 是否热重载
    """
    uvicorn.run("shuai_travel_agent.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    start_server(host="0.0.0.0", port=8000, reload=True)
