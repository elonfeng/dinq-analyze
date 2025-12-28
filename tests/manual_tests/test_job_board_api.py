#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
手动测试脚本：验证 Job Board API 是否正常工作

此脚本使用 requests 库手动测试 Job Board API 的各个端点。
"""

import os
import sys
import json
import requests
from pprint import pprint

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 配置
API_BASE_URL = 'http://localhost:5001'  # 根据实际情况修改
TEST_USER_ID = 'test_user_123'  # 测试用户ID

def test_job_board_api():
    """测试 Job Board API 的各个端点"""
    print("\n===== 测试 Job Board API =====")
    
    # 测试创建职位发布
    print("\n----- 测试创建职位发布 -----")
    post_data = {
        "title": "测试招聘信息",
        "content": "这是一个测试招聘信息，用于测试 Job Board API。",
        "post_type": "job_offer",
        "location": "北京",
        "company": "测试公司",
        "position": "软件工程师",
        "salary_range": "20k-30k",
        "contact_info": "test@example.com",
        "tags": ["Python", "Flask", "SQLAlchemy"]
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Userid': TEST_USER_ID
    }
    
    response = requests.post(
        f'{API_BASE_URL}/api/job-board/posts',
        headers=headers,
        json=post_data
    )
    
    print(f"状态码: {response.status_code}")
    response_data = response.json()
    pprint(response_data)
    
    if response.status_code == 201 and response_data.get('success'):
        post_id = response_data['data']['id']
        print(f"创建成功，职位发布ID: {post_id}")
        
        # 测试获取职位发布列表
        print("\n----- 测试获取职位发布列表 -----")
        response = requests.get(
            f'{API_BASE_URL}/api/job-board/posts',
            headers={'Userid': TEST_USER_ID}
        )
        
        print(f"状态码: {response.status_code}")
        response_data = response.json()
        print(f"总数: {response_data['data']['pagination']['total']}")
        print(f"获取到 {len(response_data['data']['posts'])} 条职位发布")
        
        # 测试获取单个职位发布
        print("\n----- 测试获取单个职位发布 -----")
        response = requests.get(
            f'{API_BASE_URL}/api/job-board/posts/{post_id}',
            headers={'Userid': TEST_USER_ID}
        )
        
        print(f"状态码: {response.status_code}")
        response_data = response.json()
        pprint(response_data)
        
        # 测试更新职位发布
        print("\n----- 测试更新职位发布 -----")
        update_data = {
            "title": "更新后的测试招聘信息",
            "salary_range": "25k-35k",
            "tags": ["Python", "Django", "Flask"]
        }
        
        response = requests.put(
            f'{API_BASE_URL}/api/job-board/posts/{post_id}',
            headers=headers,
            json=update_data
        )
        
        print(f"状态码: {response.status_code}")
        response_data = response.json()
        pprint(response_data)
        
        # 测试获取当前用户的职位发布
        print("\n----- 测试获取当前用户的职位发布 -----")
        response = requests.get(
            f'{API_BASE_URL}/api/job-board/my-posts',
            headers={'Userid': TEST_USER_ID}
        )
        
        print(f"状态码: {response.status_code}")
        response_data = response.json()
        print(f"总数: {response_data['data']['pagination']['total']}")
        print(f"获取到 {len(response_data['data']['posts'])} 条职位发布")
        
        # 测试筛选职位发布
        print("\n----- 测试筛选职位发布 -----")
        response = requests.get(
            f'{API_BASE_URL}/api/job-board/posts?post_type=job_offer&location=北京&search=测试',
            headers={'Userid': TEST_USER_ID}
        )
        
        print(f"状态码: {response.status_code}")
        response_data = response.json()
        print(f"总数: {response_data['data']['pagination']['total']}")
        print(f"获取到 {len(response_data['data']['posts'])} 条职位发布")
        
        # 测试删除职位发布
        print("\n----- 测试删除职位发布 -----")
        response = requests.delete(
            f'{API_BASE_URL}/api/job-board/posts/{post_id}',
            headers={'Userid': TEST_USER_ID}
        )
        
        print(f"状态码: {response.status_code}")
        response_data = response.json()
        pprint(response_data)
        
        # 验证删除是否成功
        print("\n----- 验证删除是否成功 -----")
        response = requests.get(
            f'{API_BASE_URL}/api/job-board/posts/{post_id}',
            headers={'Userid': TEST_USER_ID}
        )
        
        print(f"状态码: {response.status_code}")
        if response.status_code == 404:
            print("删除成功，职位发布已不存在")
        else:
            print("删除失败，职位发布仍然存在")
            pprint(response.json())
    else:
        print("创建职位发布失败")
    
    print("\n===== 测试完成 =====")

if __name__ == "__main__":
    test_job_board_api()
