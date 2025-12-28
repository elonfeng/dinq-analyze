#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证完整流程

此脚本测试完整流程，包括：
1. 从URL中提取学者ID
2. 从数据库缓存中获取数据
3. 将数据保存到数据库
4. 再次从数据库缓存中获取数据
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Optional
import requests

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入相关模块
try:
    from src.utils.db_utils import create_tables
    from server.api.scholar.db_cache import get_scholar_from_cache, save_scholar_to_cache

    # 确保数据库表已创建
    create_tables()

    # 标记数据库模块是否可用
    DB_AVAILABLE = True
except ImportError as e:
    print(f"数据库模块导入失败，测试将被跳过: {e}")
    DB_AVAILABLE = False

def test_extract_scholar_id_from_url():
    """测试从URL中提取学者ID"""
    print("\n=== 测试从URL中提取学者ID ===")

    # 创建测试URL
    url = "https://scholar.google.com/citations?user=DZ-fHPgAAAAJ&hl=en"

    # 提取学者ID
    import re
    match = re.search(r'user=([\w-]+)', url)
    if match:
        scholar_id = match.group(1)
        print(f"✅ 成功从URL中提取学者ID: {scholar_id}")
        return scholar_id
    else:
        print(f"❌ 从URL中提取学者ID失败")
        return None

def _request_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Userid": os.getenv("DINQ_TEST_USER_ID", "test_user_full_flow"),
    }


def _base_url() -> str:
    return os.getenv("DINQ_TEST_BASE_URL", "http://localhost:5001")


def _run_sync_analyze(scholar_id: str) -> Optional[dict]:
    payload = {
        "source": "scholar",
        "mode": "sync",
        "input": {"scholar_id": scholar_id},
        "options": {"cache": True},
    }
    resp = requests.post(f"{_base_url()}/api/analyze", json=payload, headers=_request_headers(), timeout=300)
    if resp.status_code != 200:
        print(f"❌ /api/analyze 请求失败: {resp.status_code} {resp.text}")
        return None
    return resp.json()


def _fetch_job(job_id: str) -> Optional[dict]:
    resp = requests.get(f"{_base_url()}/api/analyze/jobs/{job_id}", headers=_request_headers(), timeout=60)
    if resp.status_code != 200:
        print(f"❌ 获取 job 失败: {resp.status_code} {resp.text}")
        return None
    return resp.json()


def test_full_flow():
    """测试完整流程"""
    if not DB_AVAILABLE:
        print("\n数据库模块不可用，跳过测试")
        return False

    print("\n=== 测试完整流程 ===")

    # 1. 从URL中提取学者ID
    scholar_id = test_extract_scholar_id_from_url()
    if not scholar_id:
        return False

    # 2. 清除缓存（如果有）
    print("\n1. 清除缓存（如果有）...")
    from src.utils.scholar_repository import scholar_repo
    scholar_repo.delete_by_scholar_id(scholar_id)
    print(f"✅ 已清除学者 {scholar_id} 的缓存")

    # 3. 第一次查询（从 /api/analyze 获取数据）
    print("\n2. 第一次查询（从 /api/analyze 获取数据）...")
    analyze_resp = _run_sync_analyze(scholar_id)
    if not analyze_resp or not analyze_resp.get("success"):
        print("❌ /api/analyze 返回失败")
        return False
    job_id = analyze_resp.get("job_id")
    if not job_id:
        print("❌ /api/analyze 未返回 job_id")
        return False

    job_payload = _fetch_job(job_id)
    if not job_payload or not job_payload.get("success"):
        print("❌ 获取 job 数据失败")
        return False

    cards = job_payload.get("job", {}).get("cards", {})
    scholar_data = cards.get("full_report", {}).get("data")

    # 检查是否成功获取数据
    if scholar_data:
        print(f"✅ 成功从Google Scholar获取数据")

        # 提取学者ID
        extracted_id = None
        if "researcher" in scholar_data and "scholar_id" in scholar_data["researcher"]:
            extracted_id = scholar_data["researcher"]["scholar_id"]

        if extracted_id == scholar_id:
            print(f"✅ 学者ID正确: {extracted_id}")
        else:
            print(f"❌ 学者ID不正确，期望: {scholar_id}，实际: {extracted_id}")
    else:
        print(f"❌ 从Google Scholar获取数据失败")
        return False

    # 4. 保存数据到缓存
    print("\n3. 保存数据到缓存...")
    success = save_scholar_to_cache(scholar_data, scholar_id)
    if success:
        print(f"✅ 成功将学者 {scholar_id} 的数据保存到缓存")
    else:
        print(f"❌ 保存学者 {scholar_id} 的数据到缓存失败")
        return False

    # 5. 第二次查询（从缓存获取数据）
    print("\n4. 第二次查询（从缓存获取数据）...")
    cached_entry = get_scholar_from_cache(scholar_id)
    cached_data = cached_entry if isinstance(cached_entry, dict) else None

    # 检查是否成功从缓存获取数据
    if cached_data:
        print(f"✅ 成功从缓存获取数据")

        # 检查数据是否与原始数据相同
        cached_id = cached_data.get("researcher", {}).get("scholar_id")
        if cached_id == scholar_id:
            print(f"✅ 缓存数据学者ID匹配: {cached_id}")
        else:
            print(f"❌ 缓存数据学者ID不匹配: {cached_id}")
    else:
        print(f"❌ 从缓存获取数据失败")
        return False

    # 触发二次 analyze，验证 cache path 是否可用
    print("\n5. 再次调用 /api/analyze 验证缓存路径...")
    analyze_resp_2 = _run_sync_analyze(scholar_id)
    if not analyze_resp_2 or not analyze_resp_2.get("success"):
        print("❌ 第二次 /api/analyze 返回失败")
        return False

    print("\n=== 完整流程测试完成 ===")
    return True

if __name__ == "__main__":
    test_full_flow()
