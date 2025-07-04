"""
安全环境变量管理系统
使用SQLite数据库存储加密的敏感配置信息
"""
import sqlite3
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SecureEnvManager:
    """安全环境变量管理器"""
    
    def __init__(self, db_path: str = "secure_env.db", master_key: Optional[str] = None):
        # 如果是相对路径，尝试在项目根目录查找
        if not os.path.isabs(db_path) and not os.path.exists(db_path):
            # 尝试在上级目录查找
            parent_path = os.path.join("..", db_path)
            if os.path.exists(parent_path):
                db_path = parent_path
            else:
                # 尝试在上上级目录查找
                grandparent_path = os.path.join("..", "..", db_path)
                if os.path.exists(grandparent_path):
                    db_path = grandparent_path
        """
        初始化安全环境变量管理器
        
        Args:
            db_path: SQLite数据库文件路径
            master_key: 主密钥，如果不提供则从环境变量或文件中获取
        """
        self.db_path = db_path
        self.master_key = master_key or self._get_master_key()
        self.fernet = self._create_fernet_key()
        self._init_database()
        self._cached_env: Dict[str, str] = {}
    
    def _get_master_key(self) -> str:
        """获取主密钥"""
        # 优先级：环境变量 > 密钥文件 > 生成新密钥
        
        # 1. 从环境变量获取
        master_key = os.getenv("SECURE_ENV_MASTER_KEY")
        if master_key:
            return master_key
        
        # 2. 从密钥文件获取
        key_file = Path(".master_key")
        if not key_file.exists():
            # 尝试在上级目录查找
            key_file = Path("../.master_key")
            if not key_file.exists():
                # 尝试在上上级目录查找
                key_file = Path("../../.master_key")
        
        if key_file.exists():
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        
        # 3. 生成新密钥并保存
        new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(new_key)
        
        # 设置文件权限（仅所有者可读写）
        os.chmod(key_file, 0o600)
        
        logger.warning(f"生成新的主密钥并保存到 {key_file}")
        logger.warning("请妥善保管此密钥文件，丢失将无法解密数据！")
        
        return new_key
    
    def _create_fernet_key(self) -> Fernet:
        """基于主密钥创建Fernet加密实例"""
        # 使用PBKDF2从主密钥派生加密密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'secure_env_salt',  # 在生产环境中应该使用随机盐
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def _init_database(self):
        """初始化SQLite数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS secure_env (
                    key TEXT PRIMARY KEY,
                    encrypted_value TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON secure_env(category)")
            conn.commit()
    
    def encrypt_value(self, value: str) -> str:
        """加密值"""
        return self.fernet.encrypt(value.encode()).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """解密值"""
        return self.fernet.decrypt(encrypted_value.encode()).decode()
    
    def set_env(self, key: str, value: str, description: str = "", category: str = "general"):
        """设置加密环境变量"""
        encrypted_value = self.encrypt_value(value)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO secure_env 
                (key, encrypted_value, description, category, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, encrypted_value, description, category))
            conn.commit()
        
        # 更新缓存
        self._cached_env[key] = value
        logger.info(f"已设置加密环境变量: {key}")
    
    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取解密后的环境变量"""
        # 先检查缓存
        if key in self._cached_env:
            return self._cached_env[key]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT encrypted_value FROM secure_env WHERE key = ?", 
                (key,)
            )
            row = cursor.fetchone()
            
            if row:
                try:
                    decrypted_value = self.decrypt_value(row[0])
                    # 缓存解密后的值
                    self._cached_env[key] = decrypted_value
                    return decrypted_value
                except Exception as e:
                    logger.error(f"解密环境变量 {key} 失败: {e}")
                    return default
            
            return default
    
    def get_all_env(self, category: Optional[str] = None) -> Dict[str, str]:
        """获取所有解密后的环境变量"""
        query = "SELECT key, encrypted_value FROM secure_env"
        params = ()
        
        if category:
            query += " WHERE category = ?"
            params = (category,)
        
        result = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            for key, encrypted_value in cursor.fetchall():
                try:
                    result[key] = self.decrypt_value(encrypted_value)
                except Exception as e:
                    logger.error(f"解密环境变量 {key} 失败: {e}")
        
        # 更新缓存
        self._cached_env.update(result)
        return result
    
    def delete_env(self, key: str) -> bool:
        """删除环境变量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM secure_env WHERE key = ?", (key,))
            conn.commit()
            
            # 从缓存中移除
            self._cached_env.pop(key, None)
            
            return cursor.rowcount > 0
    
    def list_env_keys(self, category: Optional[str] = None) -> list:
        """列出所有环境变量键名"""
        query = "SELECT key, description, category FROM secure_env"
        params = ()
        
        if category:
            query += " WHERE category = ?"
            params = (category,)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return [
                {"key": row[0], "description": row[1], "category": row[2]}
                for row in cursor.fetchall()
            ]
    
    def load_to_os_environ(self, category: Optional[str] = None):
        """将解密后的环境变量加载到os.environ中"""
        env_vars = self.get_all_env(category)
        for key, value in env_vars.items():
            os.environ[key] = value
        
        logger.info(f"已加载 {len(env_vars)} 个环境变量到 os.environ")
    
    def import_from_env_file(self, env_file_path: str = ".env"):
        """从.env文件导入并加密存储"""
        if not os.path.exists(env_file_path):
            logger.warning(f"环境文件 {env_file_path} 不存在")
            return
        
        imported_count = 0
        with open(env_file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # 跳过注释和空行
                if not line or line.startswith("#"):
                    continue
                
                # 解析键值对
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 移除引号
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # 根据键名确定分类
                    category = self._categorize_env_key(key)
                    
                    self.set_env(key, value, f"从 {env_file_path} 导入", category)
                    imported_count += 1
                else:
                    logger.warning(f"{env_file_path}:{line_num} 格式错误: {line}")
        
        logger.info(f"从 {env_file_path} 导入了 {imported_count} 个环境变量")
    
    def _categorize_env_key(self, key: str) -> str:
        """根据键名自动分类"""
        key_lower = key.lower()
        
        if any(db_key in key_lower for db_key in ["database", "postgres", "db_"]):
            return "database"
        elif any(jwt_key in key_lower for jwt_key in ["jwt", "token", "secret"]):
            return "security"
        elif any(api_key in key_lower for api_key in ["api_key", "openai", "recaptcha"]):
            return "api"
        elif any(mail_key in key_lower for mail_key in ["smtp", "mail", "email"]):
            return "email"
        elif any(redis_key in key_lower for redis_key in ["redis", "cache"]):
            return "cache"
        else:
            return "general"
    
    def export_to_env_template(self, output_path: str = ".env.template"):
        """导出环境变量模板（不包含敏感值）"""
        env_keys = self.list_env_keys()
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 🔐 环境变量配置模板\n")
            f.write("# 此文件不包含敏感信息，可以安全地提交到版本控制\n\n")
            
            categories = {}
            for item in env_keys:
                category = item["category"]
                if category not in categories:
                    categories[category] = []
                categories[category].append(item)
            
            for category, items in categories.items():
                f.write(f"# ==================== {category.upper()} 配置 ====================\n")
                for item in items:
                    desc = f" # {item['description']}" if item["description"] else ""
                    f.write(f"{item['key']}=<请设置实际值>{desc}\n")
                f.write("\n")
        
        logger.info(f"已导出环境变量模板到 {output_path}")
    
    def backup_database(self, backup_path: str):
        """备份加密数据库"""
        import shutil
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"已备份数据库到 {backup_path}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            # 总数
            total_count = conn.execute("SELECT COUNT(*) FROM secure_env").fetchone()[0]
            
            # 按分类统计
            category_stats = {}
            cursor = conn.execute("""
                SELECT category, COUNT(*) 
                FROM secure_env 
                GROUP BY category
            """)
            for category, count in cursor.fetchall():
                category_stats[category] = count
        
        return {
            "total_count": total_count,
            "category_stats": category_stats,
            "database_path": self.db_path,
            "cached_count": len(self._cached_env)
        }


# 全局实例
_secure_env_manager: Optional[SecureEnvManager] = None


def get_secure_env_manager() -> SecureEnvManager:
    """获取全局安全环境变量管理器实例"""
    global _secure_env_manager
    if _secure_env_manager is None:
        _secure_env_manager = SecureEnvManager()
    return _secure_env_manager


def secure_getenv(key: str, default: Optional[str] = None) -> Optional[str]:
    """安全获取环境变量（替代os.getenv）"""
    manager = get_secure_env_manager()
    return manager.get_env(key, default)


def init_secure_env(auto_load: bool = True, env_file: str = ".env"):
    """初始化安全环境变量系统"""
    manager = get_secure_env_manager()
    
    # 如果数据库为空且存在.env文件，则导入
    stats = manager.get_stats()
    if stats["total_count"] == 0 and os.path.exists(env_file):
        logger.info("检测到空数据库，正在从 .env 文件导入配置...")
        manager.import_from_env_file(env_file)
    
    # 自动加载到os.environ
    if auto_load:
        manager.load_to_os_environ()
    
    return manager


if __name__ == "__main__":
    # 示例用法
    manager = SecureEnvManager()
    
    # 设置一些示例环境变量
    manager.set_env("DATABASE_PASSWORD", "super_secret_password", "数据库密码", "database")
    manager.set_env("JWT_SECRET_KEY", "jwt-secret-key-12345", "JWT密钥", "security")
    manager.set_env("OPENAI_API_KEY", "sk-1234567890", "OpenAI API密钥", "api")
    
    # 获取环境变量
    print("数据库密码:", manager.get_env("DATABASE_PASSWORD"))
    print("JWT密钥:", manager.get_env("JWT_SECRET_KEY"))
    
    # 显示统计信息
    print("统计信息:", manager.get_stats())
    
    # 列出所有键
    print("所有环境变量键:", manager.list_env_keys())