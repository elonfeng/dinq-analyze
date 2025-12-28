"""
Scholar Report Generator

This module contains functions for generating and saving scholar reports.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

# 直接导入transform_profile模块
from server.transform_profile import transform_data

# 导入dotenv库用于加载.env文件
try:
    from dotenv import load_dotenv
    # 尝试加载.env文件
    load_dotenv()
    dotenv_loaded = True
except ImportError:
    dotenv_loaded = False
    logging.warning("python-dotenv not installed. Environment variables from .env file will not be loaded.")

# 设置日志记录器
logger = logging.getLogger(__name__)

def save_scholar_report(report: Dict, query: str, session_id: str) -> Dict[str, str]:
    """保存Scholar报告为JSON并生成HTML报告

    Args:
        report: Scholar报告数据
        query: 用户查询
        session_id: 会话 ID

    Returns:
        包含 JSON URL、HTML URL 和研究者名称的字典
    """
    # 创建reports目录（如果不存在）
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # 获取研究者姓名和Scholar ID
    researcher_name = report.get("researcher", {}).get("name", "unknown")
    researcher_name = researcher_name.replace(" ", "_")
    scholar_id = report.get("researcher", {}).get("scholar_id", "")

    # 如果没有Scholar ID，使用时间戳作为备用
    if not scholar_id:
        logger.warning(f"No Scholar ID found for {researcher_name}, using timestamp instead")
        scholar_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 生成文件名 (姓名+谷歌学术ID)
    json_filename = f"{researcher_name}_{scholar_id}.json"
    json_filepath = os.path.join(reports_dir, json_filename)

    # 保存JSON文件
    try:
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Report data saved to {json_filepath}")
    except Exception as e:
        logger.error(f"Error saving report data: {str(e)}")

    # 使用transform_profile模块直接转换JSON数据
    formatted_json_filename = f"{researcher_name}_{scholar_id}_formatted.json"
    formatted_json_filepath = os.path.join(reports_dir, formatted_json_filename)

    try:
        # 直接调用transform_data函数
        transformed_data = transform_data(report)

        # 保存转换后的JSON文件
        with open(formatted_json_filepath, "w", encoding="utf-8") as f:
            json.dump(transformed_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Formatted JSON generated at {formatted_json_filepath}")
        # 使用转换后的JSON文件路径
        json_filepath = formatted_json_filepath
    except Exception as e:
        logger.error(f"Error transforming data: {str(e)}")

    # 从环境变量中获取域名配置，或使用默认值
    domain = os.environ.get("DINQ_API_DOMAIN", "http://127.0.0.1:5001")

    # 根据环境变量选择不同的域名
    env = os.environ.get("DINQ_ENV", "development")
    if env == "production":
        domain = os.environ.get("DINQ_API_DOMAIN", "https://api.dinq.ai")
    elif env == "test":
        domain = os.environ.get("DINQ_API_DOMAIN", "https://test-api.dinq.ai")

    logger.info(f"Using domain: {domain} for environment: {env}")

    # 获取JSON文件的相对路径，用于前端直接获取数据
    json_relative_path = os.path.relpath(json_filepath, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    json_url = f"{domain}/{json_relative_path}"

    return {
        "json_url": json_url,
        "html_url": json_url,  # 使用相同的URL，因为不再生成HTML
        "researcher_name": researcher_name
    }
