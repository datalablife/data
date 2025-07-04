#!/usr/bin/env python3
"""
安全环境变量管理命令行工具
"""
import argparse
import sys
import os
from pathlib import Path
import json
from typing import Optional

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from secure_env import SecureEnvManager, init_secure_env


def cmd_init(args):
    """初始化安全环境变量系统"""
    print("🔧 初始化安全环境变量系统...")
    
    manager = SecureEnvManager(args.db_path)
    
    # 如果指定了.env文件，则导入
    if args.env_file and os.path.exists(args.env_file):
        print(f"📥 从 {args.env_file} 导入环境变量...")
        manager.import_from_env_file(args.env_file)
        
        # 生成模板文件
        template_path = args.env_file + ".template"
        manager.export_to_env_template(template_path)
        print(f"📄 已生成模板文件: {template_path}")
    
    stats = manager.get_stats()
    print(f"✅ 初始化完成！共有 {stats['total_count']} 个环境变量")
    print(f"📊 分类统计: {stats['category_stats']}")


def cmd_set(args):
    """设置环境变量"""
    manager = SecureEnvManager(args.db_path)
    
    # 如果没有提供值，则提示输入
    value = args.value
    if not value:
        import getpass
        value = getpass.getpass(f"请输入 {args.key} 的值: ")
    
    manager.set_env(args.key, value, args.description or "", args.category or "general")
    print(f"✅ 已设置环境变量: {args.key}")


def cmd_get(args):
    """获取环境变量"""
    manager = SecureEnvManager(args.db_path)
    
    if args.key:
        # 获取单个变量
        value = manager.get_env(args.key)
        if value is not None:
            if args.show_value:
                print(f"{args.key}={value}")
            else:
                print(f"{args.key}=<已设置>")
        else:
            print(f"❌ 环境变量 {args.key} 不存在")
            sys.exit(1)
    else:
        # 获取所有变量
        env_vars = manager.get_all_env(args.category)
        if not env_vars:
            print("📭 没有找到环境变量")
            return
        
        print(f"📋 环境变量列表 ({len(env_vars)} 个):")
        for key, value in env_vars.items():
            if args.show_value:
                print(f"  {key}={value}")
            else:
                print(f"  {key}=<已设置>")


def cmd_delete(args):
    """删除环境变量"""
    manager = SecureEnvManager(args.db_path)
    
    if not args.force:
        confirm = input(f"确定要删除环境变量 '{args.key}' 吗？(y/N): ")
        if confirm.lower() != 'y':
            print("❌ 操作已取消")
            return
    
    if manager.delete_env(args.key):
        print(f"✅ 已删除环境变量: {args.key}")
    else:
        print(f"❌ 环境变量 {args.key} 不存在")


def cmd_list(args):
    """列出环境变量键名"""
    manager = SecureEnvManager(args.db_path)
    
    keys = manager.list_env_keys(args.category)
    if not keys:
        print("📭 没有找到环境变量")
        return
    
    print(f"📋 环境变量列表 ({len(keys)} 个):")
    
    if args.format == "json":
        print(json.dumps(keys, indent=2, ensure_ascii=False))
    else:
        # 按分类分组显示
        categories = {}
        for item in keys:
            category = item["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        for category, items in categories.items():
            print(f"\n📁 {category.upper()}:")
            for item in items:
                desc = f" - {item['description']}" if item["description"] else ""
                print(f"  • {item['key']}{desc}")


def cmd_import(args):
    """从.env文件导入"""
    manager = SecureEnvManager(args.db_path)
    
    if not os.path.exists(args.env_file):
        print(f"❌ 文件 {args.env_file} 不存在")
        sys.exit(1)
    
    if not args.force:
        confirm = input(f"确定要从 {args.env_file} 导入环境变量吗？(y/N): ")
        if confirm.lower() != 'y':
            print("❌ 操作已取消")
            return
    
    manager.import_from_env_file(args.env_file)
    print(f"✅ 已从 {args.env_file} 导入环境变量")


def cmd_export(args):
    """导出环境变量模板"""
    manager = SecureEnvManager(args.db_path)
    
    manager.export_to_env_template(args.output)
    print(f"✅ 已导出模板到 {args.output}")


def cmd_stats(args):
    """显示统计信息"""
    manager = SecureEnvManager(args.db_path)
    
    stats = manager.get_stats()
    print("📊 统计信息:")
    print(f"  总数量: {stats['total_count']}")
    print(f"  缓存数量: {stats['cached_count']}")
    print(f"  数据库路径: {stats['database_path']}")
    print("  分类统计:")
    for category, count in stats['category_stats'].items():
        print(f"    {category}: {count}")


def cmd_backup(args):
    """备份数据库"""
    manager = SecureEnvManager(args.db_path)
    
    backup_path = args.backup_path or f"{args.db_path}.backup"
    manager.backup_database(backup_path)
    print(f"✅ 已备份到 {backup_path}")


def cmd_load(args):
    """加载环境变量到当前进程"""
    manager = SecureEnvManager(args.db_path)
    
    manager.load_to_os_environ(args.category)
    print("✅ 已加载环境变量到当前进程")
    
    if args.show:
        print("\n当前环境变量:")
        env_vars = manager.get_all_env(args.category)
        for key, value in env_vars.items():
            print(f"  {key}={value}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="安全环境变量管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 初始化并从.env导入
  python env_manager_cli.py init --env-file .env
  
  # 设置环境变量
  python env_manager_cli.py set DATABASE_PASSWORD --category database --description "数据库密码"
  
  # 获取环境变量
  python env_manager_cli.py get DATABASE_PASSWORD --show-value
  
  # 列出所有环境变量
  python env_manager_cli.py list
  
  # 显示统计信息
  python env_manager_cli.py stats
        """
    )
    
    parser.add_argument(
        "--db-path",
        default="secure_env.db",
        help="SQLite数据库文件路径 (默认: secure_env.db)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化安全环境变量系统")
    init_parser.add_argument("--env-file", help="要导入的.env文件路径")
    init_parser.set_defaults(func=cmd_init)
    
    # set 命令
    set_parser = subparsers.add_parser("set", help="设置环境变量")
    set_parser.add_argument("key", help="环境变量键名")
    set_parser.add_argument("value", nargs="?", help="环境变量值（如果不提供则提示输入）")
    set_parser.add_argument("--description", help="描述信息")
    set_parser.add_argument("--category", help="分类")
    set_parser.set_defaults(func=cmd_set)
    
    # get 命令
    get_parser = subparsers.add_parser("get", help="获取环境变量")
    get_parser.add_argument("key", nargs="?", help="环境变量键名（如果不提供则显示所有）")
    get_parser.add_argument("--show-value", action="store_true", help="显示实际值")
    get_parser.add_argument("--category", help="按分类过滤")
    get_parser.set_defaults(func=cmd_get)
    
    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除环境变量")
    delete_parser.add_argument("key", help="环境变量键名")
    delete_parser.add_argument("--force", action="store_true", help="强制删除，不提示确认")
    delete_parser.set_defaults(func=cmd_delete)
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出环境变量键名")
    list_parser.add_argument("--category", help="按分类过滤")
    list_parser.add_argument("--format", choices=["table", "json"], default="table", help="输出格式")
    list_parser.set_defaults(func=cmd_list)
    
    # import 命令
    import_parser = subparsers.add_parser("import", help="从.env文件导入")
    import_parser.add_argument("env_file", help=".env文件路径")
    import_parser.add_argument("--force", action="store_true", help="强制导入，不提示确认")
    import_parser.set_defaults(func=cmd_import)
    
    # export 命令
    export_parser = subparsers.add_parser("export", help="导出环境变量模板")
    export_parser.add_argument("--output", default=".env.template", help="输出文件路径")
    export_parser.set_defaults(func=cmd_export)
    
    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="显示统计信息")
    stats_parser.set_defaults(func=cmd_stats)
    
    # backup 命令
    backup_parser = subparsers.add_parser("backup", help="备份数据库")
    backup_parser.add_argument("--backup-path", help="备份文件路径")
    backup_parser.set_defaults(func=cmd_backup)
    
    # load 命令
    load_parser = subparsers.add_parser("load", help="加载环境变量到当前进程")
    load_parser.add_argument("--category", help="按分类加载")
    load_parser.add_argument("--show", action="store_true", help="显示加载的变量")
    load_parser.set_defaults(func=cmd_load)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n❌ 操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()