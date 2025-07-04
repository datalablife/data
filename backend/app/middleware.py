"""
中间件配置
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time
import uuid
from typing import Callable

from .config import settings
from .security import security_utils


def setup_middleware(app: FastAPI) -> None:
    """配置所有中间件"""
    
    # 1. HTTPS 重定向中间件（生产环境）
    if settings.environment == "production":
        app.add_middleware(HTTPSRedirectMiddleware)
    
    # 2. 受信任主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts + ["*"] if settings.debug else settings.allowed_hosts
    )
    
    # 3. CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time"]
    )
    
    # 4. 速率限制中间件
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    
    # 5. 安全头中间件
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Callable) -> Response:
        """添加安全响应头"""
        response = await call_next(request)
        
        # 安全头
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://www.google.com https://www.gstatic.com; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https:; "
                "frame-src https://www.google.com;"
            )
        }
        
        # 生产环境添加 HSTS
        if settings.environment == "production":
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    # 6. 请求ID和响应时间中间件
    @app.middleware("http")
    async def add_request_id_and_timing(request: Request, call_next: Callable) -> Response:
        """添加请求ID和响应时间"""
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 记录开始时间
        start_time = time.time()
        
        # 处理请求
        response = await call_next(request)
        
        # 计算响应时间
        process_time = time.time() - start_time
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{process_time:.4f}s"
        
        return response
    
    # 7. 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        """记录请求日志"""
        # 获取客户端信息
        client_ip = security_utils.get_client_ip(request)
        user_agent = security_utils.sanitize_user_agent(
            request.headers.get("user-agent", "")
        )
        
        # 记录请求开始
        start_time = time.time()
        
        # 处理请求
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 记录日志（这里可以集成到日志系统）
        log_data = {
            "request_id": getattr(request.state, "request_id", "unknown"),
            "method": request.method,
            "url": str(request.url),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "status_code": response.status_code,
            "process_time": process_time
        }
        
        # 在开发环境打印日志
        if settings.debug:
            print(f"[{log_data['request_id']}] {log_data['method']} {log_data['url']} - "
                  f"{log_data['status_code']} - {log_data['process_time']:.4f}s")
        
        return response
    
    # 8. 错误处理中间件
    @app.middleware("http")
    async def catch_exceptions(request: Request, call_next: Callable) -> Response:
        """全局异常捕获"""
        try:
            return await call_next(request)
        except Exception as e:
            # 记录错误（这里可以集成到日志系统）
            error_id = str(uuid.uuid4())
            
            if settings.debug:
                print(f"[ERROR-{error_id}] {type(e).__name__}: {str(e)}")
            
            # 返回通用错误响应
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "INTERNAL_SERVER_ERROR",
                    "message": "服务器内部错误，请稍后重试",
                    "error_id": error_id
                }
            )


def setup_rate_limiting(app: FastAPI) -> Limiter:
    """配置速率限制"""
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    
    # 自定义速率限制错误处理
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """速率限制异常处理"""
        from fastapi.responses import JSONResponse
        
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": "RATE_LIMIT_EXCEEDED",
                "message": f"请求过于频繁，请稍后重试。限制: {exc.detail}",
                "retry_after": getattr(exc, "retry_after", None)
            },
            headers={"Retry-After": str(getattr(exc, "retry_after", 60))}
        )
    
    return limiter


# 中间件工具函数
def get_request_id(request: Request) -> str:
    """获取请求ID"""
    return getattr(request.state, "request_id", "unknown")


def is_safe_path(path: str) -> bool:
    """检查路径是否安全"""
    # 防止路径遍历攻击
    dangerous_patterns = ["../", "..\\", "/etc/", "/proc/", "C:\\"]
    return not any(pattern in path for pattern in dangerous_patterns)


def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    import re
    # 移除危险字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 限制长度
    return filename[:255]