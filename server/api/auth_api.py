"""
Authentication API

This module provides API endpoints for user authentication.
"""

import logging
from flask import Blueprint, request, jsonify
import jwt
from datetime import datetime, timedelta
import json
import os
import re


# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Configure logging
logger = logging.getLogger('server.api.auth')

# 从配置文件读取配置
def load_config():
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'dashboard', 'src', 'config.js')
        logger.info(f"Loading config from: {config_path}")
        
        if not os.path.exists(config_path):
            logger.error(f"Config file not found at: {config_path}")
            return [], {
                'secret': 'dinq-admin-secret-key-2024',
                'expiration': 24 * 60 * 60
            }
            
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"Config file content: {content}")
            
            # 提取 ADMIN_USERS 数组
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end != -1:
                users_str = content[start:end]
                logger.info(f"Found users string: {users_str}")
                
                # 使用正则表达式提取键值对
                def convert_js_to_dict(js_str):
                    # 移除注释
                    js_str = re.sub(r'//.*$', '', js_str, flags=re.MULTILINE)
                    
                    # 提取所有键值对
                    pattern = r'(\w+):\s*[\'"]?([^\'",\s]+)[\'"]?'
                    matches = re.findall(pattern, js_str)
                    
                    # 构建字典
                    result = {}
                    for key, value in matches:
                        # 转换键名
                        if key == 'userType':
                            key = 'user_type'
                        # 尝试将值转换为数字
                        try:
                            if value.isdigit():
                                value = int(value)
                            elif value.replace('.', '').isdigit():
                                value = float(value)
                        except ValueError:
                            pass
                        result[key] = value
                    
                    return result
                
                # 提取每个用户对象
                user_pattern = r'{[^}]+}'
                user_matches = re.findall(user_pattern, users_str)
                admin_users = [convert_js_to_dict(user) for user in user_matches]
                logger.info(f"Parsed admin users: {admin_users}")
            else:
                logger.error("Could not find ADMIN_USERS array in config file")
                admin_users = []
                
            # 提取 JWT_CONFIG
            jwt_start = content.find('JWT_CONFIG')
            if jwt_start != -1:
                jwt_str = content[jwt_start:].split('export')[0]
                jwt_config = convert_js_to_dict(jwt_str)
                # 确保 expiration 是数字
                if isinstance(jwt_config.get('expiration'), str):
                    try:
                        jwt_config['expiration'] = int(jwt_config['expiration'])
                    except ValueError:
                        jwt_config['expiration'] = 24 * 60 * 60
                logger.info(f"Parsed JWT config: {jwt_config}")
            else:
                logger.error("Could not find JWT_CONFIG in config file")
                jwt_config = {
                    'secret': 'dinq-admin-secret-key-2024',
                    'expiration': 24 * 60 * 60
                }
                
            return admin_users, jwt_config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return [], {
            'secret': 'dinq-admin-secret-key-2024',
            'expiration': 24 * 60 * 60
        }

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """
    用户登录
    
    Request body:
        username: 用户名
        password: 密码
        
    Returns:
        JSON response with token if successful
    """
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': '用户名和密码不能为空'
            }), 400
            
        # 从配置文件加载配置
        admin_users, jwt_config = load_config()
        
        # 查找用户
        print(f"admin_users: {admin_users}")
        user = next((u for u in admin_users if u['username'] == username), None)
        print(f"user: {user}")
        # 验证用户存在性和密码
        if not user or user['password'] != password:
            return jsonify({
                'success': False,
                'error': '用户名或密码错误'
            }), 401
            
        # 生成JWT token
        token = jwt.encode({
            'username': user['username'],
            'user_type': user['user_type'],
            'exp': datetime.utcnow() + timedelta(seconds=jwt_config['expiration'])
        }, jwt_config['secret'], algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'username': user['username'],
                'user_type': user['user_type']
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': '登录失败'
        }), 500

@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """
    获取当前用户信息
    
    Returns:
        JSON response with user info
    """
    try:
        # 从请求头获取token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': '未登录'
            }), 401
            
        token = auth_header.split(' ')[1]
        
        # 从配置文件加载配置
        admin_users, jwt_config = load_config()
        
        # 验证token
        try:
            payload = jwt.decode(token, jwt_config['secret'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': '登录已过期'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': '无效的token'
            }), 401
            
        # 查找用户
        user = next((u for u in admin_users if u['username'] == payload['username']), None)
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 404
            
        return jsonify({
            'success': True,
            'user': {
                'username': user['username'],
                'user_type': user['user_type']
            }
        })
        
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取用户信息失败'
        }), 500 