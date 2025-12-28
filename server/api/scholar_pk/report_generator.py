"""
Scholar PK Report Generator

This module contains functions for generating and saving scholar PK reports.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

# 加载 .env（不打印变量值，避免泄露）
try:
    from server.config.env_loader import load_environment_variables

    load_environment_variables(log_dinq_vars=False)
except Exception:
    # Best effort: report 生成不应因 env loader 失败而崩
    pass

# 设置日志记录器
logger = logging.getLogger(__name__)

def save_pk_report(pk_result: Dict, query1: str, query2: str, session_id: str) -> Dict[str, str]:
    """保存Scholar PK报告为JSON

    Args:
        pk_result: PK结果数据，包含两位研究者的信息
        query1: 第一位研究者的查询
        query2: 第二位研究者的查询
        session_id: 会话 ID

    Returns:
        包含两位研究者的JSON URL的字典
    """
    # 创建reports目录（如果不存在）
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # 获取两位研究者的姓名和Scholar ID
    researcher1_name = pk_result.get("researcher1", {}).get("name", "unknown")
    researcher1_name = researcher1_name.replace(" ", "_")
    scholar_id1 = pk_result.get("researcher1", {}).get("scholar_id", "")

    researcher2_name = pk_result.get("researcher2", {}).get("name", "unknown")
    researcher2_name = researcher2_name.replace(" ", "_")
    scholar_id2 = pk_result.get("researcher2", {}).get("scholar_id", "")

    # 如果没有Scholar ID，使用时间戳作为备用
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not scholar_id1:
        logger.warning(f"No Scholar ID found for {researcher1_name}, using timestamp instead")
        scholar_id1 = f"{timestamp}_1"

    if not scholar_id2:
        logger.warning(f"No Scholar ID found for {researcher2_name}, using timestamp instead")
        scholar_id2 = f"{timestamp}_2"

    # 生成PK文件名 (两位研究者姓名+谷歌学术ID)
    pk_filename = f"pk_{researcher1_name}_{scholar_id1}_vs_{researcher2_name}_{scholar_id2}.json"
    pk_filepath = os.path.join(reports_dir, pk_filename)

    # 保存PK JSON文件
    try:
        with open(pk_filepath, "w", encoding="utf-8") as f:
            json.dump(pk_result, f, ensure_ascii=False, indent=2)
        logger.info(f"PK report data saved to {pk_filepath}")
    except Exception as e:
        logger.error(f"Error saving PK report data: {str(e)}")

    # 从环境变量中获取域名配置，或使用默认值
    domain = os.environ.get("DINQ_API_DOMAIN", "http://127.0.0.1:5001")
    env = os.environ.get("DINQ_ENV", "development")

    if env == "production":
        domain = os.environ.get("DINQ_API_DOMAIN", "https://api.dinq.ai")
    elif env == "test":
        domain = os.environ.get("DINQ_API_DOMAIN", "https://test-api.dinq.ai")

    logger.info(f"Using domain: {domain} for environment: {env}")

    # 获取JSON文件的相对路径，用于前端直接获取数据
    json_relative_path = os.path.relpath(pk_filepath, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    pk_json_url = f"{domain}/{json_relative_path}"

    # 返回包含两位研究者数据URL的字典
    return {
        "pk_json_url": pk_json_url,
        "researcher1_name": researcher1_name,
        "researcher2_name": researcher2_name,
        "scholar_id1": scholar_id1,
        "scholar_id2": scholar_id2
    }
