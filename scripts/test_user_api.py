#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试用户 API 的脚本

这个脚本提供了一个简单的方式来测试用户 API 的功能。
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

def get_user_info(base_url, user_id):
    """
    获取用户信息
    
    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        
    Returns:
        dict: 用户信息
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }
    
    try:
        response = requests.get(f"{base_url}/api/user/me", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def update_user_info(base_url, user_id, display_name=None, email=None):
    """
    更新用户信息
    
    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        display_name: 显示名称
        email: 电子邮件
        
    Returns:
        dict: 更新后的用户信息
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }
    
    data = {}
    if display_name:
        data['display_name'] = display_name
    if email:
        data['email'] = email
    
    try:
        response = requests.put(f"{base_url}/api/user/me", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def use_activation_code(base_url, user_id, code):
    """
    使用激活码
    
    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        code: 激活码
        
    Returns:
        dict: 使用结果
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }
    
    data = {
        'code': code
    }
    
    try:
        response = requests.post(f"{base_url}/api/activation-codes/use", headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def create_activation_code(base_url, user_id):
    """
    创建激活码
    
    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        
    Returns:
        dict: 创建结果
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }
    
    data = {
        'notes': '测试激活码'
    }
    
    try:
        response = requests.post(f"{base_url}/api/activation-codes/create", headers=headers, json=data)
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
    parser = argparse.ArgumentParser(description='测试用户 API')
    parser.add_argument('--base-url', default='http://localhost:5001', help='API 基础 URL')
    parser.add_argument('--user-id', required=True, help='用户 ID')
    parser.add_argument('--action', choices=['get', 'update', 'activate', 'create-code'], default='get', help='要执行的操作')
    parser.add_argument('--display-name', help='用户显示名称')
    parser.add_argument('--email', help='用户电子邮件')
    parser.add_argument('--code', help='激活码')
    
    args = parser.parse_args()
    
    if args.action == 'get':
        print("获取用户信息...")
        result = get_user_info(args.base_url, args.user_id)
        if result:
            print_json(result)
    
    elif args.action == 'update':
        if not args.display_name and not args.email:
            print("错误: 更新操作需要提供 display-name 或 email")
            return
        
        print("更新用户信息...")
        result = update_user_info(args.base_url, args.user_id, args.display_name, args.email)
        if result:
            print_json(result)
    
    elif args.action == 'activate':
        if not args.code:
            print("错误: 激活操作需要提供 code")
            return
        
        print("使用激活码...")
        result = use_activation_code(args.base_url, args.user_id, args.code)
        if result:
            print_json(result)
    
    elif args.action == 'create-code':
        print("创建激活码...")
        result = create_activation_code(args.base_url, args.user_id)
        if result:
            print_json(result)

if __name__ == '__main__':
    main()
