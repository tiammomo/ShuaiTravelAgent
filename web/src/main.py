"""
ShuaiTravelAgent Web API Server

FastAPI-based web server for the travel agent application.
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import chat_router, session_router, model_router, city_router, health_router
from src.routes.model import set_config_manager


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ShuaiTravelAgent API",
        description="AI Travel Assistant API with SSE streaming support",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware - 生产环境应该限制为实际的前端域名
    allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Initialize ConfigManager and pass to routes
    try:
        # Get project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, 'config', 'llm_config.yaml')

        from src.config.config_manager import ConfigManager
        config_manager = ConfigManager(config_path)
        print(f"[*] Config loaded from: {config_path}")

        # Pass config manager to model router
        set_config_manager(config_manager)

        # Also pass to other routes that need it
        if hasattr(chat_router, 'set_config_manager'):
            chat_router.set_config_manager(config_manager)

    except Exception as e:
        print(f"[!] Warning: Could not load config: {e}")

    # Initialize dependency injection container
    from src.dependencies.container import get_container
    get_container()
    print("[*] Dependency container initialized")

    # Include routers
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(session_router, prefix="/api", tags=["session"])
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    app.include_router(model_router, prefix="/api", tags=["model"])
    app.include_router(city_router, prefix="/api", tags=["city"])

    # Initialize gRPC stub for chat service
    try:
        from src.routes.chat import init_grpc_stub
        init_grpc_stub()
        print("[*] gRPC client initialized")
    except Exception as e:
        print(f"[!] Warning: Could not initialize gRPC client: {e}")

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "ShuaiTravelAgent API",
            "version": "1.0.0",
            "docs": "/docs"
        }

    return app


# Create app instance
app = create_app()


def main(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Run the server."""
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    main(args.host, args.port, args.debug)
