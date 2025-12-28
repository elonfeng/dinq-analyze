"""
Environment Variable Loader

This module provides functions for loading environment variables from .env files.
"""

from __future__ import annotations

import os
import logging
from typing import List, Set
from dotenv import load_dotenv

# 获取模块日志记录器
logger = logging.getLogger('server.config.env_loader')


def _get_runtime_env() -> str:
    """
    Determine runtime environment name used for env file selection.

    Priority:
    - DINQ_ENV
    - FLASK_ENV
    - development
    """
    raw = os.environ.get("DINQ_ENV") or os.environ.get("FLASK_ENV") or "development"
    return str(raw).strip().lower() or "development"


def _candidate_env_files(project_root: str, runtime_env: str) -> list[str]:
    """
    Build env file candidate list ordered from highest to lowest precedence.

    Notes:
    - We use load_dotenv(..., override=False), so earlier files win.
    - External env vars always take precedence over files.
    """
    names: List[str] = []

    # Most specific -> least specific (earlier wins)
    names.append(f".env.{runtime_env}.local")
    names.append(".env.local")
    names.append(f".env.{runtime_env}")
    names.append(".env")

    candidates: List[str] = []
    for filename in names:
        candidates.append(os.path.join(project_root, filename))
        candidates.append(os.path.join(os.getcwd(), filename))
    # Deduplicate while preserving order
    seen: Set[str] = set()
    ordered: List[str] = []
    for p in candidates:
        p = os.path.abspath(p)
        if p in seen:
            continue
        seen.add(p)
        ordered.append(p)
    return ordered


def load_environment_variables(log_dinq_vars: bool = False):
    """
    加载环境变量，按照以下顺序尝试：
    1) 项目根目录 / 当前工作目录下的 .env* 文件（按优先级）
       - .env.<env>.local
       - .env.local
       - .env.<env>
       - .env
    2) 默认路径（不指定路径）
    
    Args:
        log_dinq_vars (bool): 是否记录以 DINQ_ 开头的环境变量，默认为 True
        
    Returns:
        bool: 是否成功加载了任何 .env 文件
    """
    loaded = False
    
    try:
        # 获取项目根目录路径
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
        runtime_env = _get_runtime_env()
        logger.info("Resolved runtime env: %s", runtime_env)

        candidates = _candidate_env_files(project_root, runtime_env)
        for path in candidates:
            if not os.path.exists(path):
                continue
            load_dotenv(dotenv_path=path, override=False)
            logger.info("Loaded env file: %s", path)
            loaded = True

        if not loaded:
            # 尝试默认加载（不指定路径）
            load_dotenv()
            logger.info("Attempted to load .env file using default path")
    except Exception as e:
        logger.error(f"Error loading .env file: {str(e)}")
        return False
    
    # 记录 DINQ_ 相关环境变量（默认关闭，避免日志泄露敏感信息）
    if log_dinq_vars:
        log_dinq_environment_variables()
    
    return loaded

def log_dinq_environment_variables():
    """
    记录所有以 DINQ_ 开头的环境变量（会对疑似敏感值做脱敏），便于调试
    """
    logger.info("DINQ environment variables:")
    dinq_vars = {k: v for k, v in os.environ.items() if k.startswith("DINQ_")}

    if dinq_vars:
        for key, value in dinq_vars.items():
            logger.info("  %s: %s", key, _mask_env_value(key, value))
    else:
        logger.warning("No DINQ_ environment variables found")


def _mask_env_value(key: str, value: str) -> str:
    if value is None:
        return ""

    key_upper = (key or "").upper()
    if any(s in key_upper for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "DSN")):
        return "***"

    v = str(value)
    if len(v) <= 6:
        return v
    return f"{v[:2]}***{v[-2:]}"

def get_env_var(name, default=None):
    """
    获取环境变量，如果不存在则返回默认值
    
    Args:
        name (str): 环境变量名称
        default: 默认值，如果环境变量不存在则返回此值
        
    Returns:
        环境变量的值或默认值
    """
    value = os.environ.get(name, default)
    if value is None:
        logger.warning(f"Environment variable {name} not found")
    return value
