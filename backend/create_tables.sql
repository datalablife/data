-- 🗄️ 用户认证系统数据库表结构
-- 数据库: PostgreSQL
-- 注意: 绝不能在数据库中存储明文密码

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE NULL,
    
    -- 约束
    CONSTRAINT users_username_length CHECK (char_length(username) >= 3),
    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT users_failed_attempts_positive CHECK (failed_login_attempts >= 0)
);

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- 刷新令牌表
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    device_info TEXT,
    ip_address INET,
    
    -- 外键约束
    CONSTRAINT fk_refresh_tokens_user_id 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- 约束
    CONSTRAINT refresh_tokens_expires_future CHECK (expires_at > created_at)
);

-- 刷新令牌表索引
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_is_revoked ON refresh_tokens(is_revoked);

-- 用户会话表 (可选，用于会话管理)
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    session_token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束
    CONSTRAINT fk_user_sessions_user_id 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- 约束
    CONSTRAINT user_sessions_expires_future CHECK (expires_at > created_at)
);

-- 用户会话表索引
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_token ON user_sessions(session_token);

-- 认证日志表
CREATE TABLE IF NOT EXISTS auth_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    action VARCHAR(50) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    details TEXT, -- JSON格式的详细信息
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键约束 (允许NULL，因为注册失败时可能没有user_id)
    CONSTRAINT fk_auth_logs_user_id 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    
    -- 约束
    CONSTRAINT auth_logs_action_valid CHECK (
        action IN ('login', 'logout', 'register', 'failed_login', 'token_refresh', 'account_locked')
    )
);

-- 认证日志表索引
CREATE INDEX IF NOT EXISTS idx_auth_logs_user_id ON auth_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_logs_action ON auth_logs(action);
CREATE INDEX IF NOT EXISTS idx_auth_logs_created_at ON auth_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_auth_logs_success ON auth_logs(success);
CREATE INDEX IF NOT EXISTS idx_auth_logs_ip_address ON auth_logs(ip_address);

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为用户表创建更新时间触发器
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 创建清理过期令牌的函数
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除过期的刷新令牌
    DELETE FROM refresh_tokens 
    WHERE expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- 删除过期的用户会话
    DELETE FROM user_sessions 
    WHERE expires_at < CURRENT_TIMESTAMP;
    
    RETURN deleted_count;
END;
$$ language 'plpgsql';

-- 创建清理旧日志的函数 (保留90天)
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除90天前的认证日志
    DELETE FROM auth_logs 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ language 'plpgsql';

-- 创建用户统计视图
CREATE OR REPLACE VIEW user_stats AS
SELECT 
    COUNT(*) as total_users,
    COUNT(*) FILTER (WHERE is_active = true) as active_users,
    COUNT(*) FILTER (WHERE is_verified = true) as verified_users,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as new_users_today,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as new_users_week,
    COUNT(*) FILTER (WHERE last_login >= CURRENT_DATE - INTERVAL '7 days') as active_users_week
FROM users;

-- 创建认证统计视图
CREATE OR REPLACE VIEW auth_stats AS
SELECT 
    action,
    success,
    COUNT(*) as count,
    DATE(created_at) as date
FROM auth_logs 
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY action, success, DATE(created_at)
ORDER BY date DESC, action;

-- 插入示例数据 (仅用于测试，生产环境请删除)
-- 注意: 这里的密码已经使用 Argon2 哈希，原始密码是 "TestPassword123!"
/*
INSERT INTO users (username, email, hashed_password, salt, is_verified) VALUES 
(
    'testuser', 
    'test@example.com', 
    '$argon2id$v=19$m=65536,t=3,p=1$randomsalt123456$hashedpasswordhere',
    'randomsalt123456',
    true
) ON CONFLICT (username) DO NOTHING;
*/

-- 创建数据库注释
COMMENT ON TABLE users IS '用户表 - 存储用户基本信息和认证数据';
COMMENT ON COLUMN users.id IS '用户唯一标识 (UUID)';
COMMENT ON COLUMN users.username IS '用户名 (唯一)';
COMMENT ON COLUMN users.email IS '邮箱地址 (唯一)';
COMMENT ON COLUMN users.hashed_password IS '哈希后的密码 (绝不存储明文)';
COMMENT ON COLUMN users.salt IS '密码盐值';
COMMENT ON COLUMN users.is_active IS '账户是否激活';
COMMENT ON COLUMN users.is_verified IS '邮箱是否已验证';
COMMENT ON COLUMN users.failed_login_attempts IS '失败登录尝试次数';
COMMENT ON COLUMN users.locked_until IS '账户锁定到期时间';

COMMENT ON TABLE refresh_tokens IS '刷新令牌表 - 存储JWT刷新令牌';
COMMENT ON COLUMN refresh_tokens.token_hash IS '令牌哈希值 (不存储原始令牌)';
COMMENT ON COLUMN refresh_tokens.device_info IS '设备信息 (JSON格式)';

COMMENT ON TABLE auth_logs IS '认证日志表 - 记录所有认证相关操作';
COMMENT ON COLUMN auth_logs.action IS '操作类型: login, logout, register, failed_login, token_refresh, account_locked';
COMMENT ON COLUMN auth_logs.details IS '详细信息 (JSON格式)';

-- 显示创建结果
SELECT 'Tables created successfully!' as status;

-- 显示表信息
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN ('users', 'refresh_tokens', 'user_sessions', 'auth_logs')
ORDER BY tablename;