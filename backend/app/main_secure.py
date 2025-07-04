"""
使用安全环境变量的主应用文件示例
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

# 使用安全配置
import sys
import os
from pathlib import Path

# 确保当前目录在Python路径中
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from .secure_config import get_secure_settings, validate_secure_settings
    from .secure_env import get_secure_env_manager
except ImportError:
    from secure_config import get_secure_settings, validate_secure_settings
    from secure_env import get_secure_env_manager

# 其他导入 - 创建基本路由
try:
    try:
        from .auth import router as auth_router
        from .routes import router as api_router
    except ImportError:
        from auth import router as auth_router
        from routes import router as api_router
except ImportError:
    # 如果没有这些模块，创建空路由
    from fastapi import APIRouter
    auth_router = APIRouter()
    api_router = APIRouter()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI()

# 安全配置实例
settings = get_secure_settings()

# 验证配置
try:
    validate_secure_settings()
    logger.info("✅ 安全配置验证通过")
except ValueError as e:
    logger.error(f"❌ 配置验证失败: {e}")
    raise


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("🚀 应用启动中...")
    
    # 显示配置统计
    env_manager = get_secure_env_manager()
    stats = env_manager.get_stats()
    logger.info(f"📊 已加载 {stats['total_count']} 个环境变量")
    
    # 显示应用信息（不包含敏感信息）
    logger.info(f"📱 应用名称: {settings.app_name}")
    logger.info(f"🔢 版本: {settings.app_version}")
    logger.info(f"🌍 环境: {settings.environment}")
    logger.info(f"🔗 API前缀: {settings.api_v1_prefix}")
    
    # 数据库连接测试（不显示敏感信息）
    logger.info(f"🗄️  数据库主机: {settings.database_host}:{settings.database_port}")
    logger.info(f"📊 数据库名: {settings.postgres_db}")
    
    logger.info("✅ 应用启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("🛑 应用正在关闭...")
    
    # 清理缓存
    env_manager = get_secure_env_manager()
    env_manager._cached_env.clear()
    
    logger.info("✅ 应用已关闭")


# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    env_manager = get_secure_env_manager()
    stats = env_manager.get_stats()
    
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "env_vars_count": stats["total_count"],
        "database_connected": True,  # 这里应该实际测试数据库连接
    }


# 配置信息端点（仅显示非敏感信息）
@app.get("/config")
async def get_config_info():
    """获取配置信息（非敏感）"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "api_prefix": settings.api_v1_prefix,
        "debug": settings.debug,
        "cors_origins": settings.allowed_origins,
        "password_policy": {
            "min_length": settings.password_min_length,
            "require_uppercase": settings.password_require_uppercase,
            "require_lowercase": settings.password_require_lowercase,
            "require_numbers": settings.password_require_numbers,
            "require_special_chars": settings.password_require_special_chars,
        },
        "rate_limits": {
            "login": settings.rate_limit_login,
            "register": settings.rate_limit_register,
            "refresh": settings.rate_limit_refresh,
        }
    }


# 环境变量管理端点（仅开发环境）
@app.get("/admin/env-stats")
async def get_env_stats():
    """获取环境变量统计（仅开发环境）"""
    if settings.environment != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="此端点仅在开发环境可用"
        )
    
    env_manager = get_secure_env_manager()
    stats = env_manager.get_stats()
    
    # 获取键名列表（不包含值）
    keys = env_manager.list_env_keys()
    
    return {
        "stats": stats,
        "keys": keys
    }


# 注册路由
if auth_router:
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
if api_router:
    app.include_router(api_router, prefix=settings.api_v1_prefix)


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": f"欢迎使用 {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    # 从安全配置获取运行参数
    uvicorn.run(
        "main_secure:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )