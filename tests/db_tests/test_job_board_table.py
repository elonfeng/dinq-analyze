#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证 JobPost 表是否正确创建

此脚本测试 JobPost 表是否正确创建，并测试基本的 CRUD 操作。
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 导入数据库相关模块
try:
    from src.utils.db_utils import create_tables
    from src.models.job_board import JobPost
    from src.utils.job_board_repository import job_post_repo

    # 确保数据库表已创建
    create_tables()

    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_job_post_table():
    """测试 JobPost 表是否正确创建"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return

    print("\n测试 JobPost 表...")

    # 使用直接的数据库会话操作
    from src.utils.db_utils import get_db_session

    try:
        with get_db_session() as session:
            # 创建测试记录
            test_post = JobPost(
                user_id="test_user_123",
                title="测试招聘信息",
                content="这是一个测试招聘信息，用于验证 JobPost 表是否正确创建。",
                post_type="job_offer",
                location="北京",
                company="测试公司",
                position="软件工程师",
                salary_range="20k-30k",
                contact_info="test@example.com",
                tags=["Python", "Flask", "SQLAlchemy"],
                is_active=True,
                view_count=0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # 添加到会话
            session.add(test_post)
            session.commit()

            # 获取ID
            post_id = test_post.id
            print(f"成功创建职位发布: ID={post_id}, 标题='{test_post.title}'")

            # 查询职位发布
            retrieved_post = session.query(JobPost).filter(JobPost.id == post_id).first()
            if retrieved_post:
                print(f"成功获取职位发布: ID={retrieved_post.id}, 标题='{retrieved_post.title}'")
            else:
                print("获取职位发布失败")
                return False

            # 更新职位发布
            retrieved_post.title = "更新后的测试招聘信息"
            retrieved_post.salary_range = "25k-35k"
            retrieved_post.updated_at = datetime.now()
            session.commit()

            print("成功更新职位发布")

            # 再次查询以验证更新
            updated_post = session.query(JobPost).filter(JobPost.id == post_id).first()
            if updated_post:
                print(f"更新后的标题: '{updated_post.title}'")
                print(f"更新后的薪资范围: '{updated_post.salary_range}'")
            else:
                print("获取更新后的职位发布失败")
                return False

            # 增加浏览次数
            updated_post.view_count += 1
            session.commit()

            print("成功增加浏览次数")

            # 再次查询以验证浏览次数
            viewed_post = session.query(JobPost).filter(JobPost.id == post_id).first()
            if viewed_post:
                print(f"浏览次数: {viewed_post.view_count}")
            else:
                print("获取更新后的职位发布失败")
                return False

            # 获取职位发布列表
            posts = session.query(JobPost).limit(10).all()
            print(f"获取到 {len(posts)} 条职位发布")

            # 按条件筛选职位发布
            from sqlalchemy import or_
            filtered_posts = session.query(JobPost).filter(
                JobPost.post_type == "job_offer",
                JobPost.location.like("%北京%"),
                or_(
                    JobPost.title.like("%测试%"),
                    JobPost.content.like("%测试%")
                )
            ).limit(10).all()

            print(f"筛选后获取到 {len(filtered_posts)} 条职位发布")

            # 统计职位发布数量
            from sqlalchemy import func
            count = session.query(func.count(JobPost.id)).filter(JobPost.post_type == "job_offer").scalar()
            print(f"职位发布数量: {count}")

            # 删除职位发布
            session.delete(viewed_post)
            session.commit()

            # 验证删除
            deleted_check = session.query(JobPost).filter(JobPost.id == post_id).first()
            if deleted_check is None:
                print("成功删除职位发布")
            else:
                print("删除职位发布失败")
                return False

            print("JobPost 表测试成功!")
            return True
    except Exception as e:
        print(f"测试失败: {e}")
        return False

if __name__ == "__main__":
    test_job_post_table()
