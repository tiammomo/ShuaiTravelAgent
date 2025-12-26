"""
FastAPI Web服务模块
提供HTTP API接口和静态页面服务

核心功能：
1. 多会话管理 - 支持多个并发用户会话
2. 聊天接口 - 支持非流式和流式（SSE）两种模式
3. 会话管理 - 创建、查询、清空会话
4. 健康检查 - 系统健康状态检查
5. 城市和景点查询 - 旅游知识库查询接口
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import os
import json
import asyncio
import uuid
from datetime import datetime

from .agent import TravelAgent

# 创建FastAPI应用实例
app = FastAPI(
    title="旅游助手API",
    description="基于单智能体的旅游推荐系统",
    version="1.0.0"
)

# 配置CORS，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React开发服务器地址
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

# 全局会话存储：key为session_id，value为会话数据（Agent实例、创建时间、最后活动时间、消息数）
sessions: Dict[str, Dict[str, Any]] = {}

# 会话超时时间（秒），默认24小时 = 86400秒
SESSION_TIMEOUT = 86400

# ============ 数据模型定义 ============

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str  # 用户消息内容
    session_id: Optional[str] = None  # 可选的会话ID，为None时创建新会话

class ChatResponse(BaseModel):
    """聊天响应模型"""
    success: bool  # 处理是否成功
    response: str  # 响应文本
    intent: Optional[str] = None  # 识别到的用户意图
    data: Optional[Dict[str, Any]] = None  # 结构化数据（如推荐列表、路线规划等）
    error: Optional[str] = None  # 错误信息
    session_id: Optional[str] = None  # 本次请求的会话ID

class SessionInfo(BaseModel):
    """会话信息模型"""
    session_id: str  # 会话唯一标识
    created_at: str  # 创建时间
    last_active: str  # 最后活动时间
    message_count: int  # 消息数量
    name: Optional[str] = None  # 会话名称

class UpdateSessionNameRequest(BaseModel):
    """更新会话名称请求模型"""
    name: str  # 新的会话名称

class ModelInfo(BaseModel):
    """模型信息"""
    model_id: str  # 模型唯一标识
    name: str  # 显示名称
    provider: str  # 提供商
    model: str  # 实际模型名称

class AvailableModelsResponse(BaseModel):
    """可用模型列表响应"""
    success: bool
    models: List[ModelInfo]

class SetSessionModelRequest(BaseModel):
    """设置会话模型请求"""
    model_id: str

class SetSessionModelResponse(BaseModel):
    """设置会话模型响应"""
    success: bool
    message: str
    model_id: str

# 会话管理辅助函数
def get_or_create_session(session_id: Optional[str] = None, model_id: Optional[str] = None) -> tuple[str, TravelAgent]:
    """
    获取或创建会话

    Args:
        session_id: 会话ID，如果为None则创建新会话
        model_id: 模型ID，创建新会话时使用

    Returns:
        (session_id, agent)
    """
    # 如果没有提供session_id或session_id不存在，创建新会话
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            'agent': TravelAgent(model_config=model_id),
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'message_count': 0,
            'name': None,
            'model_id': model_id or 'default'
        }
    else:
        # 更新最后活动时间
        sessions[session_id]['last_active'] = datetime.now().isoformat()

    return session_id, sessions[session_id]['agent']

def clean_expired_sessions():
    """清理过期的会话"""
    current_time = datetime.now()
    expired_sessions = []
    
    for sid, session_data in sessions.items():
        last_active = datetime.fromisoformat(session_data['last_active'])
        if (current_time - last_active).total_seconds() > SESSION_TIMEOUT:
            expired_sessions.append(sid)
    
    for sid in expired_sessions:
        del sessions[sid]

# API路由
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    处理用户消息（非流式）
    
    Args:
        request: 聊天请求
        
    Returns:
        聊天响应
    """
    try:
        # 获取或创建会话
        session_id, agent = get_or_create_session(request.session_id)
        
        # 处理用户输入
        result = agent.process(request.message)
        
        # 更新消息计数
        sessions[session_id]['message_count'] += 1
        
        return ChatResponse(
            success=result.get('success', False),
            response=result.get('response', result.get('error', '处理失败')),
            intent=result.get('intent'),
            data=result.get('data'),
            error=result.get('error'),
            session_id=session_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    处理用户消息（SSE流式）
    
    Args:
        request: 聊天请求
        
    Returns:
        SSE流式响应
    """
    # 获取或创建会话
    session_id, agent = get_or_create_session(request.session_id)
    
    async def event_generator():
        try:
            # 发送session_id
            yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"
            
            # 添加用户消息到记忆
            agent.memory_manager.add_message('user', request.message)
            
            # 意图识别和推理
            intent = agent.reasoner.recognize_intent(request.message)
            params = agent.reasoner.extract_parameters(request.message)
            
            context = {
                'user_query': request.message,
                'last_recommended_cities': agent.memory_manager.get_session_state('last_recommended_cities', []),
                'user_preference': agent.memory_manager.get_user_preference()
            }
            plan = agent.reasoner.generate_action_plan(intent, params, context)
            
            # 生成系统上下文
            system_context = agent.memory_manager.get_context_summary()
            
            # 获取对话历史
            history = agent.memory_manager.get_messages_for_llm(limit=5)
            
            # 构建system prompt
            system_message = {
                "role": "system",
                "content": f"""你是一个专业的旅游助手，负责回答用户关于旅游的各类问题。

当前上下文：
{system_context}

请友好、专业地回答用户问题，提供实用的旅游建议。"""
            }
            
            messages = [system_message] + history
            
            # 流式调用LLM
            full_response = ""
            for chunk in agent.llm_client.chat_stream(messages):
                full_response += chunk
                # 发送SSE事件
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)  # 让出event loop
            
            # 添加助手回复到记忆
            agent.memory_manager.add_message('assistant', full_response)
            
            # 更新消息计数
            sessions[session_id]['message_count'] += 1
            
            # 发送结束信号
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            # 错误信息
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用nginx缓冲
        }
    )

@app.get("/api/history")
async def get_history(session_id: Optional[str] = None):
    """
    获取指定会话的对话历史
    
    Args:
        session_id: 会话ID
        
    Returns:
        对话历史列表
    """
    try:
        if not session_id or session_id not in sessions:
            return {
                "success": False,
                "error": "会话不存在"
            }
        
        # 从会话中获取Agent实例
        agent = sessions[session_id]['agent']
        history = agent.get_conversation_history()
        return {
            "success": True,
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/new")
async def create_new_session():
    """
    创建新会话
    
    Returns:
        新会话的ID和创建信息
    """
    try:
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())
        # 初始化会话数据：Agent实例、创建时间、最后活动时间、消息计数
        sessions[session_id] = {
            'agent': TravelAgent(),
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'message_count': 0,
            'name': None
        }
        return {
            "success": True,
            "session_id": session_id,
            "message": "新会话已创建"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def list_sessions():
    """
    获取所有会话列表（按最后活动时间排序）
    
    Returns:
        会话列表及总数
    """
    try:
        # 清理过期会话（超过24小时未活动的会话）
        clean_expired_sessions()
        
        # 构建会话信息列表
        session_list = []
        for sid, session_data in sessions.items():
            session_list.append({
                "session_id": sid,
                "created_at": session_data['created_at'],
                "last_active": session_data['last_active'],
                "message_count": session_data['message_count'],
                "name": session_data.get('name')  # 会话名称
            })
        
        # 按最后活动时间从新到旧排序
        session_list.sort(key=lambda x: x['last_active'], reverse=True)
        
        return {
            "success": True,
            "sessions": session_list,
            "total": len(session_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """
    删除指定会话
    
    Args:
        session_id: 要删除的会话ID
        
    Returns:
        删除结果
    """
    try:
        if session_id in sessions:
            del sessions[session_id]
            return {
                "success": True,
                "message": "会话已删除"
            }
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear")
async def clear_conversation(session_id: Optional[str] = None):
    """
    清空指定会话的对话历史
    
    Args:
        session_id: 会话ID
        
    Returns:
        清空结果
    """
    try:
        if not session_id or session_id not in sessions:
            return {
                "success": False,
                "error": "会话不存在"
            }
        
        # 获取Agent实例并清空对话
        agent = sessions[session_id]['agent']
        agent.clear_conversation()
        # 重置消息计数
        sessions[session_id]['message_count'] = 0
        
        return {
            "success": True,
            "message": "对话历史已清空"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/session/{session_id}/name")
async def update_session_name(session_id: str, request: UpdateSessionNameRequest):
    """
    更新会话名称
    
    Args:
        session_id: 会话ID
        request: 更新请求，包含新名称
        
    Returns:
        更新结果
    """
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        sessions[session_id]['name'] = request.name
        return {
            "success": True,
            "message": "会话名称已更新",
            "name": request.name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cities")
async def get_cities():
    """
    获取系统支持的所有城市列表
    
    Returns:
        城市列表
    """
    try:
        # 创建临时Agent实例获取配置管理器中的城市数据
        temp_agent = TravelAgent()
        cities = temp_agent.config_manager.get_all_cities()
        return {
            "success": True,
            "cities": cities
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/city/{city_name}")
async def get_city_info(city_name: str):
    """
    获取指定城市的详细信息（包括景点、预算、推荐天数等）
    
    Args:
        city_name: 城市名称
        
    Returns:
        城市详细信息
    """
    try:
        # 创建临时Agent实例获取城市信息
        temp_agent = TravelAgent()
        city_info = temp_agent.config_manager.get_city_info(city_name)
        if city_info:
            return {
                "success": True,
                "city": city_name,
                "info": city_info
            }
        else:
            raise HTTPException(status_code=404, detail=f"城市不存在: {city_name}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """
    系统健康检查接口

    Returns:
        系统状态和版本信息
    """
    return {
        "status": "healthy",
        "agent": "TravelAssistantAgent",
        "version": "1.0.0"
    }

@app.get("/api/models", response_model=AvailableModelsResponse)
async def get_available_models():
    """
    获取可用的模型列表

    Returns:
        可用模型列表
    """
    try:
        # 创建临时 Agent 获取配置
        temp_agent = TravelAgent()
        models = temp_agent.config_manager.get_available_models()

        return AvailableModelsResponse(
            success=True,
            models=[ModelInfo(**m) for m in models]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/session/{session_id}/model", response_model=SetSessionModelResponse)
async def set_session_model(session_id: str, request: SetSessionModelRequest):
    """
    设置会话的模型

    Args:
        session_id: 会话ID
        request: 包含 model_id 的请求

    Returns:
        设置结果
    """
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 验证模型是否存在
        try:
            temp_agent = TravelAgent()
            model_config = temp_agent.config_manager.get_model_config(request.model_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 创建新 Agent 实例
        try:
            new_agent = TravelAgent(model_config=request.model_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"创建模型实例失败: {str(e)}"
            )

        # 更新会话
        sessions[session_id]['agent'] = new_agent
        sessions[session_id]['model_id'] = request.model_id

        return SetSessionModelResponse(
            success=True,
            message="模型已切换",
            model_id=request.model_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")

@app.get("/api/session/{session_id}/model")
async def get_session_model(session_id: str):
    """
    获取会话当前使用的模型

    Args:
        session_id: 会话ID

    Returns:
        模型信息
    """
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="会话不存在")

        model_id = sessions[session_id].get('model_id', 'default')

        return {
            "success": True,
            "model_id": model_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ 启动函数 ============

def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    启动FastAPI Web服务器
    
    Args:
        host: 绑定的主机地址（默认0.0.0.0表示所有网卡）
        port: 监听端口（默认8000）
        reload: 是否启用热重载（开发模式）
    """
    # 使用uvicorn.run启动服务器
    # 参数说明：
    #  - "shuai_travel_agent.app:app" - 指定应用位置（模块:实例）
    #  - host - 绑定地址
    #  - port - 监听端口
    #  - reload - 代码变更时自动重启（仅开发环境）
    uvicorn.run("shuai_travel_agent.app:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    # 从配置文件读取Web服务参数
    import os
    # 切换到项目根目录，确保相对路径正确
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    # 从config.json加载配置
    temp_agent = TravelAgent(config_path=os.path.join('config', 'config.json'))
    # 获取web配置部分
    web_config = temp_agent.config_manager.get_config('web', {})
    # 启动服务器，使用配置中的参数
    start_server(
        host=web_config.get('host', '0.0.0.0'),
        port=web_config.get('port', 8000),
        reload=web_config.get('debug', True)
    )
