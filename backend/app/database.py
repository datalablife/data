"""
数据库连接和模型定义
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from typing import AsyncGenerator

from .config import settings


# 创建异步数据库引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # 开发环境下显示SQL语句
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 连接池预检查
    pool_recycle=3600,   # 1小时后回收连接
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """数据库模型基类"""
    pass


class User(Base):
    """用户表模型"""
    __tablename__ = "users"
    
    # 主键 - 使用UUID防止ID枚举攻击
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="用户唯一标识"
    )
    
    # 用户基本信息
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="用户名"
    )
    
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="邮箱地址"
    )
    
    # 密码相关 - 绝不存储明文密码
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="哈希后的密码"
    )
    
    salt: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码盐值"
    )
    
    # 账户状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="账户是否激活"
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="邮箱是否已验证"
    )
    
    # 安全相关
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="失败登录尝试次数"
    )
    
    locked_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="账户锁定到期时间"
    )
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )
    
    last_login: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class RefreshToken(Base):
    """刷新令牌表模型"""
    __tablename__ = "refresh_tokens"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="令牌唯一标识"
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="用户ID"
    )
    
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="令牌哈希值"
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="过期时间"
    )
    
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否已撤销"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间"
    )
    
    # 设备信息 (可选)
    device_info: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="设备信息JSON"
    )
    
    ip_address: Mapped[str] = mapped_column(
        String(45),  # 支持IPv6
        nullable=True,
        comment="IP地址"
    )
    
    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


class AuthLog(Base):
    """认证日志表模型"""
    __tablename__ = "auth_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="日志唯一标识"
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # 注册失败时可能没有user_id
        index=True,
        comment="用户ID"
    )
    
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="操作类型: login, logout, register, failed_login"
    )
    
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=True,
        comment="IP地址"
    )
    
    user_agent: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="用户代理"
    )
    
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="操作是否成功"
    )
    
    details: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="详细信息JSON"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        comment="创建时间"
    )
    
    def __repr__(self) -> str:
        return f"<AuthLog(id={self.id}, action='{self.action}', success={self.success})>"


# 数据库会话依赖
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 数据库初始化
async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)


# 数据库健康检查
async def check_db_health() -> bool:
    """检查数据库连接健康状态"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False