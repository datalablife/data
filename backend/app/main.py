"""
FastAPI 主应用程序
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

try:
    from .config import settings, validate_settings
    from .database import init_db, check_db_health
    from .middleware import setup_middleware, setup_rate_limiting
    from .routes import get_auth_routes
except ImportError:
    from config import settings, validate_settings
    from database import init_db, check_db_health
    from middleware import setup_middleware, setup_rate_limiting
    from routes import get_auth_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    # 启动时执行
    print("🚀 启动用户认证系统...")
    
    # 验证配置
    try:
        validate_settings()
        print("✅ 配置验证通过")
    except ValueError as e:
        print(f"❌ 配置验证失败: {e}")
        raise
    
    # 初始化数据库
    try:
        await init_db()
        print("✅ 数据库初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        raise
    
    # 检查数据库连接
    try:
        db_healthy = await check_db_health()
        if db_healthy:
            print("✅ 数据库连接正常")
        else:
            print("⚠️  数据库连接异常")
    except Exception as e:
        print(f"❌ 数据库健康检查失败: {e}")
    
    print(f"🎉 {settings.app_name} v{settings.app_version} 启动成功!")
    print(f"📍 环境: {settings.environment}")
    print(f"🔗 API文档: http://localhost:8000/docs")
    
    yield
    
    # 关闭时执行
    print("👋 正在关闭用户认证系统...")


def create_app() -> FastAPI:
    """创建 FastAPI 应用程序"""
    
    # 创建应用实例
    app = FastAPI(
        title=settings.app_name,
        description="""
        ## 🔐 用户认证系统 API
        
        一个安全、现代化的用户认证系统，提供以下功能：
        
        ### 🚀 核心功能
        - **用户注册**: 支持用户名/邮箱注册，集成 reCAPTCHA 验证
        - **用户登录**: 安全的登录验证，防暴力破解
        - **JWT 认证**: 双Token机制 (Access Token + Refresh Token)
        - **账户安全**: 账户锁定、登录日志、会话管理
        
        ### 🛡️ 安全特性
        - **密码安全**: Argon2 哈希算法，加盐存储
        - **人机验证**: Google reCAPTCHA v3 集成
        - **速率限制**: 防止暴力破解和滥用
        - **安全头**: 完整的安全响应头配置
        - **CORS 保护**: 跨域资源共享控制
        
        ### 📊 监控功能
        - **健康检查**: 系统状态监控
        - **审计日志**: 完整的认证操作记录
        - **请求追踪**: 唯一请求ID和响应时间
        
        ---
        
        **技术栈**: FastAPI + PostgreSQL + JWT + reCAPTCHA
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan
    )
    
    # 配置中间件
    setup_middleware(app)
    
    # 配置速率限制
    limiter = setup_rate_limiting(app)
    
    # 注册路由
    app.include_router(
        get_auth_routes(),
        prefix=settings.api_v1_prefix
    )
    
    # 根路径
    @app.get("/", tags=["根路径"])
    async def root():
        """根路径 - 系统信息"""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "running",
            "docs": "/docs",
            "api": settings.api_v1_prefix
        }
    
    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理器"""
        import traceback
        import uuid
        
        error_id = str(uuid.uuid4())
        
        # 记录错误详情（开发环境）
        if settings.debug:
            print(f"[ERROR-{error_id}] {type(exc).__name__}: {str(exc)}")
            print(f"Traceback: {traceback.format_exc()}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误，请稍后重试",
                "error_id": error_id,
                "path": str(request.url.path)
            }
        )
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    """直接运行时的配置"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
        server_header=False,  # 隐藏服务器信息
        date_header=False     # 隐藏日期头
    )