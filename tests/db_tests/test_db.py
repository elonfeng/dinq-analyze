"""
Test database connection and operations.
"""
import sys
import os
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from src.models.db import Scholar
from src.utils.db_utils import create_tables, drop_tables, get_db_session
from src.utils.scholar_repository import scholar_repo, get_scholar_by_id, save_scholar_data

def test_database_connection():
    """测试数据库连接"""
    print("测试数据库连接...")
    try:
        with get_db_session() as session:
            # 执行简单查询
            result = session.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("✅ 数据库连接成功!")
                return True
            else:
                print("❌ 数据库连接失败: 查询结果不正确")
                return False
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

def test_create_tables():
    """测试创建表"""
    print("测试创建数据库表...")
    result = create_tables()
    if result:
        print("✅ 数据库表创建成功!")
    else:
        print("❌ 数据库表创建失败")
    return result

def test_scholar_crud():
    """测试Scholar模型的CRUD操作"""
    print("测试Scholar模型的CRUD操作...")

    # 测试数据
    test_scholar = {
        'scholar_id': 'TEST123456',
        'name': 'Test Researcher',
        'affiliation': 'Test University',
        'email': 'test@example.com',
        'research_fields': ['AI', 'Machine Learning', 'Computer Vision'],
        'total_citations': 1000,
        'h_index': 20,
        'i10_index': 30,
        'profile_data': {'key': 'value'},
        'publications_data': [{'title': 'Test Paper', 'year': 2023}],
        'coauthors_data': [{'name': 'Coauthor 1'}, {'name': 'Coauthor 2'}],
        'report_data': {'summary': 'Test report'}
    }

    # 使用save_scholar_data函数代替create方法
    # 1. 创建
    print("1. 测试创建Scholar记录...")
    success = save_scholar_data(test_scholar)
    if success:
        print("✅ Scholar记录创建成功!")
    else:
        print("❌ Scholar记录创建失败")
        return False

    # 2. 读取
    print("2. 测试读取Scholar记录...")
    retrieved = get_scholar_by_id(test_scholar['scholar_id'])
    if retrieved and retrieved['scholar_id'] == test_scholar['scholar_id']:
        print(f"✅ Scholar记录读取成功! Name: {retrieved['name']}")
    else:
        print("❌ Scholar记录读取失败")
        return False

    # 3. 更新
    print("3. 测试更新Scholar记录...")
    update_data = {
        'scholar_id': test_scholar['scholar_id'],
        'total_citations': 1500,
        'h_index': 25
    }
    updated = save_scholar_data(update_data)
    if updated:
        # 验证更新
        updated_record = get_scholar_by_id(test_scholar['scholar_id'])
        if updated_record and updated_record['total_citations'] == 1500:
            print("✅ Scholar记录更新成功!")
        else:
            print("❌ Scholar记录更新验证失败")
            return False
    else:
        print("❌ Scholar记录更新失败")
        return False

    # 4. 删除
    print("4. 测试删除Scholar记录...")
    deleted = scholar_repo.delete_by_scholar_id(test_scholar['scholar_id'])
    if deleted:
        # 验证删除
        deleted_record = get_scholar_by_id(test_scholar['scholar_id'])
        if not deleted_record:
            print("✅ Scholar记录删除成功!")
        else:
            print("❌ Scholar记录删除验证失败")
            return False
    else:
        print("❌ Scholar记录删除失败")
        return False

    print("✅ Scholar模型的CRUD操作测试全部通过!")
    return True

def test_helper_functions():
    """测试辅助函数"""
    print("测试辅助函数...")

    # 测试数据
    test_scholar = {
        'scholar_id': 'HELPER123',
        'name': 'Helper Test',
        'affiliation': 'Helper University',
        'total_citations': 500,
        'h_index': 15
    }

    # 1. 保存数据
    print("1. 测试保存学者数据...")
    saved = save_scholar_data(test_scholar)
    if saved:
        print("✅ 保存学者数据成功!")
    else:
        print("❌ 保存学者数据失败")
        return False

    # 2. 获取数据
    print("2. 测试获取学者数据...")
    retrieved = get_scholar_by_id(test_scholar['scholar_id'])
    if retrieved and retrieved['name'] == test_scholar['name']:
        print(f"✅ 获取学者数据成功! Name: {retrieved['name']}")
    else:
        print("❌ 获取学者数据失败")
        return False

    # 3. 清理测试数据
    print("3. 清理测试数据...")
    deleted = scholar_repo.delete_by_scholar_id(test_scholar['scholar_id'])
    if deleted:
        print("✅ 清理测试数据成功!")
    else:
        print("❌ 清理测试数据失败")
        return False

    print("✅ 辅助函数测试全部通过!")
    return True

def run_all_tests():
    """运行所有测试"""
    print("=== 开始数据库测试 ===")

    # 测试数据库连接
    if not test_database_connection():
        print("❌ 数据库连接测试失败，终止后续测试")
        return False

    # 测试创建表
    if not test_create_tables():
        print("❌ 创建表测试失败，终止后续测试")
        return False

    # 测试CRUD操作
    if not test_scholar_crud():
        print("❌ CRUD操作测试失败")
        return False

    # 测试辅助函数
    if not test_helper_functions():
        print("❌ 辅助函数测试失败")
        return False

    print("=== 所有数据库测试通过! ===")
    return True

if __name__ == "__main__":
    run_all_tests()
