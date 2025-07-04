"""
应用配置模块
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os

# 尝试导入安全环境变量系统
try:
    try:
        from .secure_env import init_secure_env
    except ImportError:
        from secure_env import init_secure_env
    # 初始化安全环境变量系统
    init_secure_env(auto_load=True)
    print("✅ 已加载安全环境变量系统")
except ImportError:
    print("⚠️  未找到安全环境变量系统，使用传统.env文件")
except Exception as e:
    print(f"⚠️  安全环境变量系统加载失败: {e}，使用传统.env文件")


class Settings(BaseSettings):
    """应用配置类"""
    
    # ==================== 应用基础配置 ====================
    app_name: str = Field(default="用户认证系统", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", env="API_V1_PREFIX")
    
    # ==================== 数据库配置 ====================
    database_host: str = Field(env="DATABASE_HOST")
    database_port: int = Field(default=5432, env="DATABASE_PORT")
    postgres_user: str = Field(env="POSTGRES_USER")
    postgres_password: str = Field(env="POSTGRES_PASSWORD")
    postgres_db: str = Field(env="POSTGRES_DB")
    
    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.database_host}:{self.database_port}/{self.postgres_db}"
    
    # ==================== JWT 配置 ====================
    jwt_secret_key: str = Field(env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=15, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # ==================== reCAPTCHA 配置 ====================
    recaptcha_site_key: str = Field(env="RECAPTCHA_SITE_KEY")
    recaptcha_secret_key: str = Field(env="RECAPTCHA_SECRET_KEY")
    recaptcha_verify_url: str = Field(
        default="https://www.google.com/recaptcha/api/siteverify",
        env="RECAPTCHA_VERIFY_URL"
    )
    recaptcha_min_score: float = Field(default=0.5)  # reCAPTCHA v3 最小分数
    
    # ==================== CORS 配置 ====================
    allowed_origins_str: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        env="ALLOWED_ORIGINS"
    )
    allowed_hosts_str: str = Field(
        default="localhost,127.0.0.1",
        env="ALLOWED_HOSTS"
    )
    
    @property
    def allowed_origins(self) -> List[str]:
        """解析允许的源列表"""
        return [origin.strip() for origin in self.allowed_origins_str.split(',')]
    
    @property
    def allowed_hosts(self) -> List[str]:
        """解析允许的主机列表"""
        return [host.strip() for host in self.allowed_hosts_str.split(',')]
    
    # ==================== Redis 配置 ====================
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: str = Field(default="", env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    
    @property
    def redis_url(self) -> str:
        """构建Redis连接URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # ==================== OpenAI 配置 ====================
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=1000, env="OPENAI_MAX_TOKENS")
    
    # ==================== 邮件配置 ====================
    smtp_host: str = Field(default="", env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: str = Field(default="", env="SMTP_USER")
    smtp_password: str = Field(default="", env="SMTP_PASSWORD")
    smtp_tls: bool = Field(default=True, env="SMTP_TLS")
    
    # ==================== 日志配置 ====================
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", env="LOG_FILE")
    
    # ==================== 速率限制配置 ====================
    rate_limit_login: str = Field(default="5/minute", env="RATE_LIMIT_LOGIN")
    rate_limit_register: str = Field(default="3/hour", env="RATE_LIMIT_REGISTER")
    rate_limit_refresh: str = Field(default="10/minute", env="RATE_LIMIT_REFRESH")
    
    # ==================== 密码策略配置 ====================
    password_min_length: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    password_require_uppercase: bool = Field(default=True, env="PASSWORD_REQUIRE_UPPERCASE")
    password_require_lowercase: bool = Field(default=True, env="PASSWORD_REQUIRE_LOWERCASE")
    password_require_numbers: bool = Field(default=True, env="PASSWORD_REQUIRE_NUMBERS")
    password_require_special_chars: bool = Field(default=True, env="PASSWORD_REQUIRE_SPECIAL_CHARS")
    
    # ==================== 账户安全配置 ====================
    max_login_attempts: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    account_lockout_duration_minutes: int = Field(default=30, env="ACCOUNT_LOCKOUT_DURATION_MINUTES")
    session_timeout_minutes: int = Field(default=60, env="SESSION_TIMEOUT_MINUTES")
    
    # ==================== 文件上传配置 ====================
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    upload_dir: str = Field(default="uploads", env="UPLOAD_DIR")
    allowed_file_types_str: str = Field(
        default="jpg,jpeg,png,gif,pdf,doc,docx",
        env="ALLOWED_FILE_TYPES"
    )
    
    @property
    def allowed_file_types(self) -> List[str]:
        """解析允许的文件类型列表"""
        return [file_type.strip() for file_type in self.allowed_file_types_str.split(',')]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


# 验证关键配置
def validate_settings():
    """验证关键配置项"""
    errors = []
    
    # 验证数据库配置
    if not settings.database_host:
        errors.append("DATABASE_HOST 未配置")
    if not settings.postgres_user:
        errors.append("POSTGRES_USER 未配置")
    if not settings.postgres_password:
        errors.append("POSTGRES_PASSWORD 未配置")
    if not settings.postgres_db:
        errors.append("POSTGRES_DB 未配置")
    
    # 验证JWT配置
    if not settings.jwt_secret_key or len(settings.jwt_secret_key) < 32:
        errors.append("JWT_SECRET_KEY 未配置或长度不足32位")
    
    # 验证reCAPTCHA配置
    if not settings.recaptcha_site_key:
        errors.append("RECAPTCHA_SITE_KEY 未配置")
    if not settings.recaptcha_secret_key:
        errors.append("RECAPTCHA_SECRET_KEY 未配置")
    
    if errors:
        raise ValueError(f"配置验证失败: {'; '.join(errors)}")
    
    return True


# 在模块加载时验证配置
if __name__ != "__main__":
    try:
        validate_settings()
    except ValueError as e:
        print(f"⚠️  配置警告: {e}")
        print("请检查 .env 文件中的配置项")