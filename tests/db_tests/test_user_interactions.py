#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证用户交互（点赞和收藏）功能

此脚本测试用户对Job Board帖子的点赞和收藏功能。
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
    from src.utils.db_utils import create_tables, get_db_session
    from src.models.job_board import JobPost
    from src.models.user_interactions import JobPostLike, JobPostBookmark
    from src.utils.job_board_repository import job_post_repo
    from src.utils.user_interactions_repository import job_post_like_repo, job_post_bookmark_repo

    # 确保数据库表已创建
    create_tables()

    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def create_test_post(user_id: str) -> int:
    """创建测试帖子并返回ID"""
    post_data = job_post_repo.create_post(
        user_id=user_id,
        title="测试职位 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        content="这是一个测试职位，用于测试点赞和收藏功能。",
        post_type="job_offer",
        location="测试城市",
        company="测试公司",
        position="测试职位",
        tags=["测试", "点赞", "收藏"]
    )
    
    if post_data:
        return post_data['id']
    return None

def test_job_post_likes():
    """测试职位帖子点赞功能"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return False
    
    print("\n===== 测试职位帖子点赞功能 =====")
    
    # 创建测试用户ID
    user_id = "test_user_" + datetime.now().strftime("%Y%m%d%H%M%S")
    print(f"测试用户ID: {user_id}")
    
    # 创建测试帖子
    post_id = create_test_post(user_id)
    if not post_id:
        print("创建测试帖子失败")
        return False
    
    print(f"创建测试帖子成功，ID: {post_id}")
    
    # 测试点赞
    print("\n1. 测试点赞功能")
    like_result = job_post_like_repo.like_post(user_id, post_id)
    if like_result:
        print(f"用户 {user_id} 成功点赞帖子 {post_id}")
    else:
        print(f"用户 {user_id} 点赞帖子 {post_id} 失败")
        return False
    
    # 测试检查是否已点赞
    print("\n2. 测试检查是否已点赞")
    is_liked = job_post_like_repo.is_post_liked(user_id, post_id)
    print(f"用户 {user_id} 是否已点赞帖子 {post_id}: {is_liked}")
    
    # 测试获取点赞数
    print("\n3. 测试获取点赞数")
    like_count = job_post_like_repo.count_post_likes(post_id)
    print(f"帖子 {post_id} 的点赞数: {like_count}")
    
    # 测试获取用户点赞的帖子
    print("\n4. 测试获取用户点赞的帖子")
    liked_posts = job_post_like_repo.get_user_liked_posts(user_id)
    print(f"用户 {user_id} 点赞的帖子数量: {len(liked_posts)}")
    if liked_posts:
        print(f"第一个点赞的帖子: ID={liked_posts[0]['id']}, 标题={liked_posts[0]['title']}")
    
    # 测试取消点赞
    print("\n5. 测试取消点赞")
    unlike_result = job_post_like_repo.unlike_post(user_id, post_id)
    if unlike_result:
        print(f"用户 {user_id} 成功取消点赞帖子 {post_id}")
    else:
        print(f"用户 {user_id} 取消点赞帖子 {post_id} 失败")
        return False
    
    # 再次检查是否已点赞
    is_liked = job_post_like_repo.is_post_liked(user_id, post_id)
    print(f"取消点赞后，用户 {user_id} 是否已点赞帖子 {post_id}: {is_liked}")
    
    print("\n职位帖子点赞功能测试成功!")
    return True

def test_job_post_bookmarks():
    """测试职位帖子收藏功能"""
    if not DB_AVAILABLE:
        print("数据库模块不可用，跳过测试")
        return False
    
    print("\n===== 测试职位帖子收藏功能 =====")
    
    # 创建测试用户ID
    user_id = "test_user_" + datetime.now().strftime("%Y%m%d%H%M%S")
    print(f"测试用户ID: {user_id}")
    
    # 创建测试帖子
    post_id = create_test_post(user_id)
    if not post_id:
        print("创建测试帖子失败")
        return False
    
    print(f"创建测试帖子成功，ID: {post_id}")
    
    # 测试收藏
    print("\n1. 测试收藏功能")
    bookmark_result = job_post_bookmark_repo.bookmark_post(
        user_id=user_id, 
        post_id=post_id, 
        notes="这是一个测试收藏，看起来很有趣的职位"
    )
    if bookmark_result:
        print(f"用户 {user_id} 成功收藏帖子 {post_id}")
    else:
        print(f"用户 {user_id} 收藏帖子 {post_id} 失败")
        return False
    
    # 测试检查是否已收藏
    print("\n2. 测试检查是否已收藏")
    is_bookmarked = job_post_bookmark_repo.is_post_bookmarked(user_id, post_id)
    print(f"用户 {user_id} 是否已收藏帖子 {post_id}: {is_bookmarked}")
    
    # 测试更新收藏备注
    print("\n3. 测试更新收藏备注")
    update_result = job_post_bookmark_repo.update_bookmark_notes(
        user_id=user_id,
        post_id=post_id,
        notes="更新后的备注：这个职位非常适合我"
    )
    if update_result:
        print(f"用户 {user_id} 成功更新帖子 {post_id} 的收藏备注")
    else:
        print(f"用户 {user_id} 更新帖子 {post_id} 的收藏备注失败")
        return False
    
    # 测试获取用户收藏的帖子
    print("\n4. 测试获取用户收藏的帖子")
    bookmarked_posts = job_post_bookmark_repo.get_user_bookmarked_posts(user_id)
    print(f"用户 {user_id} 收藏的帖子数量: {len(bookmarked_posts)}")
    if bookmarked_posts:
        print(f"第一个收藏的帖子: ID={bookmarked_posts[0]['id']}, 标题={bookmarked_posts[0]['title']}")
        print(f"收藏备注: {bookmarked_posts[0]['bookmark']['notes']}")
    
    # 测试获取用户收藏数
    print("\n5. 测试获取用户收藏数")
    bookmark_count = job_post_bookmark_repo.count_user_bookmarks(user_id)
    print(f"用户 {user_id} 的收藏数: {bookmark_count}")
    
    # 测试取消收藏
    print("\n6. 测试取消收藏")
    remove_result = job_post_bookmark_repo.remove_bookmark(user_id, post_id)
    if remove_result:
        print(f"用户 {user_id} 成功取消收藏帖子 {post_id}")
    else:
        print(f"用户 {user_id} 取消收藏帖子 {post_id} 失败")
        return False
    
    # 再次检查是否已收藏
    is_bookmarked = job_post_bookmark_repo.is_post_bookmarked(user_id, post_id)
    print(f"取消收藏后，用户 {user_id} 是否已收藏帖子 {post_id}: {is_bookmarked}")
    
    print("\n职位帖子收藏功能测试成功!")
    return True

def run_all_tests():
    """运行所有测试"""
    print("开始测试用户交互功能...")
    
    likes_test_result = test_job_post_likes()
    bookmarks_test_result = test_job_post_bookmarks()
    
    if likes_test_result and bookmarks_test_result:
        print("\n所有测试通过!")
        return True
    else:
        print("\n测试失败!")
        return False

if __name__ == "__main__":
    run_all_tests()
