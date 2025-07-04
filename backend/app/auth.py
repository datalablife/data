"""
认证相关业务逻辑
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
import uuid
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .database import User, RefreshToken, AuthLog
from .schemas import (
    UserCreate, UserLogin, UserResponse, AuthLogCreate,
    AccountSecurityInfo, UserSession
)
from .security import (
    password_manager, jwt_manager, captcha_verifier, security_utils
)
from .config import settings


class AuthService:
    """认证服务类"""
    
    def __init__(self):
        self.max_login_attempts = settings.max_login_attempts
        self.lockout_duration = timedelta(minutes=settings.account_lockout_duration_minutes)
    
    async def register_user(
        self,
        user_data: UserCreate,
        request: Request,
        db: AsyncSession
    ) -> UserResponse:
        """
        用户注册
        
        Args:
            user_data: 用户注册数据
            request: HTTP请求对象
            db: 数据库会话
            
        Returns:
            UserResponse: 注册成功的用户信息
            
        Raises:
            HTTPException: 注册失败时抛出异常
        """
        # 1. 验证reCAPTCHA
        client_ip = security_utils.get_client_ip(request)
        captcha_result = await captcha_verifier.verify_captcha(
            user_data.captcha_token,
            client_ip
        )
        
        if not captcha_result.success:
            await self._log_auth_event(
                db, None, "register", client_ip,
                request.headers.get("user-agent"),
                False, {"error": "captcha_failed", "captcha_errors": captcha_result.error_codes}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="人机验证失败，请重试"
            )
        
        # 2. 检查用户名和邮箱是否已存在
        existing_user = await db.execute(
            select(User).where(
                or_(
                    User.username == user_data.username,
                    User.email == user_data.email
                )
            )
        )
        existing_user = existing_user.scalar_one_or_none()
        
        if existing_user:
            error_detail = "用户名已存在" if existing_user.username == user_data.username else "邮箱已被注册"
            await self._log_auth_event(
                db, None, "register", client_ip,
                request.headers.get("user-agent"),
                False, {"error": "user_exists", "detail": error_detail}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail
            )
        
        # 3. 哈希密码
        hashed_password, salt = password_manager.hash_password(user_data.password)
        
        # 4. 创建用户
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            salt=salt,
            is_active=True,
            is_verified=False  # 需要邮箱验证
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        # 5. 记录注册日志
        await self._log_auth_event(
            db, new_user.id, "register", client_ip,
            request.headers.get("user-agent"),
            True, {"username": user_data.username, "email": user_data.email}
        )
        
        return UserResponse.from_orm(new_user)
    
    async def authenticate_user(
        self,
        login_data: UserLogin,
        request: Request,
        db: AsyncSession
    ) -> Tuple[UserResponse, dict]:
        """
        用户登录认证
        
        Args:
            login_data: 登录数据
            request: HTTP请求对象
            db: 数据库会话
            
        Returns:
            Tuple[UserResponse, dict]: 用户信息和令牌数据
            
        Raises:
            HTTPException: 认证失败时抛出异常
        """
        client_ip = security_utils.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # 1. 验证reCAPTCHA
        captcha_result = await captcha_verifier.verify_captcha(
            login_data.captcha_token,
            client_ip
        )
        
        if not captcha_result.success:
            await self._log_auth_event(
                db, None, "failed_login", client_ip, user_agent,
                False, {"error": "captcha_failed", "username": login_data.username}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="人机验证失败，请重试"
            )
        
        # 2. 查找用户（支持用户名或邮箱登录）
        user = await db.execute(
            select(User).where(
                or_(
                    User.username == login_data.username,
                    User.email == login_data.username
                )
            )
        )
        user = user.scalar_one_or_none()
        
        if not user:
            await self._log_auth_event(
                db, None, "failed_login", client_ip, user_agent,
                False, {"error": "user_not_found", "username": login_data.username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 3. 检查账户状态
        if not user.is_active:
            await self._log_auth_event(
                db, user.id, "failed_login", client_ip, user_agent,
                False, {"error": "account_inactive", "username": login_data.username}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账户已被禁用"
            )
        
        # 4. 检查账户是否被锁定
        if user.locked_until and user.locked_until > datetime.utcnow():
            await self._log_auth_event(
                db, user.id, "failed_login", client_ip, user_agent,
                False, {"error": "account_locked", "locked_until": user.locked_until.isoformat()}
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"账户已被锁定，请在 {user.locked_until.strftime('%Y-%m-%d %H:%M:%S')} 后重试"
            )
        
        # 5. 验证密码
        if not password_manager.verify_password(login_data.password, user.hashed_password, user.salt):
            # 增加失败尝试次数
            user.failed_login_attempts += 1
            
            # 检查是否需要锁定账户
            if user.failed_login_attempts >= self.max_login_attempts:
                user.locked_until = datetime.utcnow() + self.lockout_duration
                await self._log_auth_event(
                    db, user.id, "account_locked", client_ip, user_agent,
                    True, {"attempts": user.failed_login_attempts}
                )
            
            await db.commit()
            
            await self._log_auth_event(
                db, user.id, "failed_login", client_ip, user_agent,
                False, {"error": "invalid_password", "attempts": user.failed_login_attempts}
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 6. 登录成功，重置失败尝试次数
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        
        # 7. 检查密码是否需要重新哈希
        if password_manager.needs_rehash(user.hashed_password):
            new_hashed, new_salt = password_manager.hash_password(login_data.password)
            user.hashed_password = new_hashed
            user.salt = new_salt
        
        await db.commit()
        
        # 8. 生成JWT令牌
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_verified": user.is_verified
        }
        
        access_token = jwt_manager.create_access_token(token_data)
        refresh_token = jwt_manager.create_refresh_token({"sub": str(user.id)})
        
        # 9. 存储刷新令牌
        await self._store_refresh_token(
            db, user.id, refresh_token, client_ip, user_agent, login_data.remember_me
        )
        
        # 10. 记录登录日志
        await self._log_auth_event(
            db, user.id, "login", client_ip, user_agent,
            True, {"username": user.username}
        )
        
        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60
        }
        
        return UserResponse.from_orm(user), tokens
    
    async def refresh_access_token(
        self,
        refresh_token: str,
        request: Request,
        db: AsyncSession
    ) -> dict:
        """
        刷新访问令牌
        
        Args:
            refresh_token: 刷新令牌
            request: HTTP请求对象
            db: 数据库会话
            
        Returns:
            dict: 新的访问令牌数据
            
        Raises:
            HTTPException: 刷新失败时抛出异常
        """
        # 1. 验证刷新令牌
        payload = jwt_manager.verify_token(refresh_token, "refresh")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌格式错误"
            )
        
        # 2. 检查刷新令牌是否在数据库中存在且有效
        token_hash = security_utils.hash_token(refresh_token)
        stored_token = await db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.user_id == uuid.UUID(user_id),
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.expires_at > datetime.utcnow(),
                    RefreshToken.is_revoked == False
                )
            )
        )
        stored_token = stored_token.scalar_one_or_none()
        
        if not stored_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌已过期或无效"
            )
        
        # 3. 获取用户信息
        user = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = user.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用"
            )
        
        # 4. 生成新的访问令牌
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_verified": user.is_verified
        }
        
        new_access_token = jwt_manager.create_access_token(token_data)
        
        # 5. 记录令牌刷新日志
        client_ip = security_utils.get_client_ip(request)
        await self._log_auth_event(
            db, user.id, "token_refresh", client_ip,
            request.headers.get("user-agent"),
            True, {"username": user.username}
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60
        }
    
    async def logout_user(
        self,
        refresh_token: str,
        request: Request,
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        用户登出
        
        Args:
            refresh_token: 刷新令牌
            request: HTTP请求对象
            db: 数据库会话
            user_id: 用户ID（可选）
            
        Returns:
            bool: 登出是否成功
        """
        try:
            # 撤销刷新令牌
            token_hash = security_utils.hash_token(refresh_token)
            
            query = update(RefreshToken).where(
                RefreshToken.token_hash == token_hash
            ).values(is_revoked=True)
            
            if user_id:
                query = query.where(RefreshToken.user_id == user_id)
            
            await db.execute(query)
            await db.commit()
            
            # 记录登出日志
            if user_id:
                client_ip = security_utils.get_client_ip(request)
                await self._log_auth_event(
                    db, user_id, "logout", client_ip,
                    request.headers.get("user-agent"),
                    True, {}
                )
            
            return True
        except Exception:
            return False
    
    async def get_current_user(
        self,
        token: str,
        db: AsyncSession
    ) -> UserSession:
        """
        根据访问令牌获取当前用户
        
        Args:
            token: 访问令牌
            db: 数据库会话
            
        Returns:
            UserSession: 用户会话信息
            
        Raises:
            HTTPException: 令牌无效时抛出异常
        """
        # 验证访问令牌
        payload = jwt_manager.verify_token(token, "access")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的访问令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌格式错误",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 获取用户信息
        user = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = user.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return UserSession(
            user_id=user.id,
            username=user.username,
            email=user.email,
            is_verified=user.is_verified,
            permissions=[]  # 可以根据需要添加权限系统
        )
    
    async def get_account_security_info(
        self,
        user_id: uuid.UUID,
        db: AsyncSession
    ) -> AccountSecurityInfo:
        """获取账户安全信息"""
        user = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 统计活跃会话数
        active_sessions = await db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.expires_at > datetime.utcnow(),
                    RefreshToken.is_revoked == False
                )
            )
        )
        active_sessions_count = len(active_sessions.scalars().all())
        
        return AccountSecurityInfo(
            failed_login_attempts=user.failed_login_attempts,
            is_locked=user.locked_until is not None and user.locked_until > datetime.utcnow(),
            locked_until=user.locked_until,
            last_login=user.last_login,
            active_sessions=active_sessions_count
        )
    
    async def _store_refresh_token(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        refresh_token: str,
        ip_address: str,
        user_agent: str,
        remember_me: bool = False
    ):
        """存储刷新令牌"""
        token_hash = security_utils.hash_token(refresh_token)
        expires_at = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
        
        # 如果不是"记住我"，缩短过期时间
        if not remember_me:
            expires_at = datetime.utcnow() + timedelta(hours=24)
        
        device_info = {
            "user_agent": security_utils.sanitize_user_agent(user_agent),
            "ip_address": ip_address,
            "remember_me": remember_me
        }
        
        refresh_token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=json.dumps(device_info),
            ip_address=ip_address
        )
        
        db.add(refresh_token_record)
        await db.commit()
    
    async def _log_auth_event(
        self,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        action: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        details: dict
    ):
        """记录认证事件日志"""
        log_entry = AuthLog(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=security_utils.sanitize_user_agent(user_agent),
            success=success,
            details=json.dumps(details) if details else None
        )
        
        db.add(log_entry)
        await db.commit()


# HTTP Bearer 认证方案
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    db: AsyncSession = None
) -> UserSession:
    """依赖注入：获取当前用户"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    auth_service = AuthService()
    return await auth_service.get_current_user(credentials.credentials, db)


# 创建全局认证服务实例
auth_service = AuthService()