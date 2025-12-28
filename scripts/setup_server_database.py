#!/usr/bin/env python3
"""
服务器数据库设置脚本

为服务器环境配置数据库连接，当Supabase不可用时自动使用备用数据库
"""

import sys
import os
import subprocess
import time

def check_network_connectivity():
    """检查网络连接"""
    print("🔍 检查网络连接...")
    
    # 检查基本网络
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        print("✅ 基本网络连接正常")
    except OSError:
        print("❌ 基本网络连接失败")
        return False
    
    # 检查Supabase连接
    try:
        import socket
        socket.create_connection(("db.kqfpikinqkcujlzrsaad.supabase.co", 5432), timeout=10)
        print("✅ Supabase数据库可达")
        return True
    except OSError as e:
        print(f"❌ Supabase数据库不可达: {e}")
        return False

def setup_local_postgresql():
    """设置本地PostgreSQL"""
    print("\n🔧 设置本地PostgreSQL...")
    
    try:
        # 检查PostgreSQL是否已安装
        result = subprocess.run(['which', 'psql'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ PostgreSQL未安装")
            print("💡 安装建议:")
            print("   Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib")
            print("   CentOS/RHEL: sudo yum install postgresql-server postgresql-contrib")
            print("   macOS: brew install postgresql")
            return False
        
        print("✅ PostgreSQL已安装")
        
        # 检查PostgreSQL服务状态
        result = subprocess.run(['sudo', 'systemctl', 'status', 'postgresql'], 
                              capture_output=True, text=True)
        if 'active (running)' in result.stdout:
            print("✅ PostgreSQL服务正在运行")
        else:
            print("⚠️ PostgreSQL服务未运行，尝试启动...")
            subprocess.run(['sudo', 'systemctl', 'start', 'postgresql'])
            time.sleep(3)
        
        # 创建数据库和用户
        print("🔧 配置数据库...")
        
        # 创建数据库
        create_db_cmd = [
            'sudo', '-u', 'postgres', 'psql', '-c',
            "CREATE DATABASE dinq;"
        ]
        subprocess.run(create_db_cmd, capture_output=True)
        
        # 创建用户
        create_user_cmd = [
            'sudo', '-u', 'postgres', 'psql', '-c',
            "CREATE USER dinq_user WITH PASSWORD 'dinq_password';"
        ]
        subprocess.run(create_user_cmd, capture_output=True)
        
        # 授权
        grant_cmd = [
            'sudo', '-u', 'postgres', 'psql', '-c',
            "GRANT ALL PRIVILEGES ON DATABASE dinq TO dinq_user;"
        ]
        subprocess.run(grant_cmd, capture_output=True)
        
        print("✅ 本地PostgreSQL配置完成")
        
        # 创建环境变量配置
        env_config = """
# 本地PostgreSQL配置
LOCAL_PG_HOST=localhost
LOCAL_PG_PORT=5432
LOCAL_PG_USER=dinq_user
LOCAL_PG_PASSWORD=dinq_password
LOCAL_PG_DATABASE=dinq
PREFERRED_DATABASE=local_pg
"""
        
        with open('.env.local', 'w') as f:
            f.write(env_config)
        
        print("✅ 环境变量配置已保存到 .env.local")
        return True
        
    except Exception as e:
        print(f"❌ 本地PostgreSQL设置失败: {e}")
        return False

def setup_mysql_fallback():
    """设置MySQL备用连接"""
    print("\n🔧 设置MySQL备用连接...")
    
    # 测试现有MySQL连接
    try:
        import pymysql
        
        connection = pymysql.connect(
            host='157.230.67.105',
            port=3306,
            user='devuser',
            password='devpassword',
            database='devfun',
            connect_timeout=10
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            print(f"✅ MySQL连接成功，版本: {version}")
        
        connection.close()
        
        # 创建环境变量配置
        env_config = """
# MySQL备用配置
MYSQL_HOST=157.230.67.105
MYSQL_PORT=3306
MYSQL_USER=devuser
MYSQL_PASSWORD=devpassword
MYSQL_DATABASE=devfun
PREFERRED_DATABASE=mysql
"""
        
        with open('.env.mysql', 'w') as f:
            f.write(env_config)
        
        print("✅ MySQL备用配置已保存到 .env.mysql")
        return True
        
    except Exception as e:
        print(f"❌ MySQL连接失败: {e}")
        return False

def setup_sqlite_fallback():
    """设置SQLite备用"""
    print("\n🔧 设置SQLite备用...")
    
    try:
        import sqlite3
        
        # 创建SQLite数据库
        db_path = '/var/lib/dinq/dinq.db'
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 测试基本操作
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        print(f"✅ SQLite可用，版本: {version}")
        
        conn.close()
        
        # 创建环境变量配置
        env_config = f"""
# SQLite备用配置
SQLITE_PATH={db_path}
PREFERRED_DATABASE=sqlite
"""
        
        with open('.env.sqlite', 'w') as f:
            f.write(env_config)
        
        print(f"✅ SQLite备用配置已保存到 .env.sqlite")
        print(f"📁 数据库文件: {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ SQLite设置失败: {e}")
        return False

def test_database_connection(config_file):
    """测试数据库连接"""
    print(f"\n🧪 测试数据库连接 ({config_file})...")
    
    try:
        # 加载环境变量
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        
        # 测试连接
        sys.path.insert(0, '.')
        
        # 重新导入模块以应用新的环境变量
        if 'src.utils.db_utils' in sys.modules:
            del sys.modules['src.utils.db_utils']
        
        from src.utils.db_utils import engine, db_name
        
        # 测试基本查询
        from sqlalchemy import text
        with engine.connect() as conn:
            if 'postgresql' in str(engine.url):
                result = conn.execute(text('SELECT version();'))
                version = result.fetchone()[0]
                print(f"✅ PostgreSQL连接成功: {version}")
            elif 'mysql' in str(engine.url):
                result = conn.execute(text('SELECT VERSION();'))
                version = result.fetchone()[0]
                print(f"✅ MySQL连接成功: {version}")
            elif 'sqlite' in str(engine.url):
                result = conn.execute(text('SELECT sqlite_version();'))
                version = result.fetchone()[0]
                print(f"✅ SQLite连接成功: {version}")
        
        print(f"🎉 数据库连接测试成功，使用: {db_name}")
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        return False

def create_deployment_script():
    """创建部署脚本"""
    print("\n📝 创建部署脚本...")
    
    script_content = '''#!/bin/bash

# DINQ服务器部署脚本
# 自动检测和配置数据库连接

set -e

echo "🚀 开始DINQ服务器部署..."

# 检查Supabase连接
echo "🔍 检查Supabase连接..."
if timeout 10 bash -c "</dev/tcp/db.kqfpikinqkcujlzrsaad.supabase.co/5432" 2>/dev/null; then
    echo "✅ Supabase可达，使用默认配置"
    # 使用默认的Supabase配置
else
    echo "❌ Supabase不可达，配置备用数据库..."
    
    # 检查本地PostgreSQL
    if systemctl is-active --quiet postgresql 2>/dev/null; then
        echo "✅ 发现本地PostgreSQL，使用本地数据库"
        cp .env.local .env 2>/dev/null || echo "LOCAL_PG_HOST=localhost" > .env
    elif timeout 5 bash -c "</dev/tcp/157.230.67.105/3306" 2>/dev/null; then
        echo "✅ MySQL服务器可达，使用MySQL备用"
        cp .env.mysql .env 2>/dev/null || echo "PREFERRED_DATABASE=mysql" > .env
    else
        echo "⚠️ 使用SQLite备用数据库"
        cp .env.sqlite .env 2>/dev/null || echo "PREFERRED_DATABASE=sqlite" > .env
    fi
fi

# 安装依赖
echo "📦 安装Python依赖..."
pip install -r requirements.txt

# 启动服务
echo "🚀 启动DINQ服务..."
python server/app.py

echo "🎉 DINQ服务器部署完成！"
'''
    
    with open('deploy_server.sh', 'w') as f:
        f.write(script_content)
    
    os.chmod('deploy_server.sh', 0o755)
    print("✅ 部署脚本已创建: deploy_server.sh")

def main():
    """主函数"""
    print("🔧 DINQ服务器数据库设置")
    print("=" * 50)
    
    # 检查网络连接
    supabase_available = check_network_connectivity()
    
    if supabase_available:
        print("\n✅ Supabase可用，建议使用默认配置")
        print("💡 如果后续出现连接问题，可以运行此脚本配置备用数据库")
    else:
        print("\n⚠️ Supabase不可用，配置备用数据库...")
        
        # 尝试配置备用数据库
        success = False
        
        # 1. 尝试本地PostgreSQL
        if setup_local_postgresql():
            if test_database_connection('.env.local'):
                print("✅ 本地PostgreSQL配置成功")
                success = True
        
        # 2. 尝试MySQL
        if not success and setup_mysql_fallback():
            if test_database_connection('.env.mysql'):
                print("✅ MySQL备用配置成功")
                success = True
        
        # 3. 最后使用SQLite
        if not success and setup_sqlite_fallback():
            if test_database_connection('.env.sqlite'):
                print("✅ SQLite备用配置成功")
                success = True
        
        if not success:
            print("❌ 所有数据库配置都失败了")
            return False
    
    # 创建部署脚本
    create_deployment_script()
    
    print("\n🎉 服务器数据库设置完成！")
    print("\n📋 使用说明:")
    print("1. 如果Supabase可用，直接运行: python server/app.py")
    print("2. 如果Supabase不可用，运行: ./deploy_server.sh")
    print("3. 手动配置: 复制相应的 .env.* 文件为 .env")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
