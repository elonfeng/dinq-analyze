#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化用户交互表

此脚本用于初始化用户交互相关的数据库表，包括点赞和收藏表。
"""

import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_tables():
    """初始化数据库表"""
    try:
        # 导入数据库相关模块
        from src.utils.db_utils import create_tables
        from src.models.user_interactions import JobPostLike, JobPostBookmark
        
        # 创建表
        logger.info("开始创建用户交互表...")
        create_tables()
        logger.info("用户交互表创建成功!")
        
        return True
    except Exception as e:
        logger.error(f"创建用户交互表失败: {e}")
        return False

if __name__ == "__main__":
    init_tables()
