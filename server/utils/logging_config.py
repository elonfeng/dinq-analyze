"""
Logging Configuration

This module provides a centralized logging configuration for the DINQ project.
It sets up file-based logging with rotation and console output, with support
for request tracing via unique trace IDs.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 导入Axiom日志处理器
try:
    from server.utils.axiom_logger import add_axiom_handler
    AXIOM_AVAILABLE = True
except ImportError:
    AXIOM_AVAILABLE = False

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    load_dotenv()
    dotenv_loaded = True
except ImportError:
    dotenv_loaded = False

class TraceFormatter(logging.Formatter):
    """
    Custom formatter that includes trace ID and request information in log messages.
    """

    def format(self, record):
        # Try to get trace ID from record extra or from trace context
        trace_id = getattr(record, 'trace_id', None)

        if not trace_id:
            # Try to import and get trace ID from context
            try:
                from server.utils.trace_context import TraceContext
                trace_id = TraceContext.get_trace_id()
            except ImportError:
                trace_id = None

        # Add trace ID to record
        if trace_id:
            record.trace_id = trace_id
        else:
            record.trace_id = 'no-trace'

        # Add request information if available
        user_id = getattr(record, 'user_id', None)
        method = getattr(record, 'method', None)
        path = getattr(record, 'path', None)

        # Build additional context string
        context_parts = []
        if user_id:
            context_parts.append(f"user:{user_id}")
        if method and path:
            context_parts.append(f"{method} {path}")

        if context_parts:
            record.request_context = f" [{' | '.join(context_parts)}]"
        else:
            record.request_context = ""

        return super().format(record)

def setup_logging(log_dir=None, log_level=None, enable_axiom=None):
    """
    Set up logging configuration for the application.

    Args:
        log_dir: Directory to store log files. If None, uses LOG_DIR from environment or creates 'logs' directory in project root.
        log_level: Logging level. If None, uses LOG_LEVEL from environment or defaults to INFO.

    Returns:
        Logger: Root logger
    """
    # Get log level from environment variable if not provided
    if log_level is None:
        log_level_str = os.environ.get('LOG_LEVEL', 'INFO')
        log_level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        log_level = log_level_map.get(log_level_str, logging.INFO)

    # Get log directory from environment variable if not provided
    if log_dir is None:
        env_log_dir = os.environ.get('LOG_DIR')
        if env_log_dir:
            log_dir = Path(env_log_dir)
        else:
            # Get project root directory
            project_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
            log_dir = project_root / 'logs'

    # Create directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicate logs
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Create formatters with trace ID support
    file_formatter = TraceFormatter(
        '%(asctime)s - [%(trace_id)s] - %(name)s - %(levelname)s - %(message)s%(request_context)s'
    )
    console_formatter = TraceFormatter(
        '%(asctime)s - [%(trace_id)s] - %(name)s - %(levelname)s - %(message)s%(request_context)s'
    )

    # 创建统一的日志文件 - 所有日志都输出到这里
    all_in_one_log_file = os.path.join(log_dir, 'dinq_allin_one.log')
    file_handler = RotatingFileHandler(
        all_in_one_log_file,
        maxBytes=50*1024*1024,  # 50MB 文件大小限制
        backupCount=10,         # 保留10个备份文件
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # 只添加统一的文件处理器和控制台处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 检查是否启用 Axiom 日志
    if enable_axiom is None:
        # 从环境变量读取配置，默认为启用
        axiom_enabled_str = os.environ.get('AXIOM_ENABLED', 'true').lower()
        enable_axiom = axiom_enabled_str in ('true', 'yes', '1', 'on')

    # Add Axiom handler if available and enabled
    if AXIOM_AVAILABLE and enable_axiom:
        try:
            # 获取 AXIOM_DATASET 环境变量，默认为 'dinq'
            axiom_dataset = os.environ.get('AXIOM_DATASET', 'dinq')
            add_axiom_handler(root_logger, dataset=axiom_dataset, level=log_level)
            root_logger.info(f"Axiom logging enabled. Dataset: {axiom_dataset}")
        except Exception as e:
            root_logger.error(f"Failed to initialize Axiom logging: {e}")

    # 创建模块特定的日志记录器 - 现在它们都会使用根日志记录器的处理器
    create_module_logger('server', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('server.api', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('server.api.scholar', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('server.api.scholar.name_scholar', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('server.services', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('server.utils', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('server.utils.auth', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('onepage', log_dir, log_level, file_formatter, enable_axiom)
    create_module_logger('account', log_dir, log_level, file_formatter, enable_axiom)

    # Log that logging has been set up
    root_logger.info(f"Unified logging initialized. All logs will be stored in {all_in_one_log_file}")

    return root_logger

def create_module_logger(module_name, log_dir, log_level, formatter, enable_axiom=None):
    """
    Create a logger for a specific module without its own log file.
    All logs will go to the unified log file via the root logger.

    Args:
        module_name: Name of the module
        log_dir: Directory to store log files (not used for individual files anymore)
        log_level: Logging level
        formatter: Log formatter
    """
    # Get module logger
    logger = logging.getLogger(module_name)
    logger.setLevel(log_level)

    # 确保日志传播到根日志记录器，这样所有日志都会进入统一的日志文件
    logger.propagate = True

    # 检查是否启用 Axiom 日志
    if enable_axiom is None:
        # 从环境变量读取配置，默认为启用
        axiom_enabled_str = os.environ.get('AXIOM_ENABLED', 'true').lower()
        enable_axiom = axiom_enabled_str in ('true', 'yes', '1', 'on')

    # Add Axiom handler if available and enabled
    if AXIOM_AVAILABLE and enable_axiom:
        try:
            # 使用单一数据集，避免多次检查不同数据集
            axiom_dataset = os.environ.get('AXIOM_DATASET', 'dinq')
            add_axiom_handler(logger, dataset=axiom_dataset, level=log_level)
        except Exception as e:
            logger.error(f"Failed to initialize Axiom logging for module {module_name}: {e}")
