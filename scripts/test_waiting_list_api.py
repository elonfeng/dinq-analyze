#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试等待列表 API 的脚本

这个脚本提供了一个简单的方式来测试等待列表 API 的功能。
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

def join_waiting_list(base_url, user_id, email, name, data=None):
    """
    加入等待列表

    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        email: 用户电子邮件
        name: 用户全名
        data: 额外数据

    Returns:
        dict: 操作结果
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }

    # 准备请求数据
    request_data = {
        'email': email,
        'name': name
    }

    # 添加额外数据
    if data:
        request_data.update(data)

    try:
        response = requests.post(f"{base_url}/api/waiting-list/join", headers=headers, json=request_data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def get_waiting_list_status(base_url, user_id):
    """
    获取等待列表状态

    Args:
        base_url: API 基础 URL
        user_id: 用户 ID

    Returns:
        dict: 等待列表状态
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }

    try:
        response = requests.get(f"{base_url}/api/waiting-list/status", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def get_waiting_list_entries(base_url, user_id, status=None, limit=10, offset=0):
    """
    获取等待列表条目

    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        status: 按状态筛选
        limit: 返回的最大条目数
        offset: 分页偏移量

    Returns:
        dict: 等待列表条目
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }

    # 构建查询参数
    params = {
        'limit': limit,
        'offset': offset
    }

    if status:
        params['status'] = status

    try:
        response = requests.get(f"{base_url}/api/waiting-list/entries", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def update_waiting_list_status(base_url, admin_user_id, user_id, status):
    """
    更新等待列表条目状态

    Args:
        base_url: API 基础 URL
        admin_user_id: 管理员用户 ID
        user_id: 要更新的条目的用户 ID
        status: 新状态

    Returns:
        dict: 操作结果
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': admin_user_id
    }

    data = {
        'user_id': user_id,
        'status': status
    }

    try:
        response = requests.post(f"{base_url}/api/waiting-list/update-status", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def print_json(data):
    """
    打印 JSON 数据

    Args:
        data: 要打印的数据
    """
    print(json.dumps(data, indent=2, ensure_ascii=False))

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='测试等待列表 API')
    parser.add_argument('--base-url', default='http://localhost:5001', help='API 基础 URL')
    parser.add_argument('--user-id', required=True, help='用户 ID')
    parser.add_argument('--action', choices=['join', 'status', 'list', 'update'], required=True, help='要执行的操作')
    parser.add_argument('--email', help='用户电子邮件')
    parser.add_argument('--name', help='用户全名')
    parser.add_argument('--organization', help='用户组织或公司')
    parser.add_argument('--job-title', help='用户职位')
    parser.add_argument('--reason', help='加入等待列表的原因')
    parser.add_argument('--status', help='状态 (pending, approved, rejected)')
    parser.add_argument('--target-user-id', help='要更新的条目的用户 ID')
    parser.add_argument('--limit', type=int, default=10, help='返回的最大条目数')
    parser.add_argument('--offset', type=int, default=0, help='分页偏移量')

    args = parser.parse_args()

    if args.action == 'join':
        if not args.email or not args.name:
            print("错误: 加入等待列表需要提供 email 和 name")
            return

        # 准备数据
        data = {
            'email': args.email,
            'name': args.name
        }

        # 添加可选字段
        if args.organization:
            data['organization'] = args.organization
        if args.job_title:
            data['job_title'] = args.job_title
        if args.reason:
            data['reason'] = args.reason

        print("加入等待列表...")
        result = join_waiting_list(args.base_url, args.user_id, args.email, args.name, data)
        if result:
            print_json(result)

    elif args.action == 'status':
        print("获取等待列表状态...")
        result = get_waiting_list_status(args.base_url, args.user_id)
        if result:
            print_json(result)

    elif args.action == 'list':
        print("获取等待列表条目...")
        result = get_waiting_list_entries(args.base_url, args.user_id, args.status, args.limit, args.offset)
        if result:
            print_json(result)

    elif args.action == 'update':
        if not args.target_user_id or not args.status:
            print("错误: 更新等待列表状态需要提供 target-user-id 和 status")
            return

        print("更新等待列表条目状态...")
        result = update_waiting_list_status(args.base_url, args.user_id, args.target_user_id, args.status)
        if result:
            print_json(result)

if __name__ == '__main__':
    main()


#
# 加入等待列表
# python scripts/test_waiting_list_api.py --user-id your_user_id --action join --email user@example.com --name "User Name" --organization "Company" --job-title "Developer" --reason "I want to join"

# # 获取等待列表状态
# python scripts/test_waiting_list_api.py --user-id your_user_id --action status

# # 获取等待列表条目
# python scripts/test_waiting_list_api.py --user-id admin_user_id --action list --status pending

# # 更新等待列表条目状态
# python scripts/test_waiting_list_api.py --user-id admin_user_id --action update --target-user-id user_id_to_update --status approved