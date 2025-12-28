#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Firebase 用户信息 API 的脚本

这个脚本提供了一个简单的方式来测试 Firebase 用户信息 API 的功能。
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime

def get_firebase_user_info(base_url, user_id):
    """
    获取 Firebase 用户信息
    
    Args:
        base_url: API 基础 URL
        user_id: 用户 ID
        
    Returns:
        dict: Firebase 用户信息
    """
    headers = {
        'Content-Type': 'application/json',
        'Userid': user_id
    }
    
    try:
        response = requests.get(f"{base_url}/api/user/firebase-info", headers=headers)
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
    parser = argparse.ArgumentParser(description='测试 Firebase 用户信息 API')
    parser.add_argument('--base-url', default='http://localhost:5001', help='API 基础 URL')
    parser.add_argument('--user-id', required=True, help='用户 ID')
    
    args = parser.parse_args()
    
    print("获取 Firebase 用户信息...")
    result = get_firebase_user_info(args.base_url, args.user_id)
    if result:
        print_json(result)

if __name__ == '__main__':
    main()
