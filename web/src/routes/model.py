"""模型API路由模块 (Model API Routes)

提供AI模型信息查询的RESTful API接口。
支持列出可用模型、获取模型详情等功能。

主要组件:
- router: API路由路由器
- _config_manager: 全局配置管理器实例

API端点:
- GET /models - 列出所有可用模型
- GET /models/{model_id} - 获取模型详细信息

功能特点:
- 动态从ConfigManager获取模型配置
- 支持回退到默认模型列表
- 支持动态获取模型详情

使用示例:
    # 列出所有可用模型
    GET /models

    # 获取特定模型详情
    GET /models/gpt-4o-mini

配置说明:
    _config_manager 通过 set_config_manager() 函数设置
    用于从配置文件动态加载模型配置

回退机制:
    如果_config_manager未设置或查询失败，使用内置的默认模型列表
    默认包含：gpt-4o-mini, gpt-4o, claude-3-5-sonnet

返回格式:
    成功: {"success": True, "models": [...]} 或 {"success": True, ...model_details}
    失败: {"success": False, "error": "错误信息"}
"""

from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter()

# 全局配置管理器实例
# 通过 set_config_manager() 设置，用于动态加载模型配置
_config_manager: Any = None


def set_config_manager(config_manager):
    """
    设置配置管理器实例

    Args:
        config_manager: 配置管理器对象，需提供 get_available_models() 和 get_model_config() 方法
    """
    global _config_manager
    _config_manager = config_manager


@router.get(
    "/models",
    responses={
        200: {
            "description": "获取成功",
            "content": {"application/json": {"example": {"success": True, "models": [{"model_id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"}, {"model_id": "gpt-4o", "name": "GPT-4o", "provider": "openai"}]}}}
        },
        500: {"description": "获取失败", "content": {"application/json": {"example": {"success": False, "error": "无法获取模型列表"}}}}
    }
)
async def list_models():
    """
    列出所有可用模型

    优先从ConfigManager动态获取模型列表，
    如果ConfigManager未设置或获取失败，使用默认模型列表。

    返回:
        {
            "success": bool,
            "models": [...]  // 模型配置列表
        }

    模型配置项:
        - model_id: str 模型唯一标识
        - name: str 模型名称
        - provider: str 提供商 (openai/anthropic/google等)
    """
    if _config_manager:
        # 从 ConfigManager 动态获取模型列表
        models = _config_manager.get_available_models()
        return {"success": True, "models": models}

    # 回退到默认模型列表
    return {
        "success": True,
        "models": [
            {
                "model_id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "openai"
            },
            {
                "model_id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "openai"
            },
            {
                "model_id": "claude-3-5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "provider": "anthropic"
            }
        ]
    }


@router.get(
    "/models/{model_id}",
    responses={
        200: {
            "description": "获取成功",
            "content": {"application/json": {"example": {"success": True, "model_id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "model": "gpt-4o-mini", "temperature": 0.7}}}
        },
        404: {"description": "模型不存在", "content": {"application/json": {"example": {"success": False, "error": "Model not found"}}}},
        500: {"description": "获取失败", "content": {"application/json": {"example": {"success": False, "error": "无法获取模型配置"}}}}
    }
)
async def get_model(model_id: str):
    """
    获取模型详细信息

    路径参数:
        model_id: str 模型唯一标识

    优先从ConfigManager获取详细配置，
    如果ConfigManager未设置或查询失败，使用默认模型详情。

    返回:
        {
            "success": bool,
            "model_id": str,
            "name": str,
            "provider": str,
            ... 其他配置项
        }

    错误:
        {"success": False, "error": "Model not found"} 模型不存在
    """
    if _config_manager:
        try:
            model_config = _config_manager.get_model_config(model_id)
            return {
                "success": True,
                "model_id": model_id,
                "name": model_config.get('name', model_id),
                "provider": model_config.get('provider', 'unknown'),
                **model_config
            }
        except ValueError:
            # ConfigManager抛出异常表示模型不存在
            pass

    # 回退到默认模型详情
    models = {
        "gpt-4o-mini": {"name": "GPT-4o Mini", "provider": "openai", "description": "高效快速的小型模型"},
        "gpt-4o": {"name": "GPT-4o", "provider": "openai", "description": "强大的多模态模型"},
        "claude-3-5-sonnet": {"name": "Claude 3.5 Sonnet", "provider": "anthropic", "description": "平衡性能与速度"},
    }

    if model_id not in models:
        return {"success": False, "error": "Model not found"}

    return {"success": True, "model_id": model_id, **models[model_id]}
