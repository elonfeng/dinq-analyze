"""
Scholar Data Retriever

This module contains functions for retrieving scholar data.
"""

import time
import logging
import threading
from queue import Queue
from typing import Dict, List, Any, Optional, Tuple

from server.services.scholar.scholar_service import run_scholar_analysis

# 设置日志记录器（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger(__name__)
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger(__name__)

def retrieve_scholar_data(query: str, scholar_id: str = None, message_callback=None) -> Tuple[Optional[Dict], List[str]]:
    """检索Scholar数据

    Args:
        query: 用户查询
        scholar_id: 可选的Google Scholar ID
        message_callback: 可选的回调函数，用于实时返回状态消息

    Returns:
        元组（scholar数据，思考日志）
    """
    logger.info(f"Starting retrieve_scholar_data for query: {query}, scholar_id: {scholar_id}")
    # 创建一个事件来通知主线程何时可以继续
    scholar_data_ready = threading.Event()
    scholar_report = {"data": None}
    scholar_output_queue = Queue()

    # 定义回调函数来处理收到的状态更新
    def status_callback(message):
        # 将消息放入队列，无论是字符串还是字典
        scholar_output_queue.put(message)
        # 如果提供了消息回调函数，则实时调用它
        if message_callback:
            # 直接传递消息，无需转换，保留所有信息（包括进度）
            message_callback(message)

    # 在单独的线程中运行scholar_service
    def run_scholar_service():
        try:
            from server.config.api_keys import API_KEYS

            api_token = API_KEYS.get("CRAWLBASE_API_TOKEN")
            use_crawlbase = bool(api_token)

            # 如果有scholar_id，直接使用它
            if scholar_id:
                status_callback(f"Using scholar ID directly: {scholar_id}")
                report = run_scholar_analysis(
                    scholar_id=scholar_id,  # 直接使用scholar_id
                    use_crawlbase=use_crawlbase,
                    api_token=api_token,
                    callback=status_callback,  # 传入回调函数
                    use_cache=True,  # 启用缓存
                    cache_max_age_days=3  # 缓存有效期为3天
                )
            else:
                # 如果没有scholar_id，使用查询作为研究者姓名
                status_callback(f"Using query as researcher name: {query}")
                report = run_scholar_analysis(
                    researcher_name=query,
                    use_crawlbase=use_crawlbase,
                    api_token=api_token,
                    callback=status_callback,  # 传入回调函数
                    use_cache=True,  # 启用缓存
                    cache_max_age_days=3  # 缓存有效期为3天
                )

            scholar_report["data"] = report
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error in run_scholar_service: {e}")
            logger.error(f"Error details: {error_trace}")

            # 检查是否是上下文长度限制错误
            error_str = str(e)
            if 'maximum context length' in error_str or 'context window' in error_str or 'token limit' in error_str:
                logger.error(f"Context length error detected: {error_str}")

            status_callback(f"Error: {str(e)}")
        finally:
            scholar_data_ready.set()

    # 启动scholar_service线程，并传播trace context
    try:
        from server.utils.trace_context import propagate_trace_to_thread
        scholar_thread = threading.Thread(target=propagate_trace_to_thread(run_scholar_service))
    except ImportError:
        # Fallback to regular thread if trace context is not available
        scholar_thread = threading.Thread(target=run_scholar_service)

    scholar_thread.start()

    # 等待并收集输出
    waiting_time = 0
    max_waiting_time = 300  # 最大等待时间（秒）

    # 创建一个列表来存储所有消息
    all_messages = []

    while not scholar_data_ready.is_set() and waiting_time < max_waiting_time:
        # 检查是否有新的消息
        try:
            # 非阻塞方式检查队列
            while not scholar_output_queue.empty():
                message = scholar_output_queue.get_nowait()
                all_messages.append(message)
                waiting_time = 0  # 重置等待时间，因为我们有活动
        except Exception:
            pass  # 忽略队列操作异常

        # 如果没有新消息，等待一小段时间
        if waiting_time == 0:
            time.sleep(0.1)
        else:
            time.sleep(0.5)
        waiting_time += 0.5

    # 确保我们收集了所有剩余的消息
    try:
        while not scholar_output_queue.empty():
            message = scholar_output_queue.get_nowait()
            all_messages.append(message)
            # 如果提供了消息回调函数，则实时调用它
            if message_callback:
                message_callback(message)
    except Exception:
        pass  # 忽略队列操作异常

    # 检查是否成功获取了数据
    error_message = None
    try:
        # 检查是否有错误信息在队列中
        for message in all_messages:
            # 检查消息类型，处理字符串和字典两种情况
            if isinstance(message, str) and message.startswith("Error:"):
                error_message = message
                break
            elif isinstance(message, dict) and 'message' in message and isinstance(message['message'], str) and message['message'].startswith("Error:"):
                error_message = message['message']
                break

        # 检查数据是否存在
        if scholar_report.get("data") is None or error_message:
            logger.error(f"Scholar data retrieval failed: {error_message or '未知错误'}")
            return None, all_messages
    except Exception as e:
        logger.error(f"Error checking scholar data: {str(e)}")
        return None, all_messages

    return scholar_report["data"], all_messages
