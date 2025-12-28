#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证 Firebase 用户 ID 的有效性

此脚本使用 Firebase Admin SDK 验证特定用户 ID 是否有效。
"""

import os
import sys
import time
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('firebase_user_validation')

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 尝试导入 Firebase 配置
try:
    # 首先修改环境变量，禁用开发模式下跳过认证
    os.environ['FIREBASE_SKIP_AUTH_IN_DEV'] = 'false'

    # 然后导入 Firebase 配置
    from server.config.firebase_config import firebase_auth, firebase_initialized, init_firebase
    FIREBASE_AVAILABLE = True
except ImportError as e:
    logger.error(f"Firebase 模块导入失败: {e}")
    FIREBASE_AVAILABLE = False

def test_firebase_user_validation(user_id):
    """
    测试 Firebase 用户 ID 的有效性

    Args:
        user_id: 要验证的用户 ID
    """
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase 模块不可用，无法进行验证")
        return False

    logger.info(f"开始验证用户 ID: {user_id}")

    # 确保 Firebase 已初始化
    if not firebase_initialized:
        logger.info("Firebase 未初始化，尝试初始化...")
        success = init_firebase()
        if not success:
            logger.error("Firebase 初始化失败，无法进行验证")
            return False
        logger.info("Firebase 初始化成功")

    # 验证用户 ID
    try:
        start_time = time.time()
        user = firebase_auth.get_user(user_id)
        verification_time = time.time() - start_time

        logger.info(f"用户验证成功! 耗时: {verification_time:.2f}秒")
        logger.info(f"用户信息:")
        logger.info(f"  - UID: {user.uid}")
        logger.info(f"  - 邮箱: {getattr(user, 'email', 'unknown')}")
        logger.info(f"  - 显示名称: {getattr(user, 'display_name', 'unknown')}")
        logger.info(f"  - 电话号码: {getattr(user, 'phone_number', 'unknown')}")

        # 获取用户的认证提供商
        providers = []
        if hasattr(user, 'provider_data') and user.provider_data:
            providers = [provider.provider_id for provider in user.provider_data]
        logger.info(f"  - 认证提供商: {providers}")

        # 获取用户的自定义声明
        if hasattr(user, 'custom_claims') and user.custom_claims:
            logger.info(f"  - 自定义声明: {user.custom_claims}")

        return True
    except Exception as e:
        logger.error(f"用户验证失败: {e}")
        return False

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="验证 Firebase 用户 ID 的有效性")
    parser.add_argument("user_id", help="要验证的用户 ID")
    parser.add_argument("--service-account", help="Firebase 服务账号文件路径")

    args = parser.parse_args()

    # 如果提供了服务账号文件路径，使用它初始化 Firebase
    if args.service_account:
        if FIREBASE_AVAILABLE:
            logger.info(f"使用服务账号文件初始化 Firebase: {args.service_account}")
            init_firebase(args.service_account)

    # 验证用户 ID
    success = test_firebase_user_validation(args.user_id)

    # 设置退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # 如果没有提供命令行参数，使用默认用户 ID
    if len(sys.argv) == 1:
        sys.argv.append("ffQNKT7sMMQ0MBxpFOQFMcAk3k72")

    main()
