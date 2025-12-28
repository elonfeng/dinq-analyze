#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的 Firebase 用户验证脚本

此脚本验证指定的 Firebase 用户 ID 是否有效。
"""

import os
import sys
import time
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 禁用开发模式下跳过认证
os.environ['FIREBASE_SKIP_AUTH_IN_DEV'] = 'false'

# 导入 Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, auth
except ImportError:
    logging.error("Firebase Admin SDK 未安装，请运行: pip install firebase-admin")
    sys.exit(1)

def verify_user(user_id, service_account_path=None):
    """
    验证 Firebase 用户 ID 是否有效
    
    Args:
        user_id: 要验证的用户 ID
        service_account_path: Firebase 服务账号文件路径
    
    Returns:
        bool: 用户 ID 是否有效
    """
    # 初始化 Firebase Admin SDK
    try:
        # 如果 Firebase 已初始化，先删除所有应用
        for app in firebase_admin._apps.values():
            firebase_admin.delete_app(app)
        
        # 使用服务账号文件初始化 Firebase
        if service_account_path and os.path.exists(service_account_path):
            logging.info(f"使用服务账号文件初始化 Firebase: {service_account_path}")
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
        else:
            # 尝试使用默认服务账号
            default_path = os.path.join(os.path.dirname(__file__), '../../server/secrets/firebase-adminsdk.json')
            if os.path.exists(default_path):
                logging.info(f"使用默认服务账号文件初始化 Firebase: {default_path}")
                cred = credentials.Certificate(default_path)
                firebase_admin.initialize_app(cred)
            else:
                logging.error("未找到服务账号文件，无法初始化 Firebase")
                return False
    except Exception as e:
        logging.error(f"初始化 Firebase 失败: {e}")
        return False
    
    # 验证用户 ID
    try:
        logging.info(f"开始验证用户 ID: {user_id}")
        start_time = time.time()
        user = auth.get_user(user_id)
        verification_time = time.time() - start_time
        
        logging.info(f"用户验证成功! 耗时: {verification_time:.2f}秒")
        logging.info(f"用户信息:")
        logging.info(f"  - UID: {user.uid}")
        logging.info(f"  - 邮箱: {getattr(user, 'email', 'unknown')}")
        logging.info(f"  - 显示名称: {getattr(user, 'display_name', 'unknown')}")
        
        # 获取用户的认证提供商
        providers = []
        if hasattr(user, 'provider_data') and user.provider_data:
            providers = [provider.provider_id for provider in user.provider_data]
        logging.info(f"  - 认证提供商: {providers}")
        
        return True
    except Exception as e:
        logging.error(f"用户验证失败: {e}")
        return False

if __name__ == "__main__":
    # 要验证的用户 ID
    USER_ID = "ffQNKT7sMMQ0MBxpFOQFMcAk3k72"
    
    # 如果提供了命令行参数，使用它作为用户 ID
    if len(sys.argv) > 1:
        USER_ID = sys.argv[1]
    
    # 服务账号文件路径
    SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), '../../server/secrets/firebase-adminsdk.json')
    
    # 验证用户 ID
    success = verify_user(USER_ID, SERVICE_ACCOUNT_PATH)
    
    # 设置退出码
    sys.exit(0 if success else 1)
