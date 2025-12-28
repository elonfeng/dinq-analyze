#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Axiom 日志集成

此脚本用于测试 Axiom 日志集成功能。
"""

import os
import time
import logging
import random
from datetime import datetime

# 导入日志配置
from server.utils.logging_config import setup_logging
from server.utils.axiom_logger import info, error, warning, debug

# 设置环境变量
os.environ['AXIOM_DATASET'] = 'dinq_logs'  # 使用默认数据集名称

def generate_test_logs():
    """生成测试日志"""
    # 设置日志
    logger = setup_logging()

    # 创建特定模块的日志记录器
    test_logger = logging.getLogger('test.axiom')

    # 生成一些测试日志
    logger.info("Starting Axiom logging test")

    # 使用标准日志记录
    for i in range(5):
        level = random.choice(['debug', 'info', 'warning', 'error'])
        if level == 'debug':
            test_logger.debug(f"Debug message {i}: {datetime.now()}")
        elif level == 'info':
            test_logger.info(f"Info message {i}: {datetime.now()}")
        elif level == 'warning':
            test_logger.warning(f"Warning message {i}: {datetime.now()}")
        elif level == 'error':
            test_logger.error(f"Error message {i}: {datetime.now()}")

        # 添加一些延迟
        time.sleep(0.5)

    # 使用带上下文的日志记录
    logger.info("Testing context-aware logging")

    for i in range(5):
        user_id = f"user_{random.randint(1000, 9999)}"
        action = random.choice(['login', 'logout', 'view', 'edit', 'delete'])
        status = random.choice(['success', 'failure', 'pending'])

        context = {
            'user_id': user_id,
            'action': action,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'request_id': f"req-{random.randint(10000, 99999)}",
            'ip_address': f"192.168.1.{random.randint(1, 255)}"
        }

        if status == 'success':
            info(test_logger, f"User {user_id} performed {action}", context)
        elif status == 'failure':
            error(test_logger, f"Failed to perform {action} for user {user_id}", context)
        else:
            warning(test_logger, f"Action {action} is pending for user {user_id}", context)

        # 添加一些延迟
        time.sleep(0.5)

    # 测试异常日志
    try:
        # 故意引发异常
        result = 1 / 0
    except Exception as e:
        error(test_logger, "An error occurred during calculation", {
            'operation': 'division',
            'error_type': type(e).__name__,
            'timestamp': datetime.now().isoformat()
        }, exc_info=True)

    logger.info("Axiom logging test completed")

    # 等待一段时间，确保所有日志都被发送
    time.sleep(10)
    print("Test completed. Check Axiom dashboard for logs.")

if __name__ == "__main__":
    generate_test_logs()
