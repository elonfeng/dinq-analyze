"""
Twitter Analyzer API

This module provides Flask API endpoints for analyzing Twitter/X user profiles.
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify
from server.utils.auth import require_verified_user
from server.utils.api_usage_tracker import track_api_call
from server.twitter_analyzer.analyzer import TwitterAnalyzer
from server.analyze.api import create_analysis_job, run_sync_job

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
twitter_analyzer_bp = Blueprint('twitter_analyzer', __name__, url_prefix='/api/twitter')

def get_analyzer() -> TwitterAnalyzer:
    """Get Twitter analyzer instance"""
    return TwitterAnalyzer()

@twitter_analyzer_bp.route('/card/analyze', methods=['POST'])
def analyze_twitter_card():
    """
    Twitter用户卡片分析接口
    
    返回用户的基本信息、核心数据、Top粉丝
    
    Request body:
    {
        "username": "twitter_username"
    }
    
    Returns:
    {
        "code": 200,
        "message": "Twitter card analysis completed successfully",
        "data": {
            "username": "username",
            "basic_info": {
                "display_name": "Display Name",
                "bio": "User bio...",
                "location": "Location",
                "website": "https://website.com",
                "join_date": "2020-01-01T00:00:00Z",
                "verified": true,
                "profile_image": "https://...",
                "banner_image": "https://..."
            },
            "core_stats": {
                "followers_count": 10000,
                "verified_followers_count": 50
            },
            "top_followers": [
                {
                    "username": "follower1",
                    "display_name": "Follower 1",
                    "followers_count": 50000,
                    "verified": true,
                    "profile_image": "https://...",
                    "bio": "Bio..."
                }
            ]
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
                source="twitter",
                input_payload={"username": username},
                requested_cards=data.get("cards") or None,
                options={},
            )
            payload, status = run_sync_job(job_id, "twitter", data.get("cards") or None)
            return jsonify(payload), status

        # 获取分析器实例
        analyzer = get_analyzer()
        
        # 执行分析
        logger.info(f"Starting Twitter card analysis: {username}")

        result = analyzer.analyze_profile(username)
        
        if result is None:
            return jsonify({
                'code': 404,
                'message': f'Twitter profile not found or not accessible for: {username}'
            }), 404
        
        return jsonify({
            'code': 200,
            'message': 'Twitter card analysis completed successfully',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error in Twitter card analysis: {str(e)}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': 'Error occurred while analyzing profile, please try again later'
        }), 500



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
        core_stats = result.get('core_stats', {})
        top_followers = result.get('top_followers', [])

        # 构建返回数据
        card_data = {
            'username': username,
            'basic_info': basic_info,
            'core_stats': core_stats,
            'top_followers': top_followers[:10]  # 确保最多10个
        }

        return card_data

    except Exception as e:
        logger.error(f"Error processing analysis result: {e}")
        # 返回基本结构
        return {
            'username': result.get('username', ''),
            'basic_info': {},
            'core_stats': {},
            'top_followers': []
        }
