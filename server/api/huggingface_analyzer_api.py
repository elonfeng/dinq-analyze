"""
Hugging Face Analyzer API

This module provides Flask API endpoints for analyzing Hugging Face user profiles.
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify, g
from server.utils.auth import require_verified_user
from server.utils.api_usage_tracker import track_api_call
from server.huggingface_analyzer.analyzer import HuggingFaceAnalyzer
from server.analyze.api import create_analysis_job, run_sync_job

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
huggingface_analyzer_bp = Blueprint('huggingface_analyzer', __name__, url_prefix='/api/huggingface')

def get_analyzer() -> HuggingFaceAnalyzer:
    """Get HuggingFace analyzer instance"""
    return HuggingFaceAnalyzer()

@huggingface_analyzer_bp.route('/card/analyze', methods=['POST'])
def analyze_huggingface_card():
    """
    Hugging Face用户卡片分析接口
    
    返回用户的基本信息、核心数据、感兴趣领域、组织和代表作
    
    Request body:
    {
        "username": "huggingface_username"
    }
    
    Returns:
    {
        "code": 200,
        "message": "Hugging Face card analysis completed successfully",
        "data": {
            "username": "username",
            "basic_stats": {
                "models": 10,
                "datasets": 5,
                "spaces": 3,
                "docs": 2,
                "claps": 100,
                "collections": 1
            },
            "interests": ["NLP", "Computer Vision", "Machine Learning"],
            "organizations": [
                {
                    "name": "Hugging Face",
                    "url": "https://huggingface.co/huggingface",
                    "logo": "https://..."
                }
            ],
            "representative_work": {
                "title": "BERT Base Model",
                "description": "Pre-trained BERT model...",
                "type": "model",
                "updated_time": "2 days ago",
                "stats": {
                    "downloads": 1000000,
                    "likes": 500
                }
            }
        }
    }
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({
                'code': 400,
                'message': 'Missing username in request body'
            }), 400
        
        username = data['username'].strip()
        if not username:
            return jsonify({
                'code': 400,
                'message': 'Username cannot be empty'
            }), 400

        legacy_flag = data.get("legacy") or request.args.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")
        if not use_legacy:
            job_id, _created = create_analysis_job(
                user_id="anonymous",
                source="huggingface",
                input_payload={"username": username},
                requested_cards=data.get("cards") or None,
                options={},
            )
            payload, status = run_sync_job(job_id, "huggingface", data.get("cards") or None)
            return jsonify(payload), status

        # 获取分析器实例
        analyzer = get_analyzer()
        
        # 执行分析
        logger.info(f"Starting Hugging Face card analysis: {username}")

        result = analyzer.analyze_profile(username)
        
        if result is None:
            return jsonify({
                'code': 404,
                'message': f'Hugging Face profile not found or not accessible for: {username}'
            }), 404
        
        return jsonify({
            'code': 200,
            'message': 'Hugging Face card analysis completed successfully',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error in Hugging Face card analysis: {str(e)}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': 'Error occurred while analyzing profile, please try again later'
        }), 500

def _is_valid_username(username: str) -> bool:
    """
    验证Hugging Face用户名格式
    
    Args:
        username: 用户名
        
    Returns:
        是否为有效用户名
    """
    # Hugging Face用户名规则：字母、数字、连字符、下划线
    import re
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, username)) and len(username) <= 50

def _process_analysis_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理分析结果，确保数据格式正确

    Args:
        result: 原始分析结果

    Returns:
        处理后的卡片数据
    """
    try:
        # 基本信息
        username = result.get('username', '')
        basic_info = result.get('basic_info', {})

        # 核心数据 - 只显示存在的数据（大于0的）
        core_stats = result.get('core_stats', {})
        filtered_stats = {}

        for field in ['models', 'datasets', 'spaces', 'papers', 'discussions', 'upvotes', 'likes']:
            if core_stats.get(field, 0) > 0:
                filtered_stats[field] = core_stats[field]

        # 加入的组织 - 最多显示10个
        organizations = result.get('organizations', [])[:10]

        # 代表作
        representative_work = result.get('representative_work')

        # 构建返回数据
        card_data = {
            'username': username,
            'basic_info': basic_info,
            'core_stats': filtered_stats,
            'organizations': organizations
        }

        # 只有存在代表作时才添加
        if representative_work:
            card_data['representative_work'] = representative_work

        return card_data

    except Exception as e:
        logger.error(f"Error processing analysis result: {e}")
        # 返回基本结构
        return {
            'username': result.get('username', ''),
            'basic_info': {},
            'core_stats': {},
            'organizations': []
        }



@huggingface_analyzer_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'huggingface_analyzer',
        'message': 'Hugging Face analysis service is running normally'
    })
