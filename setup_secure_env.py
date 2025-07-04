#!/usr/bin/env python3
"""
安全环境变量系统初始化脚本
"""
import os
import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_path = Path(__file__).parent / "backend" / "app"
sys.path.insert(0, str(backend_path))

from secure_env import SecureEnvManager


def main():
    """主函数"""
    print("🔐 安全环境变量系统初始化")
    print("=" * 50)
    
    # 创建管理器实例
    manager = SecureEnvManager()
    
    # 检查是否已有数据
    stats = manager.get_stats()
    if stats["total_count"] > 0:
        print(f"✅ 检测到已有 {stats['total_count']} 个环境变量")
        choice = input("是否要重新导入 .env 文件？(y/N): ")
        if choice.lower() != 'y':
            print("🚀 系统已就绪！")
            return
    
    # 检查.env文件
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"❌ 未找到 {env_file} 文件")
        print("请先创建 .env 文件并添加您的配置")
        return
    
    print(f"📥 正在从 {env_file} 导入环境变量...")
    
    try:
        # 导入环境变量
        manager.import_from_env_file(env_file)
        
        # 生成模板文件
        template_file = ".env.template"
        manager.export_to_env_template(template_file)
        
        # 显示统计信息
        stats = manager.get_stats()
        print(f"\n✅ 导入完成！")
        print(f"📊 总共导入了 {stats['total_count']} 个环境变量")
        print(f"📁 分类统计:")
        for category, count in stats['category_stats'].items():
            print(f"   {category}: {count} 个")
        
        print(f"\n📄 已生成模板文件: {template_file}")
        print("   此文件不包含敏感信息，可以安全地提交到版本控制")
        
        # 安全建议
        print(f"\n🔒 安全建议:")
        print(f"1. 将 {env_file} 添加到 .gitignore 中")
        print(f"2. 妥善保管 .master_key 文件（已自动生成）")
        print(f"3. 定期备份 secure_env.db 数据库文件")
        print(f"4. 在生产环境中使用环境变量设置 SECURE_ENV_MASTER_KEY")
        
        # 创建.gitignore条目
        gitignore_file = ".gitignore"
        gitignore_entries = [
            "# 安全环境变量系统",
            ".env",
            ".master_key",
            "secure_env.db",
            "secure_env.db.backup",
        ]
        
        if os.path.exists(gitignore_file):
            with open(gitignore_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
            
            # 检查是否已有相关条目
            if ".master_key" not in existing_content:
                with open(gitignore_file, "a", encoding="utf-8") as f:
                    f.write("\n" + "\n".join(gitignore_entries) + "\n")
                print(f"📝 已更新 {gitignore_file}")
        else:
            with open(gitignore_file, "w", encoding="utf-8") as f:
                f.write("\n".join(gitignore_entries) + "\n")
            print(f"📝 已创建 {gitignore_file}")
        
        print(f"\n🚀 系统初始化完成！")
        print(f"💡 使用以下命令管理环境变量:")
        print(f"   python backend/app/env_manager_cli.py --help")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()