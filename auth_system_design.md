# 🔐 用户登录验证系统 - 完整设计方案

## 角色：高级全栈架构师

作为一名专精于安全认证系统的高级全栈架构师，我为您设计了一个完整的用户登录验证系统。

## 一、核心技术栈与要求

### 技术栈
- **前端**: Next.js (Web端 + 移动端API服务)
- **后端**: Python FastAPI
- **数据库**: PostgreSQL
- **认证**: JWT (Access Token + Refresh Token)
- **安全**: Google reCAPTCHA v3

### 核心功能
1. 用户名/密码注册和登录功能
2. 人类验证机制 (Google reCAPTCHA v3)
3. JWT双Token认证机制

## 二、系统架构概述

### 架构图

```mermaid
graph TB
    subgraph "客户端层"
        A[Web浏览器] 
        B[移动应用]
    end
    
    subgraph "前端服务层"
        C[Next.js应用]
        D[API路由]
    end
    
    subgraph "后端服务层"
        E[FastAPI服务器]
        F[JWT中间件]
        G[CAPTCHA验证]
    end
    
    subgraph "数据层"
        H[PostgreSQL数据库]
        I[Redis缓存]
    end
    
    subgraph "外部服务"
        J[Google reCAPTCHA]
    end
    
    A --> C
    B --> D
    C --> D
    D --> E
    E --> F
    E --> G
    G --> J
    F --> H
    E --> I
    
    classDef frontend fill:#e1f5fe
    classDef backend fill:#f3e5f5
    classDef database fill:#e8f5e8
    classDef external fill:#fff3e0
    
    class A,B,C,D frontend
    class E,F,G backend
    class H,I database
    class J external
```

### 数据流说明

1. **注册流程**:
   - 用户在前端填写注册信息 → reCAPTCHA验证 → 后端验证CAPTCHA → 密码哈希 → 存储到PostgreSQL

2. **登录流程**:
   - 用户输入凭据 → reCAPTCHA验证 → 后端验证 → 生成JWT Token → 返回给前端

3. **访问保护资源**:
   - 前端携带Access Token → 后端验证Token → 返回资源

4. **Token刷新**:
   - Access Token过期 → 使用Refresh Token → 获取新的Access Token

## 三、PostgreSQL 数据库表结构

### 用户表 (users)

```sql
-- 用户表设计
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- 创建索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);

-- 刷新令牌表
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_info JSONB,
    ip_address INET
);

-- 创建索引
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- 用户会话表 (可选，用于会话管理)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 审计日志表
CREATE TABLE auth_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(50) NOT NULL, -- 'login', 'logout', 'register', 'failed_login'
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

### 安全特性说明
- **绝不存储明文密码**: 使用 `hashed_password` 和 `salt` 字段
- **UUID主键**: 防止ID枚举攻击
- **账户锁定**: `failed_login_attempts` 和 `locked_until` 防暴力破解
- **审计日志**: 记录所有认证相关操作

## 四、REST API 端点设计

### 4.1 用户注册 - POST /api/v1/auth/register

#### 请求示例
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "captcha_token": "03AGdBq25..."
}
```

#### 成功响应 (201 Created)
```json
{
  "success": true,
  "message": "用户注册成功",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "john_doe",
    "email": "john@example.com",
    "is_verified": false
  }
}
```

#### 错误响应
```json
// 400 Bad Request - 验证失败
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "message": "输入数据验证失败",
  "details": {
    "username": ["用户名已存在"],
    "password": ["密码强度不足"]
  }
}

// 400 Bad Request - CAPTCHA失败
{
  "success": false,
  "error": "CAPTCHA_FAILED",
  "message": "人机验证失败"
}
```

### 4.2 用户登录 - POST /api/v1/auth/login

#### 请求示例
```json
{
  "username": "john_doe",
  "password": "SecurePass123!",
  "captcha_token": "03AGdBq25...",
  "remember_me": true
}
```

#### 成功响应 (200 OK)
```json
{
  "success": true,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "username": "john_doe",
      "email": "john@example.com"
    }
  }
}
```

#### 错误响应
```json
// 401 Unauthorized - 凭据错误
{
  "success": false,
  "error": "INVALID_CREDENTIALS",
  "message": "用户名或密码错误"
}

// 423 Locked - 账户被锁定
{
  "success": false,
  "error": "ACCOUNT_LOCKED",
  "message": "账户已被锁定，请30分钟后重试",
  "locked_until": "2024-12-20T10:30:00Z"
}
```

### 4.3 刷新Token - POST /api/v1/auth/refresh

#### 请求示例
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 成功响应 (200 OK)
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### 4.4 用户登出 - POST /api/v1/auth/logout

#### 请求头
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 请求示例
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 成功响应 (200 OK)
```json
{
  "success": true,
  "message": "登出成功"
}
```

### 4.5 获取当前用户信息 - GET /api/v1/users/me

#### 请求头
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 成功响应 (200 OK)
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "john_doe",
    "email": "john@example.com",
    "is_verified": true,
    "created_at": "2024-12-01T10:00:00Z",
    "last_login": "2024-12-20T09:00:00Z"
  }
}
```

## 五、认证流程详解

### 5.1 用户注册流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as Next.js前端
    participant C as reCAPTCHA
    participant B as FastAPI后端
    participant D as PostgreSQL

    U->>F: 填写注册表单
    F->>C: 请求CAPTCHA验证
    C->>F: 返回CAPTCHA token
    F->>B: 提交注册数据+CAPTCHA token
    B->>C: 验证CAPTCHA token
    C->>B: 验证结果
    B->>B: 验证用户输入
    B->>B: 生成salt+哈希密码
    B->>D: 存储用户数据
    D->>B: 确认存储成功
    B->>F: 返回注册成功
    F->>U: 显示注册成功消息
```

### 5.2 用户登录流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as Next.js前端
    participant C as reCAPTCHA
    participant B as FastAPI后端
    participant D as PostgreSQL
    participant R as Redis

    U->>F: 输入登录凭据
    F->>C: 请求CAPTCHA验证
    C->>F: 返回CAPTCHA token
    F->>B: 提交登录数据+CAPTCHA token
    B->>C: 验证CAPTCHA token
    C->>B: 验证结果
    B->>D: 查询用户信息
    D->>B: 返回用户数据
    B->>B: 验证密码哈希
    B->>B: 生成Access Token + Refresh Token
    B->>D: 存储Refresh Token
    B->>R: 缓存用户会话
    B->>F: 返回Token
    F->>F: 存储Token (内存+httpOnly Cookie)
    F->>U: 登录成功，跳转到主页
```

### 5.3 Token存储策略 (前端最佳实践)

#### Next.js 前端Token存储方案

1. **Access Token**: 存储在内存中 (React State/Context)
   - 防范XSS攻击
   - 页面刷新时丢失，需要用Refresh Token重新获取

2. **Refresh Token**: 存储在httpOnly Cookie中
   - 防范XSS攻击
   - 自动在请求中携带
   - 设置Secure和SameSite属性

```javascript
// 前端Token管理示例
class TokenManager {
  constructor() {
    this.accessToken = null;
  }

  setAccessToken(token) {
    this.accessToken = token;
  }

  getAccessToken() {
    return this.accessToken;
  }

  clearTokens() {
    this.accessToken = null;
    // Refresh Token通过API调用清除
  }
}
```

### 5.4 访问受保护资源流程

```mermaid
sequenceDiagram
    participant F as Next.js前端
    participant B as FastAPI后端
    participant J as JWT中间件
    participant D as PostgreSQL

    F->>B: 请求受保护资源 (携带Access Token)
    B->>J: 验证Access Token
    J->>J: 检查Token签名和过期时间
    alt Token有效
        J->>D: 查询用户信息 (可选)
        D->>J: 返回用户数据
        J->>B: 验证通过，传递用户信息
        B->>F: 返回受保护资源
    else Token无效/过期
        J->>B: 返回401 Unauthorized
        B->>F: 返回401错误
        F->>F: 自动使用Refresh Token刷新
    end
```

### 5.5 Token刷新流程

```mermaid
sequenceDiagram
    participant F as Next.js前端
    participant B as FastAPI后端
    participant D as PostgreSQL

    F->>B: Access Token过期，使用Refresh Token请求新Token
    B->>D: 验证Refresh Token
    D->>B: 返回Token信息
    alt Refresh Token有效
        B->>B: 生成新的Access Token
        B->>F: 返回新的Access Token
        F->>F: 更新内存中的Access Token
        F->>B: 重新发起原始请求
    else Refresh Token无效/过期
        B->>F: 返回401错误
        F->>F: 清除所有Token
        F->>F: 重定向到登录页
    end
```

## 六、安全性与最佳实践

### 6.1 密码哈希

#### 使用Argon2算法 (推荐)
```python
import argon2
from argon2 import PasswordHasher
import secrets

class PasswordManager:
    def __init__(self):
        self.ph = PasswordHasher(
            time_cost=3,      # 时间成本
            memory_cost=65536, # 内存成本 (64MB)
            parallelism=1,    # 并行度
            hash_len=32,      # 哈希长度
            salt_len=16       # 盐长度
        )
    
    def hash_password(self, password: str) -> tuple[str, str]:
        """哈希密码并返回哈希值和盐"""
        salt = secrets.token_hex(16)
        hashed = self.ph.hash(password + salt)
        return hashed, salt
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """验证密码"""
        try:
            self.ph.verify(hashed, password + salt)
            return True
        except argon2.exceptions.VerifyMismatchError:
            return False
```

### 6.2 CORS 配置

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js开发环境
        "https://yourdomain.com", # 生产环境域名
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### 6.3 速率限制 (Rate Limiting)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 应用到登录端点
@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")  # 每分钟最多5次登录尝试
async def login(request: Request, login_data: LoginRequest):
    # 登录逻辑
    pass

@app.post("/api/v1/auth/register")
@limiter.limit("3/hour")   # 每小时最多3次注册
async def register(request: Request, register_data: RegisterRequest):
    # 注册逻辑
    pass
```

### 6.4 输入验证

```python
from pydantic import BaseModel, EmailStr, validator
import re

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    captcha_token: str
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50字符之间')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少8位')
        if not re.search(r'[A-Z]', v):
            raise ValueError('密码必须包含大写字母')
        if not re.search(r'[a-z]', v):
            raise ValueError('密码必须包含小写字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('密码必须包含特殊字符')
        return v
```

### 6.5 HTTPS 强制

```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# 生产环境强制HTTPS
if settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

### 6.6 安全头设置

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi import Response

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

## 七、JWT Token 配置

### 7.1 Token 配置参数

```python
import jwt
from datetime import datetime, timedelta
from typing import Optional

class JWTManager:
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 15  # 15分钟
        self.refresh_token_expire_days = 7     # 7天
    
    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow()
        })
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "iat": datetime.utcnow()
        })
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
```

---

这个设计方案提供了一个完整、安全、可扩展的用户认证系统架构。所有的安全最佳实践都已经考虑在内，包括密码哈希、CAPTCHA验证、速率限制、CORS配置等。

你希望我接下来：
1. 🔧 实现具体的代码文件（FastAPI后端代码）
2. 🎨 创建Next.js前端组件和页面
3. 🗄️ 提供数据库迁移脚本
4. 🧪 编写测试用例
5. 📦 创建Docker部署配置

请告诉我你最希望优先实现哪个部分？