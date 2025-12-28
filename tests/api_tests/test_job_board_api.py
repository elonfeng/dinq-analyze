#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证 Job Board API 是否正常工作

此脚本测试 Job Board API 的各个端点是否正常工作。
"""

import os
import sys
import json
import unittest
from flask import Flask
from unittest.mock import patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Default to a local sqlite db for standalone runs
os.environ.setdefault("DINQ_DB_URL", "sqlite:////tmp/dinq_job_board_test.db")
# Ensure auth bypass in local test client
os.environ.setdefault("DINQ_AUTH_BYPASS", "true")
os.environ.setdefault("FLASK_ENV", "development")

# 导入相关模块
from server.api.job_board import job_board_bp
from src.utils.job_board_repository import job_post_repo
from src.utils.db_utils import create_tables

# 创建测试应用
app = Flask(__name__)
app.register_blueprint(job_board_bp)

# 配置测试环境
app.config['TESTING'] = True
app.config['DEBUG'] = False

# 确保数据库表已创建
create_tables()

class JobBoardAPITestCase(unittest.TestCase):
    """测试 Job Board API"""
    
    def setUp(self):
        """设置测试环境"""
        self.client = app.test_client()
        self.client.testing = True
        
        # 创建测试用户ID
        self.test_user_id = "test_user_123"
        
        # 模拟认证
        self.auth_patcher = patch('server.utils.auth.get_user_id_from_header')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = self.test_user_id
        
        # 模拟用户工具
        self.user_utils_patcher = patch('server.utils.user_utils.get_current_user_id')
        self.mock_user_utils = self.user_utils_patcher.start()
        self.mock_user_utils.return_value = self.test_user_id
        self.auth_headers = {"Userid": self.test_user_id}
        
        # 创建测试数据
        self.test_post = job_post_repo.create_post(
            user_id=self.test_user_id,
            title="测试招聘信息",
            content="这是一个测试招聘信息，用于测试 Job Board API。",
            post_type="job",
            location="北京",
            company="测试公司",
            position="软件工程师",
            salary_range="20k-30k",
            contact_info="test@example.com",
            tags=["Python", "Flask", "SQLAlchemy"]
        )
        self.test_post_id = None
        if isinstance(self.test_post, dict):
            self.test_post_id = self.test_post.get("id")
    
    def tearDown(self):
        """清理测试环境"""
        # 停止模拟
        self.auth_patcher.stop()
        self.user_utils_patcher.stop()
        
        # 删除测试数据
        if self.test_post_id:
            job_post_repo.delete_post(self.test_post_id, self.test_user_id)
    
    def test_get_job_posts(self):
        """测试获取职位发布列表"""
        response = self.client.get('/api/job-board/posts')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('posts', data['data'])
        self.assertIn('pagination', data['data'])
        self.assertGreaterEqual(len(data['data']['posts']), 1)
    
    def test_get_job_post(self):
        """测试获取单个职位发布"""
        response = self.client.get(f'/api/job-board/posts/{self.test_post_id}')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['id'], self.test_post_id)
        self.assertEqual(data['data']['title'], self.test_post.get('title') if isinstance(self.test_post, dict) else None)
    
    def test_create_job_post(self):
        """测试创建职位发布"""
        post_data = {
            "title": "新的测试招聘信息",
            "content": "这是一个新的测试招聘信息，用于测试创建职位发布API。",
            "post_type": "job",
            "location": "上海",
            "company": "新测试公司",
            "position": "前端工程师",
            "salary_range": "15k-25k",
            "contact_info": "new_test@example.com",
            "tags": ["JavaScript", "React", "Vue"]
        }
        
        response = self.client.post(
            '/api/job-board/posts',
            data=json.dumps(post_data),
            content_type='application/json',
            headers=self.auth_headers,
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['title'], post_data['title'])
        self.assertEqual(data['data']['content'], post_data['content'])
        self.assertEqual(data['data']['post_type'], post_data['post_type'])
        
        # 清理创建的测试数据
        if 'id' in data['data']:
            job_post_repo.delete_post(data['data']['id'], self.test_user_id)
    
    def test_update_job_post(self):
        """测试更新职位发布"""
        update_data = {
            "title": "更新后的测试招聘信息",
            "salary_range": "25k-35k",
            "tags": ["Python", "Django", "Flask"]
        }
        
        response = self.client.put(
            f'/api/job-board/posts/{self.test_post_id}',
            data=json.dumps(update_data),
            content_type='application/json',
            headers=self.auth_headers,
        )
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['title'], update_data['title'])
        self.assertEqual(data['data']['salary_range'], update_data['salary_range'])
    
    def test_delete_job_post(self):
        """测试删除职位发布"""
        # 创建一个新的职位发布用于测试删除
        test_post_to_delete = job_post_repo.create_post(
            user_id=self.test_user_id,
            title="要删除的测试招聘信息",
            content="这是一个要删除的测试招聘信息。",
            post_type="job"
        )

        post_id = test_post_to_delete.get("id") if isinstance(test_post_to_delete, dict) else None
        response = self.client.delete(f'/api/job-board/posts/{post_id}', headers=self.auth_headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        
        # 验证是否已删除
        deleted_post = job_post_repo.get_post_by_id(post_id)
        self.assertIsNone(deleted_post)
    
    def test_get_my_job_posts(self):
        """测试获取当前用户的职位发布"""
        response = self.client.get('/api/job-board/my-posts', headers=self.auth_headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('posts', data['data'])
        self.assertIn('pagination', data['data'])
        self.assertGreaterEqual(len(data['data']['posts']), 1)
        
        # 验证所有职位发布都属于测试用户
        for post in data['data']['posts']:
            self.assertEqual(post['user_id'], self.test_user_id)

if __name__ == '__main__':
    unittest.main()
