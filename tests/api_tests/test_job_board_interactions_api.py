#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证Job Board交互API接口

此脚本测试Job Board的点赞和收藏API接口功能。
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 配置测试参数
BASE_URL = "http://localhost:5001"  # 服务器地址
USER_ID = "gAckWxWYazcI5k95n627hRBHB712"  # 测试用户ID
HEADERS = {
    "Content-Type": "application/json",
    "Userid": USER_ID  # 在请求头中添加用户ID
}

def create_test_post():
    """创建测试帖子并返回ID"""
    url = f"{BASE_URL}/api/job-board/posts"
    data = {
        "title": f"测试职位 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "content": "这是一个测试职位，用于测试点赞和收藏API接口。",
        "post_type": "job",
        "location": "测试城市",
        "company": "测试公司",
        "position": "测试职位",
        "tags": ["测试", "点赞", "收藏"]
    }

    response = requests.post(url, json=data, headers=HEADERS)
    if response.status_code in (200, 201):
        result = response.json()
        if result.get("success"):
            post_id = result.get("data", {}).get("id")
            print(f"创建测试帖子成功，ID: {post_id}")
            return post_id
        else:
            print(f"创建测试帖子失败: {json.dumps(result, indent=2)}")
    else:
        print(f"创建测试帖子失败: {response.text}")

    # 如果响应中包含了帖子ID，尝试提取并返回
    try:
        result = response.json()
        if isinstance(result, dict) and "data" in result and "id" in result["data"]:
            post_id = result["data"]["id"]
            print(f"尝试提取帖子ID: {post_id}")
            return post_id
    except Exception as e:
        print(f"提取帖子ID失败: {str(e)}")

    return None

def test_like_api():
    """测试点赞API接口"""
    print("\n===== 测试点赞API接口 =====")

    # 创建测试帖子
    post_id = create_test_post()
    if not post_id:
        return False

    # 测试获取帖子交互状态
    print("\n1. 测试获取帖子交互状态")
    status_url = f"{BASE_URL}/api/job-board/posts/{post_id}/status"
    response = requests.get(status_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"帖子交互状态: {json.dumps(result.get('data', {}), indent=2)}")
    else:
        print(f"获取帖子交互状态失败: {response.text}")
        return False

    # 测试点赞帖子
    print("\n2. 测试点赞帖子")
    like_url = f"{BASE_URL}/api/job-board/posts/{post_id}/like"
    response = requests.post(like_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"点赞结果: {json.dumps(result, indent=2)}")
    else:
        print(f"点赞帖子失败: {response.text}")
        return False

    # 再次获取帖子交互状态
    print("\n3. 再次获取帖子交互状态")
    response = requests.get(status_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"点赞后的帖子交互状态: {json.dumps(result.get('data', {}), indent=2)}")
    else:
        print(f"获取帖子交互状态失败: {response.text}")
        return False

    # 测试获取用户点赞的帖子
    print("\n4. 测试获取用户点赞的帖子")
    liked_posts_url = f"{BASE_URL}/api/job-board/my-liked-posts"
    response = requests.get(liked_posts_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        posts = result.get("data", {}).get("posts", [])
        print(f"用户点赞的帖子数量: {len(posts)}")
        if posts:
            print(f"第一个点赞的帖子: {json.dumps(posts[0], indent=2)}")
    else:
        print(f"获取用户点赞的帖子失败: {response.text}")
        return False

    # 测试取消点赞
    print("\n5. 测试取消点赞")
    response = requests.delete(like_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"取消点赞结果: {json.dumps(result, indent=2)}")
    else:
        print(f"取消点赞失败: {response.text}")
        return False

    # 再次获取帖子交互状态
    print("\n6. 取消点赞后再次获取帖子交互状态")
    response = requests.get(status_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"取消点赞后的帖子交互状态: {json.dumps(result.get('data', {}), indent=2)}")
    else:
        print(f"获取帖子交互状态失败: {response.text}")
        return False

    print("\n点赞API接口测试成功!")
    return True

def test_bookmark_api():
    """测试收藏API接口"""
    print("\n===== 测试收藏API接口 =====")

    # 创建测试帖子
    post_id = create_test_post()
    if not post_id:
        return False

    # 测试收藏帖子
    print("\n1. 测试收藏帖子")
    bookmark_url = f"{BASE_URL}/api/job-board/posts/{post_id}/bookmark"
    bookmark_data = {
        "notes": "这是一个测试收藏，看起来很有趣的职位"
    }
    response = requests.post(bookmark_url, json=bookmark_data, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"收藏结果: {json.dumps(result, indent=2)}")
    else:
        print(f"收藏帖子失败: {response.text}")
        return False

    # 获取帖子交互状态
    print("\n2. 获取帖子交互状态")
    status_url = f"{BASE_URL}/api/job-board/posts/{post_id}/status"
    response = requests.get(status_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"收藏后的帖子交互状态: {json.dumps(result.get('data', {}), indent=2)}")
    else:
        print(f"获取帖子交互状态失败: {response.text}")
        return False

    # 测试更新收藏备注
    print("\n3. 测试更新收藏备注")
    notes_url = f"{BASE_URL}/api/job-board/posts/{post_id}/bookmark/notes"
    notes_data = {
        "notes": "更新后的备注：这个职位非常适合我"
    }
    response = requests.put(notes_url, json=notes_data, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"更新收藏备注结果: {json.dumps(result, indent=2)}")
    else:
        print(f"更新收藏备注失败: {response.text}")
        return False

    # 测试获取用户收藏的帖子
    print("\n4. 测试获取用户收藏的帖子")
    bookmarked_posts_url = f"{BASE_URL}/api/job-board/my-bookmarked-posts"
    response = requests.get(bookmarked_posts_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        posts = result.get("data", {}).get("posts", [])
        print(f"用户收藏的帖子数量: {len(posts)}")
        if posts:
            print(f"第一个收藏的帖子: {json.dumps(posts[0], indent=2)}")
    else:
        print(f"获取用户收藏的帖子失败: {response.text}")
        return False

    # 测试取消收藏
    print("\n5. 测试取消收藏")
    response = requests.delete(bookmark_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"取消收藏结果: {json.dumps(result, indent=2)}")
    else:
        print(f"取消收藏失败: {response.text}")
        return False

    # 再次获取帖子交互状态
    print("\n6. 取消收藏后再次获取帖子交互状态")
    response = requests.get(status_url, headers=HEADERS)
    if response.status_code == 200:
        result = response.json()
        print(f"取消收藏后的帖子交互状态: {json.dumps(result.get('data', {}), indent=2)}")
    else:
        print(f"获取帖子交互状态失败: {response.text}")
        return False

    print("\n收藏API接口测试成功!")
    return True

def run_all_tests():
    """运行所有测试"""
    print("开始测试Job Board交互API接口...")

    like_test_result = test_like_api()
    bookmark_test_result = test_bookmark_api()

    if like_test_result and bookmark_test_result:
        print("\n所有API接口测试通过!")
        return True
    else:
        print("\nAPI接口测试失败!")
        return False

if __name__ == "__main__":
    run_all_tests()
