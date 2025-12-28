"""
Axiom Logger Integration

This module provides integration with Axiom for centralized log collection and analysis.
"""

import os
import logging
import threading
import queue
import time
from typing import Dict, Any, Optional
import axiom_py
# from axiom_py.logging import AxiomHandler  # 不再使用，改为自定义处理器

# 默认的数据集名称
DEFAULT_DATASET = "dinq"

# 获取Axiom API令牌
AXIOM_TOKEN = os.environ.get("AXIOM_TOKEN", "")

# 批处理大小和刷新间隔
BATCH_SIZE = 100
FLUSH_INTERVAL = 5  # 秒

class BatchingAxiomHandler(logging.Handler):
    """
    扩展AxiomHandler以支持批处理和异步发送日志
    """

    def __init__(self, client, dataset, level=logging.NOTSET, **kwargs):
        """
        初始化批处理Axiom处理器

        Args:
            client: Axiom客户端
            dataset: Axiom数据集名称
            level: 日志级别
            **kwargs: 其他参数
        """
        super().__init__(level)
        self.client = client
        self.dataset = dataset
        self.queue = queue.Queue()
        self.batch = []
        self.lock = threading.Lock()
        self.last_flush = time.time()

        # 启动后台线程
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def format_time(self, timestamp):
        """
        格式化时间戳为 ISO 8601 格式

        Args:
            timestamp: 时间戳

        Returns:
            str: ISO 8601 格式的时间字符串
        """
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).isoformat()

    def formatException(self, exc_info):
        """
        格式化异常信息

        Args:
            exc_info: 异常信息元组 (type, value, traceback)

        Returns:
            str: 格式化后的异常信息
        """
        import traceback
        if exc_info and isinstance(exc_info, tuple) and len(exc_info) == 3:
            return '\n'.join(traceback.format_exception(*exc_info))
        return str(exc_info)

    def emit(self, record):
        """
        将日志记录添加到队列

        Args:
            record: 日志记录
        """
        try:
            # 格式化日志记录
            event = self.format_record(record)
            # 添加到队列
            self.queue.put(event)
        except Exception:
            self.handleError(record)

    def format_record(self, record) -> Dict[str, Any]:
        """
        格式化日志记录为Axiom事件

        Args:
            record: 日志记录

        Returns:
            Dict: 格式化后的事件
        """
        # 获取基本信息
        event = {
            "_time": self.format_time(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "process": record.process,
            "thread": record.thread,
        }

        # 添加异常信息
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "axiom_fields") and isinstance(record.axiom_fields, dict):
            event.update(record.axiom_fields)

        return event

    def _worker(self):
        """
        后台工作线程，负责批处理和发送日志
        """
        while True:
            try:
                # 从队列获取事件，最多等待1秒
                try:
                    event = self.queue.get(timeout=1.0)
                    with self.lock:
                        self.batch.append(event)
                except queue.Empty:
                    # 队列为空，检查是否需要刷新
                    pass

                # 检查是否需要刷新
                with self.lock:
                    current_time = time.time()
                    should_flush = (
                        len(self.batch) >= BATCH_SIZE or
                        (len(self.batch) > 0 and current_time - self.last_flush >= FLUSH_INTERVAL)
                    )

                if should_flush:
                    self.flush()
            except Exception as e:
                # 记录错误但不中断线程
                print(f"Error in Axiom logger worker: {e}")

    def flush(self):
        """
        刷新批处理中的事件到Axiom
        """
        with self.lock:
            if not self.batch:
                return

            events_to_send = self.batch.copy()
            self.batch = []
            self.last_flush = time.time()

        # 发送事件
        try:
            self.client.ingest_events(self.dataset, events_to_send)
        except Exception as e:
            print(f"Error sending events to Axiom: {e}")


def get_axiom_client() -> axiom_py.Client:
    """
    获取Axiom客户端实例

    Returns:
        axiom_py.Client: Axiom客户端
    """
    if not AXIOM_TOKEN:
        raise RuntimeError("AXIOM_TOKEN not set")
    return axiom_py.Client(AXIOM_TOKEN)


def check_dataset_exists(client: axiom_py.Client, dataset: str) -> bool:
    """
    检查数据集是否存在

    Args:
        client: Axiom客户端
        dataset: 数据集名称

    Returns:
        bool: 数据集是否存在
    """
    try:
        # 尝试向数据集发送一个空事件，如果成功则表示数据集存在
        client.ingest_events(dataset, [])
        return True
    except Exception as e:
        if "404" in str(e) and "dataset not found" in str(e).lower():
            return False
        # 其他错误，假设数据集存在
        return True


def add_axiom_handler(logger: Optional[logging.Logger] = None,
                      dataset: str = DEFAULT_DATASET,
                      level: int = logging.INFO) -> None:
    """
    为指定的logger添加Axiom处理器

    Args:
        logger: 要添加处理器的logger，如果为None则使用根logger
        dataset: Axiom数据集名称
        level: 日志级别
    """
    if logger is None:
        logger = logging.getLogger()

    if not AXIOM_TOKEN:
        logger.warning("AXIOM_TOKEN not set; skip enabling Axiom logging")
        return

    # 创建Axiom客户端
    client = get_axiom_client()

    # 使用默认数据集 'dinq'，不检查数据集是否存在
    # 这样可以避免多次检查不同数据集导致的延迟
    dataset = DEFAULT_DATASET

    # 创建批处理Axiom处理器
    handler = BatchingAxiomHandler(client, dataset, level=level)

    # 添加处理器到logger
    logger.addHandler(handler)

    return handler


def log_with_context(logger: logging.Logger, level: int, msg: str,
                     context: Dict[str, Any] = None, **kwargs):
    """
    使用上下文信息记录日志

    Args:
        logger: 日志记录器
        level: 日志级别
        msg: 日志消息
        context: 上下文信息
        **kwargs: 其他参数
    """
    # 获取异常信息
    exc_info = kwargs.get('exc_info', None)
    if exc_info is True:  # 如果是True，获取当前异常
        import sys
        exc_info = sys.exc_info()

    # 创建日志记录
    record = logging.LogRecord(
        name=logger.name,
        level=level,
        pathname=kwargs.get('pathname', ''),
        lineno=kwargs.get('lineno', 0),
        msg=msg,
        args=(),
        exc_info=exc_info,
        func=kwargs.get('func', None),
    )

    # 添加上下文信息
    if context:
        record.axiom_fields = context

    # 处理日志记录
    logger.handle(record)


# 辅助函数，用于简化日志记录
def debug(logger, msg, context=None, **kwargs):
    log_with_context(logger, logging.DEBUG, msg, context, **kwargs)

def info(logger, msg, context=None, **kwargs):
    log_with_context(logger, logging.INFO, msg, context, **kwargs)

def warning(logger, msg, context=None, **kwargs):
    log_with_context(logger, logging.WARNING, msg, context, **kwargs)

def error(logger, msg, context=None, **kwargs):
    log_with_context(logger, logging.ERROR, msg, context, **kwargs)

def critical(logger, msg, context=None, **kwargs):
    log_with_context(logger, logging.CRITICAL, msg, context, **kwargs)
