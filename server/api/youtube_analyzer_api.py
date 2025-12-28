"""
YouTube Analysis API Module

Provides simple API endpoints for YouTube channel analysis.
"""

import os
import logging
from flask import Blueprint, request, jsonify

# Try to use DINQ project's trace logging system
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger(__name__)
except ImportError:
    # If cannot import, use standard logging
    logger = logging.getLogger(__name__)

# Import YouTube analyzer
from server.youtube_analyzer.analyzer import YouTubeAnalyzer

# Create blueprint
youtube_analyzer_bp = Blueprint('youtube_analyzer', __name__, url_prefix='/api/youtube')

# Global YouTube analyzer instance
youtube_analyzer = None

def get_youtube_analyzer() -> YouTubeAnalyzer:
    """获取YouTube分析器实例 - 参考LinkedIn的get_linkedin_analyzer"""
    global youtube_analyzer
    
    if youtube_analyzer is None:
        # Get configuration from environment variables or config file
        config = {
            "youtube": {
                "api_key": os.environ.get("YOUTUBE_API_KEY", "")
            }
        }
        
        # Try to get API key from DINQ config system
        try:
            from server.config.api_keys import API_KEYS
            if not config["youtube"]["api_key"]:
                config["youtube"]["api_key"] = API_KEYS.get('YOUTUBE_API_KEY', '')
        except ImportError:
            pass
        
        youtube_analyzer = YouTubeAnalyzer(config)
        logger.info("YouTube analyzer initialized")
    
    return youtube_analyzer

@youtube_analyzer_bp.route('/analyze', methods=['POST'])
def analyze_youtube_channel():
    """
    YouTube channel analysis API - simplified version
    """
    try:
        # 解析请求数据
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({
                'code': 400,
                'message': 'Missing content in request body'
            }), 400

        content = data['content'].strip()
        if not content:
            return jsonify({
                'code': 400,
                'message': 'Content cannot be empty'
            }), 400

        legacy_flag = data.get("legacy") or request.args.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")
        if not use_legacy:
            from server.analyze.api import create_analysis_job, run_sync_job
            job_id, _created = create_analysis_job(
                user_id="anonymous",
                source="youtube",
                input_payload={"channel_id": content, "channel": content},
                requested_cards=data.get("cards") or None,
                options={},
            )
            payload, status = run_sync_job(job_id, "youtube", data.get("cards") or None)
            return jsonify(payload), status

        logger.info(f"YouTube analysis request: {content}")

        # 获取分析器实例
        analyzer = get_youtube_analyzer()

        # 执行分析
        result = analyzer.get_result(channel_input=content)

        if not result:
            return jsonify({
                'code': 404,
                'message': f'YouTube channel not found or not accessible for: {content}'
            }), 404

        logger.info(f"YouTube analysis completed")

        return jsonify({
            'code': 200,
            'message': 'YouTube analysis completed successfully',
            'data': result
        })

    except Exception as e:
        logger.error(f"Error in YouTube analysis: {str(e)}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': 'Error occurred while analyzing profile, please try again later'
        }), 500





@youtube_analyzer_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'youtube_analyzer',
        'message': 'YouTube analysis service is running normally'
    })
