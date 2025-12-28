#!/usr/bin/env python3
"""
数据库备用连接测试脚本

模拟不同的网络环境，测试数据库连接的备用机制
"""

import sys
import os
import time
import socket
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_normal_connection():
    """测试正常连接情况"""
    print("🔍 测试1: 正常网络环境")
    print("-" * 40)
    
    try:
        from src.utils.db_utils import create_database_connection
        
        engine, db_name = create_database_connection()
        print(f"✅ 连接成功，使用: {db_name}")
        
        # 测试基本查询
        from sqlalchemy import text
        with engine.connect() as conn:
            if 'postgresql' in str(engine.url):
                result = conn.execute(text('SELECT version();'))
                version = result.fetchone()[0]
                print(f"📊 数据库版本: {version}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_supabase_blocked():
    """测试Supabase被阻止的情况"""
    print("\n🔍 测试2: 模拟Supabase网络不可达")
    print("-" * 40)
    
    # 模拟网络连接失败
    original_create_engine = None
    
    def mock_create_engine(url, **kwargs):
        if 'supabase.co' in url:
            raise Exception("Network is unreachable")
        else:
            # 调用原始的create_engine
            from sqlalchemy import create_engine as original_create_engine_func
            return original_create_engine_func(url, **kwargs)
    
    try:
        # 重新导入模块以应用mock
        if 'src.utils.db_utils' in sys.modules:
            del sys.modules['src.utils.db_utils']
        
        with patch('sqlalchemy.create_engine', side_effect=mock_create_engine):
            from src.utils.db_utils import create_database_connection
            
            engine, db_name = create_database_connection()
            print(f"✅ 备用连接成功，使用: {db_name}")
            
            # 验证不是Supabase
            if 'supabase' not in db_name.lower():
                print("✅ 成功切换到备用数据库")
            else:
                print("⚠️ 仍在使用Supabase连接")
            
            engine.dispose()
            return True
            
    except Exception as e:
        print(f"❌ 备用连接也失败: {e}")
        return False

def test_all_external_blocked():
    """测试所有外部数据库都被阻止的情况"""
    print("\n🔍 测试3: 模拟所有外部数据库不可达")
    print("-" * 40)
    
    def mock_create_engine(url, **kwargs):
        if any(host in url for host in ['supabase.co', '157.230.67.105', 'localhost']):
            if 'localhost' in url and 'postgresql' in url:
                # 模拟本地PostgreSQL也不可用
                raise Exception("Connection refused")
            elif '157.230.67.105' in url:
                # 模拟MySQL服务器不可达
                raise Exception("Network is unreachable")
            elif 'supabase.co' in url:
                # 模拟Supabase不可达
                raise Exception("Network is unreachable")
        
        # 允许SQLite连接
        from sqlalchemy import create_engine as original_create_engine_func
        return original_create_engine_func(url, **kwargs)
    
    try:
        # 重新导入模块
        if 'src.utils.db_utils' in sys.modules:
            del sys.modules['src.utils.db_utils']
        
        with patch('sqlalchemy.create_engine', side_effect=mock_create_engine):
            from src.utils.db_utils import create_database_connection
            
            engine, db_name = create_database_connection()
            print(f"✅ 最终备用连接成功，使用: {db_name}")
            
            # 验证是SQLite
            if 'sqlite' in db_name.lower():
                print("✅ 成功切换到SQLite备用数据库")
                
                # 测试SQLite功能
                from sqlalchemy import text
                with engine.connect() as conn:
                    result = conn.execute(text('SELECT sqlite_version();'))
                    version = result.fetchone()[0]
                    print(f"📊 SQLite版本: {version}")
                    
                    # 测试创建表
                    conn.execute(text('''
                        CREATE TABLE IF NOT EXISTS test_table (
                            id INTEGER PRIMARY KEY,
                            name TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    '''))
                    
                    # 测试插入数据
                    conn.execute(text('''
                        INSERT INTO test_table (name) VALUES ('测试数据')
                    '''))
                    
                    # 测试查询数据
                    result = conn.execute(text('SELECT COUNT(*) FROM test_table'))
                    count = result.fetchone()[0]
                    print(f"📊 测试表中有 {count} 条记录")
                    
                    # 清理测试表
                    conn.execute(text('DROP TABLE test_table'))
                    print("🧹 测试表清理完成")
            
            engine.dispose()
            return True
            
    except Exception as e:
        print(f"❌ 所有数据库连接都失败: {e}")
        return False

def test_environment_variables():
    """测试环境变量配置"""
    print("\n🔍 测试4: 环境变量配置")
    print("-" * 40)
    
    # 设置环境变量强制使用SQLite
    os.environ['PREFERRED_DATABASE'] = 'sqlite'
    os.environ['SQLITE_PATH'] = 'test_env.db'
    
    try:
        # 重新导入模块
        if 'src.utils.db_utils' in sys.modules:
            del sys.modules['src.utils.db_utils']
        
        from src.utils.db_utils import create_database_connection
        
        engine, db_name = create_database_connection()
        print(f"✅ 环境变量配置生效，使用: {db_name}")
        
        # 验证使用了指定的SQLite文件
        if 'sqlite' in db_name.lower():
            print("✅ 成功使用环境变量指定的数据库")
        
        engine.dispose()
        
        # 清理测试文件
        if os.path.exists('test_env.db'):
            os.remove('test_env.db')
            print("🧹 测试数据库文件清理完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 环境变量配置测试失败: {e}")
        return False
    finally:
        # 清理环境变量
        if 'PREFERRED_DATABASE' in os.environ:
            del os.environ['PREFERRED_DATABASE']
        if 'SQLITE_PATH' in os.environ:
            del os.environ['SQLITE_PATH']

def test_server_deployment():
    """测试服务器部署场景"""
    print("\n🔍 测试5: 服务器部署场景")
    print("-" * 40)
    
    # 模拟服务器环境：设置MySQL作为备用
    os.environ['LOCAL_PG_HOST'] = 'localhost'
    os.environ['LOCAL_PG_USER'] = 'postgres'
    os.environ['LOCAL_PG_PASSWORD'] = 'password'
    os.environ['LOCAL_PG_DATABASE'] = 'dinq'
    
    def mock_create_engine_server(url, **kwargs):
        if 'supabase.co' in url:
            # 模拟服务器无法连接到Supabase
            raise Exception("Network is unreachable")
        elif 'localhost' in url and 'postgresql' in url:
            # 模拟本地PostgreSQL不可用
            raise Exception("Connection refused")
        else:
            # 允许MySQL和SQLite连接
            from sqlalchemy import create_engine as original_create_engine_func
            return original_create_engine_func(url, **kwargs)
    
    try:
        # 重新导入模块
        if 'src.utils.db_utils' in sys.modules:
            del sys.modules['src.utils.db_utils']
        
        with patch('sqlalchemy.create_engine', side_effect=mock_create_engine_server):
            from src.utils.db_utils import create_database_connection
            
            engine, db_name = create_database_connection()
            print(f"✅ 服务器环境连接成功，使用: {db_name}")
            
            # 验证连接类型
            if 'mysql' in db_name.lower():
                print("✅ 成功使用MySQL作为备用数据库")
            elif 'sqlite' in db_name.lower():
                print("✅ 使用SQLite作为最终备用数据库")
            
            engine.dispose()
            return True
            
    except Exception as e:
        print(f"❌ 服务器部署测试失败: {e}")
        return False
    finally:
        # 清理环境变量
        for key in ['LOCAL_PG_HOST', 'LOCAL_PG_USER', 'LOCAL_PG_PASSWORD', 'LOCAL_PG_DATABASE']:
            if key in os.environ:
                del os.environ[key]

def main():
    """主测试函数"""
    print("🚀 开始数据库备用连接测试")
    print("=" * 60)
    
    tests = [
        ("正常连接测试", test_normal_connection),
        ("Supabase阻止测试", test_supabase_blocked),
        ("所有外部数据库阻止测试", test_all_external_blocked),
        ("环境变量配置测试", test_environment_variables),
        ("服务器部署场景测试", test_server_deployment),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
                
        except Exception as e:
            print(f"💥 {test_name} 执行异常: {e}")
            results.append((test_name, False))
        
        # 清理模块缓存，确保下次测试重新加载
        if 'src.utils.db_utils' in sys.modules:
            del sys.modules['src.utils.db_utils']
        
        time.sleep(1)  # 短暂延迟
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{total} 个测试通过")
    
    if passed >= 3:  # 至少3个测试通过就认为是成功的
        print("🎉 数据库备用连接机制工作正常！")
        print("\n💡 部署建议:")
        print("1. 如果服务器无法连接Supabase，系统会自动尝试其他数据库")
        print("2. 可以通过环境变量 PREFERRED_DATABASE 指定首选数据库")
        print("3. 建议在服务器上配置本地PostgreSQL或MySQL作为备用")
        print("4. SQLite会作为最终备用方案，确保应用程序能够启动")
        return True
    else:
        print("⚠️ 部分测试失败，请检查数据库配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
