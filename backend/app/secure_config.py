"""
安全配置模块 - 使用加密的环境变量
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os

# 导入安全环境变量管理器
try:
    from .secure_env import init_secure_env, secure_getenv
except ImportError:
    from secure_env import init_secure_env, secure_getenv


class SecureSettings(BaseSettings):
    """安全配置类 - 使用加密的环境变量"""
    
    def __init__(self, **kwargs):
        # 初始化安全环境变量系统
        init_secure_env()
        super().__init__(**kwargs)
    
    # ==================== 应用基础配置 ====================
    app_name: str = Field(default="用户认证系统")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    api_v1_prefix: str = Field(default="/api/v1")
    
    # ==================== 数据库配置 ====================
    @property
    def database_host(self) -> str:
        return secure_getenv("DATABASE_HOST", "localhost")
    
    @property
    def database_port(self) -> int:
        return int(secure_getenv("DATABASE_PORT", "5432"))
    
    @property
    def postgres_user(self) -> str:
        return secure_getenv("POSTGRES_USER", "")
    
    @property
    def postgres_password(self) -> str:
        return secure_getenv("POSTGRES_PASSWORD", "")
    
    @property
    def postgres_db(self) -> str:
        return secure_getenv("POSTGRES_DB", "")
    
    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.database_host}:{self.database_port}/{self.postgres_db}"
    
    # ==================== JWT 配置 ====================
    @property
    def jwt_secret_key(self) -> str:
        return secure_getenv("JWT_SECRET_KEY", "")
    
    @property
    def jwt_algorithm(self) -> str:
        return secure_getenv("JWT_ALGORITHM", "HS256")
    
    @property
    def jwt_access_token_expire_minutes(self) -> int:
        return int(secure_getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    
    @property
    def jwt_refresh_token_expire_days(self) -> int:
        return int(secure_getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # ==================== reCAPTCHA 配置 ====================
    @property
    def recaptcha_site_key(self) -> str:
        return secure_getenv("RECAPTCHA_SITE_KEY", "")
    
    @property
    def recaptcha_secret_key(self) -> str:
        return secure_getenv("RECAPTCHA_SECRET_KEY", "")
    
    @property
    def recaptcha_verify_url(self) -> str:
        return secure_getenv("RECAPTCHA_VERIFY_URL", "https://www.google.com/recaptcha/api/siteverify")
    
    recaptcha_min_score: float = Field(default=0.5)
    
    # ==================== CORS 配置 ====================
    @property
    def allowed_origins(self) -> List[str]:
        origins = secure_getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        return [origin.strip() for origin in origins.split(",")]
    
    @property
    def allowed_hosts(self) -> List[str]:
        hosts = secure_getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
        return [host.strip() for host in hosts.split(",")]
    
    # ==================== Redis 配置 ====================
    @property
    def redis_host(self) -> str:
        return secure_getenv("REDIS_HOST", "localhost")
    
    @property
    def redis_port(self) -> int:
        return int(secure_getenv("REDIS_PORT", "6379"))
    
    @property
    def redis_password(self) -> str:
        return secure_getenv("REDIS_PASSWORD", "")
    
    @property
    def redis_db(self) -> int:
        return int(secure_getenv("REDIS_DB", "0"))
    
    @property
    def redis_url(self) -> str:
        """构建Redis连接URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # ==================== OpenAI 配置 ====================
    @property
    def openai_api_key(self) -> str:
        return secure_getenv("OPENAI_API_KEY", "")
    
    @property
    def openai_model(self) -> str:
        return secure_getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    @property
    def openai_max_tokens(self) -> int:
        return int(secure_getenv("OPENAI_MAX_TOKENS", "1000"))
    
    # ==================== 邮件配置 ====================
    @property
    def smtp_host(self) -> str:
        return secure_getenv("SMTP_HOST", "")
    
    @property
    def smtp_port(self) -> int:
        return int(secure_getenv("SMTP_PORT", "587"))
    
    @property
    def smtp_user(self) -> str:
        return secure_getenv("SMTP_USER", "")
    
    @property
    def smtp_password(self) -> str:
        return secure_getenv("SMTP_PASSWORD", "")
    
    @property
    def smtp_tls(self) -> bool:
        return secure_getenv("SMTP_TLS", "true").lower() == "true"
    
    # ==================== 日志配置 ====================
    @property
    def log_level(self) -> str:
        return secure_getenv("LOG_LEVEL", "INFO")
    
    @property
    def log_file(self) -> str:
        return secure_getenv("LOG_FILE", "logs/app.log")
    
    # ==================== 速率限制配置 ====================
    @property
    def rate_limit_login(self) -> str:
        return secure_getenv("RATE_LIMIT_LOGIN", "5/minute")
    
    @property
    def rate_limit_register(self) -> str:
        return secure_getenv("RATE_LIMIT_REGISTER", "3/hour")
    
    @property
    def rate_limit_refresh(self) -> str:
        return secure_getenv("RATE_LIMIT_REFRESH", "10/minute")
    
    # ==================== 密码策略配置 ====================
    @property
    def password_min_length(self) -> int:
        return int(secure_getenv("PASSWORD_MIN_LENGTH", "8"))
    
    @property
    def password_require_uppercase(self) -> bool:
        return secure_getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
    
    @property
    def password_require_lowercase(self) -> bool:
        return secure_getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
    
    @property
    def password_require_numbers(self) -> bool:
        return secure_getenv("PASSWORD_REQUIRE_NUMBERS", "true").lower() == "true"
    
    @property
    def password_require_special_chars(self) -> bool:
        return secure_getenv("PASSWORD_REQUIRE_SPECIAL_CHARS", "true").lower() == "true"
    
    # ==================== 账户安全配置 ====================
    @property
    def max_login_attempts(self) -> int:
        return int(secure_getenv("MAX_LOGIN_ATTEMPTS", "5"))
    
    @property
    def account_lockout_duration_minutes(self) -> int:
        return int(secure_getenv("ACCOUNT_LOCKOUT_DURATION_MINUTES", "30"))
    
    @property
    def session_timeout_minutes(self) -> int:
        return int(secure_getenv("SESSION_TIMEOUT_MINUTES", "60"))
    
    # ==================== 文件上传配置 ====================
    @property
    def max_file_size_mb(self) -> int:
        return int(secure_getenv("MAX_FILE_SIZE_MB", "10"))
    
    @property
    def upload_dir(self) -> str:
        return secure_getenv("UPLOAD_DIR", "uploads")
    
    @property
    def allowed_file_types(self) -> List[str]:
        types = secure_getenv("ALLOWED_FILE_TYPES", "jpg,jpeg,png,gif,pdf,doc,docx")
        return [file_type.strip() for file_type in types.split(",")]
    
    class Config:
        case_sensitive = False


# 创建全局配置实例
secure_settings = SecureSettings()


def get_secure_settings() -> SecureSettings:
    """获取安全配置实例"""
    return secure_settings


# 验证关键配置
def validate_secure_settings():
    """验证关键配置项"""
    errors = []
    
    # 验证数据库配置
    if not secure_settings.database_host:
        errors.append("DATABASE_HOST 未配置")
    if not secure_settings.postgres_user:
        errors.append("POSTGRES_USER 未配置")
    if not secure_settings.postgres_password:
        errors.append("POSTGRES_PASSWORD 未配置")
    if not secure_settings.postgres_db:
        errors.append("POSTGRES_DB 未配置")
    
    # 验证JWT配置
    if not secure_settings.jwt_secret_key or len(secure_settings.jwt_secret_key) < 32:
        errors.append("JWT_SECRET_KEY 未配置或长度不足32位")
    
    # 验证reCAPTCHA配置
    if not secure_settings.recaptcha_site_key:
        errors.append("RECAPTCHA_SITE_KEY 未配置")
    if not secure_settings.recaptcha_secret_key:
        errors.append("RECAPTCHA_SECRET_KEY 未配置")
    
    if errors:
        raise ValueError(f"配置验证失败: {'; '.join(errors)}")
    
    return True


# 在模块加载时验证配置
if __name__ != "__main__":
    try:
        validate_secure_settings()
    except ValueError as e:
        print(f"⚠️  配置警告: {e}")
        print("请检查加密数据库中的配置项")