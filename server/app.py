"""
Scholar Demo Server Application

This module provides the main server application for the Scholar Demo.
It integrates all the server components and handles HTTP requests using Flask.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, Callable, Generator
from flask import Flask, Response, request, send_from_directory, jsonify, abort, g
from werkzeug.exceptions import NotFound, BadRequest

# Import and load environment variables
from server.config.env_loader import load_environment_variables
# Load environment variables before any other imports that might use them
load_environment_variables()

# Import logging configuration
from server.utils.logging_config import setup_logging

# Configure logging
logger = setup_logging()
logger = logging.getLogger(__name__)
# Initialize Sentry for error monitoring
from server.utils.sentry_config import init_sentry

# Initialize Sentry with environment variables
# SENTRY_DSN should be set in the environment or .env file
sentry_initialized = init_sentry(
    environment=os.environ.get('FLASK_ENV', 'development'),
    traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
    profiles_sample_rate=float(os.environ.get('SENTRY_PROFILES_SAMPLE_RATE', '0.1')),
    send_default_pii=os.environ.get('SENTRY_SEND_DEFAULT_PII', 'False').lower() == 'true'
)
if sentry_initialized:
    logger.info("Sentry monitoring initialized successfully")
else:
    logger.warning("Sentry monitoring not initialized. Set SENTRY_DSN in environment to enable.")

# Import API modules
from server.api.researcher_data import get_researcher_data
from server.api.sub_html_handler import serve_sub_html_file
from server.api.reports_handler import serve_report_file
from server.api.images_handler import serve_image_file
from server.api.talents_handler import get_top_talents
from server.api.linkedin_talents_handler import get_top_linkedin_talents
from server.api.scholar_pk.pk_handler import build_pk_task_fn
from server.api.sentry_handler import sentry_bp, configure_sentry_handler
from src.utils.scholar_repository import get_scholar_name
# Import Job Board API
from server.api.job_board import job_board_bp
from server.api.job_board.user_interactions_api import job_board_interactions_bp

# Import Demo Request API
from server.api.demo_request_api import demo_request_bp
from server.api.demo_form_api import demo_form_bp

# Import Scholar Name API
from server.api.scholar.name_scholar_api import name_scholar_bp

# Import Scholar Sync API
from server.api.scholar.scholar_api import scholar_sync_bp

# Import API Usage API
from server.api.usage_api import usage_api_bp

# Import Activation Code API
from server.api.activation_code_api import activation_code_bp

# Import User API
from server.api.user_api import user_bp

# Import Waiting List API
from server.api.waiting_list_api import waiting_list_bp

# Import Image Upload API
from server.api.image_upload_api import image_upload_bp

# Import User Verification API
from server.api.user_verification_api import user_verification_bp
from server.api.email_verification_page import email_verification_page_bp

# Import GitHub Analyzer API
from server.api.github_analyzer_api import github_analyzer_bp

# Import LinkedIn Analyzer API
from server.api.linkedin_analyzer_api import linkedin_analyzer_bp

# Import Hugging Face Analyzer API
from server.api.huggingface_analyzer_api import huggingface_analyzer_bp

# Import YouTube Analyzer API
from server.api.youtube_analyzer_api import youtube_analyzer_bp

# Import Twitter Analyzer API
from server.api.twitter_analyzer_api import twitter_analyzer_bp
from server.api.openreview_analyzer_api import openreview_analyzer_bp

# Import Talent Move API
from server.api.talent_move_api import talent_move_bp, init_app as init_talent_move_app

# Import authentication utilities
from server.utils.auth import require_auth, require_verified_user

# Import API usage limiter
from server.utils.usage_limiter import usage_limiter

from server.utils.stream_protocol import create_event, create_error_event
from server.utils.stream_task import run_streaming_task

# Import trace context for request tracking
from server.utils.trace_context import TraceContext, get_trace_logger

# Import API blueprints
from server.api.auth_api import auth_bp
from server.api.scholar.stream_processor import build_scholar_task_fn

from server.api.article_api import article_bp

from server.api.author_api import author_bp

# Unified analysis API
from server.analyze.api import analyze_bp
# Create Flask application
app = Flask(__name__)

# Simple health endpoint (used by CI/smoke tests and local readiness checks).
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

# Register blueprints
app.register_blueprint(sentry_bp)
app.register_blueprint(job_board_bp)
app.register_blueprint(job_board_interactions_bp)
app.register_blueprint(demo_request_bp)
app.register_blueprint(demo_form_bp)
app.register_blueprint(name_scholar_bp)
app.register_blueprint(scholar_sync_bp)
app.register_blueprint(usage_api_bp)
app.register_blueprint(activation_code_bp)
app.register_blueprint(user_bp)
app.register_blueprint(waiting_list_bp)
app.register_blueprint(image_upload_bp)
app.register_blueprint(user_verification_bp)
app.register_blueprint(email_verification_page_bp)
app.register_blueprint(github_analyzer_bp)
app.register_blueprint(linkedin_analyzer_bp)
app.register_blueprint(huggingface_analyzer_bp)
app.register_blueprint(youtube_analyzer_bp)
app.register_blueprint(twitter_analyzer_bp)
app.register_blueprint(openreview_analyzer_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(article_bp)
app.register_blueprint(author_bp)
app.register_blueprint(talent_move_bp)
app.register_blueprint(analyze_bp)
# Configure Sentry handler with initialization status
configure_sentry_handler(sentry_initialized)

# Local-first analysis: replicate cache artifacts to remote backup DB asynchronously (best-effort).
try:
    from server.tasks.backup_replicator import start_backup_replicator

    start_backup_replicator()
except Exception:
    pass

# Local-first analysis: keep local SQLite cache bounded (best-effort).
try:
    from server.tasks.local_cache_eviction import start_local_cache_evictor

    start_local_cache_evictor()
except Exception:
    pass

# Store active sessions
active_sessions: Dict[str, Dict[str, Any]] = {}

# Default static directory path
DEFAULT_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'frontend', 'out'
)

# Configure static directory
static_dir = DEFAULT_STATIC_DIR

# Frontend routes that should return index.html
frontend_routes = ['chat', 'about', 'network', 'chart-test']


def configure_app(static_directory: str = None) -> None:
    """
    Configure the Flask application.

    Args:
        static_directory: Directory containing static files (Next.js build output)
    """
    global static_dir

    if static_directory:
        static_dir = static_directory

    # Ensure the static directory exists
    if not os.path.exists(static_dir):
        logger.warning(f"Static directory not found at {static_dir}")
    else:
        logger.info(f"Using static files from {static_dir}")


@app.before_request
def setup_request_tracing():
    """
    Set up request tracing for each HTTP request.

    This function runs before each request and:
    1. Generates a unique trace ID for the request
    2. Sets up the trace context
    3. Logs the start of the request
    """
    # Generate or extract trace ID
    trace_id = request.headers.get('X-Trace-ID')
    if not trace_id:
        trace_id = TraceContext.generate_trace_id()

    # Set trace ID in context
    TraceContext.set_trace_id(trace_id)

    # Store trace ID in Flask's g object for easy access
    g.trace_id = trace_id

    # Get trace-aware logger
    trace_logger = get_trace_logger(__name__)

    # Log request start (only for non-static requests)
    if not request.path.startswith('/static') and not request.path.endswith(('.css', '.js', '.png', '.jpg', '.ico', '.svg')):
        trace_logger.info(f"Request started: {request.method} {request.path}")


@app.after_request
def add_cors_headers(response):
    """
    Add CORS headers after each HTTP request.

    This function runs after each request and:
    1. Adds trace ID to response headers
    2. Logs the completion of the request
    3. Adds CORS headers
    4. Cleans up trace context
    """
    # Add trace ID to response headers for client debugging
    trace_id = TraceContext.get_trace_id()
    if trace_id:
        response.headers['X-Trace-ID'] = trace_id

    # Add CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization, X-Requested-With, X-Trace-ID'
    response.headers['Access-Control-Allow-Credentials'] = 'true'

    # Get trace-aware logger
    trace_logger = get_trace_logger(__name__)

    # Log request completion (only for non-static requests)
    if not request.path.startswith('/static') and not request.path.endswith(('.css', '.js', '.png', '.jpg', '.ico', '.svg')):
        trace_logger.info(f"Request completed: {request.method} {request.path} - Status: {response.status_code}")

    return response


# @app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
# @app.route('/<path:path>', methods=['OPTIONS'])
# def options_handler(path):
#     """Handle OPTIONS requests for CORS preflight.

#     Args:
#         path: The path requested (not used but required by the route)
#     """
#     # path 参数不使用，但是由路由规则提供
#     response = app.make_default_options_response()
#     add_cors_headers(response)
#     return response


@app.route('/api/stream', methods=['GET', 'POST', 'OPTIONS'])
@require_verified_user
def stream_api():
    """Handle streaming API requests for GET, POST, and OPTIONS methods."""
    # 处理 OPTIONS 请求
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        add_cors_headers(response)
        return response

    try:
        # 获取查询参数，根据请求方法不同而处理
        if request.method == 'GET':
            query = request.args.get('query', '')
        else:  # POST
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({"error": "Missing query parameter"}), 400
            query = data['query']

        # 检查查询参数是否存在
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400

        # Set Sentry context if available
        if sentry_initialized:
            from server.utils.sentry_config import set_tag
            set_tag('query', query)

        # 在生成器函数外部获取用户ID，确保在应用上下文中执行
        user_id = g.user_id
        trace_logger = get_trace_logger(__name__)
        trace_logger.info(f"Streaming API request from user: {user_id}")

        # 检查用户是否超过了使用限制（30天内最多5次）
        is_allowed, limit_info = usage_limiter.check_monthly_limit(
            user_id=user_id,
            endpoints=['/api/stream', '/api/scholar-pk','/api/github/analyze','/api/github/compare','/api/linkedin/analyze','/api/linkedin/compare'],
            limit=5,
            days=30
        )

        # 如果用户超过了使用限制，返回错误
        if not is_allowed:
            logger.warning(f"User {user_id} has exceeded their monthly limit for streaming API")
            return jsonify(usage_limiter.get_limit_response(limit_info)), 429  # 429 Too Many Requests

        trace_id = getattr(g, 'trace_id', None)

        task_fn = build_scholar_task_fn(
            query=query,
            active_sessions=active_sessions,
            user_id=user_id,
            trace_id=trace_id,
        )

        def result_event_builder(result_type: str, payload: Any) -> Dict[str, Any]:
            if result_type == "success":
                return create_event(
                    source="scholar",
                    event_type="final",
                    message="Scholar analysis completed",
                    payload=payload if isinstance(payload, dict) else {"result": payload},
                )
            message = str(payload)
            lowered = message.lower()
            code = "internal_error"
            retryable = False
            if "cancel" in lowered:
                code = "cancelled"
                retryable = True
            return create_error_event(
                source="scholar",
                code=code,
                message=message,
                retryable=retryable,
                detail={"query": query},
                step="stream_error",
            )

        def generate():
            return run_streaming_task(
                source="scholar",
                task_fn=task_fn,
                timeout_seconds=300,
                keepalive_seconds=15,
                result_event_builder=result_event_builder,
            )

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )
    except Exception as e:
        logger.error(f"Error in stream API: {str(e)}")
        # Capture exception in Sentry if available
        if sentry_initialized:
            from server.utils.sentry_config import capture_exception
            capture_exception(e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scholar', methods=['GET'])
def get_scholar_api():
    """Handle scholar API requests for GET"""
    try:
        scholar_id = request.args.get('user', '')
        # 检查查询参数是否存在
        if not scholar_id:
            return jsonify({"error": "Missing query parameter"}), 400
        
        

        scholar_name = get_scholar_name(scholar_id)
        if not scholar_name:
           return jsonify({
                'error': 'cached data not found',
                'message': f'未找到缓存数据'
            }), 404
        scholar_name = scholar_name.replace(" ", "_")
        formatted_json_filename = f"{scholar_name}_{scholar_id}_formatted.json"
        return serve_report_file(formatted_json_filename)
    except Exception as e:
        logger.error(f"Error in scholar API: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scholar/report", methods=["GET", "OPTIONS"])
@require_verified_user
def get_scholar_report_from_cache():
    """
    Fetch the latest scholar report from DB cache.
    """
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        add_cors_headers(response)
        return response

    scholar_id = (request.args.get("scholar_id") or request.args.get("scholarId") or "").strip()
    if not scholar_id:
        return jsonify({"success": False, "error": "Missing scholar_id"}), 400

    try:
        max_age_days = int(request.args.get("max_age_days", "30") or "30")
    except ValueError:
        max_age_days = 30

    allow_stale = (request.args.get("allow_stale", "") or "").strip().lower() in ("1", "true", "yes", "on")

    try:
        from src.utils.scholar_repository import get_scholar_by_id
        from server.api.scholar.db_cache import get_scholar_from_cache_no_log
        from server.services.scholar.completeness import compute_scholar_completeness

        cached = None
        if allow_stale:
            row = get_scholar_by_id(scholar_id)
            if isinstance(row, dict):
                cached = row.get("report_data")
        else:
            cached = get_scholar_from_cache_no_log(scholar_id, max_age_days=max_age_days)

        if not isinstance(cached, dict) or not cached:
            return jsonify({"success": False, "error": "Not found"}), 404

        meta_row = get_scholar_by_id(scholar_id) or {}
        return jsonify(
            {
                "success": True,
                "scholarId": scholar_id,
                "last_updated": meta_row.get("last_updated"),
                "completeness": compute_scholar_completeness(cached),
                "report": cached,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": str(exc)}), 500

@app.route('/api/scholar_compare', methods=['GET'])
def get_scholar_compare_api():
    """Handle scholar_compare API requests for GET"""
    try:
        scholar1_id = request.args.get('user1', '')
        scholar2_id = request.args.get('user2', '')
        # 检查查询参数是否存在
        if not scholar1_id or not scholar2_id:
            return jsonify({"error": "Missing query parameter"}), 400
        
        scholar1_name = get_scholar_name(scholar1_id)

        scholar2_name = get_scholar_name(scholar2_id)
        if not scholar1_name or not scholar2_name:
           return jsonify({
                'error': 'cached data not found',
                'message': f'未找到缓存数据'
            }), 404
        scholar1_name = scholar1_name.replace(" ", "_")
        scholar2_name = scholar2_name.replace(" ", "_")
        pk_filename = f"pk_{scholar1_name}_{scholar1_id}_vs_{scholar2_name}_{scholar2_id}.json"
        return serve_report_file(pk_filename)
    except Exception as e:
        logger.error(f"Error in scholar API: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/researcher-data', methods=['GET', 'OPTIONS'])
@require_auth
def researcher_data_api():
    """Handle requests for researcher data."""
    # 处理 OPTIONS 请求
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        add_cors_headers(response)
        return response

    try:
        researcher_data = get_researcher_data()
        return jsonify(researcher_data)
    except Exception as e:
        logger.error(f"Error retrieving researcher data: {str(e)}")
        # Capture exception in Sentry if available
        if sentry_initialized:
            from server.utils.sentry_config import capture_exception
            capture_exception(e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/top-talents', methods=['GET', 'OPTIONS'])
# @require_auth
def top_talents_api():
    """Handle requests for top AI talents."""
    # 处理 OPTIONS 请求
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        add_cors_headers(response)
        return response

    try:
        # Get the count parameter from the request, default to 5
        count = request.args.get('count', default=5, type=int)

        # Validate count parameter
        if count < 1 or count > 20:
            return jsonify({"error": "Count must be between 1 and 20"}), 400

        # Get top talents
        talents_data = get_top_talents(count)
        return jsonify(talents_data)
    except Exception as e:
        logger.error(f"Error retrieving top talents: {str(e)}")
        # Capture exception in Sentry if available
        if sentry_initialized:
            from server.utils.sentry_config import capture_exception
            capture_exception(e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/linkedin-talents', methods=['GET', 'OPTIONS'])
# @require_auth
def linkedin_talents_api():
    """Handle requests for top LinkedIn talents."""
    # 处理 OPTIONS 请求
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        add_cors_headers(response)
        return response

    try:
        # Get parameters from the request
        count = request.args.get('count', default=3, type=int)
        company_filter = request.args.get('company', default=None, type=str)
        title_filter = request.args.get('title', default=None, type=str)
        min_salary = request.args.get('min_salary', default=None, type=int)

        # Validate count parameter
        if count < 1 or count > 20:
            return jsonify({"error": "Count must be between 1 and 20"}), 400

        # Get LinkedIn talents
        talents_data = get_top_linkedin_talents(count, company_filter, title_filter, min_salary)
        response = jsonify(talents_data)
        add_cors_headers(response)
        return response
    except Exception as e:
        logger.error(f"Error retrieving LinkedIn talents: {str(e)}")
        # Capture exception in Sentry if available
        if sentry_initialized:
            from server.utils.sentry_config import capture_exception
            capture_exception(e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/scholar-pk', methods=['POST', 'OPTIONS'])
@require_verified_user
def scholar_pk_api():
    """Handle requests for scholar PK."""
    # 处理 OPTIONS 请求
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        add_cors_headers(response)
        return response

    try:
        # Get the researchers from the request body
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Extract researcher queries
        researcher1 = data.get('researcher1')
        researcher2 = data.get('researcher2')

        # Validate input
        if not researcher1 or not researcher2:
            return jsonify({"error": "Both researcher1 and researcher2 are required"}), 400

        # Set Sentry context if available
        if sentry_initialized:
            from server.utils.sentry_config import set_tag
            set_tag('researcher1', researcher1)
            set_tag('researcher2', researcher2)

        # 在生成器函数外部获取用户ID，确保在应用上下文中执行
        user_id = g.user_id
        logger.info(f"Scholar PK API request from user: {user_id}")

        # 检查用户是否超过了使用限制（30天内最多5次）
        is_allowed, limit_info = usage_limiter.check_monthly_limit(
            user_id=user_id,
            endpoints=['/api/stream', '/api/scholar-pk','/api/github/analyze','/api/github/compare','/api/linkedin/analyze','/api/linkedin/compare'],
            limit=5,
            days=30
        )

        # 如果用户超过了使用限制，返回错误
        if not is_allowed:
            logger.warning(f"User {user_id} has exceeded their monthly limit for Scholar PK API")
            return jsonify(usage_limiter.get_limit_response(limit_info)), 429  # 429 Too Many Requests

        trace_id = getattr(g, 'trace_id', None)

        task_fn = build_pk_task_fn(researcher1, researcher2, user_id=user_id, trace_id=trace_id)

        def result_event_builder(result_type: str, payload: Any) -> Optional[Dict[str, Any]]:
            # 避免重复发送 final；仅依赖 PK generator 输出的 finalContent/reportData 等
            if result_type == "success":
                return None
            message = str(payload)
            lowered = message.lower()
            code = "internal_error"
            retryable = False
            if "cancel" in lowered:
                code = "cancelled"
                retryable = True
            return create_error_event(
                source="scholar",
                code=code,
                message=message,
                retryable=retryable,
                detail={"researcher1": researcher1, "researcher2": researcher2},
                step="pk_error",
            )

        return Response(
            run_streaming_task(
                source="scholar",
                task_fn=task_fn,
                timeout_seconds=300,
                keepalive_seconds=15,
                result_event_builder=result_event_builder,
            ),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        )
    except Exception as e:
        logger.error(f"Error in scholar PK API: {str(e)}")
        # Capture exception in Sentry if available
        if sentry_initialized:
            from server.utils.sentry_config import capture_exception
            capture_exception(e)
        return jsonify({"error": str(e)}), 500


@app.route('/sub_html/', defaults={'path': ''})
@app.route('/sub_html/<path:path>')
def serve_sub_html(path):
    """
    Serve files from the sub_html directory.

    Args:
        path: The path to the requested file, relative to the sub_html directory

    Returns:
        The requested file or an error response
    """
    return serve_sub_html_file(path)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/article/<path:path>')
def serve_html(path):
    """
    Serve files from the sub_html directory.

    Args:
        path: The path to the requested file, relative to the sub_html directory

    Returns:
        The requested file or an error response
    """
    
    host = request.headers.get('Host', '')
    subdomain = host.replace('.dinq.io', '')

    path= subdomain + '/' + path + '.html'
    logger.info(f"Serving subdomain: {subdomain} for path: {path}")
    return serve_sub_html_file(path)


@app.route('/reports/<path:path>')
def serve_report(path):
    """
    Serve files from the reports directory.

    Args:
        path: The path to the requested file, relative to the reports directory

    Returns:
        The requested file or an error response
    """
    return serve_report_file(path)


@app.route('/images/', defaults={'path': ''})
@app.route('/images/<path:path>')
def serve_image(path):
    """
    Serve files from the images directory.

    Args:
        path: The path to the requested file, relative to the images directory

    Returns:
        The requested file or an error response
    """
    return serve_image_file(path)


@app.route('/data/', defaults={'path': ''})
@app.route('/data/<path:path>')
@require_verified_user
def serve_data(path):
    """
    Serve data files from the data directory.

    Args:
        path: The path to the requested file, relative to the data directory

    Returns:
        The requested data file as JSON or an error response
    """
    # 获取data目录的绝对路径
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data'
    )

    # 如果路径为空，返回可用数据文件列表
    if not path:
        try:
            data_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f)) and f.endswith('.json')]
            return jsonify({
                "available_data_files": data_files
            })
        except Exception as e:
            logger.error(f"Error listing data files: {str(e)}")
            return jsonify({"error": "Failed to list data files"}), 500

    # 构建完整的文件路径
    file_path = os.path.join(data_dir, path)

    # 安全检查：确保请求的文件在data目录内
    if not os.path.abspath(file_path).startswith(os.path.abspath(data_dir)):
        logger.warning(f"Attempted path traversal: {path}")
        return jsonify({"error": "Invalid file path"}), 403

    # 检查文件是否存在
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # 如果是JSON文件，读取并返回JSON数据
    if file_path.endswith('.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON file"}), 500
        except Exception as e:
            logger.error(f"Error reading data file {path}: {str(e)}")
            return jsonify({"error": f"Failed to read data file: {str(e)}"}), 500
    else:
        # 对于非JSON文件，返回错误
        return jsonify({"error": "Only JSON files are supported"}), 400


# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# # /chat
# def serve_static(path):
#     """
#     Serve static files from the Next.js build output.

#     Args:
#         path: The path to the requested file

#     Returns:
#         The requested file or a fallback
#     """
#     # 如果路径以sub_html开头，重定向到sub_html路由处理器
#     if path.startswith('sub_html/'):
#         sub_path = path[len('sub_html/'):]
#         return serve_sub_html(sub_path)

#     # 如果路径以images开头，重定向到images路由处理器
#     if path.startswith('images/'):
#         img_path = path[len('images/'):]
#         return serve_image(img_path)

#     # 如果是前端路由路径，返回index.html
#     frontend_routes = ['chat', 'about', 'network', 'report', 'chart-test']
#     if path in frontend_routes or path.split('/')[0] in frontend_routes:
#         path = 'index.html'

#     # If path is empty, serve index.html
#     if not path:
#         path = 'index.html'

#     # Try to serve the file directly
#     try:
#         return send_from_directory(static_dir, path)
#     except NotFound:
#         # For directories, try to serve index.html
#         if os.path.isdir(os.path.join(static_dir, path)):
#             try:
#                 return send_from_directory(os.path.join(static_dir, path), 'index.html')
#             except NotFound:
#                 pass

#         # For Next.js client-side routing, serve index.html
#         if '.' not in path:
#             return send_from_directory(static_dir, 'index.html')

#         # For 404 errors, try to serve the 404.html page
#         try:
#             return send_from_directory(static_dir, '404.html'), 404
#         except NotFound:
#             abort(404)


def run_server(host: str = 'localhost', port: int = 5001, static_directory: str = None) -> None:
    """
    Run the Scholar Demo server.

    Args:
        host: Host address to bind to
        port: Port to listen on
        static_directory: Directory containing static files
    """
    # Configure the application
    configure_app(static_directory)

    # Check if we're in debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'

    # Run the Flask application
    logger.info(f"Starting server on {host}:{port} (Debug mode: {debug_mode})")
    logger.info(f"Press Ctrl+C to stop the server")

    app.run(host=host, port=port, debug=debug_mode, threaded=True)

# 配置
UPLOAD_CONFIGS = {
    'image': {
        'allowed_extensions': {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'},
        'max_size': 10 * 1024 * 1024  # 10MB
    },
    'html': {
        'allowed_extensions': {'html', 'htm'},
        'max_size': 5 * 1024 * 1024   # 5MB
    }
}

# 支持的业务类型
BUSINESS_TYPES = ['scholar', 'github', 'github_compare', 'scholar_compare','blog']

def get_upload_folder(file_type, business_type):
    """根据文件类型和业务类型生成存储路径"""
    if file_type == 'image':
        dirpath = "images"
    if file_type == "html":
        dirpath = "sub_html"
    return os.path.join(dirpath, business_type)

def allowed_file(filename, file_type):
    """检查文件是否允许上传"""
    if file_type not in UPLOAD_CONFIGS:
        return False
    
    if '.' not in filename:
        return False
        
    file_extension = filename.rsplit('.', 1)[1].lower()
    return file_extension in UPLOAD_CONFIGS[file_type]['allowed_extensions']

def check_file_size(file_size, file_type):
    """检查文件大小"""
    if file_type not in UPLOAD_CONFIGS:
        return False
    return file_size <= UPLOAD_CONFIGS[file_type]['max_size']

@app.route('/api/upload_server', methods=['POST'])
def upload_file():
    try:
        # 检查type参数

        import uuid
        from datetime import datetime
        file_type = request.form.get('type')
        if not file_type:
            return jsonify({'error': '缺少type参数'}), 400
            
        if file_type not in UPLOAD_CONFIGS:
            return jsonify({
                'error': '不支持的type类型',
                'supported_types': list(UPLOAD_CONFIGS.keys())
            }), 400
        
        # 检查business_type参数
        business_type = request.form.get('business_type')
        if not business_type:
            return jsonify({'error': '缺少business_type参数'}), 400
            
        if business_type not in BUSINESS_TYPES:
            return jsonify({
                'error': '不支持的business_type类型',
                'supported_business_types': BUSINESS_TYPES
            }), 400
        
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        # 检查文件类型
        if not allowed_file(file.filename, file_type):
            return jsonify({
                'error': f'不支持的文件类型，{file_type}类型仅支持',
                'allowed_extensions': list(UPLOAD_CONFIGS[file_type]['allowed_extensions'])
            }), 400
        
        # 获取文件大小
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        file.seek(0)     # 回到文件开头
        
        # 检查文件大小
        if not check_file_size(file_size, file_type):
            max_size_mb = UPLOAD_CONFIGS[file_type]['max_size'] / (1024 * 1024)
            return jsonify({
                'error': f'文件太大，{file_type}类型最大支持{max_size_mb}MB'
            }), 400
        
        # 生成安全的文件名
        original_filename = file.filename
        file_extension = original_filename.rsplit('.', 1)[1]
        file_prename = original_filename.rsplit('.', 1)[0]
        # 根据type和business_type决定存储目录
        upload_folder = get_upload_folder(file_type, business_type)
        
        # 确保目录存在
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, original_filename)
        
        # 保存文件
        file.save(file_path)
        
        # 返回成功响应
        if file_type == 'image':
            url = f'https://{business_type}.dinq.io/images/blog/{file_prename}.{file_extension}'
        else:
            if business_type == 'blog':
                url = f'https://blog.dinq.io/article/{file_prename}'
            else:
                url = f'https://{business_type}.dinq.io/{file_prename}'
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'date':{
                'url': url
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'上传失败: {str(e)}'}), 500

if __name__ == '__main__':
    # Print debug information
    print("Starting server...")
    print(f"Project root: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")
    print(f"CSV path: {os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'top_ai_talents.csv')}")

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Start the Scholar Demo server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5001, help='Port to listen on')
    parser.add_argument('--static-dir', help='Directory containing static files (Next.js build output)')
    args = parser.parse_args()

    # Run the server
    run_server(host=args.host, port=args.port, static_directory=args.static_dir)
