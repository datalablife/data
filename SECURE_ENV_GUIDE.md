# 🔐 安全环境变量管理系统使用指南

## 概述

本系统提供了一个安全的环境变量管理解决方案，使用SQLite数据库存储加密的敏感配置信息，避免在代码中直接暴露敏感数据。

## 🏗️ 系统架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   应用程序      │    │  安全环境变量    │    │  SQLite数据库   │
│                 │    │  管理器          │    │                 │
│ - 配置加载      │◄──►│ - 加密/解密      │◄──►│ - 加密存储      │
│ - 业务逻辑      │    │ - 缓存管理       │    │ - 分类管理      │
│                 │    │ - 安全验证       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   主密钥文件     │
                       │  .master_key     │
                       └──────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install cryptography pydantic-settings
```

### 2. 初始化系统

```bash
# 运行初始化脚本
python setup_secure_env.py
```

这将：
- 从现有的 `.env` 文件导入配置
- 生成主密钥文件 `.master_key`
- 创建加密数据库 `secure_env.db`
- 生成模板文件 `.env.template`
- 更新 `.gitignore`

### 3. 验证安装

```bash
# 查看统计信息
python backend/app/env_manager_cli.py stats

# 列出所有环境变量
python backend/app/env_manager_cli.py list
```

## 🔧 命令行工具使用

### 基本命令

```bash
# 显示帮助
python backend/app/env_manager_cli.py --help

# 设置环境变量
python backend/app/env_manager_cli.py set DATABASE_PASSWORD --category database --description "数据库密码"

# 获取环境变量（不显示值）
python backend/app/env_manager_cli.py get DATABASE_PASSWORD

# 获取环境变量（显示值）
python backend/app/env_manager_cli.py get DATABASE_PASSWORD --show-value

# 列出所有环境变量
python backend/app/env_manager_cli.py list

# 按分类列出
python backend/app/env_manager_cli.py list --category database

# 删除环境变量
python backend/app/env_manager_cli.py delete OLD_CONFIG_KEY

# 显示统计信息
python backend/app/env_manager_cli.py stats
```

### 导入导出

```bash
# 从.env文件导入
python backend/app/env_manager_cli.py import .env

# 导出模板文件
python backend/app/env_manager_cli.py export --output .env.template

# 备份数据库
python backend/app/env_manager_cli.py backup --backup-path secure_env_backup.db
```

## 💻 在代码中使用

### 1. 使用安全配置类

```python
from backend.app.secure_config import get_secure_settings

# 获取配置实例
settings = get_secure_settings()

# 使用配置
database_url = settings.database_url
jwt_secret = settings.jwt_secret_key
```

### 2. 直接使用安全环境变量

```python
from backend.app.secure_env import secure_getenv

# 获取环境变量
api_key = secure_getenv("OPENAI_API_KEY")
database_password = secure_getenv("DATABASE_PASSWORD", "default_value")
```

### 3. 批量加载到os.environ

```python
from backend.app.secure_env import init_secure_env

# 初始化并加载所有环境变量
init_secure_env(auto_load=True)

# 现在可以使用标准的os.getenv
import os
api_key = os.getenv("OPENAI_API_KEY")
```

## 🔒 安全特性

### 1. 加密算法
- 使用 **Fernet** (AES 128 CBC + HMAC SHA256)
- 基于 **PBKDF2** 的密钥派生
- 100,000 次迭代增强安全性

### 2. 密钥管理
- 主密钥自动生成并保存到 `.master_key` 文件
- 支持通过环境变量 `SECURE_ENV_MASTER_KEY` 设置
- 文件权限自动设置为 600 (仅所有者可读写)

### 3. 数据分类
自动根据键名分类：
- `database`: 数据库相关配置
- `security`: JWT、密钥等安全配置
- `api`: API密钥配置
- `email`: 邮件服务配置
- `cache`: Redis等缓存配置
- `general`: 其他配置

### 4. 访问控制
- 内存缓存减少数据库访问
- 支持按分类加载配置
- 开发环境专用管理端点

## 📁 文件结构

```
project/
├── .env                    # 原始环境变量文件（导入后可删除）
├── .env.template          # 环境变量模板（可提交到版本控制）
├── .master_key            # 主密钥文件（不要提交到版本控制）
├── secure_env.db          # 加密数据库（不要提交到版本控制）
├── setup_secure_env.py    # 初始化脚本
└── backend/app/
    ├── secure_env.py      # 核心管理器
    ├── secure_config.py   # 安全配置类
    ├── env_manager_cli.py # 命令行工具
    └── main_secure.py     # 使用示例
```

## 🛡️ 最佳实践

### 1. 开发环境
```bash
# 1. 初始化系统
python setup_secure_env.py

# 2. 验证配置
python backend/app/env_manager_cli.py stats

# 3. 在应用中使用安全配置
from backend.app.secure_config import get_secure_settings
```

### 2. 生产环境
```bash
# 1. 设置主密钥环境变量
export SECURE_ENV_MASTER_KEY="your-production-master-key"

# 2. 部署加密数据库文件
cp secure_env.db /path/to/production/

# 3. 启动应用
python -m backend.app.main_secure
```

### 3. 团队协作
```bash
# 1. 提交模板文件到版本控制
git add .env.template

# 2. 团队成员根据模板创建自己的配置
cp .env.template .env
# 编辑 .env 文件填入实际值

# 3. 初始化个人环境
python setup_secure_env.py
```

## 🔧 配置迁移

### 从传统.env迁移

```bash
# 1. 备份原始.env文件
cp .env .env.backup

# 2. 运行迁移
python setup_secure_env.py

# 3. 验证迁移结果
python backend/app/env_manager_cli.py list

# 4. 测试应用
python backend/app/main_secure.py
```

### 更新配置

```bash
# 添加新配置
python backend/app/env_manager_cli.py set NEW_API_KEY "your-new-key" --category api

# 更新现有配置
python backend/app/env_manager_cli.py set DATABASE_PASSWORD "new-password" --category database

# 删除废弃配置
python backend/app/env_manager_cli.py delete OLD_CONFIG_KEY
```

## 🚨 故障排除

### 1. 密钥丢失
如果 `.master_key` 文件丢失：
```bash
# 无法恢复加密数据，需要重新设置
rm secure_env.db
python setup_secure_env.py
```

### 2. 数据库损坏
```bash
# 从备份恢复
cp secure_env_backup.db secure_env.db

# 或重新初始化
rm secure_env.db
python setup_secure_env.py
```

### 3. 配置验证失败
```bash
# 检查必需的配置项
python backend/app/env_manager_cli.py get DATABASE_HOST --show-value
python backend/app/env_manager_cli.py get JWT_SECRET_KEY --show-value

# 设置缺失的配置
python backend/app/env_manager_cli.py set MISSING_KEY "value"
```

## 📊 监控和维护

### 定期备份
```bash
# 创建定时备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
python backend/app/env_manager_cli.py backup --backup-path "backups/secure_env_${DATE}.db"
```

### 配置审计
```bash
# 查看配置统计
python backend/app/env_manager_cli.py stats

# 列出所有配置（不显示值）
python backend/app/env_manager_cli.py list --format json > config_audit.json
```

### 性能监控
```python
from backend.app.secure_env import get_secure_env_manager

manager = get_secure_env_manager()
stats = manager.get_stats()
print(f"缓存命中率: {stats['cached_count']}/{stats['total_count']}")
```

## 🔗 相关文档

- [系统设计文档](auth_system_design.md)
- [认证系统指南](AUTHENTICATION_SYSTEM_GUIDE.md)
- [项目计划](project_plan/README.md)

## 📞 支持

如有问题，请：
1. 查看本文档的故障排除部分
2. 检查日志文件
3. 使用 `--help` 参数查看命令帮助
4. 提交 Issue 或联系开发团队