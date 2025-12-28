"""
OpenReview Analyzer API

This module provides Flask API endpoints for analyzing OpenReview user profiles and papers.
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify, g
from server.utils.auth import require_verified_user
from server.utils.api_usage_tracker import track_api_call
from server.openreview_analyzer.analyzer import analyze_openreview_profile
from server.analyze.api import create_analysis_job, run_sync_job

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
openreview_analyzer_bp = Blueprint('openreview_analyzer', __name__, url_prefix='/api/openreview')

@openreview_analyzer_bp.route('/card/analyze', methods=['POST'])
def analyze_openreview_card():
    """
    OpenReview用户卡片分析接口

    分析OpenReview用户的学术信息，返回论文统计、代表作和AI评估

    Request body:
    {
        "query": "researcher_name_or_email"  // 研究者姓名或邮箱
    }

    Returns:
    {
        "code": 200,
        "message": "OpenReview card analysis completed successfully",
        "data": {
            "researcher": {
                "name": "Researcher Name",
                "email": "researcher@university.edu",
                "affiliation": "University Name",
                "research_fields": ["Machine Learning", "NLP"],
                "total_papers": 15,
                "total_citations": 500,
                "h_index": 8
            },
            "papers_summary": {
                "total_count": 15,
                "by_year": {
                    "2023": 5,
                    "2022": 7,
                    "2021": 3
                },
                "by_venue": {
                    "ICLR": 3,
                    "NeurIPS": 2,
                    "ICML": 1
                }
            },
            "representative_paper": {
                "title": "Paper Title",
                "abstract": "Paper abstract...",
                "authors": ["Author 1", "Author 2"],
                "venue": "ICLR 2023",
                "citations": 50,
                "ai_selection": {
                    "reason": "AI选择原因"
                }
            }
        }
    }
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'code': 400,
                'message': 'Missing query in request body'
            }), 400

        query = data['query'].strip()
        if not query:
            return jsonify({
                'code': 400,
                'message': 'Query cannot be empty'
            }), 400


        legacy_flag = data.get("legacy") or request.args.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")
        if not use_legacy:
            job_id, _created = create_analysis_job(
                user_id="anonymous",
                source="openreview",
                input_payload={"username": query, "email": query},
                requested_cards=data.get("cards") or None,
                options={},
            )
            payload, status = run_sync_job(job_id, "openreview", data.get("cards") or None)
            return jsonify(payload), status

        # 执行分析
        logger.info(f"Starting OpenReview card analysis: {query}")

        result = analyze_openreview_profile(query)

        if result is None:
            return jsonify({
                'code': 404,
                'message': f'OpenReview profile not found or not accessible for: {query}'
            }), 404


        logger.info(f"OpenReview card analysis for {query} completed")

        return jsonify({
            'code': 200,
            'message': 'OpenReview card analysis completed successfully',
            'data': result
        })

    except Exception as e:
        logger.error(f"Error in OpenReview card analysis: {str(e)}", exc_info=True)

        return jsonify({
            'code': 500,
            'message': 'Error occurred while analyzing profile, please try again later'
        }), 500
