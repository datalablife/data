"""
Pydantic 数据模型和验证
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import re


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")


class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    captcha_token: str = Field(..., description="reCAPTCHA令牌")
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名格式"""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        
        # 检查是否以数字开头
        if v[0].isdigit():
            raise ValueError('用户名不能以数字开头')
        
        # 检查保留用户名
        reserved_names = ['admin', 'root', 'system', 'api', 'www', 'mail', 'ftp']
        if v.lower() in reserved_names:
            raise ValueError('该用户名为系统保留，请选择其他用户名')
        
        return v
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        errors = []
        
        if len(v) < 8:
            errors.append('密码长度至少8位')
        
        if not re.search(r'[A-Z]', v):
            errors.append('密码必须包含大写字母')
        
        if not re.search(r'[a-z]', v):
            errors.append('密码必须包含小写字母')
        
        if not re.search(r'\d', v):
            errors.append('密码必须包含数字')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            errors.append('密码必须包含特殊字符')
        
        # 检查常见弱密码
        weak_passwords = [
            'password', '12345678', 'qwerty123', 'abc123456',
            'password123', '123456789', 'admin123'
        ]
        if v.lower() in weak_passwords:
            errors.append('密码过于简单，请选择更复杂的密码')
        
        if errors:
            raise ValueError('; '.join(errors))
        
        return v


class UserLogin(BaseModel):
    """用户登录模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")
    captcha_token: str = Field(..., description="reCAPTCHA令牌")
    remember_me: bool = Field(default=False, description="记住我")


class UserResponse(UserBase):
    """用户响应模型"""
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """用户更新模型"""
    email: Optional[EmailStr] = None
    
    @validator('email')
    def validate_email_change(cls, v):
        """验证邮箱变更"""
        if v:
            # 这里可以添加额外的邮箱验证逻辑
            pass
        return v


class PasswordChange(BaseModel):
    """密码修改模型"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """验证新密码强度"""
        # 复用UserCreate的密码验证逻辑
        return UserCreate.validate_password(v)


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    """Token刷新模型"""
    refresh_token: str = Field(..., description="刷新令牌")


class LoginResponse(BaseModel):
    """登录响应模型"""
    success: bool = True
    message: str = "登录成功"
    data: Dict[str, Any]


class RegisterResponse(BaseModel):
    """注册响应模型"""
    success: bool = True
    message: str = "注册成功"
    data: UserResponse


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """成功响应模型"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


# reCAPTCHA 相关模型
class CaptchaVerifyRequest(BaseModel):
    """CAPTCHA验证请求模型"""
    token: str = Field(..., description="reCAPTCHA令牌")
    action: str = Field(default="submit", description="操作类型")


class CaptchaVerifyResponse(BaseModel):
    """CAPTCHA验证响应模型"""
    success: bool
    score: Optional[float] = None
    action: Optional[str] = None
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    error_codes: Optional[list] = None


# 用户会话模型
class UserSession(BaseModel):
    """用户会话模型"""
    user_id: uuid.UUID
    username: str
    email: str
    is_verified: bool
    permissions: list = []


# 审计日志模型
class AuthLogCreate(BaseModel):
    """认证日志创建模型"""
    user_id: Optional[uuid.UUID] = None
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    details: Optional[Dict[str, Any]] = None


class AuthLogResponse(BaseModel):
    """认证日志响应模型"""
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    action: str
    ip_address: Optional[str]
    success: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# 账户安全模型
class AccountSecurityInfo(BaseModel):
    """账户安全信息模型"""
    failed_login_attempts: int
    is_locked: bool
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    active_sessions: int = 0


# 系统健康检查模型
class HealthCheck(BaseModel):
    """系统健康检查模型"""
    status: str = "healthy"
    database: bool = True
    redis: bool = True
    timestamp: datetime
    version: str


# 分页模型
class PaginationParams(BaseModel):
    """分页参数模型"""
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel):
    """分页响应模型"""
    items: list
    total: int
    page: int
    size: int
    pages: int
    
    @classmethod
    def create(cls, items: list, total: int, page: int, size: int):
        """创建分页响应"""
        pages = (total + size - 1) // size  # 向上取整
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )