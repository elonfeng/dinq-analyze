"""
LinkedIn Analysis API Module

Provides API endpoints for LinkedIn profile analysis with streaming support.
"""

import os
import json
import asyncio
import logging
import threading
import queue
import csv
import time
import requests
from typing import Dict, Any, Optional, Callable, Generator
from flask import Blueprint, request, Response, jsonify, abort, g, stream_with_context
from werkzeug.exceptions import BadRequest

# Try to use DINQ project's trace logging system
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger(__name__)
except ImportError:
    # If cannot import, use standard logging
    logger = logging.getLogger(__name__)

from server.utils.auth import require_auth, require_verified_user
from server.utils.stream_protocol import create_error_event, create_event, format_stream_message
from server.utils.stream_task import run_streaming_task
from server.utils.streaming_task_builder import build_stream_task_fn, UsageLimitConfig
from server.analyze.api import create_analysis_job, stream_job_events, init_scheduler, run_sync_job

# Import LinkedIn analyzer
from server.linkedin_analyzer.analyzer import LinkedInAnalyzer

# Import API usage tracker
from server.utils.api_usage_tracker import track_api_call

# Create blueprint
linkedin_analyzer_bp = Blueprint('linkedin_analyzer', __name__, url_prefix='/api/linkedin')

def generate_linkedin_highlights(work_experience: list, education: list) -> Dict[str, Any]:
    """
    Generate AI summary of top 3 highlights from LinkedIn profile

    Args:
        work_experience: List of work experience entries
        education: List of education entries

    Returns:
        JSON with top 3 highlights (1 education + 2 work experiences)
    """
    try:
        from server.llm.gateway import openrouter_chat

        # Prepare simplified data for AI analysis (just for identification)
        work_data = []
        for i, work in enumerate(work_experience):
            work_info = {
                "index": i,
                "company": work.get("title", ""),
                "position": work.get("subtitle", ""),
                "duration": work.get("caption", ""),
                "description": ""
            }
            # Extract description from subComponents if available
            if work.get("subComponents"):
                for sub in work.get("subComponents", []):
                    if sub.get("description"):
                        for desc in sub.get("description", []):
                            if desc.get("text"):
                                work_info["description"] = desc.get("text", "")
                                break
            work_data.append(work_info)

        education_data = []
        for i, edu in enumerate(education):
            edu_info = {
                "index": i,
                "school": edu.get("title", ""),
                "degree": edu.get("subtitle", ""),
                "duration": edu.get("caption", ""),
                "description": ""
            }
            # Extract description from subComponents if available
            if edu.get("subComponents"):
                for sub in edu.get("subComponents", []):
                    if sub.get("description"):
                        for desc in sub.get("description", []):
                            if desc.get("text"):
                                edu_info["description"] = desc.get("text", "")
                                break
            education_data.append(edu_info)

        # Create prompt for AI analysis (only for identification)
        prompt = f"""
Analyze the following LinkedIn profile data and select the top 3 highlights:
- 1 most impressive education experience
- 2 most impressive work experiences

Work Experience:
{json.dumps(work_data, indent=2)}

Education:
{json.dumps(education_data, indent=2)}

Requirements:
1. Select exactly 1 education highlight and 2 work experience highlights
2. Focus on prestige, impact, and career significance
3. Return ONLY the indices in JSON format:

{{
    "selected_education_index": 0,
    "selected_work_indices": [0, 2]
}}

Focus on prestigious companies, universities, senior positions, and significant achievements.
Return only the indices of the selected items, not the full data.
"""

        from server.config.llm_models import get_model

        content = openrouter_chat(
            task="linkedin.highlights",
            model=get_model("fast", task="linkedin.highlights"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        if content:
            content = str(content).strip()

            # Extract JSON from response
            try:
                # Find JSON content between braces
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1

                if start_idx != -1 and end_idx > start_idx:
                    json_content = content[start_idx:end_idx]
                    indices_data = json.loads(json_content)

                    # Extract selected indices with validation
                    edu_index = indices_data.get('selected_education_index')
                    work_indices = indices_data.get('selected_work_indices', [])

                    # Validate and build highlights from original data using indices
                    highlights = []

                    # Add selected education (default to first/latest if invalid)
                    if edu_index is not None and 0 <= edu_index < len(education):
                        edu = education[edu_index]
                        highlights.append(extract_education_highlight(edu))
                    elif education:
                        # Default to first (latest) education
                        logger.warning(f"Invalid education index {edu_index}, using first education")
                        highlights.append(extract_education_highlight(education[0]))

                    # Add selected work experiences (default to first two if invalid)
                    valid_work_count = 0
                    if isinstance(work_indices, list) and work_indices:
                        for work_idx in work_indices[:2]:  # Ensure max 2 work experiences
                            if isinstance(work_idx, int) and 0 <= work_idx < len(work_experience):
                                work = work_experience[work_idx]
                                highlights.append(extract_work_highlight(work))
                                valid_work_count += 1

                    # Fill remaining work slots with latest entries if needed
                    if valid_work_count < 2:
                        logger.warning(f"Only got {valid_work_count} valid work indices, filling with latest entries")
                        for i in range(min(2 - valid_work_count, len(work_experience))):
                            if i < len(work_experience):
                                highlights.append(extract_work_highlight(work_experience[i]))

                    # Ensure we have at least some highlights
                    if not highlights:
                        logger.error("No valid highlights generated, using fallback")
                        return generate_fallback_highlights(work_experience, education)

                    return {"highlights": highlights}
                else:
                    logger.error("No valid JSON found in AI response")
                    return generate_fallback_highlights(work_experience, education)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response JSON: {e}")
                return generate_fallback_highlights(work_experience, education)
        logger.error("AI highlights generation failed: empty response")
        return generate_fallback_highlights(work_experience, education)

    except Exception as e:
        logger.error(f"Error generating LinkedIn highlights: {e}")
        return generate_fallback_highlights(work_experience, education)

def extract_education_highlight(edu: Dict[str, Any]) -> Dict[str, Any]:
    """Extract education highlight from LinkedIn education data structure"""
    # Extract description from subComponents
    description = ""
    if edu.get("subComponents"):
        for sub in edu.get("subComponents", []):
            if sub.get("description"):
                for desc in sub.get("description", []):
                    if desc.get("text"):
                        description = desc.get("text", "")
                        break

    return {
        "type": "education",
        "organization_name": edu.get("title", "University"),
        "organization_url": edu.get("companyLink1", "https://university.edu"),
        "organization_logo_url": edu.get("logo", ""),
        "position_degree": edu.get("subtitle", "Degree"),
        "time_duration": edu.get("caption", "Duration"),
        "field_major": description[:100] + "..." if len(description) > 100 else description
    }

def extract_work_highlight(work: Dict[str, Any]) -> Dict[str, Any]:
    """Extract work highlight from LinkedIn work experience data structure"""
    # Extract description from subComponents
    description = ""
    if work.get("subComponents"):
        for sub in work.get("subComponents", []):
            if sub.get("description"):
                for desc in sub.get("description", []):
                    if desc.get("text"):
                        description = desc.get("text", "")
                        break

    # Parse subtitle to extract company and position
    subtitle = work.get("subtitle", "")
    if " · " in subtitle:
        # Format: "Company · Full-time" or "Company · Part-time"
        company_part = subtitle.split(" · ")[0]
        position = work.get("title", "Position")
    else:
        # Fallback
        company_part = subtitle if subtitle else "Company"
        position = work.get("title", "Position")

    return {
        "type": "work",
        "organization_name": company_part,  # Company name from subtitle
        "organization_url": work.get("companyLink1", "https://company.com"),
        "organization_logo_url": work.get("logo", ""),
        "position_degree": position,  # Position from title
        "time_duration": work.get("caption", "Duration"),
        "field_major": description[:100] + "..." if len(description) > 100 else description
    }

def generate_fallback_highlights(work_experience: list, education: list) -> Dict[str, Any]:
    """
    Generate fallback highlights when AI processing fails - always use latest entries

    Args:
        work_experience: List of work experience entries
        education: List of education entries

    Returns:
        Fallback highlights structure with latest entries
    """
    highlights = []

    logger.info("Generating fallback highlights using latest entries")

    # Add latest education (first one in list is usually most recent)
    if education:
        highlights.append(extract_education_highlight(education[0]))
        logger.info(f"Added latest education: {education[0].get('title', 'Unknown')}")
    else:
        # Fallback education entry
        highlights.append({
            "type": "education",
            "organization_name": "University",
            "organization_url": "https://university.edu",
            "organization_logo_url": "",
            "position_degree": "Degree",
            "time_duration": "Duration",
            "field_major": "Field of Study"
        })
        logger.warning("No education data available, using placeholder")

    # Add latest 2 work experiences (first two in list are usually most recent)
    work_count = 0
    for work in work_experience[:2]:
        highlights.append(extract_work_highlight(work))
        logger.info(f"Added latest work #{work_count + 1}: {work.get('title', 'Unknown')}")
        work_count += 1

    # Fill remaining slots if needed
    while work_count < 2:
        highlights.append({
            "type": "work",
            "organization_name": "Company",
            "organization_url": "https://company.com",
            "organization_logo_url": "",
            "position_degree": "Position",
            "time_duration": "Duration",
            "field_major": "Professional Work"
        })
        logger.warning(f"Insufficient work data, using placeholder #{work_count + 1}")
        work_count += 1

    logger.info(f"Generated {len(highlights)} fallback highlights")
    return {"highlights": highlights}

def lookup_linkedin_url_from_csv(name: str) -> Optional[str]:
    """
    从linkedin.csv文件中查找对应的LinkedIn URL

    Args:
        name: 要查找的姓名

    Returns:
        对应的LinkedIn URL，如果未找到则返回None
    """
    try:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'linkedin_analyzer', 'linkedin.csv')
        if not os.path.exists(csv_path):
            logger.warning(f"LinkedIn CSV file not found: {csv_path}")
            return None

        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # 检查name字段是否匹配（不区分大小写）
                if row.get('Name', '').lower().strip() == name.lower().strip():
                    linkedin_url = row.get('linkedin', '').strip()
                    if linkedin_url:
                        logger.info(f"Found LinkedIn URL for {name}: {linkedin_url}")
                        return linkedin_url

        logger.info(f"No LinkedIn URL found for {name} in CSV")
        return None

    except Exception as e:
        logger.error(f"Error reading LinkedIn CSV file: {e}")
        return None

# Global LinkedIn analyzer instance
linkedin_analyzer = None

def get_linkedin_analyzer() -> LinkedInAnalyzer:
    """Get LinkedIn analyzer instance"""
    global linkedin_analyzer
    
    if linkedin_analyzer is None:
        # Get configuration from environment variables or config file
        config = {
            "tavily": {
                "api_key": os.environ.get("TAVILY_API_KEY", "")
            },
            "scrapingdog": {
                "api_key": os.environ.get("SCRAPINGDOG_API_KEY", "6879d42f3014d358eedfdcec")
            },
            "use_cache": True,
            "cache_max_age_days": 7
        }
        
        linkedin_analyzer = LinkedInAnalyzer(config)
        logger.info("LinkedIn analyzer initialized")
    
    return linkedin_analyzer

def send_status(step: str, message: str, callback: Callable = None, progress: float = None):
    """Send status update"""
    if callback:
        try:
            callback(step, message, progress)
        except Exception as e:
            logger.warning(f"Status callback failed: {e}")

@linkedin_analyzer_bp.route('/analyze', methods=['POST', 'OPTIONS'])
@require_verified_user
def analyze_linkedin_profile():
    """
    LinkedIn profile analysis API with streaming response
    
    Request body:
    {
        "content": "Name to analyze or LinkedIn URL"
    }
    
    Returns:
    Streaming response with analysis progress and results
    """
    if request.method == 'OPTIONS':
        return Response(status=200)
    
    try:
        user_id = g.user_id
        trace_id = getattr(g, 'trace_id', None)
        
        # Parse request data
        data = request.get_json()
        if not data:
            abort(400, description="Request body cannot be empty")

        # Get LinkedIn analyzer
        analyzer = get_linkedin_analyzer()
        linkedinId = data.get('linkedin_id')
        legacy_flag = data.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")


        content = data.get('content')
        if linkedinId:
            content = linkedinId

        if not content:
            abort(400, description="content parameter is required")

        # 检查content是否在linkedin.csv中，如果是则替换为对应的LinkedIn URL
        if 'linkedin.com/in/' not in content:
            # content不是LinkedIn URL，尝试从CSV中查找
            csv_linkedin_url = lookup_linkedin_url_from_csv(content)
            if csv_linkedin_url:
                logger.info(f"Replacing content '{content}' with LinkedIn URL from CSV: {csv_linkedin_url}")
                content = csv_linkedin_url

        # Determine if content is LinkedIn URL or person name
        if 'linkedin.com/in/' in content:
            # Content is a LinkedIn URL
            linkedin_url = content
            person_name = None  # Will be extracted from profile data
            logger.info(f"Content is LinkedIn URL: {linkedin_url}")
        else:
            # Content is a person name
            person_name = content
            linkedin_url = None
            logger.info(f"Content is person name: {person_name}")
        
        usage_config = UsageLimitConfig(
            endpoints=[
                '/api/stream',
                '/api/scholar-pk',
                '/api/github/analyze',
                '/api/github/compare',
                '/api/linkedin/analyze',
                '/api/linkedin/compare',
            ],
            limit=5,
            days=30,
        )

        if not use_legacy:
            is_allowed, limit_info = usage_limiter.check_monthly_limit(
                user_id=user_id,
                endpoints=list(usage_config.endpoints),
                limit=usage_config.limit,
                days=usage_config.days,
            )
            if not is_allowed:
                return Response(
                    format_stream_message(
                        create_error_event(
                            source="linkedin",
                            code="usage_limit",
                            message="Monthly usage limit exceeded",
                            retryable=False,
                            detail=limit_info,
                            step="usage_check",
                        )
                    ),
                    mimetype='text/event-stream',
                )

            init_scheduler()
            job_id, _created = create_analysis_job(
                user_id=user_id or "anonymous",
                source="linkedin",
                input_payload={"content": content, "linkedin_id": linkedinId} if content else {"linkedin_id": linkedinId},
                requested_cards=None,
                options={"legacy": False},
            )

            def generate():
                return stream_job_events(job_id=job_id, after_seq=0)

            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
            )

        def start_message() -> str:
            if person_name:
                return f"Starting LinkedIn analysis for {person_name}"
            return f"Starting LinkedIn analysis for URL: {linkedin_url}"

        analyzer_holder: Dict[str, Any] = {"analyzer": analyzer}

        def cache_lookup(ctx):
            if not linkedinId:
                return None
            ctx.progress("cache_lookup", "Loading cached result...")
            return analyzer_holder["analyzer"].get_cached_result(linkedinId)

        def cache_hit_payload_builder(cached: Any, limit_info: Dict[str, Any]) -> Dict[str, Any]:
            return {"data": cached, "from_cache": True, "usage_info": limit_info}

        def work(ctx, _limit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            def progress_callback(step: str, message: str, data=None):
                ctx.progress(step, message, payload=data if isinstance(data, dict) else None)

            if person_name:
                result = analyzer_holder["analyzer"].get_result_with_progress(
                    person_name,
                    progress_callback,
                    linkedin_url,
                    cancel_event=ctx.cancel_event,
                )
            else:
                if "linkedin.com/in/" in linkedin_url:
                    linkedin_username = (
                        linkedin_url.split("linkedin.com/in/")[1]
                        .split("?")[0]
                        .split("/")[0]
                    )
                    result = analyzer_holder["analyzer"].get_result_with_progress(
                        linkedin_username,
                        progress_callback,
                        linkedin_url,
                        cancel_event=ctx.cancel_event,
                    )
                else:
                    result = analyzer_holder["analyzer"].get_result_with_progress(
                        "Unknown",
                        progress_callback,
                        linkedin_url,
                        cancel_event=ctx.cancel_event,
                    )

            if not result:
                raise ValueError("LinkedIn profile not found or analysis failed")
            return {"data": result, "from_cache": bool(result.get("_from_cache"))}

        def on_success(_payload: Dict[str, Any]) -> None:
            track_api_call(
                endpoint="/api/linkedin/analyze",
                query=content,
                query_type="person_name",
                status="success",
                user_id=user_id,
            )

        def on_error(error_message: str) -> None:
            track_api_call(
                endpoint="/api/linkedin/analyze",
                query=content,
                query_type="person_name",
                status="error",
                error_message=error_message,
                user_id=user_id,
            )

        task_fn = build_stream_task_fn(
            source="linkedin",
            trace_id=trace_id,
            usage_limiter=usage_limiter,
            usage_config=usage_config,
            user_id=user_id,
            start_message=start_message(),
            start_payload={"person_name": person_name, "linkedin_url": linkedin_url},
            cache_lookup=cache_lookup,
            cache_hit_payload_builder=cache_hit_payload_builder,
            work=work,
            on_success=on_success,
            on_error=on_error,
        )

        def result_event_builder(result_type: str, payload: Any):
            if result_type == "success":
                return create_event(
                    source="linkedin",
                    event_type="final",
                    message="LinkedIn analysis completed",
                    payload=payload if isinstance(payload, dict) else {"result": payload},
                    legacy_type="success",
                )
            message = str(payload)
            lowered = message.lower()
            code = "internal_error"
            retryable = False
            if "limit" in lowered and "exceed" in lowered:
                code = "usage_limit"
            if "cancel" in lowered:
                code = "cancelled"
                retryable = True
            return create_error_event(
                source="linkedin",
                code=code,
                message=message,
                retryable=retryable,
                detail={"person_name": person_name, "linkedin_url": linkedin_url},
                step="analyze_error",
            )

        return Response(
            run_streaming_task(
                source="linkedin",
                task_fn=task_fn,
                timeout_seconds=300,
                keepalive_seconds=15,
                result_event_builder=result_event_builder,
            ),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
            },
        )
        
    except Exception as e:
        logger.error(f"LinkedIn analysis API error: {e}")
        return jsonify({'error': str(e)}), 500

@linkedin_analyzer_bp.route('/analyze-sync', methods=['POST', 'OPTIONS'])
@require_verified_user
def analyze_linkedin_profile_sync():
    """
    LinkedIn profile analysis API (synchronous version)
    
    Request body:
    {
        "content": "Name to analyze or LinkedIn URL"
    }
    
    Returns:
    JSON response with analysis results
    """
    if request.method == 'OPTIONS':
        return Response(status=200)
    
    try:
        # 获取用户ID
        user_id = request.headers.get('Userid')
        if not user_id:
            return jsonify({"error": "User ID is required"}), 401
        
        # 检查用户是否超过了使用限制（30天内最多5次）
        from server.utils.usage_limiter import UsageLimiter
        usage_limiter = UsageLimiter()
        
        is_allowed, limit_info = usage_limiter.check_monthly_limit(
            user_id=user_id,
            endpoints=['/api/stream', '/api/scholar-pk', '/api/github/analyze', '/api/github/compare', '/api/linkedin/analyze', '/api/linkedin/compare'],
            limit=5,
            days=30
        )

        # 如果用户超过了使用限制，返回错误
        if not is_allowed:
            logger.warning(f"User {user_id} has exceeded their monthly limit for LinkedIn analysis API")
            return jsonify(usage_limiter.get_limit_response(limit_info)), 429  # 429 Too Many Requests
        
        # Parse request data
        data = request.get_json()
        if not data:
            abort(400, description="Request body cannot be empty")

        content = data.get('content')
        if not content:
            abort(400, description="content parameter is required")

        legacy_flag = data.get("legacy") or request.args.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")
        if not use_legacy:
            job_id, _created = create_analysis_job(
                user_id=user_id,
                source="linkedin",
                input_payload={"content": content},
                requested_cards=data.get("cards") or None,
                options={},
            )
            payload, status = run_sync_job(job_id, "linkedin", data.get("cards") or None)
            return jsonify(payload), status

        # 检查content是否在linkedin.csv中，如果是则替换为对应的LinkedIn URL
        if 'linkedin.com/in/' not in content:
            # content不是LinkedIn URL，尝试从CSV中查找
            csv_linkedin_url = lookup_linkedin_url_from_csv(content)
            if csv_linkedin_url:
                logger.info(f"Replacing content '{content}' with LinkedIn URL from CSV: {csv_linkedin_url}")
                content = csv_linkedin_url

        # Determine if content is LinkedIn URL or person name
        if 'linkedin.com/in/' in content:
            # Content is a LinkedIn URL
            linkedin_url = content
            # Extract person name from LinkedIn URL
            person_name = content.split('/')[-1].replace('-', ' ').title()
            logger.info(f"Content is LinkedIn URL: {linkedin_url}, extracted name: {person_name}")
        else:
            # Content is a person name
            person_name = content
            linkedin_url = None
            logger.info(f"Content is person name: {person_name}")
        
        # Get LinkedIn analyzer
        analyzer = get_linkedin_analyzer()
        
        # Execute synchronous analysis
        if person_name:
            # Use person name for analysis
            result = analyzer.get_result(person_name, linkedin_url)
        else:
            # Use LinkedIn URL directly, need to extract person name first
            # Get profile data first to extract person name
            profile_data = analyzer.get_linkedin_profile(linkedin_url)
            if profile_data:
                # Extract person name from profile data
                extracted_name = profile_data.get('fullName') or profile_data.get('firstName', '') + ' ' + profile_data.get('lastName', '')
                if extracted_name.strip():
                    extracted_person_name = extracted_name.strip()
                    result = analyzer.get_result(extracted_person_name, linkedin_url)
                else:
                    # Fallback to using URL as identifier
                    result = analyzer.get_result("Unknown", linkedin_url)
            else:
                result = None
        
        if result:
            return jsonify({
                'success': True,
                'message': 'LinkedIn analysis completed',
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'LinkedIn profile not found or analysis failed',
                'data': None
            }), 404

    except Exception as e:
        logger.error(f"LinkedIn analysis API error: {e}")
        return jsonify({'error': str(e)}), 500


@linkedin_analyzer_bp.route('/cache/stats', methods=['GET'])
@require_verified_user
def get_cache_stats():
    """
    Get LinkedIn cache statistics
    
    Returns:
    {
        "total_records": 10,
        "recent_records_24h": 5,
        "oldest_record_date": "2024-01-01T00:00:00",
        "newest_record_date": "2024-01-10T00:00:00"
    }
    """
    try:
        from src.utils.linkedin_cache import get_linkedin_cache_stats
        
        stats = get_linkedin_cache_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Cache stats API error: {e}")
        return jsonify({'error': str(e)}), 500

@linkedin_analyzer_bp.route('/cache/clear', methods=['POST', 'OPTIONS'])
def clear_cache():
    """
    Clear LinkedIn cache
    
    Request body (optional):
    {
        "linkedin_id": "Specific LinkedIn ID to clear"
    }
    
    Returns:
    {
        "success": true,
        "message": "Cache cleared successfully"
    }
    """
    if request.method == 'OPTIONS':
        return Response(status=200)
    
    try:
        from src.utils.linkedin_cache import clear_linkedin_cache
        
        data = request.get_json() or {}
        linkedin_id = data.get('linkedin_id')
        
        success = clear_linkedin_cache(linkedin_id)
        
        if success:
            message = f"Cache cleared for {linkedin_id}" if linkedin_id else "All cache cleared"
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to clear cache'
            }), 500
        
    except Exception as e:
        logger.error(f"Cache clear API error: {e}")
        return jsonify({'error': str(e)}), 500

@linkedin_analyzer_bp.route('/compare', methods=['POST'])
@require_verified_user
def linkedin_pk_compare_stream():
    """
    LinkedIn PK comparison API

    Request body:
    {
        "person1": "Name 1 or LinkedIn URL 1",
        "person2": "Name 2 or LinkedIn URL 2"
    }

    Returns:
    JSON response with PK comparison results including 5 dimensions and roast
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        person1 = data.get('content1')
        person2 = data.get('content2')
        linkedinId1 = data.get('linkedin_id1')
        linkedinId2 = data.get('linkedin_id2')
        if linkedinId1:
            person1 = linkedinId1
        if linkedinId2:
            person2 = linkedinId2

        if not person1 or not person2:
            return jsonify({
                'success': False,
                'error': 'Both person1 and person2 are required'
            }), 400

        # 获取用户ID（优先使用鉴权写入的 g.user_id，兼容旧的 Userid header）
        user_id = getattr(g, 'user_id', None) or request.headers.get('Userid')
        logger.info("LinkedIn PK stream request - user: %s", user_id)

        # Get LinkedIn analyzer instance
        analyzer = get_linkedin_analyzer()

        # Process person1 input
        person1_name = None
        linkedin_url1 = None
        if 'linkedin.com/in/' in person1:
            linkedin_url1 = person1
        else:
            person1_name = person1
            # Check CSV for LinkedIn URL
            csv_linkedin_url = lookup_linkedin_url_from_csv(person1)
            if csv_linkedin_url:
                linkedin_url1 = csv_linkedin_url
                logger.info(f"Found LinkedIn URL for {person1} in CSV: {csv_linkedin_url}")

        # Process person2 input
        person2_name = None
        linkedin_url2 = None
        if 'linkedin.com/in/' in person2:
            linkedin_url2 = person2
        else:
            person2_name = person2
            # Check CSV for LinkedIn URL
            csv_linkedin_url = lookup_linkedin_url_from_csv(person2)
            if csv_linkedin_url:
                linkedin_url2 = csv_linkedin_url
                logger.info(f"Found LinkedIn URL for {person2} in CSV: {csv_linkedin_url}")

        # Get LinkedIn analyzer instance
        analyzer = get_linkedin_analyzer()

        # 获取LinkedIn ID用于缓存检查
        def get_linkedin_id(person_input, linkedin_url, linkedin_id_param):
            """获取LinkedIn ID，优先级：参数 > URL解析 > 姓名搜索"""
            if linkedin_id_param:
                # 如果直接提供了LinkedIn ID，直接使用
                return linkedin_id_param
            elif linkedin_url and "linkedin.com/in/" in linkedin_url:
                # 从URL中解析LinkedIn ID
                return linkedin_url.split("linkedin.com/in/")[1].split("?")[0].split("/")[0]
            else:
                # 通过姓名搜索获取LinkedIn URL，然后解析ID
                try:
                    linkedin_results = analyzer.search_linkedin_url(person_input)
                    if linkedin_results and len(linkedin_results) > 0:
                        found_url = linkedin_results[0]['url']
                        if "linkedin.com/in/" in found_url:
                            return found_url.split("linkedin.com/in/")[1].split("?")[0].split("/")[0]
                except Exception as e:
                    logger.error(f"Error searching LinkedIn URL for {person_input}: {e}")
                return None

        # 获取两个人的LinkedIn ID
        person1_linkedin_id = get_linkedin_id(person1, linkedin_url1, linkedinId1)
        person2_linkedin_id = get_linkedin_id(person2, linkedin_url2, linkedinId2)

        if not person1_linkedin_id or not person2_linkedin_id:
            return jsonify({
                'success': False,
                'error': 'Unable to determine LinkedIn IDs for both persons'
            }), 400

        usage_config = UsageLimitConfig(
            endpoints=[
                '/api/stream',
                '/api/scholar-pk',
                '/api/github/analyze',
                '/api/github/compare',
                '/api/linkedin/analyze',
                '/api/linkedin/compare',
            ],
            limit=5,
            days=30,
        )

        def cache_lookup(_ctx):
            return analyzer.get_cached_pk_result(person1_linkedin_id, person2_linkedin_id)

        def cache_hit_payload_builder(cached: Any, limit_info: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "success": True,
                "data": cached,
                "from_cache": True,
                "usage_info": limit_info,
            }

        def work(ctx, limit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            def progress_callback(step: str, message: str, data=None):
                ctx.progress(step, message, payload=data if isinstance(data, dict) else None)

            progress_callback("user1_start", f"Analyzing {person1_linkedin_id}...")
            result1 = analyzer.get_result_with_progress(
                person1_linkedin_id,
                progress_callback,
                linkedin_url1,
                cancel_event=ctx.cancel_event,
            )
            if not result1:
                raise ValueError(f"Failed to get analysis result for {person1_linkedin_id}")
            progress_callback("user1_completed", f"{person1_linkedin_id} analysis completed")

            progress_callback("user2_start", f"Analyzing {person2_linkedin_id}...")
            result2 = analyzer.get_result_with_progress(
                person2_linkedin_id,
                progress_callback,
                linkedin_url2,
                cancel_event=ctx.cancel_event,
            )
            if not result2:
                raise ValueError(f"Failed to get analysis result for {person2_linkedin_id}")
            progress_callback("user2_completed", f"{person2_linkedin_id} analysis completed")

            progress_callback("generating_pk", "Generating PK comparison result...")
            pk_result = analyzer.transform_linkedin_pk_result(
                person1_linkedin_id,
                person2_linkedin_id,
                result1,
                result2,
            )

            report_urls = None
            if pk_result:
                try:
                    report_urls = analyzer.save_pk_report(pk_result)
                    progress_callback("cache_saved", "Result saved to cache")
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to save LinkedIn PK report: %s", exc)

            return {
                "success": True,
                "data": pk_result,
                "report_urls": report_urls,
                "from_cache": False,
                "usage_info": limit_info or {},
            }

        def on_success(_payload: Dict[str, Any]) -> None:
            track_api_call(
                endpoint="/api/linkedin/compare",
                query=f"{person1_linkedin_id} vs {person2_linkedin_id}",
                query_type="linkedin_pk",
                status="success",
                user_id=user_id,
            )

        def on_error(error_message: str) -> None:
            track_api_call(
                endpoint="/api/linkedin/compare",
                query=f"{person1_linkedin_id} vs {person2_linkedin_id}",
                query_type="linkedin_pk",
                status="error",
                error_message=error_message,
                user_id=user_id,
            )

        task_fn = build_stream_task_fn(
            source="linkedin",
            trace_id=getattr(g, 'trace_id', None),
            usage_limiter=usage_limiter,
            usage_config=usage_config,
            user_id=user_id,
            start_message=f"Starting LinkedIn PK analysis: {person1_linkedin_id} vs {person2_linkedin_id}",
            start_payload={
                "person1": person1_linkedin_id,
                "person2": person2_linkedin_id,
                "linkedin_url1": linkedin_url1,
                "linkedin_url2": linkedin_url2,
            },
            cache_lookup=cache_lookup,
            cache_hit_payload_builder=cache_hit_payload_builder,
            work=work,
            on_success=on_success,
            on_error=on_error,
        )

        def result_event_builder(result_type: str, payload: Any):
            if result_type == "success":
                return create_event(
                    source="linkedin",
                    event_type="final",
                    message="LinkedIn PK analysis completed",
                    payload=payload if isinstance(payload, dict) else {"result": payload},
                    legacy_type="completed",
                )

            detail: Any = None
            message = str(payload)
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("error") or "LinkedIn PK analysis failed")
                detail = payload

            lowered = message.lower()
            code = "internal_error"
            retryable = False
            if "limit" in lowered and "exceed" in lowered:
                code = "usage_limit"
            if "cancel" in lowered:
                code = "cancelled"
                retryable = True

            return create_error_event(
                source="linkedin",
                code=code,
                message=message,
                retryable=retryable,
                detail={
                    "person1": person1_linkedin_id,
                    "person2": person2_linkedin_id,
                    "upstream": detail,
                },
                step="compare_error",
            )

        return Response(
            run_streaming_task(
                source="linkedin",
                task_fn=task_fn,
                timeout_seconds=300,
                keepalive_seconds=15,
                result_event_builder=result_event_builder,
            ),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
            },
        )

    except Exception as e:
        logger.error(f"LinkedIn PK API error: {e}")

        # Track failed API usage
        track_api_call(
            endpoint="/api/linkedin/compare",
            query="unknown",
            query_type="linkedin_pk",
            status="error",
            error_message=str(e),
            user_id=getattr(g, 'user_id', None)
        )

        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@linkedin_analyzer_bp.route('/compare', methods=['GET'])
def linkedin_pk_get_cached():
    """
    Get cached LinkedIn PK comparison result

    Query parameters:
    - person1: Name 1 or LinkedIn URL 1
    - person2: Name 2 or LinkedIn URL 2

    Returns:
    Cached PK comparison result if available, otherwise 404
    """
    try:
        person1 = request.args.get('person1')
        person2 = request.args.get('person2')

        if not person1 or not person2:
            return jsonify({
                'success': False,
                'error': 'Both person1 and person2 parameters are required'
            }), 400

        # Get LinkedIn analyzer instance
        analyzer = get_linkedin_analyzer()

        # Process person inputs to get cache keys
        person1_key = person1
        person2_key = person2

        # Check CSV for LinkedIn URLs if needed
        if 'linkedin.com/in/' not in person1:
            csv_linkedin_url = lookup_linkedin_url_from_csv(person1)
            if csv_linkedin_url:
                person1_key = csv_linkedin_url

        if 'linkedin.com/in/' not in person2:
            csv_linkedin_url = lookup_linkedin_url_from_csv(person2)
            if csv_linkedin_url:
                person2_key = csv_linkedin_url

        # Try to get cached PK result directly
        person1_name = person1.split('/')[-1] if 'linkedin.com/in/' in person1 else person1
        person2_name = person2.split('/')[-1] if 'linkedin.com/in/' in person2 else person2

        cached_pk_result = analyzer.get_cached_pk_result(person1_name, person2_name)

        if cached_pk_result:
            return jsonify({
                'success': True,
                'message': 'Cached LinkedIn PK result found',
                'data': cached_pk_result,
                'cached': True
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No cached result found',
                'data': None,
                'cached': False
            }), 404

    except Exception as e:
        logger.error(f"LinkedIn PK cache retrieval error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@linkedin_analyzer_bp.route('/analyze', methods=['GET'])
def linkedin_analyze_get_cached():
    """
    Get cached LinkedIn analysis result

    Query parameters:
    - content: Person name or LinkedIn URL

    Returns:
    Cached analysis result if available, otherwise 404
    """
    try:
        content = request.args.get('content')

        if not content:
            return jsonify({
                'success': False,
                'error': 'content parameter is required'
            }), 400

        # 检查content是否在linkedin.csv中，如果是则替换为对应的LinkedIn URL
        if 'linkedin.com/in/' not in content:
            # content不是LinkedIn URL，尝试从CSV中查找
            csv_linkedin_url = lookup_linkedin_url_from_csv(content)
            if csv_linkedin_url:
                logger.info(f"Replacing content '{content}' with LinkedIn URL from CSV: {csv_linkedin_url}")
                content = csv_linkedin_url
                content = content.split('/')[-1]

                # Get LinkedIn analyzer instance
        analyzer = get_linkedin_analyzer()

        # Try to get cached result
        cached_result = analyzer.get_cached_result(content)

        if cached_result:
            return jsonify({
                'success': True,
                'message': 'Cached LinkedIn analysis result found',
                'data': cached_result,
                'cached': True
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No cached result found',
                'data': None,
                'cached': False
            }), 404

    except Exception as e:
        logger.error(f"LinkedIn analysis cache retrieval error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@linkedin_analyzer_bp.route('/card/analyze', methods=['POST'])
def analyze_linkedin_card():
    """
    LinkedIn用户卡片分析接口

    返回完整的LinkedIn分析结果，不进行字段摘取和AI摘要

    Request body:
    {
        "content": "Name to analyze or LinkedIn URL"
    }

    Returns:
    {
        "code": 200,
        "message": "LinkedIn card analysis completed successfully",
        "data": {
            // 完整的LinkedIn分析结果
        }
    }
    """
    try:
        # 获取请求数据
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

        # 获取分析器实例
        analyzer = get_linkedin_analyzer()

        # 执行分析
        logger.info(f"Starting LinkedIn card analysis: {content}")
        result = analyzer.get_result(content)

        if result is None:
            return jsonify({
                'code': 404,
                'message': f'LinkedIn profile not found or not accessible for: {content}'
            }), 404

        # 提取工作经历和教育经历进行AI处理
        work_experience = result.get("profile_data").get('work_experience', [])
        education = result.get("profile_data").get('education', [])

        # 生成AI高光履历总结
        highlights = generate_linkedin_highlights(work_experience, education)



        logger.info(f"LinkedIn card analysis for {content} completed with AI highlights")

        return jsonify({
            'code': 200,
            'message': 'LinkedIn card analysis completed successfully',
            'data': highlights
        })

    except Exception as e:
        logger.error(f"Error in LinkedIn card analysis: {str(e)}", exc_info=True)

        return jsonify({
            'code': 500,
            'message': 'Error occurred while analyzing profile, please try again later'
        }), 500


@linkedin_analyzer_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'linkedin_analyzer',
        'message': 'LinkedIn analysis service is running normally'
    })
