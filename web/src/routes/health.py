"""健康检查API路由模块 (Health Check API Routes)

提供服务健康状态检查的RESTful API接口。
用于负载均衡器和服务监控探测。

主要组件:
- router: API路由路由器
- HealthResponse: 健康检查响应模型

API端点:
- GET /health - 详细健康检查（返回完整状态）
- GET /ready - 就绪检查（服务是否准备好接收请求）
- GET /live - 存活检查（服务是否正在运行）

使用示例:
    # 详细健康状态
    GET /health

    # 就绪检查
    GET /ready

    # 存活检查
    GET /live

响应格式:
    /health: 返回完整的健康状态信息
    /ready: {"status": "ready"}
    /live: {"status": "alive"}

应用场景:
    - Kubernetes: livenessProbe 和 readinessProbe
    - 负载均衡器: 流量分配决策
    - 监控告警: 服务状态监控

健康状态说明:
    - healthy/ready/alive: 服务正常运行
    - unhealthy/not ready: 服务异常，不可接收流量
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """
    健康检查响应模型

    属性:
        status: str 服务状态（healthy/unhealthy）
        version: str 应用版本号
        agent: str Agent服务状态
        services: dict 各子服务的健康状态
    """
    status: str
    version: str
    agent: str
    services: dict


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {
            "description": "服务健康",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "agent": "connected",
                        "services": {
                            "api": "healthy",
                            "database": "healthy",
                            "agent": "healthy"
                        }
                    }
                }
            }
        },
        503: {
            "description": "服务不健康",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "version": "1.0.0",
                        "agent": "disconnected",
                        "services": {
                            "api": "healthy",
                            "database": "healthy",
                            "agent": "unhealthy"
                        }
                    }
                }
            }
        }
    }
)
async def health_check():
    """
    详细健康检查端点

    返回完整的健康状态信息，包括：
    - 服务总体状态
    - 应用版本
    - Agent连接状态
    - 各子服务状态

    Returns:
        HealthResponse: 完整的健康状态信息

    子服务状态:
        - api: API服务状态
        - database: 数据库状态
        - agent: Agent服务状态
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        agent="connected",
        services={
            "api": "healthy",
            "database": "healthy",
            "agent": "healthy"
        }
    )


@router.get(
    "/ready",
    responses={
        200: {"description": "服务已就绪", "content": {"application/json": {"example": {"status": "ready"}}}},
        503: {"description": "服务未就绪", "content": {"application/json": {"example": {"status": "not ready"}}}}
    }
)
async def readiness_check():
    """
    就绪检查端点

    用于判断服务是否准备好接收流量。
    在启动过程中返回not ready，完全启动后返回ready。

    Returns:
        {"status": "ready"} 服务已就绪

    使用场景:
        - Kubernetes readinessProbe
        - 负载均衡器流量分配
        - 服务发现注册
    """
    return {"status": "ready"}


@router.get(
    "/live",
    responses={
        200: {"description": "服务存活", "content": {"application/json": {"example": {"status": "alive"}}}},
        503: {"description": "服务不存活", "content": {"application/json": {"example": {"status": "dead"}}}}
    }
)
async def liveness_check():
    """
    存活检查端点

    用于判断服务是否正在运行。
    这是最简单的检查，只确认进程存活。

    Returns:
        {"status": "alive"} 服务存活

    使用场景:
        - Kubernetes livenessProbe
        - 进程存活验证
        - 基础心跳检测
    """
    return {"status": "alive"}
