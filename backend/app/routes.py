"""
API 路由定义
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from .database import get_db
from .schemas import (
    UserCreate, UserLogin, UserResponse, TokenRefresh,
    LoginResponse, RegisterResponse, ErrorResponse, SuccessResponse,
    TokenResponse, AccountSecurityInfo
)
from .auth import auth_service, security_scheme, get_current_user
from .security import security_utils


# 创建路由器
auth_router = APIRouter(prefix="/auth", tags=["认证"])
users_router = APIRouter(prefix="/users", tags=["用户"])


@auth_router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="用户注册，包含 CAPTCHA 验证"
)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册端点
    
    - **username**: 用户名 (3-50字符，只能包含字母、数字、下划线)
    - **email**: 邮箱地址
    - **password**: 密码 (至少8位，包含大小写字母、数字、特殊字符)
    - **captcha_token**: reCAPTCHA令牌
    """
    try:
        user = await auth_service.register_user(user_data, request, db)
        return RegisterResponse(
            success=True,
            message="注册成功，请查收邮箱验证邮件",
            data=user
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    summary="用户登录",
    description="用户登录，验证凭据和 CAPTCHA 后，返回 JWT Access Token 和 Refresh Token"
)
async def login(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录端点
    
    - **username**: 用户名或邮箱
    - **password**: 密码
    - **captcha_token**: reCAPTCHA令牌
    - **remember_me**: 是否记住登录状态
    """
    try:
        user, tokens = await auth_service.authenticate_user(login_data, request, db)
        
        return LoginResponse(
            success=True,
            message="登录成功",
            data={
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "expires_in": tokens["expires_in"],
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "is_verified": user.is_verified
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@auth_router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新访问令牌",
    description="使用 Refresh Token 获取一个新的 Access Token"
)
async def refresh_token(
    token_data: TokenRefresh,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    刷新访问令牌端点
    
    - **refresh_token**: 刷新令牌
    """
    try:
        new_tokens = await auth_service.refresh_access_token(
            token_data.refresh_token, request, db
        )
        
        return TokenResponse(**new_tokens)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="令牌刷新失败，请重新登录"
        )


@auth_router.post(
    "/logout",
    response_model=SuccessResponse,
    summary="用户登出",
    description="使 Refresh Token 失效"
)
async def logout(
    token_data: TokenRefresh,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登出端点
    
    需要在请求头中提供 Authorization: Bearer <access_token>
    请求体中提供 refresh_token
    """
    try:
        # 获取当前用户信息
        current_user = await get_current_user(credentials, db)
        
        # 登出用户
        success = await auth_service.logout_user(
            token_data.refresh_token, request, db, current_user.user_id
        )
        
        if success:
            return SuccessResponse(
                success=True,
                message="登出成功"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="登出失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败，请稍后重试"
        )


@users_router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户信息",
    description="一个受保护的路由，用于验证 Access Token 并返回当前用户信息"
)
async def get_current_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户信息端点
    
    需要在请求头中提供 Authorization: Bearer <access_token>
    """
    try:
        # 获取当前用户会话信息
        current_user = await get_current_user(credentials, db)
        
        # 从数据库获取完整用户信息
        from sqlalchemy import select
        from .database import User
        
        user = await db.execute(
            select(User).where(User.id == current_user.user_id)
        )
        user = user.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return UserResponse.from_orm(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


@users_router.get(
    "/me/security",
    response_model=AccountSecurityInfo,
    summary="获取账户安全信息",
    description="获取当前用户的账户安全状态信息"
)
async def get_account_security(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    获取账户安全信息端点
    
    返回账户的安全状态，包括登录失败次数、锁定状态等
    """
    try:
        current_user = await get_current_user(credentials, db)
        security_info = await auth_service.get_account_security_info(
            current_user.user_id, db
        )
        return security_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取安全信息失败"
        )


@users_router.post(
    "/me/logout-all",
    response_model=SuccessResponse,
    summary="登出所有设备",
    description="撤销用户的所有刷新令牌，强制所有设备重新登录"
)
async def logout_all_devices(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
):
    """
    登出所有设备端点
    
    撤销用户的所有刷新令牌，用于安全场景下强制所有设备重新登录
    """
    try:
        current_user = await get_current_user(credentials, db)
        
        # 撤销所有刷新令牌
        from sqlalchemy import update
        from .database import RefreshToken
        
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == current_user.user_id)
            .values(is_revoked=True)
        )
        await db.commit()
        
        return SuccessResponse(
            success=True,
            message="已成功登出所有设备"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="操作失败，请稍后重试"
        )


# 健康检查端点
@auth_router.get(
    "/health",
    summary="健康检查",
    description="检查认证服务的健康状态"
)
async def health_check(db: AsyncSession = Depends(get_db)):
    """健康检查端点"""
    try:
        from .database import check_db_health
        from datetime import datetime
        
        db_healthy = await check_db_health()
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": db_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# 错误处理
@auth_router.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """认证相关异常处理"""
    return ErrorResponse(
        success=False,
        error=exc.detail,
        message=exc.detail
    )


# 组合所有路由
def get_auth_routes() -> APIRouter:
    """获取认证相关的所有路由"""
    main_router = APIRouter()
    main_router.include_router(auth_router)
    main_router.include_router(users_router)
    return main_router