"""
Scholar PK Stream Processor

This module contains functions for processing scholar PK data streams.
"""

import logging
import os
import json
import random
from typing import Any, Callable, Dict, List, Optional, Tuple
from server.utils.logging_config import setup_logging
from server.prompts.researcher_prompts import get_paper_evaluation_prompt, get_pk_roast_prompt
from server.utils.venue_processor import process_venue_string
# Generator
from typing import Generator
from server.config.llm_models import get_model

from server.utils.stream_protocol import (
    create_think_title, create_final_content,
    create_status, format_stream_message
)
from server.utils.ai_tools import generate_session_id
from server.api.scholar.utils import create_state_message
from server.api.scholar.db_cache import get_scholar_from_cache
from server.api.scholar_pk.report_generator import save_pk_report
from server.api.scholar_pk.utils import create_pk_data_message, create_pk_report_data_message
from account.filter_scholar import filter_user_input
from server.services.scholar.cancel import raise_if_cancelled
from server.utils.streaming_task_builder import build_stream_task_fn

# Import API usage tracker
from server.utils.api_usage_tracker import track_stream_completion

# 初始化日志配置
# 确保日志目录存在
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs'))
os.makedirs(log_dir, exist_ok=True)

# 创建模块特定的日志器
logger = logging.getLogger('server.api.scholar_pk')

# 如果日志器没有处理器，说明还没有初始化，调用setup_logging
if not logger.handlers:
    setup_logging(log_dir=log_dir)
    logger.info("PK processor logger initialized")

# Get base URL from environment variables
BASE_URL = os.environ.get('DINQ_API_DOMAIN', 'http://localhost:5001')
logger.info(f"PK processor using BASE_URL: {BASE_URL}")

# List of avatar files
AVATAR_DIR = 'images/icon/avatar'
AVATAR_FILES = [f"{i}.png" for i in range(21)]  # 0.png to 20.png

def get_random_avatar():
    """
    Get a random avatar URL from the avatar directory.

    Returns:
        str: URL to a random avatar image
    """
    avatar_file = random.choice(AVATAR_FILES)
    return f"{BASE_URL}/{AVATAR_DIR}/{avatar_file}"

def format_paper_venue(paper):
    """
    Format the venue field of a paper using venue processor.

    Args:
        paper (dict): Paper dictionary containing venue information

    Returns:
        dict: Paper with formatted venue
    """
    if not paper or "venue" not in paper:
        return paper

    # 使用venue_processor处理venue字段，特别处理NeurIPS格式
    original_venue = paper["venue"]
    formatted_venue = process_venue_string(original_venue)

    # 如果格式化后的venue与原始的不同，替换并记录日志
    if formatted_venue != original_venue:
        # 记录详细的日志，包括论文标题和作者
        paper_title = paper.get("title", "Unknown title")
        paper_authors = ", ".join(paper.get("authors", ["Unknown author"])[:2])
        if len(paper.get("authors", [])) > 2:
            paper_authors += " et al."

        logger.info(f"Formatted venue for paper '{paper_title}' by {paper_authors}: '{original_venue}' -> '{formatted_venue}'")
        paper["venue"] = formatted_venue

    return paper

def handle_pk_initial_setup(query1: str, query2: str) -> Generator[str, None, Tuple[bool, Optional[str], Optional[str]]]:
    """Handle initial setup and query validation for PK

    Args:
        query1: First researcher query
        query2: Second researcher query

    Yields:
        Formatted stream messages

    Returns:
        Tuple of (is_valid, scholar_id1, scholar_id2)
    """
    # Start status message
    yield format_stream_message(create_status("Processing PK request..."))
    # Process the first query to determine if it's a scholar ID, URL, or name
    processed_input1, is_name1 = filter_user_input(query1)
    scholar_id1 = None if is_name1 else processed_input1

    if scholar_id1:
        yield format_stream_message(create_state_message(f"Detected Google Scholar ID for first researcher: {scholar_id1}"))

    # Process the second query
    processed_input2, is_name2 = filter_user_input(query2)
    scholar_id2 = None if is_name2 else processed_input2

    if scholar_id2:
        yield format_stream_message(create_state_message(f"Detected Google Scholar ID for second researcher: {scholar_id2}"))

    return True, scholar_id1, scholar_id2


def handle_scholar_data_retrieval(scholar_id1: str = None, scholar_id2: str = None, query1: str = None, query2: str = None) -> Generator[str, None, Tuple[Optional[Dict], Optional[Dict], List[str]]]:
    """Handle Scholar data retrieval for PK

    Args:
        scholar_id1: Optional Google Scholar ID for first researcher
        scholar_id2: Optional Google Scholar ID for second researcher
        query1: First researcher query (name if scholar_id1 is None)
        query2: Second researcher query (name if scholar_id2 is None)

    Yields:
        Formatted stream messages

    Returns:
        Tuple of (scholar_data1, scholar_data2, thinking_logs)
    """
    # Import run_scholar_analysis function
    from server.services.scholar.scholar_service import run_scholar_analysis
    from server.config.api_keys import API_KEYS

    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')

    # Initialization message
    yield format_stream_message(create_state_message(f"Initializing academic data retrieval..."))

    thinking_logs: List[str] = []

    def run_single(*, index: int, scholar_id: Optional[str], query: Optional[str]) -> Optional[Dict[str, Any]]:
        prefix = f"Researcher {index}: "

        if scholar_id:
            yield format_stream_message(create_state_message(f"Checking database cache for researcher {index} (ID: {scholar_id})..."))
            cached = get_scholar_from_cache(scholar_id)
            if cached:
                yield format_stream_message(create_state_message(f"Found recent data in cache for researcher {index} ✓"))
                return cached
            yield format_stream_message(create_state_message(f"No cache found for researcher {index}, retrieving fresh data..."))
        else:
            yield format_stream_message(create_state_message(f"No Scholar ID for researcher {index}, searching by name: {query}..."))

        buffered_messages: List[str] = []

        def callback(msg: Any) -> None:
            if isinstance(msg, dict):
                message_content = msg.get("message", "")
                progress = msg.get("progress")
            else:
                message_content = str(msg)
                progress = None

            thinking_logs.append(str(message_content))

            state_msg = create_state_message(f"{prefix}{message_content}")
            if progress is not None:
                state_msg["progress"] = progress
            buffered_messages.append(format_stream_message(state_msg))

        result = run_scholar_analysis(
            researcher_name=query if not scholar_id else None,
            scholar_id=scholar_id,
            use_crawlbase=True,
            api_token=api_token,
            use_cache=True,
            callback=callback,
        )

        for msg in buffered_messages:
            yield msg

        return result

    # Process both researchers (legacy generator path, no extra threads/queues).
    scholar_data1 = yield from run_single(index=1, scholar_id=scholar_id1, query=query1)
    scholar_data2 = yield from run_single(index=2, scholar_id=scholar_id2, query=query2)

    # Mark section as completed
    yield format_stream_message(create_state_message("Academic data retrieval completed ✓", "completed"))

    return scholar_data1, scholar_data2, thinking_logs

def generate_paper_evaluation(paper_info: Dict[str, Any], cancel_event=None) -> str:
    """Generate a one-sentence evaluation for a research paper

    Args:
        paper_info: Information about the research paper

    Returns:
        Evaluation string
    """
    raise_if_cancelled(cancel_event)
    from server.prompts.researcher_prompts import get_paper_evaluation_prompt
    from server.llm.gateway import openrouter_chat

    # Format paper information
    paper_str = json.dumps(paper_info)

    # Get the prompt for paper evaluation
    prompt = get_paper_evaluation_prompt(paper_str)

    model = get_model("fast", task="scholar_pk.paper_eval")
    logger.info("Sending request to OpenRouter API with model %s for paper evaluation", model)

    try:
        raise_if_cancelled(cancel_event)
        response_text = openrouter_chat(
            task="scholar_pk.paper_eval",
            model=model,
            messages=[prompt],
            temperature=0.3,
            max_tokens=100,
        )
        raise_if_cancelled(cancel_event)
        if response_text:
            return str(response_text).strip()
        logger.error("No response content for paper evaluation")
        return "No evaluation available"
    except Exception as e:
        logger.error(f"Failed to generate paper evaluation: {str(e)}")
        return "No evaluation available"


def generate_pk_roast(author1_info: Dict[str, Any], author2_info: Dict[str, Any], cancel_event=None) -> str:
    """Generate a one-sentence roast comparing two researchers

    Args:
        author1_info: Information about the first researcher
        author2_info: Information about the second researcher

    Returns:
        Roast string
    """
    raise_if_cancelled(cancel_event)
    from server.llm.gateway import openrouter_chat

    # Format author information
    author1_str = json.dumps(author1_info)
    author2_str = json.dumps(author2_info)

    # 获取提示词
    messages = get_pk_roast_prompt(author1_str, author2_str)

    try:
        raise_if_cancelled(cancel_event)
        model = get_model("fast", task="scholar_pk.roast")
        response = openrouter_chat(
            task="scholar_pk.roast",
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=300,
            expect_json=True,
        )
        raise_if_cancelled(cancel_event)

        if isinstance(response, dict) and response.get("roast"):
            return str(response.get("roast") or "").strip()
        if isinstance(response, str) and response.strip():
            # Best-effort: some models may return raw text.
            return response.strip()
        return "Failed to generate roast"

    except json.JSONDecodeError as e:
        return "Failed to generate roast due to JSON parsing error"
    except Exception as e:
        return f"Failed to generate roast: {str(e)}"

def process_pk_data(scholar_data1: Dict[str, Any], scholar_data2: Dict[str, Any], cancel_event=None) -> Dict[str, Any]:
    """Process scholar data for PK comparison

    Args:
        scholar_data1: First researcher data
        scholar_data2: Second researcher data

    Returns:
        Processed PK data
    """
    raise_if_cancelled(cancel_event)
    # 记录开始处理PK数据
    researcher1_name = scholar_data1.get("researcher", {}).get("name", "Unknown")
    researcher2_name = scholar_data2.get("researcher", {}).get("name", "Unknown")
    logger.info(f"Processing PK data for {researcher1_name} vs {researcher2_name}")
    # Import the evaluation function
    from server.prompts.researcher_evaluator import generate_critical_evaluation

    # Extract relevant information for PK
    researcher1 = scholar_data1.get("researcher", {})
    researcher2 = scholar_data2.get("researcher", {})

    pub_stats1 = scholar_data1.get("publication_stats", {})
    pub_stats2 = scholar_data2.get("publication_stats", {})

    # Create researcher info dictionaries
    # Check if researcher1 already has an avatar, if not generate one
    avatar1 = researcher1.get("researcher",{}).get("avatar")
    if not avatar1:
        logger.info(f"Generating random avatar for researcher 1: {researcher1.get('name', 'Unknown')}")
        avatar1 = get_random_avatar()
    else:
        logger.info(f"Using existing avatar for researcher 1: {researcher1.get('name', 'Unknown')}")

    # Check if researcher2 already has an avatar, if not generate one
    avatar2 = researcher2.get("researcher",{}).get("avatar")
    if not avatar2:
        logger.info(f"Generating random avatar for researcher 2: {researcher2.get('name', 'Unknown')}")
        avatar2 = get_random_avatar()
    else:
        logger.info(f"Using existing avatar for researcher 2: {researcher2.get('name', 'Unknown')}")

    # 获取最引用论文并处理venue字段
    most_cited_paper1 = scholar_data1.get("publication_stats",{}).get("most_cited_paper", {})

    # 处理venue字段
    if most_cited_paper1 and "venue" in most_cited_paper1 and most_cited_paper1["venue"]:
        original_venue = most_cited_paper1["venue"]
        most_cited_paper1["original_venue"] = original_venue
        most_cited_paper1["venue"] = process_venue_string(original_venue)

    # Generate paper evaluation if there's a most cited paper
    paper_evaluation1 = ""
    if most_cited_paper1 and "title" in most_cited_paper1 and most_cited_paper1["title"]:
        logger.info(f"Generating paper evaluation for researcher 1's most cited paper: {most_cited_paper1.get('title', 'Unknown')}")
        raise_if_cancelled(cancel_event)
        paper_evaluation1 = generate_paper_evaluation(most_cited_paper1, cancel_event=cancel_event)
    else:
        logger.info("No most cited paper found for researcher 1")
        paper_evaluation1 = "No paper evaluation available"

    researcher1_info = {
        "name": researcher1.get("name", "Unknown"),
        "affiliation": researcher1.get("affiliation", "Unknown"),
        "research_fields": researcher1.get("research_fields", []),
        "scholar_id": researcher1.get("scholar_id", ""),
        "total_citations": researcher1.get("total_citations", 0),
        "h_index": researcher1.get("h_index", 0),
        "top_tier_papers": pub_stats1.get("top_tier_papers", 0),
        "first_author_papers": pub_stats1.get("first_author_papers", 0),
        "first_author_citations": pub_stats1.get("first_author_citations", 0),
        "most_cited_paper": most_cited_paper1,
        "paper_evaluation": paper_evaluation1,  # Add paper evaluation
        "avatar": avatar1  # Add avatar URL
    }

    # 获取最引用论文并处理venue字段
    most_cited_paper2 = scholar_data2.get("publication_stats",{}).get("most_cited_paper", {})

    # 处理venue字段
    if most_cited_paper2 and "venue" in most_cited_paper2 and most_cited_paper2["venue"]:
        original_venue = most_cited_paper2["venue"]
        most_cited_paper2["original_venue"] = original_venue
        most_cited_paper2["venue"] = process_venue_string(original_venue)

    # Generate paper evaluation if there's a most cited paper
    paper_evaluation2 = ""
    if most_cited_paper2 and "title" in most_cited_paper2 and most_cited_paper2["title"]:
        logger.info(f"Generating paper evaluation for researcher 2's most cited paper: {most_cited_paper2.get('title', 'Unknown')}")
        raise_if_cancelled(cancel_event)
        paper_evaluation2 = generate_paper_evaluation(most_cited_paper2, cancel_event=cancel_event)
    else:
        logger.info("No most cited paper found for researcher 2")
        paper_evaluation2 = "No paper evaluation available"

    researcher2_info = {
        "name": researcher2.get("name", "Unknown"),
        "affiliation": researcher2.get("affiliation", "Unknown"),
        "research_fields": researcher2.get("research_fields", []),
        "scholar_id": researcher2.get("scholar_id", ""),
        "total_citations": researcher2.get("total_citations", 0),
        "h_index": researcher2.get("h_index", 0),
        "top_tier_papers": pub_stats2.get("top_tier_papers", 0),
        "first_author_papers": pub_stats2.get("first_author_papers", 0),
        "first_author_citations": pub_stats2.get("first_author_citations", 0),
        "most_cited_paper": most_cited_paper2,
        "paper_evaluation": paper_evaluation2,  # Add paper evaluation
        "avatar": avatar2  # Add avatar URL
    }

    # Generate evaluations for both researchers
    logger.info("Generating evaluations for both researchers")

    # Check if evaluations already exist in the data
    evaluation1 = scholar_data1.get("critical_evaluation")
    if not evaluation1:
        logger.info(f"Generating evaluation for researcher 1: {researcher1_info['name']}")
        raise_if_cancelled(cancel_event)
        evaluation1 = generate_critical_evaluation(scholar_data1, model="fast")
        # Add the evaluation to the original data for potential caching
        scholar_data1["critical_evaluation"] = evaluation1
    else:
        logger.info(f"Using existing evaluation for researcher 1: {researcher1_info['name']}")

    evaluation2 = scholar_data2.get("critical_evaluation")
    if not evaluation2:
        logger.info(f"Generating evaluation for researcher 2: {researcher2_info['name']}")
        raise_if_cancelled(cancel_event)
        evaluation2 = generate_critical_evaluation(scholar_data2, model="fast")
        # Add the evaluation to the original data for potential caching
        scholar_data2["critical_evaluation"] = evaluation2
    else:
        logger.info(f"Using existing evaluation for researcher 2: {researcher2_info['name']}")

    # Add evaluations to researcher info
    researcher1_info["evaluation"] = evaluation1
    researcher2_info["evaluation"] = evaluation2

    # Generate roast
    raise_if_cancelled(cancel_event)
    roast = generate_pk_roast(researcher1_info, researcher2_info, cancel_event=cancel_event)

    # Create PK result
    pk_result = {
        "researcher1": researcher1_info,
        "researcher2": researcher2_info,
        "roast": roast
    }

    # 记录PK数据处理完成
    logger.info(f"PK data processing completed for {researcher1_info['name']} vs {researcher2_info['name']}")
    logger.info(f"Stats comparison: {researcher1_info['name']} (h-index: {researcher1_info['h_index']}, citations: {researcher1_info['total_citations']}) vs "
               f"{researcher2_info['name']} (h-index: {researcher2_info['h_index']}, citations: {researcher2_info['total_citations']})")

    return pk_result

def stream_pk_process(query1: str, query2: str, active_sessions: Dict[str, Dict[str, Any]], user_id: Optional[str] = None) -> Generator[str, None, None]:
    """Generate a streaming response for scholar PK process

    Args:
        query1: First researcher query
        query2: Second researcher query
        active_sessions: Dictionary storing active session information
        user_id: ID of the user making the request (for tracking API usage)

    Yields:
        Formatted stream messages
    """
    # 1. Initial setup and query validation
    is_valid, scholar_id1, scholar_id2 = yield from handle_pk_initial_setup(query1, query2)
    if not is_valid:
        return

    # 2. Scholar data retrieval
    scholar_data1, scholar_data2, _ = yield from handle_scholar_data_retrieval(scholar_id1, scholar_id2, query1, query2)

    # If we couldn't retrieve data for either researcher, return an error
    if not scholar_data1 or not scholar_data2:
        yield format_stream_message(create_state_message("Unable to retrieve scholar data for one or both researchers ✗", "completed"))
        yield format_stream_message(create_final_content(f"Sorry, unable to retrieve scholar data for one or both researchers. Please ensure you've entered the correct scholar names or IDs."))
        return

    pk_result = process_pk_data(scholar_data1, scholar_data2)


    yield format_stream_message(create_state_message("Generating PK results..."))

    # Send PK result payload (unified event + legacy content/type)
    yield format_stream_message(create_pk_data_message(pk_result))

    # 5. Save PK report and generate URLs
    session_id = generate_session_id()
    report_urls = save_pk_report(pk_result, query1, query2, session_id)

    # Send report data message with URLs
    yield format_stream_message(create_pk_report_data_message(report_urls))

    # 6. Save session
    active_sessions[session_id] = {
        "query1": query1,
        "query2": query2,
        "status": "active",
        "pk_result": pk_result,
        "report_urls": report_urls
    }

    # Track completion (SSE end 事件由 run_streaming_task 统一发送)
    try:
        track_stream_completion(
            endpoint="/api/scholar-pk",
            query=f"{query1} vs {query2}",
            scholar_id=None,  # PK模式不记录单个学者ID
            status="success",
            user_id=user_id  # 使用从请求中传递的用户ID
        )
    except Exception as e:
        logger.error(f"Error in PK completion: {str(e)}")
        track_stream_completion(
            endpoint="/api/scholar-pk",
            query=f"{query1} vs {query2}",
            status="error",
            error_message=str(e),
            user_id=user_id  # 使用从请求中传递的用户ID
        )


def build_scholar_pk_task_fn(
    *,
    query1: str,
    query2: str,
    active_sessions: Dict[str, Dict[str, Any]],
    user_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Callable[[Callable[[Dict[str, Any]], None], Any, Optional[Any]], None]:
    """
    构建 Scholar PK 的统一 task_fn，用于 run_streaming_task。

    - 使用 build_stream_task_fn 统一 trace/异常/result 写入
    - 取消/超时：通过 cancel_event 协作取消，并透传到 run_scholar_analysis
    - 事件协议：progress/data 走 dict（由 runner 统一 format），保留 legacy content/type 兼容前端
    """

    processed_input1, is_name1 = filter_user_input(query1)
    scholar_id1 = None if is_name1 else processed_input1

    processed_input2, is_name2 = filter_user_input(query2)
    scholar_id2 = None if is_name2 else processed_input2

    def work(ctx, _limit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        from server.services.scholar.scholar_service import run_scholar_analysis
        from server.config.api_keys import API_KEYS
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        last_progress: float = 0.0
        emit_lock = threading.Lock()

        retrieval_progress_start = 5.0
        retrieval_progress_end = 85.0
        progress_lock = threading.Lock()
        progress_by_researcher: Dict[int, float] = {1: 0.0, 2: 0.0}

        def map_retrieval_progress(index: int, raw_progress: float) -> float:
            try:
                raw_f = float(raw_progress)
            except (TypeError, ValueError):
                raw_f = 0.0

            raw_f = max(0.0, min(100.0, raw_f))
            with progress_lock:
                progress_by_researcher[index] = max(progress_by_researcher.get(index, 0.0), raw_f)
                combined = retrieval_progress_start + (
                    (progress_by_researcher.get(1, 0.0) + progress_by_researcher.get(2, 0.0)) / 200.0
                ) * (retrieval_progress_end - retrieval_progress_start)
            return combined

        def emit_state(message: str, *, progress: Optional[float] = None, state: str = "thinking") -> None:
            nonlocal last_progress
            with emit_lock:
                if progress is not None:
                    try:
                        progress_f = float(progress)
                    except (TypeError, ValueError):
                        progress_f = last_progress
                    progress_f = max(0.0, min(100.0, progress_f))
                    progress_f = max(last_progress, progress_f)
                    last_progress = progress_f
                    ctx.emit_raw(create_state_message(message, state=state, progress=progress_f))
                    return
                ctx.emit_raw(create_state_message(message, state=state))

        def emit_status(message: str) -> None:
            ctx.emit_raw(create_status(message))

        def retrieve_one(
            *,
            index: int,
            query: str,
            scholar_id: Optional[str],
        ) -> Optional[Dict[str, Any]]:
            prefix = f"Researcher {index}: "

            if scholar_id:
                emit_state(
                    f"Checking database cache for researcher {index} (ID: {scholar_id})...",
                )
                cached = get_scholar_from_cache(scholar_id)
                if cached:
                    _ = map_retrieval_progress(index, 100.0)
                    emit_state(
                        f"Found recent data in cache for researcher {index} ✓",
                        progress=map_retrieval_progress(index, 100.0),
                    )
                    return cached
                emit_state(
                    f"No cache found for researcher {index}, retrieving fresh data...",
                )
            else:
                emit_state(
                    f"No Scholar ID for researcher {index}, searching by name: {query}...",
                )

            api_token = API_KEYS.get("CRAWLBASE_API_TOKEN")

            def status_callback(msg: Any) -> None:
                if ctx.cancelled():
                    return
                if isinstance(msg, dict):
                    msg_text = msg.get("message", "")
                    raw_progress = msg.get("progress")
                else:
                    msg_text = str(msg)
                    raw_progress = None

                mapped_progress: Optional[float] = None
                if raw_progress is not None:
                    mapped_progress = map_retrieval_progress(index, raw_progress)

                emit_state(f"{prefix}{msg_text}", progress=mapped_progress)

            return run_scholar_analysis(
                researcher_name=query if scholar_id is None else None,
                scholar_id=scholar_id,
                use_crawlbase=True,
                api_token=api_token,
                callback=status_callback,
                use_cache=True,
                cache_max_age_days=3,
                cancel_event=ctx.cancel_event,
                user_id=user_id,
            )

        emit_status("Processing PK request...")
        if scholar_id1:
            emit_state(f"Detected Google Scholar ID for first researcher: {scholar_id1}", progress=1.0)
        if scholar_id2:
            emit_state(f"Detected Google Scholar ID for second researcher: {scholar_id2}", progress=2.0)

        raise_if_cancelled(ctx.cancel_event)
        emit_state("Initializing academic data retrieval...", progress=3.0)

        emit_state("Starting academic data retrieval...", progress=5.0)

        scholar_data1: Optional[Dict[str, Any]] = None
        scholar_data2: Optional[Dict[str, Any]] = None

        executor = ThreadPoolExecutor(max_workers=2)
        futures = {
            executor.submit(retrieve_one, index=1, query=query1, scholar_id=scholar_id1): 1,
            executor.submit(retrieve_one, index=2, query=query2, scholar_id=scholar_id2): 2,
        }
        try:
            for fut in as_completed(futures):
                raise_if_cancelled(ctx.cancel_event)
                idx = futures[fut]
                try:
                    data = fut.result()
                except Exception:
                    for other in futures:
                        if other is not fut:
                            other.cancel()
                    raise

                if data is not None:
                    _ = map_retrieval_progress(idx, 100.0)

                if idx == 1:
                    scholar_data1 = data
                else:
                    scholar_data2 = data
        finally:
            if ctx.cancelled():
                for fut in futures:
                    fut.cancel()
                executor.shutdown(wait=False)
            else:
                executor.shutdown(wait=True)

        if not scholar_data1 or not scholar_data2:
            raise ValueError(
                "Unable to retrieve scholar data for one or both researchers. "
                "Please ensure you've entered the correct scholar names or IDs."
            )

        emit_state("Academic data retrieval completed ✓", progress=86.0, state="completed")

        emit_state("Generating PK results...", progress=88.0)
        pk_result = process_pk_data(scholar_data1, scholar_data2, cancel_event=ctx.cancel_event)

        ctx.emit_raw(create_pk_data_message(pk_result))
        emit_state("PK report generating...", progress=92.0)

        session_id = generate_session_id()
        report_urls = save_pk_report(pk_result, query1, query2, session_id)

        ctx.emit_raw(create_pk_report_data_message(report_urls))

        active_sessions[session_id] = {
            "query1": query1,
            "query2": query2,
            "status": "active",
            "pk_result": pk_result,
            "report_urls": report_urls,
        }

        emit_state("PK completed", progress=95.0)
        return {"ok": True}

    def on_success(_payload: Dict[str, Any]) -> None:
        try:
            track_stream_completion(
                endpoint="/api/scholar-pk",
                query=f"{query1} vs {query2}",
                scholar_id=None,
                status="success",
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error tracking Scholar PK completion: %s", exc)

    def on_error(error_message: str) -> None:
        try:
            track_stream_completion(
                endpoint="/api/scholar-pk",
                query=f"{query1} vs {query2}",
                scholar_id=None,
                status="error",
                error_message=error_message,
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error tracking Scholar PK completion: %s", exc)

    return build_stream_task_fn(
        source="scholar",
        trace_id=trace_id,
        usage_limiter=None,
        usage_config=None,
        user_id=user_id,
        start_message=f"Starting Scholar PK: {query1} vs {query2}",
        start_payload={"researcher1": query1, "researcher2": query2},
        work=work,
        on_success=on_success,
        on_error=on_error,
    )
