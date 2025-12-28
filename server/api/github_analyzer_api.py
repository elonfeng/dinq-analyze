"""
GitHub Analyzer API Blueprint

集成GitHub用户分析功能到DINQ项目
提供GitHub用户深度分析的REST API接口
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify, g, Response
import asyncio
from server.api.reports_handler import serve_report_file
# 导入认证和限制模块
from server.utils.auth import require_verified_user
from server.utils.usage_limiter import usage_limiter
from server.utils.trace_context import get_trace_logger, TraceContext
from server.utils.api_usage_tracker import track_api_call
from server.utils.stream_protocol import create_error_event, create_event, format_stream_message
from server.utils.stream_task import run_streaming_task
from server.utils.streaming_task_builder import build_stream_task_fn, UsageLimitConfig
from src.utils.api_usage_repository import api_usage_repo
from server.api.dev_pioneers_handler import get_dev_pioneers_data
from server.analyze.api import create_analysis_job, stream_job_events, init_scheduler, run_sync_job

# 创建蓝图
github_analyzer_bp = Blueprint('github_analyzer', __name__, url_prefix='/api/github')

# 设置日志记录器
logger = get_trace_logger(__name__)

# 全局分析器实例
_analyzer = None

def get_analyzer():
    """获取GitHub分析器实例（延迟初始化）"""
    global _analyzer
    if _analyzer is None:
        try:
            # 导入GitHub分析器模块
            from server.github_analyzer.config import load_config
            from server.github_analyzer.analyzer import GitHubAnalyzer

            # 加载配置
            config = load_config()

            # 创建分析器实例
            _analyzer = GitHubAnalyzer(config)
            logger.info("GitHub分析器初始化成功")

        except Exception as e:
            logger.error(f"GitHub分析器初始化失败: {e}")
            raise

    return _analyzer


def generate_github_ai_summary(username: str, total_stars: int, top_languages: List[str], top_repositories: List[Dict[str, Any]]) -> str:
    """
    Generate AI summary for GitHub user using GPT-4o-mini

    Args:
        username: GitHub username
        total_stars: Total stars received
        top_languages: Top programming languages
        top_repositories: Top repositories information

    Returns:
        AI generated summary string
    """
    try:
        from server.llm.gateway import openrouter_chat
        from server.config.llm_models import get_model

        # Prepare data for AI
        languages_str = ", ".join(top_languages) if top_languages else "various languages"



        # Create prompt for AI summary
        prompt = f"""
Generate a concise summary (30-40 words) for GitHub user "{username}". Summarize the categories of projects they specialize in and mention one representative open-source project.

Details:
- Total stars: {total_stars}
- Top programming languages: {languages_str}
- Representative repository: {top_repositories}
"""

        summary = openrouter_chat(
            task="github.summary",
            model=get_model("fast", task="github.summary"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100,
        )
        if summary:
            summary = str(summary).replace('"', '').replace('\n', ' ').strip()
            return summary
        logger.error("AI summary generation failed: empty response")

    except Exception as e:
        logger.error(f"Error generating GitHub AI summary: {e}")

    # Fallback summary
    if top_languages:
        return f"Software developer specializing in {', '.join(top_languages[:2])} with {total_stars} total stars"
    else:
        return "Software developer with diverse projects"


def get_user_repositories(username: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取用户的GitHub仓库信息

    Args:
        username: GitHub用户名

    Returns:
        仓库列表或None（如果失败）
    """
    try:
        url = f"https://api.github.com/users/{username}/repos"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            repos = response.json()
            # 提取所需字段
            filtered_repos = []
            for repo in repos:
                filtered_repos.append({
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "language": repo.get("language"),
                    "stargazers_count": repo.get("stargazers_count", 0)
                })
            logger.info(f"Successfully fetched {len(filtered_repos)} repositories for {username}")
            return filtered_repos
        elif response.status_code == 404:
            logger.error(f"GitHub user {username} not found")
            return None
        else:
            logger.error(f"Failed to fetch repositories: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching repositories for {username}: {e}")
        return None

def analyze_repositories_data(repos: List[Dict[str, Any]], username: str) -> Dict[str, Any]:
    """
    分析仓库数据，提取卡片所需信息

    Args:
        repos: 仓库列表
        username: GitHub用户名

    Returns:
        卡片数据
    """
    try:
        # 计算总star数
        total_stars = sum(repo.get('stargazers_count', 0) for repo in repos)

        # 按star数排序，获取top仓库
        sorted_repos = sorted(repos, key=lambda x: x.get('stargazers_count', 0), reverse=True)
        top_repos = sorted_repos[:10]  # 取前10个仓库用于语言分析

        # 获取前三个不同的编程语言（按 top_repos 顺序）
        top_languages = []
        for repo in top_repos:
            language = repo.get('language')
            if language and language != 'null' and language not in top_languages:
                top_languages.append(language)
            if len(top_languages) == 3:
                break
        # 生成AI摘要
        summary = generate_github_ai_summary(username, total_stars, top_languages, top_repos[:3])

        # 构建卡片数据
        card_data = {
            'username': username,
            'total_stars': total_stars,
            'top_languages': top_languages,
            'summary': summary
        }

        return card_data

    except Exception as e:
        logger.error(f"Error analyzing repositories data: {e}")
        return {
            'username': username,
            'total_stars': 0,
            'total_repositories': 0,
            'top_languages': [],
            'top_repositories': [],
            'summary': 'GitHub developer with various projects'
        }


@github_analyzer_bp.route('/analyze-stream', methods=['POST'])
@require_verified_user
def analyze_github_user_stream():
    """
    流式分析GitHub用户

    使用Server-Sent Events (SSE)实时返回分析进度
    """
    # 在生成器外部获取请求数据
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return Response(
                format_stream_message(
                    create_error_event(
                        source="github",
                        code="invalid_request",
                        message="Missing username in request body",
                        retryable=False,
                        detail={"required_fields": ["username"]},
                        step="validate_request",
                    )
                ),
                mimetype='text/event-stream',
            )

        username = data['username'].strip()
        if not username:
            return Response(
                format_stream_message(
                    create_error_event(
                        source="github",
                        code="invalid_request",
                        message="Invalid username",
                        retryable=False,
                        detail={"username": username},
                        step="validate_request",
                    )
                ),
                mimetype='text/event-stream',
            )

        user_id = g.user_id
        legacy_flag = data.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")
        logger.info("GitHub流式分析请求 - 用户: %s, GitHub用户名: %s", user_id, username)
    except Exception as exc:  # noqa: BLE001
        logger.error("获取请求数据时出错: %s", exc)
        return Response(
            format_stream_message(
                create_error_event(
                    source="github",
                    code="invalid_request",
                    message="请求数据格式错误",
                    retryable=False,
                    detail={"exception": str(exc)},
                    step="validate_request",
                )
            ),
            mimetype='text/event-stream',
        )

    trace_id = TraceContext.get_trace_id()

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
                        source="github",
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
            source="github",
            input_payload={"username": username},
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

    analyzer_holder: Dict[str, Any] = {"analyzer": None}

    def get_analyzer_once(ctx) -> Any:
        if analyzer_holder["analyzer"] is None:
            ctx.progress("init_analyzer", "Initializing GitHub analyzer...")
            analyzer_holder["analyzer"] = get_analyzer()
        return analyzer_holder["analyzer"]

    def _usage_info(limit_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'remaining_uses': limit_info.get('remaining', 0),
            'total_usage': limit_info.get('total_usage', 0),
            'limit': limit_info.get('limit', 10),
            'period_days': limit_info.get('period_days', 30),
        }

    def cache_lookup(ctx):
        analyzer = get_analyzer_once(ctx)
        from server.github_analyzer.models import AnalysisResult

        analysis_result = analyzer.session.get(AnalysisResult, username)
        if not analysis_result:
            return None
        try:
            return json.loads(analysis_result.result)
        except json.JSONDecodeError:
            ctx.progress("cache_invalid", "Cache data corrupted, re-analyzing")
            try:
                analyzer.session.delete(analysis_result)
                analyzer.session.commit()
            except Exception:  # noqa: BLE001
                pass
            return None

    def cache_hit_payload_builder(cached: Any, limit_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'success': True,
            'username': username,
            'data': cached,
            'from_cache': True,
            'usage_info': _usage_info(limit_info),
        }

    def work(ctx, limit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        analyzer = get_analyzer_once(ctx)

        ctx.progress("start_analysis", "Starting new analysis...")

        def progress_callback(step, message, data=None):
            ctx.progress(step, message, payload=data if isinstance(data, dict) else None)

        result = analyzer.get_result_with_progress(
            username,
            progress_callback,
            cancel_event=ctx.cancel_event,
        )
        if result is None:
            raise ValueError(f'GitHub user "{username}" does not exist or is not accessible')

        return {
            'success': True,
            'username': username,
            'data': result,
            'from_cache': False,
            'usage_info': _usage_info(limit_info or {}),
        }

    def on_success(_payload: Dict[str, Any]) -> None:
        track_api_call(
            endpoint='/api/github/analyze',
            query=username,
            query_type='github_username',
            status='success',
            user_id=user_id,
        )

    def on_error(error_message: str) -> None:
        track_api_call(
            endpoint='/api/github/analyze',
            query=username,
            query_type='github_username',
            status='error',
            error_message=error_message,
            user_id=user_id,
        )

    task_fn = build_stream_task_fn(
        source="github",
        trace_id=trace_id,
        usage_limiter=usage_limiter,
        usage_config=usage_config,
        user_id=user_id,
        start_message=f"Starting GitHub user analysis: {username}",
        start_payload={"username": username},
        cache_lookup=cache_lookup,
        cache_hit_payload_builder=cache_hit_payload_builder,
        work=work,
        on_success=on_success,
        on_error=on_error,
    )

    def result_event_builder(result_type: str, payload: Any):
        if result_type == "success":
            return create_event(
                source="github",
                event_type="final",
                message="GitHub analysis completed",
                payload=payload if isinstance(payload, dict) else {"result": payload},
                legacy_type="complete",
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
            source="github",
            code=code,
            message=message,
            retryable=retryable,
            detail={"username": username},
            step="analyze_error",
        )

    return Response(
        run_streaming_task(
            source="github",
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
            'Access-Control-Allow-Headers': 'Cache-Control',
        },
    )

@github_analyzer_bp.route('/compare-stream', methods=['POST'])
@require_verified_user
def compare_github_user_stream():
    """
    流式对比分析两个 GitHub 用户（PK）

    使用统一的 Server-Sent Events (SSE) 事件协议实时返回进度与结果。
    """
    try:
        data = request.get_json()
        if not data or 'user1' not in data or 'user2' not in data:
            return jsonify({
                'error': 'Missing username in request body',
                'message': 'Please provide {"user1": "...", "user2": "..."}',
            }), 400

        user1 = str(data['user1']).strip()
        user2 = str(data['user2']).strip()
        if not user1 or not user2:
            return jsonify({
                'error': 'Invalid username',
                'message': 'user1/user2 cannot be empty',
            }), 400

        user_id = g.user_id
        logger.info("GitHub PK stream request - user: %s, user1: %s, user2: %s", user_id, user1, user2)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse request body: %s", exc)
        return jsonify({'error': '请求数据格式错误'}), 400

    trace_id = TraceContext.get_trace_id()

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

    analyzer_holder: Dict[str, Any] = {"analyzer": None}

    def get_analyzer_once(ctx) -> Any:
        if analyzer_holder["analyzer"] is None:
            ctx.progress("init_analyzer", "Initializing GitHub analyzer...")
            analyzer_holder["analyzer"] = get_analyzer()
        return analyzer_holder["analyzer"]

    def _usage_info(limit_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "remaining_uses": limit_info.get("remaining", 0),
            "total_usage": limit_info.get("total_usage", 0),
            "limit": limit_info.get("limit", 10),
            "period_days": limit_info.get("period_days", 30),
        }

    def cache_lookup(ctx):
        analyzer = get_analyzer_once(ctx)
        try:
            return analyzer.get_cached_compare_result(user1, user2)
        except Exception:  # noqa: BLE001
            return None

    def cache_hit_payload_builder(cached: Any, limit_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "user1": user1,
            "user2": user2,
            "data": cached,
            "from_cache": True,
            "usage_info": _usage_info(limit_info),
        }

    def work(ctx, limit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        analyzer = get_analyzer_once(ctx)

        def progress_callback(which_user: str):
            def _cb(step, message, data=None):
                ctx.progress(
                    f"{which_user}_{step}",
                    message,
                    payload=data if isinstance(data, dict) else None,
                )
            return _cb

        ctx.progress("user1_start", f"Analyzing {user1}...")
        result1 = analyzer.get_result_with_progress(
            user1,
            progress_callback("user1"),
            cancel_event=ctx.cancel_event,
        )
        if result1 is None:
            raise ValueError(f'GitHub user "{user1}" does not exist or is not accessible')

        ctx.progress("user2_start", f"Analyzing {user2}...")
        result2 = analyzer.get_result_with_progress(
            user2,
            progress_callback("user2"),
            cancel_event=ctx.cancel_event,
        )
        if result2 is None:
            raise ValueError(f'GitHub user "{user2}" does not exist or is not accessible')

        ctx.progress("generate_pk", "Generating PK result...")
        pk_result = analyzer.transform_pk_result(user1, user2, result1, result2)

        report_urls = None
        try:
            if pk_result:
                report_urls = analyzer.save_pk_report(pk_result)
        except Exception:  # noqa: BLE001
            report_urls = None

        return {
            "success": True,
            "user1": user1,
            "user2": user2,
            "data": pk_result,
            "report_urls": report_urls,
            "from_cache": False,
            "usage_info": _usage_info(limit_info or {}),
        }

    def on_success(_payload: Dict[str, Any]) -> None:
        track_api_call(
            endpoint='/api/github/compare',
            query=f"{user1} vs {user2}",
            query_type='github_pk',
            status='success',
            user_id=user_id,
        )

    def on_error(error_message: str) -> None:
        track_api_call(
            endpoint='/api/github/compare',
            query=f"{user1} vs {user2}",
            query_type='github_pk',
            status='error',
            error_message=error_message,
            user_id=user_id,
        )

    task_fn = build_stream_task_fn(
        source="github",
        trace_id=trace_id,
        usage_limiter=usage_limiter,
        usage_config=usage_config,
        user_id=user_id,
        start_message=f"Starting GitHub PK analysis: {user1} vs {user2}",
        start_payload={"user1": user1, "user2": user2},
        cache_lookup=cache_lookup,
        cache_hit_payload_builder=cache_hit_payload_builder,
        work=work,
        on_success=on_success,
        on_error=on_error,
    )

    def result_event_builder(result_type: str, payload: Any):
        if result_type == "success":
            return create_event(
                source="github",
                event_type="final",
                message="GitHub PK analysis completed",
                payload=payload if isinstance(payload, dict) else {"result": payload},
                legacy_type="complete",
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
            source="github",
            code=code,
            message=message,
            retryable=retryable,
            detail={"user1": user1, "user2": user2},
            step="compare_error",
        )

    return Response(
        run_streaming_task(
            source="github",
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
            'Access-Control-Allow-Headers': 'Cache-Control',
        },
    )
    
                
@github_analyzer_bp.route('/get_result', methods=[ 'GET'])
def get_github_result():
    """
    分析GitHub用户

    支持GET和POST两种方式
    - GET: /api/github/analyze?username=octocat
    - POST: /api/github/analyze {"username": "octocat"}
    """
    try:
        username = request.args.get('user')
        if not username:
            return jsonify({
                'error': 'Missing username parameter',
                'message': 'Please provide a GitHub username as a query parameter: ?username=github_username'
            }), 400
        username = username.strip()

        if not username:
            return jsonify({
                'error': 'Invalid username',
                'message': 'Username cannot be empty'
            }), 400

        # 获取分析器实例
        analyzer = get_analyzer()

        result = analyzer.get_cached_result(username)

        if result is None:
            return jsonify({
                'error': 'cached data not found',
                'message': f'未找到缓存数据'
            }), 404

        return jsonify(result)
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': '查询用户时发生错误，请稍后重试'
        }), 500
        
        
@github_analyzer_bp.route('/analyze', methods=['POST', 'GET'])
@require_verified_user
def analyze_github_user():
    """
    分析GitHub用户

    支持GET和POST两种方式
    - GET: /api/github/analyze?username=octocat
    - POST: /api/github/analyze {"username": "octocat"}
    """
    try:
        data = None
        # 获取用户名
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'username' not in data:
                return jsonify({
                    'error': 'Missing username in request body',
                    'message': 'Please provide a GitHub username in the request body as {"username": "github_username"}'
                }), 400
            username = data['username'].strip()
        else:  # GET
            username = request.args.get('username')
            if not username:
                return jsonify({
                    'error': 'Missing username parameter',
                    'message': 'Please provide a GitHub username as a query parameter: ?username=github_username'
                }), 400
            username = username.strip()

        if not username:
            return jsonify({
                'error': 'Invalid username',
                'message': 'Username cannot be empty'
            }), 400

        # 获取用户ID
        user_id = g.user_id
        logger.info(f"GitHub分析请求 - 用户: {user_id}, GitHub用户名: {username}")

        # 检查用户是否超过了使用限制（30天内最多10次）
        is_allowed, limit_info = usage_limiter.check_monthly_limit(
            user_id=user_id,
            endpoints=['/api/stream', '/api/scholar-pk','/api/github/analyze','/api/github/compare','/api/linkedin/analyze','/api/linkedin/compare'],
            limit=5,
            days=30
        )

        if not is_allowed:
            logger.warning(f"User {user_id} has exceeded monthly usage limit for GitHub analysis")
            return jsonify(usage_limiter.get_limit_response(limit_info)), 429

        legacy_flag = None
        if request.method == 'POST':
            legacy_flag = data.get("legacy") if isinstance(data, dict) else None
        legacy_flag = legacy_flag or request.args.get("legacy")
        use_legacy = str(legacy_flag).lower() in ("1", "true", "yes", "on")

        if not use_legacy:
            requested_cards = data.get("cards") if isinstance(data, dict) else None
            job_id, _created = create_analysis_job(
                user_id=user_id or "anonymous",
                source="github",
                input_payload={"username": username},
                requested_cards=requested_cards,
                options={},
            )
            payload, status = run_sync_job(job_id, "github", requested_cards)
            return jsonify(payload), status

        # 获取分析器实例
        analyzer = get_analyzer()

        # 执行分析
        logger.info(f"Starting GitHub user analysis: {username}")
        result = analyzer.get_result(username)

        if result is None:
            return jsonify({
                'error': 'User not found',
                'message': f'GitHub user "{username}" does not exist or is not accessible'
            }), 404

        # 记录使用情况
        track_api_call(
            endpoint='/api/github/analyze',
            query=username,
            query_type='github_username',
            status='success',
            user_id=user_id
        )

        logger.info(f"GitHub user {username} analysis completed")

        return jsonify({
            'success': True,
            'username': username,
            'data': result,
            'usage_info': {
                'remaining_uses': limit_info.get('remaining', 0),
                'total_usage': limit_info.get('total_usage', 0),
                'limit': limit_info.get('limit', 10),
                'period_days': limit_info.get('period_days', 30)
            }
        })

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return jsonify({
            'error': 'Configuration error',
            'message': 'GitHub analyzer configuration is incorrect, please check environment variables'
        }), 500
    except Exception as e:
        logger.error(f"Error in analyzing GitHub user: {str(e)}", exc_info=True)

        # 捕获异常到Sentry（如果可用）
        try:
            from server.utils.sentry_config import capture_exception_with_trace
            capture_exception_with_trace(e)
        except ImportError:
            pass

        return jsonify({
            'error': 'Internal server error',
            'message': 'Error occurred while analyzing user, please try again later'
        }), 500


@github_analyzer_bp.route('/card/analyze', methods=['POST'])
def analyze_github_card():
    """
    GitHub用户卡片分析接口

    使用GitHub API直接获取仓库信息，分析用户的编程语言偏好

    Request body:
    {
        "username": "github_username"
    }

    Returns:
    {
        "code": 200,
        "message": "GitHub card analysis completed successfully",
        "data": {
            "username": "octocat",
            "total_stars": 12345,
            "top_languages": ["JavaScript", "Python", "Go"],
            "top_repositories": [...],
            "summary": "Full-stack developer, created popular web frameworks"
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

        # 执行分析
        logger.info(f"Starting GitHub card analysis: {username}")

        # 获取用户仓库信息
        repos_data = get_user_repositories(username)
        if repos_data is None:
            return jsonify({
                'code': 404,
                'message': f'GitHub user "{username}" does not exist or is not accessible'
            }), 404

        # 分析仓库数据
        card_data = analyze_repositories_data(repos_data, username)

        logger.info(f"GitHub card analysis for {username} completed")

        return jsonify({
            'code': 200,
            'message': 'GitHub card analysis completed successfully',
            'data': card_data
        })

    except Exception as e:
        logger.error(f"Error in GitHub card analysis: {str(e)}", exc_info=True)

        return jsonify({
            'code': 500,
            'message': 'Error occurred while analyzing user, please try again later'
        }), 500

@github_analyzer_bp.route('/compare', methods=['POST'])
@require_verified_user
def compare_github_user():
    """
    分析GitHub用户

    支持GET和POST两种方式
    - GET: /api/github/analyze?username=octocat
    - POST: /api/github/analyze {"username": "octocat"}
    """
    try:
        
        data = request.get_json()
        if not data or 'user1' not in data or 'user2' not in data:
            return jsonify({
                'error': 'Missing username in request body',
                'message': 'Please provide a GitHub username in the request body as {"username": "github_username"}'
            }), 400
        user1 = data['user1'].strip()
        user2 = data['user2'].strip()

        if not user1 or not user2:
            return jsonify({
                'error': 'Invalid username',
                'message': 'Username cannot be empty'
            }), 400

        # 获取用户ID
        user_id = g.user_id
        logger.info(f"GitHub比较请求 - 用户: {user_id}, GitHub用户名: {user1} 和{user2}")

        # 检查用户是否超过了使用限制（30天内最多10次）
        is_allowed, limit_info = usage_limiter.check_monthly_limit(
            user_id=user_id,
            endpoints=['/api/stream', '/api/scholar-pk','/api/github/analyze','/api/github/compare','/api/linkedin/analyze','/api/linkedin/compare'],
            limit=5,
            days=30
        )

        if not is_allowed:
            logger.warning(f"User {user_id} has exceeded monthly usage limit for GitHubpk")
            return jsonify(usage_limiter.get_limit_response(limit_info)), 429

        # 获取分析器实例
        analyzer = get_analyzer()

        # 执行分析
        logger.info(f"Starting comparison of GitHub users: {user1} and {user2}")
        result = asyncio.run(analyzer.get_compare_result(user1, user2))

        if result is None:
            return jsonify({
                'error': 'User not found',
                'message': f'GitHub user "{user1}" or "{user2}" does not exist or is not accessible'
            }), 404

        # 记录使用情况
        track_api_call(
            endpoint='/api/github/compare',
            query=f"{user1}&&{user2}",
            query_type='github_username',
            status='success',
            user_id=user_id
        )

        logger.info(f"GitHub user {user1} and {user2} comparison completed")

        return jsonify({
            'success': True,
            'user1': user1,
            'user2': user2,
            'data': result,
            'usage_info': {
                'remaining_uses': limit_info.get('remaining', 0),
                'total_usage': limit_info.get('total_usage', 0),
                'limit': limit_info.get('limit', 10),
                'period_days': limit_info.get('period_days', 30)
            }
        })

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return jsonify({
            'error': 'Configuration error',
            'message': 'GitHub analyzer configuration is incorrect, please check environment variables'
        }), 500
    except Exception as e:
        logger.error(f"Error in comparing GitHub users: {str(e)}", exc_info=True)

        # 捕获异常到Sentry（如果可用）
        try:
            from server.utils.sentry_config import capture_exception_with_trace
            capture_exception_with_trace(e)
        except ImportError:
            pass

        return jsonify({
            'error': 'Internal server error',
            'message': 'Error occurred while analyzing user, please try again later'
        }), 500
        
@github_analyzer_bp.route('/compare', methods=['GET'])
def get_github_compare_api():
    """Handle scholar_compare API requests for GET"""
    try:
        user1 = request.args.get('user1', '')
        user2 = request.args.get('user2', '')
        # 检查查询参数是否存在
        if not user1 or not user2:
            return jsonify({"error": "Missing query parameter"}), 400
        pk_filename = f"github_pk_{user1}_vs_{user2}.json"
        return serve_report_file(pk_filename)
    except Exception as e:
        logger.error(f"Error in scholar API: {str(e)}")
        return jsonify({"error": str(e)}), 500
            
@github_analyzer_bp.route('/health', methods=['GET'])
def health_check():
    """GitHub分析器健康检查"""
    try:
        # 检查分析器是否可以初始化
        get_analyzer()

        return jsonify({
            'status': 'healthy',
            'service': 'GitHub Analyzer',
            'version': '1.0.0'
        })
    except Exception as e:
        logger.error(f"GitHub分析器健康检查失败: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'GitHub Analyzer',
            'error': str(e)
        }), 500

@github_analyzer_bp.route('/dev-pioneers', methods=['GET'])
def get_dev_pioneers():
    """
    获取开发先驱数据

    支持查询参数
    - count: 返回的数量(默认: 10, 最多: 50)
    - random: 是否随机选择 (默认: false)
    - area: 按技术领域过滤(可选)
    - company: 按公司过滤(可选)
    """
    try:
        # 获取查询参数
        count = request.args.get('count', 10, type=int)
        random_selection = request.args.get('random', 'false').lower() == 'true'
        area_filter = request.args.get('area', '').strip()
        company_filter = request.args.get('company', '').strip()

        # 限制返回数量
        count = min(max(count, 1), 50)

        # 读取开发先驱数据
        pioneers_data = get_dev_pioneers_data(
            count=count,
            random_selection=random_selection,
            area_filter=area_filter,
            company_filter=company_filter
        )

        return jsonify(pioneers_data)

    except Exception as e:
        logger.error(f"获取开发先驱数据时出错: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve dev pioneers data',
            'message': '获取开发先驱数据时发生错误'
        }), 500

@github_analyzer_bp.route('/help', methods=['GET'])
def api_help():
    """GitHub分析器API使用说明"""
    return jsonify({
        'service': 'DINQ GitHub Analyzer API',
        'description': '深度分析GitHub用户的代码贡献、技能水平、项目影响力等',
        'endpoints': {
            'POST /api/github/analyze': {
                'description': '分析GitHub用户（推荐方式）',
                'authentication': 'required',
                'body': {'username': 'github_username'},
                'example': 'curl -X POST -H "Content-Type: application/json" -H "Userid: your_user_id" -d \'{"username":"octocat"}\' http://localhost:5001/api/github/analyze'
            },
            'GET /api/github/analyze': {
                'description': '通过查询参数分析GitHub用户',
                'authentication': 'required',
                'parameters': {'username': 'github_username'},
                'example': 'curl -H "Userid: your_user_id" "http://localhost:5001/api/github/analyze?username=octocat"'
            },
            'GET /api/github/health': {
                'description': '健康检查端点'
            },
            'GET /api/github/help': {
                'description': 'API使用说明'
            }
        },
        'features': [
            '深度用户分析：代码贡献、技能标签、工作经历',
            'AI驱动分析：用户标签、项目分析、角色模型匹配',
            '数据可视化：详细的统计数据和活动分析',
            '薪资评估：基于Google标准的技能水平和薪资评估',
            '角色匹配：与知名开发者进行相似度匹配',
            '智能缓存：避免重复分析，提高响应速度'
        ],
        'usage_limits': {
            'monthly_limit': 10,
            'period_days': 30,
            'note': '已激活用户不受限制'
        },
        'required_environment_variables': [
            'GITHUB_TOKEN',
            'OPENROUTER_API_KEY',
            'CRAWLBASE_TOKEN'
        ]
    })

@github_analyzer_bp.route('/stats', methods=['GET'])
@require_verified_user
def get_user_stats():
    """获取用户的GitHub分析使用统计"""
    try:
        user_id = g.user_id

        # 获取用户使用统计
        github_usage_count = api_usage_repo.get_endpoint_usage_count(
            user_id=user_id,
            endpoint='/api/github/analyze',
            days=30
        )

        usage_stats = {
            '/api/github/analyze': github_usage_count
        }

        return jsonify({
            'user_id': user_id,
            'github_analysis_stats': usage_stats,
            'limits': {
                'monthly_limit': 10,
                'period_days': 30
            }
        })

    except Exception as e:
        logger.error(f"获取用户统计时出错: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': '获取统计信息时发生错误'
        }), 500

# 错误处理
@github_analyzer_bp.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({
        'error': 'Not found',
        'message': 'Requested GitHub analysis endpoint does not exist'
    }), 404

@github_analyzer_bp.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({
        'error': 'Internal server error',
        'message': 'GitHub analysis service encountered an internal error'
    }), 500
