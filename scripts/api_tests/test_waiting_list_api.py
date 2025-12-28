#!/usr/bin/env python3
"""
等待列表 API 测试脚本

这个脚本测试等待列表 API 的所有功能，包括：
1. 加入等待列表
2. 获取等待列表状态
3. 获取等待列表条目
4. 更新等待列表条目状态

使用方法:
    python test_waiting_list_api.py [--host HOST] [--port PORT] [--user-id  USER_ID] [--admin-id ADMIN_ID]
    python test_waiting_list_api.py --user-id T2YIeGgIvWR9mUdmbomJAqqdBMD3

参数:
    --host HOST       API 主机地址，默认为 localhost
    --port PORT       API 端口，默认为 5001
    --user-id USER_ID 测试用户 ID，默认为 test_user_id
    --admin-id ADMIN_ID 管理员用户 ID，默认为 admin_user_id
"""

import argparse
import json
import random
import string
import sys
import time
from typing import Dict, Any, Optional

import requests

# 颜色定义
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='测试等待列表 API')
    parser.add_argument('--host', default='localhost', help='API 主机地址，默认为 localhost')
    parser.add_argument('--port', default=5001, type=int, help='API 端口，默认为 5001')
    parser.add_argument('--user-id', default='test_user_id', help='测试用户 ID，默认为 test_user_id')
    parser.add_argument('--admin-id', default='admin_user_id', help='管理员用户 ID，默认为 admin_user_id')
    return parser.parse_args()


def print_header(message: str):
    """打印带颜色的标题"""
    print(f"\n{BLUE}{'=' * 80}{NC}")
    print(f"{BLUE}{message.center(80)}{NC}")
    print(f"{BLUE}{'=' * 80}{NC}\n")


def print_success(message: str):
    """打印成功消息"""
    print(f"{GREEN}✓ {message}{NC}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{RED}✗ {message}{NC}")


def print_info(message: str):
    """打印信息消息"""
    print(f"{YELLOW}ℹ {message}{NC}")


def print_request(method: str, url: str, headers: Dict[str, str], data: Optional[Dict[str, Any]] = None):
    """打印请求信息"""
    print(f"\n{BLUE}请求:{NC}")
    print(f"{BLUE}  {method} {url}{NC}")
    print(f"{BLUE}  Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}{NC}")
    if data:
        print(f"{BLUE}  Data: {json.dumps(data, ensure_ascii=False, indent=2)}{NC}")


def print_response(response):
    """打印响应信息"""
    try:
        response_json = response.json()
        print(f"\n{BLUE}响应: (状态码: {response.status_code}){NC}")
        print(f"{BLUE}{json.dumps(response_json, ensure_ascii=False, indent=2)}{NC}")
        return response_json
    except json.JSONDecodeError:
        print(f"\n{RED}响应不是有效的 JSON (状态码: {response.status_code}):{NC}")
        print(f"{RED}{response.text}{NC}")
        return None


def generate_random_string(length: int = 8) -> str:
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def test_join_waiting_list(base_url: str, user_id: str) -> Dict[str, Any]:
    """测试加入等待列表 API"""
    print_header("测试加入等待列表 API")
    
    url = f"{base_url}/api/waiting-list/join"
    headers = {
        "Userid": user_id,
        "Content-Type": "application/json"
    }
    
    # 生成随机邮箱，确保每次测试都是唯一的
    random_suffix = generate_random_string()
    email = f"test.user.{random_suffix}@example.com"
    
    data = {
        "email": email,
        "name": "测试用户",
        "organization": "测试组织",
        "job_title": "测试职位",
        "reason": "测试加入等待列表",
        "additional_field1": "测试额外字段1",
        "additional_field2": "测试额外字段2"
    }
    
    print_request("POST", url, headers, data)
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response_json = print_response(response)
        
        if response.status_code == 200 and response_json and response_json.get("success"):
            print_success("成功加入等待列表")
            return response_json.get("entry", {})
        else:
            print_error(f"加入等待列表失败: {response_json.get('error', '未知错误')}")
            return {}
    except Exception as e:
        print_error(f"请求异常: {str(e)}")
        return {}


def test_get_waiting_list_status(base_url: str, user_id: str) -> Dict[str, Any]:
    """测试获取等待列表状态 API"""
    print_header("测试获取等待列表状态 API")
    
    url = f"{base_url}/api/waiting-list/status"
    headers = {
        "Userid": user_id
    }
    
    print_request("GET", url, headers)
    
    try:
        response = requests.get(url, headers=headers)
        response_json = print_response(response)
        
        if response.status_code == 200 and response_json and response_json.get("success"):
            print_success("成功获取等待列表状态")
            return response_json.get("entry", {})
        else:
            print_error(f"获取等待列表状态失败: {response_json.get('error', '未知错误')}")
            return {}
    except Exception as e:
        print_error(f"请求异常: {str(e)}")
        return {}


def test_get_waiting_list_entries(base_url: str, admin_id: str, status: str = "pending") -> Dict[str, Any]:
    """测试获取等待列表条目 API"""
    print_header(f"测试获取等待列表条目 API (状态: {status})")
    
    url = f"{base_url}/api/waiting-list/entries?status={status}&limit=10&offset=0"
    headers = {
        "Userid": admin_id
    }
    
    print_request("GET", url, headers)
    
    try:
        response = requests.get(url, headers=headers)
        response_json = print_response(response)
        
        if response.status_code == 200 and response_json and response_json.get("success"):
            print_success(f"成功获取等待列表条目 (总数: {response_json.get('total', 0)})")
            return response_json
        else:
            print_error(f"获取等待列表条目失败: {response_json.get('error', '未知错误')}")
            return {}
    except Exception as e:
        print_error(f"请求异常: {str(e)}")
        return {}


def test_update_waiting_list_status(base_url: str, admin_id: str, user_id: str, status: str = "approved") -> Dict[str, Any]:
    """测试更新等待列表条目状态 API"""
    print_header(f"测试更新等待列表条目状态 API (新状态: {status})")
    
    url = f"{base_url}/api/waiting-list/update-status"
    headers = {
        "Userid": admin_id,
        "Content-Type": "application/json"
    }
    
    data = {
        "user_id": user_id,
        "status": status
    }
    
    print_request("POST", url, headers, data)
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response_json = print_response(response)
        
        if response.status_code == 200 and response_json and response_json.get("success"):
            print_success(f"成功更新等待列表条目状态为 '{status}'")
            return response_json.get("entry", {})
        else:
            print_error(f"更新等待列表条目状态失败: {response_json.get('error', '未知错误')}")
            return {}
    except Exception as e:
        print_error(f"请求异常: {str(e)}")
        return {}


def run_all_tests(args):
    """运行所有测试"""
    base_url = f"http://{args.host}:{args.port}"
    user_id = args.user_id
    admin_id = args.admin_id
    
    print_info(f"API 基础 URL: {base_url}")
    print_info(f"测试用户 ID: {user_id}")
    print_info(f"管理员用户 ID: {admin_id}")
    
    # 测试加入等待列表
    entry = test_join_waiting_list(base_url, user_id)
    if not entry:
        print_error("加入等待列表失败，无法继续测试")
        return
    
    # 等待一秒，确保数据已保存
    time.sleep(1)
    
    # 测试获取等待列表状态
    status_entry = test_get_waiting_list_status(base_url, user_id)
    if not status_entry:
        print_error("获取等待列表状态失败，但继续测试")
    
    # 测试获取等待列表条目
    entries_result = test_get_waiting_list_entries(base_url, admin_id)
    if not entries_result:
        print_error("获取等待列表条目失败，但继续测试")
    
    # 测试更新等待列表条目状态
    updated_entry = test_update_waiting_list_status(base_url, admin_id, user_id)
    if not updated_entry:
        print_error("更新等待列表条目状态失败")
    
    # 再次测试获取等待列表状态，验证状态已更新
    if updated_entry:
        print_info("验证状态已更新...")
        time.sleep(1)  # 等待一秒，确保数据已更新
        status_entry = test_get_waiting_list_status(base_url, user_id)
        
        if status_entry and status_entry.get("status") == "approved":
            print_success("状态已成功更新为 'approved'")
        else:
            print_error("状态未成功更新")
    
    # 测试获取已批准的等待列表条目
    test_get_waiting_list_entries(base_url, admin_id, "approved")
    
    print_header("测试完成")


if __name__ == "__main__":
    args = parse_args()
    run_all_tests(args)
