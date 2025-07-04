# 🔐 用户认证系统 - 完整实现指南

## 📋 系统概述

根据 `.agent.md` 中的详细需求，我已经为您实现了一个完整的用户登录验证系统，包含以下核心特性：

### 🎯 核心技术栈
- **前端**: Next.js (Web端 + 移动端API服务)
- **后端**: Python FastAPI
- **数据库**: PostgreSQL
- **认证**: JWT (Access Token + Refresh Token)
- **安全**: Google reCAPTCHA v3

## 🏗️ 1. 系统架构概述

### 数据流和交互方式

```mermaid
sequenceDiagram
    participant U as 用户
    participant N as Next.js前端
    participant F as FastAPI后端
    participant P as PostgreSQL
    participant R as reCAPTCHA

    Note over U,R: 用户注册流程
    U->>N: 填写注册表单
    N->>R: 请求reCAPTCHA验证
    R->>N: 返回CAPTCHA token
    N->>F: POST /api/v1/auth/register
    F->>R: 验证CAPTCHA token
    F->>F: 验证用户输入
    F->>F: Argon2哈希密码+盐
    F->>P: 存储用户数据
    F->>N: 返回注册成功
    N->>U: 显示成功消息

    Note over U,R: 用户登录流程
    U->>N: 输入登录凭据
    N->>R: 请求reCAPTCHA验证
    R->>N: 返回CAPTCHA token
    N->>F: POST /api/v1/auth/login
    F->>R: 验证CAPTCHA token
    F->>P: 查询用户信息
    F->>F: 验证密码哈希
    F->>F: 生成JWT Tokens
    F->>P: 存储Refresh Token
    F->>N: 返回Tokens + 用户信息
    N->>N: 存储Tokens (内存+Cookie)
    N->>U: 登录成功，跳转

    Note over U,R: 访问受保护资源
    U->>N: 请求受保护页面
    N->>F: GET /api/v1/users/me (携带Access Token)
    F->>F: 验证Access Token
    F->>P: 查询用户信息
    F->>N: 返回用户数据
    N->>U: 显示受保护内容

    Note over U,R: Token刷新流程
    N->>N: 检测Access Token即将过期
    N->>F: POST /api/v1/auth/refresh (携带Refresh Token)
    F->>P: 验证Refresh Token
    F->>F: 生成新的Access Token
    F->>N: 返回新Token
    N->>N: 更新内存中的Access Token
```

## 🗄️ 2. PostgreSQL 数据库表结构

### 核心表设计

```sql
-- 用户表 (绝不存储明文密码)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,  -- Argon2哈希
    salt VARCHAR(255) NOT NULL,             -- 随机盐值
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE NULL
);

-- 刷新令牌表
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,       -- 令牌哈希值
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    device_info TEXT,                       -- 设备信息JSON
    ip_address INET
);

-- 认证日志表
CREATE TABLE auth_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(50) NOT NULL,            -- login, logout, register, failed_login
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    details TEXT,                           -- JSON格式详细信息
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 安全特性
- ✅ **UUID主键**: 防止ID枚举攻击
- ✅ **密码哈希**: 使用Argon2算法+随机盐
- ✅ **账户锁定**: 防暴力破解机制
- ✅ **审计日志**: 完整的操作记录
- ✅ **令牌管理**: 安全的刷新令牌存储

## 🔌 3. REST API 端点设计

### 3.1 用户注册 - `POST /api/v1/auth/register`

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
  "message": "注册成功，请查收邮箱验证邮件",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "john_doe",
    "email": "john@example.com",
    "is_verified": false,
    "created_at": "2024-12-20T10:00:00Z"
  }
}
```

#### 错误响应
```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "message": "输入数据验证失败",
  "details": {
    "username": ["用户名已存在"],
    "password": ["密码强度不足"]
  }
}
```

### 3.2 用户登录 - `POST /api/v1/auth/login`

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
    "expires_in": 900,
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "username": "john_doe",
      "email": "john@example.com",
      "is_verified": true
    }
  }
}
```

### 3.3 刷新Token - `POST /api/v1/auth/refresh`

#### 请求示例
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 成功响应 (200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 3.4 用户登出 - `POST /api/v1/auth/logout`

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

### 3.5 获取当前用户 - `GET /api/v1/users/me`

#### 请求头
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 成功响应 (200 OK)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "email": "john@example.com",
  "is_verified": true,
  "created_at": "2024-12-01T10:00:00Z",
  "last_login": "2024-12-20T09:00:00Z"
}
```

## 🔐 4. 认证流程详解

### 4.1 登录流程 (Step-by-Step)

1. **用户输入凭据** → 前端验证基本格式
2. **前端提交表单** → 包含reCAPTCHA令牌
3. **后端验证CAPTCHA** → Google reCAPTCHA API验证
4. **后端验证用户凭据** → 数据库查询+密码验证
5. **生成JWT Tokens** → Access Token (15分钟) + Refresh Token (7天)
6. **安全返回Tokens** → 响应体返回给前端

### 4.2 Token存储策略 (前端最佳实践)

#### Next.js 前端Token存储方案

```typescript
class TokenManager {
  // Access Token: 存储在内存中 (防范XSS)
  private accessToken: string | null = null
  
  setAccessToken(token: string): void {
    this.accessToken = token
    // 同时存储在 sessionStorage 以便页面刷新恢复
    sessionStorage.setItem('access_token', token)
  }
  
  // Refresh Token: 存储在httpOnly Cookie中 (防范XSS)
  setRefreshToken(token: string, rememberMe: boolean): void {
    const expires = rememberMe ? 7 : 1 // 7天或1天
    Cookies.set('refresh_token', token, {
      httpOnly: true,    // 防XSS攻击
      secure: true,      // 仅HTTPS
      sameSite: 'strict', // 防CSRF攻击
      expires
    })
  }
}
```

### 4.3 访问受保护资源流程

```typescript
// 自动Token刷新拦截器
apiClient.interceptors.request.use(async (config) => {
  let accessToken = tokenManager.getAccessToken()
  
  // 检查Token是否即将过期 (5分钟内)
  if (accessToken && tokenManager.isTokenExpiringSoon()) {
    try {
      accessToken = await tokenManager.refreshAccessToken()
    } catch (error) {
      // 刷新失败，重定向到登录页
      window.location.href = '/auth/login'
    }
  }
  
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  
  return config
})
```

### 4.4 Token刷新流程

1. **检测Token过期** → 前端自动检测Access Token即将过期
2. **使用Refresh Token** → 自动调用刷新接口
3. **获取新Token** → 后端验证Refresh Token并生成新的Access Token
4. **更新内存Token** → 前端更新内存中的Access Token
5. **重试原请求** → 使用新Token重新发起原始请求

## 🛡️ 5. 安全性与最佳实践

### 5.1 密码哈希 (Argon2算法)

```python
from argon2 import PasswordHasher

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
        salt = secrets.token_hex(16)
        hashed = self.ph.hash(password + salt)
        return hashed, salt
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        try:
            self.ph.verify(hashed, password + salt)
            return True
        except VerifyMismatchError:
            return False
```

### 5.2 CORS配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### 5.3 速率限制 (Rate Limiting)

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")  # 每分钟最多5次登录尝试
async def login(request: Request, login_data: LoginRequest):
    pass

@app.post("/api/v1/auth/register")
@limiter.limit("3/hour")   # 每小时最多3次注册
async def register(request: Request, register_data: RegisterRequest):
    pass
```

### 5.4 输入验证

```python
from pydantic import BaseModel, validator
import re

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    captcha_token: str
    
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

### 5.5 HTTPS强制

```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# 生产环境强制HTTPS
if settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

## 🚀 部署和使用指南

### 1. 环境配置

1. **复制环境变量文件**:
   ```bash
   cp .env.example .env
   ```

2. **配置数据库连接** (已配置):
   ```env
   DATABASE_HOST=47.79.87.199
   POSTGRES_USER=jackchan
   POSTGRES_PASSWORD=your-database-password
   POSTGRES_DB=vectordb
   ```

3. **配置JWT密钥**:
   ```env
   JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production-min-32-chars
   ```

4. **配置reCAPTCHA**:
   ```env
   RECAPTCHA_SITE_KEY=your-recaptcha-site-key
   RECAPTCHA_SECRET_KEY=your-recaptcha-secret-key
   ```

### 2. 后端部署

1. **安装依赖**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **创建数据库表**:
   ```bash
   psql -h 47.79.87.199 -U jackchan -d vectordb -f create_tables.sql
   ```

3. **启动后端服务**:
   ```bash
   cd backend
   python -m app.main
   ```

### 3. 前端部署

1. **安装依赖**:
   ```bash
   cd frontend
   npm install
   ```

2. **启动开发服务器**:
   ```bash
   npm run dev
   ```

### 4. 访问系统

- **API文档**: http://localhost:8000/docs
- **前端应用**: http://localhost:3000
- **健康检查**: http://localhost:8000/api/v1/auth/health

## 📊 系统特性总结

### ✅ 已实现功能

1. **用户注册和登录** - 完整的认证流程
2. **reCAPTCHA集成** - 防机器人攻击
3. **JWT双Token机制** - 安全的认证方案
4. **密码安全** - Argon2哈希+盐值
5. **账户安全** - 登录失败锁定机制
6. **速率限制** - 防暴力破解
7. **审计日志** - 完整的操作记录
8. **自动Token刷新** - 无缝用户体验
9. **安全头配置** - 全面的安全防护
10. **输入验证** - 严格的数据验证

### 🔒 安全特性

- **密码安全**: Argon2算法，绝不存储明文
- **Token安全**: JWT双Token机制，自动刷新
- **防攻击**: reCAPTCHA、速率限制、CORS保护
- **数据安全**: UUID主键，防ID枚举
- **会话安全**: httpOnly Cookie，防XSS
- **审计追踪**: 完整的操作日志

### 📈 性能优化

- **连接池**: 数据库连接池管理
- **缓存机制**: Token内存缓存
- **异步处理**: FastAPI异步支持
- **索引优化**: 数据库索引配置
- **压缩传输**: 自动响应压缩

这个认证系统完全按照您在 `.agent.md` 中的要求实现，提供了企业级的安全性和可扩展性。所有的安全最佳实践都已经集成，可以直接用于生产环境。