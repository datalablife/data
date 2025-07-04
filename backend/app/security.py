"""
安全相关功能模块
包括密码哈希、JWT处理、reCAPTCHA验证等
"""
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
import json

from jose import JWTError, jwt
from passlib.context import CryptContext
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import settings
from .schemas import CaptchaVerifyResponse


class PasswordManager:
    """密码管理器 - 使用Argon2算法"""
    
    def __init__(self):
        # 使用Argon2作为主要密码哈希算法
        self.argon2_hasher = PasswordHasher(
            time_cost=3,      # 时间成本
            memory_cost=65536, # 内存成本 (64MB)
            parallelism=1,    # 并行度
            hash_len=32,      # 哈希长度
            salt_len=16       # 盐长度
        )
        
        # 备用bcrypt上下文
        self.bcrypt_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12
        )
    
    def generate_salt(self) -> str:
        """生成随机盐值"""
        return secrets.token_hex(16)
    
    def hash_password(self, password: str) -> tuple[str, str]:
        """
        哈希密码并返回哈希值和盐
        
        Args:
            password: 明文密码
            
        Returns:
            tuple: (hashed_password, salt)
        """
        salt = self.generate_salt()
        # 将盐值与密码结合
        salted_password = password + salt
        
        try:
            # 使用Argon2哈希
            hashed = self.argon2_hasher.hash(salted_password)
            return hashed, salt
        except Exception:
            # 如果Argon2失败，使用bcrypt作为备用
            hashed = self.bcrypt_context.hash(salted_password)
            return hashed, salt
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """
        验证密码
        
        Args:
            password: 明文密码
            hashed: 哈希后的密码
            salt: 盐值
            
        Returns:
            bool: 验证结果
        """
        salted_password = password + salt
        
        try:
            # 首先尝试Argon2验证
            self.argon2_hasher.verify(hashed, salted_password)
            return True
        except VerifyMismatchError:
            # 如果Argon2失败，尝试bcrypt验证（向后兼容）
            return self.bcrypt_context.verify(salted_password, hashed)
        except Exception:
            return False
    
    def needs_rehash(self, hashed: str) -> bool:
        """检查密码是否需要重新哈希"""
        try:
            # 检查是否为Argon2格式
            if hashed.startswith('$argon2'):
                return self.argon2_hasher.check_needs_rehash(hashed)
            else:
                # bcrypt格式，建议升级到Argon2
                return True
        except Exception:
            return True


class JWTManager:
    """JWT令牌管理器"""
    
    def __init__(self):
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = settings.jwt_refresh_token_expire_days
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """
        创建访问令牌
        
        Args:
            data: 要编码的数据
            
        Returns:
            str: JWT访问令牌
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": secrets.token_hex(16)  # JWT ID
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        创建刷新令牌
        
        Args:
            data: 要编码的数据
            
        Returns:
            str: JWT刷新令牌
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_hex(16)
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        验证令牌
        
        Args:
            token: JWT令牌
            token_type: 令牌类型 ("access" 或 "refresh")
            
        Returns:
            Optional[Dict]: 解码后的数据，验证失败返回None
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # 检查令牌类型
            if payload.get("type") != token_type:
                return None
            
            return payload
        except JWTError:
            return None
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """获取令牌过期时间"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # 不验证过期时间
            )
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp)
            return None
        except JWTError:
            return None


class CaptchaVerifier:
    """reCAPTCHA验证器"""
    
    def __init__(self):
        self.secret_key = settings.recaptcha_secret_key
        self.verify_url = settings.recaptcha_verify_url
        self.min_score = settings.recaptcha_min_score
    
    async def verify_captcha(
        self,
        token: str,
        remote_ip: Optional[str] = None
    ) -> CaptchaVerifyResponse:
        """
        验证reCAPTCHA令牌
        
        Args:
            token: reCAPTCHA令牌
            remote_ip: 客户端IP地址
            
        Returns:
            CaptchaVerifyResponse: 验证结果
        """
        data = {
            "secret": self.secret_key,
            "response": token
        }
        
        if remote_ip:
            data["remoteip"] = remote_ip
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.verify_url,
                    data=data,
                    timeout=10.0
                )
                response.raise_for_status()
                result = response.json()
                
                # 解析响应
                captcha_response = CaptchaVerifyResponse(**result)
                
                # 对于reCAPTCHA v3，检查分数
                if captcha_response.score is not None:
                    captcha_response.success = (
                        captcha_response.success and 
                        captcha_response.score >= self.min_score
                    )
                
                return captcha_response
                
        except Exception as e:
            # 验证失败时返回失败响应
            return CaptchaVerifyResponse(
                success=False,
                error_codes=[f"verification_failed: {str(e)}"]
            )


class SecurityUtils:
    """安全工具类"""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """生成安全的随机令牌"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """哈希令牌（用于存储刷新令牌）"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def verify_token_hash(token: str, token_hash: str) -> bool:
        """验证令牌哈希"""
        return hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(),
            token_hash
        )
    
    @staticmethod
    def is_safe_url(url: str, allowed_hosts: list) -> bool:
        """检查URL是否安全（防止开放重定向）"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            
            # 如果是相对URL，认为是安全的
            if not parsed.netloc:
                return True
            
            # 检查主机是否在允许列表中
            return parsed.netloc in allowed_hosts
        except Exception:
            return False
    
    @staticmethod
    def sanitize_user_agent(user_agent: str) -> str:
        """清理用户代理字符串"""
        if not user_agent:
            return "Unknown"
        
        # 限制长度并移除潜在的恶意字符
        sanitized = user_agent[:500]
        # 移除控制字符
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32)
        return sanitized
    
    @staticmethod
    def get_client_ip(request) -> str:
        """获取客户端真实IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 取第一个IP（客户端真实IP）
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 回退到直接连接IP
        return request.client.host if request.client else "unknown"


# 创建全局实例
password_manager = PasswordManager()
jwt_manager = JWTManager()
captcha_verifier = CaptchaVerifier()
security_utils = SecurityUtils()