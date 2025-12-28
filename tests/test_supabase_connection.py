#!/usr/bin/env python3
"""
Supabase PostgreSQL数据库连接测试

测试新的Supabase PostgreSQL数据库连接是否正常工作
"""

import sys
import os
import traceback
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_basic_connection():
    """测试基本数据库连接"""
    print("🔗 测试基本数据库连接...")

    try:
        from src.utils.db_utils import engine, DB_CONFIG
        from sqlalchemy import text

        # 测试连接
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ 数据库连接成功!")
            print(f"📊 PostgreSQL版本: {version}")
            print(f"🏠 主机: {DB_CONFIG['host']}")
            print(f"🗄️  数据库: {DB_CONFIG['database']}")
            print(f"👤 用户: {DB_CONFIG['user']}")
            return True

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print(f"📋 详细错误信息:")
        traceback.print_exc()
        return False

def test_database_info():
    """测试数据库基本信息"""
    print("\n📊 获取数据库信息...")

    try:
        from src.utils.db_utils import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            # 获取当前数据库名
            result = connection.execute(text("SELECT current_database();"))
            current_db = result.fetchone()[0]
            print(f"📁 当前数据库: {current_db}")

            # 获取当前用户
            result = connection.execute(text("SELECT current_user;"))
            current_user = result.fetchone()[0]
            print(f"👤 当前用户: {current_user}")

            # 获取服务器时间
            result = connection.execute(text("SELECT NOW();"))
            server_time = result.fetchone()[0]
            print(f"⏰ 服务器时间: {server_time}")

            # 获取连接信息
            result = connection.execute(text("SELECT inet_server_addr(), inet_server_port();"))
            server_info = result.fetchone()
            print(f"🌐 服务器地址: {server_info[0]}:{server_info[1]}")

            return True

    except Exception as e:
        print(f"❌ 获取数据库信息失败: {e}")
        traceback.print_exc()
        return False

def test_schema_access():
    """测试模式访问权限"""
    print("\n🔐 测试模式访问权限...")

    try:
        from src.utils.db_utils import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            # 列出所有模式
            result = connection.execute(text("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                ORDER BY schema_name;
            """))
            schemas = result.fetchall()
            print(f"📂 可用模式: {[schema[0] for schema in schemas]}")

            # 检查public模式中的表
            result = connection.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = result.fetchall()
            print(f"📋 public模式中的表: {[table[0] for table in tables]}")

            return True

    except Exception as e:
        print(f"❌ 模式访问测试失败: {e}")
        traceback.print_exc()
        return False

def test_create_table():
    """测试创建表权限"""
    print("\n🛠️  测试创建表权限...")

    try:
        from src.utils.db_utils import engine
        from sqlalchemy import text

        with engine.connect() as connection:
            # 创建测试表
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS test_connection (
                    id SERIAL PRIMARY KEY,
                    test_message VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            print("✅ 测试表创建成功")

            # 插入测试数据
            connection.execute(text("""
                INSERT INTO test_connection (test_message)
                VALUES ('DINQ数据库连接测试 - {}');
            """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
            print("✅ 测试数据插入成功")

            # 查询测试数据
            result = connection.execute(text("""
                SELECT id, test_message, created_at
                FROM test_connection
                ORDER BY created_at DESC
                LIMIT 5;
            """))
            rows = result.fetchall()
            print(f"📊 查询到 {len(rows)} 条测试记录:")
            for row in rows:
                print(f"   ID: {row[0]}, 消息: {row[1]}, 时间: {row[2]}")

            # 清理测试表
            connection.execute(text("DROP TABLE IF EXISTS test_connection;"))
            print("🧹 测试表清理完成")

            return True

    except Exception as e:
        print(f"❌ 创建表测试失败: {e}")
        traceback.print_exc()
        return False

def test_sqlalchemy_models():
    """测试SQLAlchemy模型"""
    print("\n🏗️  测试SQLAlchemy模型...")

    try:
        from src.utils.db_utils import SessionLocal, Base, engine
        from sqlalchemy import Column, Integer, String, DateTime, Text
        from sqlalchemy.sql import func

        # 定义测试模型
        class TestModel(Base):
            __tablename__ = 'test_sqlalchemy_model'

            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=False)
            description = Column(Text)
            created_at = Column(DateTime, server_default=func.now())

        # 创建表
        Base.metadata.create_all(bind=engine)
        print("✅ SQLAlchemy模型表创建成功")

        # 测试会话操作
        session = SessionLocal()
        try:
            # 创建测试记录
            test_record = TestModel(
                name="DINQ测试记录",
                description="这是一个Supabase PostgreSQL连接测试记录"
            )
            session.add(test_record)
            session.commit()
            print("✅ SQLAlchemy记录创建成功")

            # 查询记录
            records = session.query(TestModel).all()
            print(f"📊 查询到 {len(records)} 条SQLAlchemy记录")

            # 删除测试记录
            session.query(TestModel).delete()
            session.commit()
            print("🧹 SQLAlchemy测试记录清理完成")

        finally:
            session.close()

        # 删除测试表
        TestModel.__table__.drop(engine)
        print("🧹 SQLAlchemy测试表清理完成")

        return True

    except Exception as e:
        print(f"❌ SQLAlchemy模型测试失败: {e}")
        traceback.print_exc()
        return False

def test_existing_models():
    """测试现有模型是否兼容"""
    print("\n🔄 测试现有模型兼容性...")

    try:
        # 测试基本的SQLAlchemy功能
        from src.utils.db_utils import engine, Base

        print("✅ 基本SQLAlchemy组件导入成功")

        # 测试创建基础表结构
        Base.metadata.create_all(bind=engine)
        print("✅ 基础表结构创建/验证成功")

        # 尝试导入现有模型（如果存在）
        models_imported = 0
        try:
            from src.models.user_model import User  # noqa: F401
            models_imported += 1
            print("✅ User模型导入成功")
        except ImportError:
            print("⚠️  User模型不存在，跳过")

        try:
            from src.models.api_usage_model import ApiUsage  # noqa: F401
            models_imported += 1
            print("✅ ApiUsage模型导入成功")
        except ImportError:
            print("⚠️  ApiUsage模型不存在，跳过")

        try:
            from src.models.demo_request_model import DemoRequest  # noqa: F401
            models_imported += 1
            print("✅ DemoRequest模型导入成功")
        except ImportError:
            print("⚠️  DemoRequest模型不存在，跳过")

        print(f"📊 成功导入 {models_imported} 个现有模型")

        return True

    except Exception as e:
        print(f"❌ 现有模型兼容性测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🚀 开始Supabase PostgreSQL数据库连接测试")
    print("=" * 60)

    tests = [
        ("基本连接测试", test_basic_connection),
        ("数据库信息测试", test_database_info),
        ("模式访问测试", test_schema_access),
        ("创建表权限测试", test_create_table),
        ("SQLAlchemy模型测试", test_sqlalchemy_models),
        ("现有模型兼容性测试", test_existing_models),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 执行异常: {e}")
            results.append((test_name, False))

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

    if passed == total:
        print("🎉 所有测试通过！Supabase PostgreSQL数据库连接配置成功！")
        return True
    else:
        print("⚠️  部分测试失败，请检查配置和权限")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
