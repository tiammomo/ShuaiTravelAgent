"""会话API路由模块 (Session API Routes)

提供会话管理相关的RESTful API接口。
支持会话的创建、查询、更新、删除等操作。

主要组件:
- UpdateNameRequest: 更新名称请求模型
- SetModelRequest: 设置模型请求模型
- router: API路由路由器

API端点:
- POST /session/new - 创建新会话
- GET /sessions - 列出所有会话
- DELETE /session/{session_id} - 删除会话
- PUT /session/{session_id}/name - 更新会话名称
- PUT /session/{session_id}/model - 设置会话模型
- GET /session/{session_id}/model - 获取会话模型
- POST /clear/{session_id} - 清空聊天记录

使用示例:
    # 创建会话
    POST /session/new
    Body: {"name": "我的旅行计划"}

    # 列出会话
    GET /sessions?include_empty=true

    # 更新名称
    PUT /session/abc123/name
    Body: {"name": "新的名称"}

    # 删除会话
    DELETE /session/abc123
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services.session_service import SessionService
from ..dependencies.container import get_container

router = APIRouter()


class UpdateNameRequest(BaseModel):
    """
    更新会话名称请求模型

    属性:
        name: str 新的会话名称
    """
    name: str


class SetModelRequest(BaseModel):
    """
    设置会话模型请求模型

    属性:
        model_id: str 要设置的模型ID
    """
    model_id: str


def get_session_service() -> SessionService:
    """
    从依赖容器获取SessionService实例

    Returns:
        SessionService: 会话服务实例
    """
    container = get_container()
    return container.resolve('SessionService')


@router.post(
    "/session/new",
    responses={
        200: {
            "description": "创建成功",
            "content": {"application/json": {"example": {"success": True, "session_id": "550e8400-e29b-41d4-a716-446655440000", "name": None}}}
        },
        500: {
            "description": "创建失败",
            "content": {"application/json": {"example": {"success": False, "error": "创建会话失败"}}}
        }
    }
)
async def create_session(name: Optional[str] = None):
    """
    创建新会话

    Query参数:
        name: str 可选的会话名称

    返回:
        {
            'success': bool,
            'session_id': str,
            'name': str
        }
    """
    service = get_session_service()
    result = await service.create_session(name=name)
    return result


@router.get(
    "/sessions",
    responses={
        200: {
            "description": "获取成功",
            "content": {"application/json": {"example": {"success": True, "sessions": [{"session_id": "xxx", "name": "北京游", "message_count": 5, "last_active": "2024-01-08T12:00:00"}], "total": 1}}}
        }
    }
)
async def list_sessions(include_empty: bool = False):
    """
    列出所有会话

    Query参数:
        include_empty: bool 是否包含空会话，默认false

    返回:
        {
            'success': bool,
            'sessions': [...],
            'total': int
        }
    """
    service = get_session_service()
    return await service.list_sessions(include_empty=include_empty)


@router.delete(
    "/session/{session_id}",
    responses={
        200: {"description": "删除成功", "content": {"application/json": {"example": {"success": True}}}},
        404: {"description": "会话不存在", "content": {"application/json": {"example": {"detail": "会话不存在"}}}},
        500: {"description": "删除失败", "content": {"application/json": {"example": {"detail": "删除失败"}}}}
    }
)
async def delete_session(session_id: str):
    """
    删除会话

    路径参数:
        session_id: str 要删除的会话ID

    返回:
        {'success': bool}

    异常:
        404: 会话不存在
    """
    service = get_session_service()
    result = await service.delete_session(session_id)
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    return result


@router.put(
    "/session/{session_id}/name",
    responses={
        200: {"description": "更新成功", "content": {"application/json": {"example": {"success": True, "name": "新的名称"}}}},
        404: {"description": "会话不存在", "content": {"application/json": {"example": {"detail": "会话不存在"}}}}
    }
)
async def update_session_name(session_id: str, request: UpdateNameRequest):
    """
    更新会话名称

    路径参数:
        session_id: str 要更新的会话ID

    请求体:
        {
            "name": str 新的会话名称
        }

    返回:
        {'success': bool, 'name': str}

    异常:
        404: 会话不存在
    """
    service = get_session_service()
    result = await service.update_session_name(session_id, request.name)
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    return result


@router.put("/session/{session_id}/model")
async def set_session_model(session_id: str, request: SetModelRequest):
    """
    设置会话使用的模型

    路径参数:
        session_id: str 要设置的会话ID

    请求体:
        {
            "model_id": str 模型ID
        }

    返回:
        {'success': bool, 'model_id': str}

    异常:
        404: 会话不存在
    """
    service = get_session_service()
    result = await service.update_session_model(session_id, request.model_id)
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    return result


@router.get("/session/{session_id}/model")
async def get_session_model(session_id: str):
    """
    获取会话当前使用的模型

    路径参数:
        session_id: str 会话ID

    返回:
        {
            'success': bool,
            'model_id': str
        }

    异常:
        404: 会话不存在
    """
    service = get_session_service()
    result = await service.get_session_model(session_id)
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    return result


@router.post("/clear/{session_id}")
async def clear_chat(session_id: str):
    """
    清空会话的聊天记录

    路径参数:
        session_id: str 要清空的会话ID

    返回:
        {'success': bool}

    异常:
        404: 会话不存在
    """
    service = get_session_service()
    result = await service.clear_chat(session_id)
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error'))
    return result
