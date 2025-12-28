# coding: UTF-8
"""
Scholar Service - Main module for Scholar API service.
Integrates data fetching, analysis, and visualization components.
"""

import os
import json
import copy
import time
import logging
from typing import Dict, Any, Optional, Callable

# 导入环境变量加载模块
from server.config.env_loader import load_environment_variables, get_env_var, log_dinq_environment_variables

# 导入获取最佳合作者的函数
from server.services.scholar.collaborator_service import get_best_collaborator

# 导入缓存验证器
from server.services.scholar.cache_validator import validate_and_complete_cache
from server.services.scholar.cancel import raise_if_cancelled

# 获取scholar服务的日志记录器（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger('server.services.scholar')
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger('server.services.scholar')

# 加载环境变量
load_environment_variables()

# 获取 DINQ_API_DOMAIN 环境变量
BASE_URL = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')
logger.info(f"BASE_URL set to: {BASE_URL}")

# 导入头像和描述相关工具函数
from server.utils.profile_utils import get_random_avatar, get_random_description, update_base_url

# 更新 profile_utils 中的 BASE_URL
update_base_url(BASE_URL)

# Import database cache modules
try:
    from server.api.scholar.db_cache import get_scholar_from_cache, save_scholar_to_cache
    DB_CACHE_AVAILABLE = True
except ImportError:
    logger.warning("Database cache modules not available")
    DB_CACHE_AVAILABLE = False

from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.analyzer import ScholarAnalyzer
from server.services.scholar.visualizer import ScholarVisualizer
from server.services.scholar.paper_summary import summarize_paper_of_year
from server.utils.find_arxiv import find_arxiv  # 在generate_report中使用
# 不再需要直接导入 get_author_detail，因为它已经在 collaborator_service 中使用
# 角色模型相关功能已移至 role_model_service 模块
from onepage.signature_news import get_latest_news  # 在generate_report中使用
from account.name_scholar import get_scholar_information
# 职级评估相关功能已移至 career_level_service 模块
from server.prompts.researcher_evaluator import generate_critical_evaluation
from server.services.scholar.status_reporter import (
    send_status,
)
from server.services.scholar.role_model_service import get_role_model
from server.services.scholar.pipeline import ScholarPipelineDeps, run_scholar_pipeline
import re
from urllib.parse import urlparse, parse_qs

class ScholarService:
    """
    Main service class for Scholar API functionality.
    Integrates data fetching, analysis, and visualization components.
    """

    def __init__(
        self,
        use_crawlbase: bool = False,
        api_token: Optional[str] = None,
        use_cache: bool = True,
        cache_max_age_days: int = 3,
        *,
        fetch_timeout_seconds: Optional[float] = None,
        fetch_max_retries: Optional[int] = None,
    ):
        """
        Initialize the Scholar Service with customizable data retrieval methods.

        Args:
            use_crawlbase (bool): Whether to use Crawlbase API instead of scholarly
            api_token (str): API token for Crawlbase if use_crawlbase is True
            use_cache (bool): Whether to use database cache
            cache_max_age_days (int): Maximum age of cache in days
        """
        self.data_fetcher = ScholarDataFetcher(
            use_crawlbase,
            api_token,
            fetch_timeout_seconds=fetch_timeout_seconds,
            fetch_max_retries=fetch_max_retries,
        )
        self.analyzer = ScholarAnalyzer()
        self.visualizer = ScholarVisualizer()
        self.tvly_client = None
        try:
            # Tavily 在一些 Python 版本上可能不兼容（或未安装），保持可选依赖，失败则回退到内部搜索。
            from tavily import TavilyClient  # type: ignore

            self.tvly_client = TavilyClient(os.getenv("TAVILY_API_KEY", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tavily client unavailable; fallback to internal scholar search: %s", exc)
        # Cache settings
        self.use_cache = use_cache and DB_CACHE_AVAILABLE
        self.cache_max_age_days = cache_max_age_days

    def extract_scholar_id_from_tavily_response(self,response):
        """
        从Tavily搜索结果中提取Google Scholar ID

        Args:
            response (dict): Tavily API的响应结果

        Returns:
            str or None: 找到的Scholar ID，如果没找到返回None
        """
        if not response or 'results' not in response:
            return None

        results = response['results']

        for result in results:
            url = result.get('url', '')

            # 检查是否是Google Scholar链接
            if 'scholar.google.com' in url and 'citations' in url:
                scholar_id = self.extract_scholar_id_from_url(url)
                if scholar_id:
                    return scholar_id

        return None

    def extract_scholar_id_from_url(self,url):
        """
        从Google Scholar URL中提取用户ID

        Args:
            url (str): Google Scholar的URL

        Returns:
            str or None: Scholar ID，如果解析失败返回None
        """
        try:
            # 解析URL
            parsed_url = urlparse(url)

            # 从查询参数中提取user ID
            query_params = parse_qs(parsed_url.query)

            if 'user' in query_params:
                return query_params['user'][0]

            # 如果查询参数中没有，尝试用正则表达式提取
            # 匹配 user=后面的ID
            match = re.search(r'user=([A-Za-z0-9_-]+)', url)
            if match:
                return match.group(1)

        except Exception as e:
            print(f"解析URL时出错: {e}")
            return None

        return None

    def generate_report(
        self,
        researcher_name=None,
        scholar_id=None,
        callback=None,
        cancel_event=None,
        user_id: Optional[str] = None,
    ):
        """
        Generate a comprehensive analysis report for a researcher.

        说明：
        - 具体逻辑已抽到 `server/services/scholar/pipeline.py`，按 6-stage 执行：
          search -> fetch_profile -> analyze -> enrich -> persist -> render
        - 通过 deps 注入解耦，便于单测/复用/替换抓取与 enrich 策略
        """

        if not researcher_name and not scholar_id:
            logger.error("Either researcher name or scholar ID must be provided")
            return None

        def _career_level(report: Dict[str, Any], from_cache: bool = False, cb: Optional[Callable] = None) -> Any:
            # Lazy import: reduce import overhead on startup.
            from server.services.scholar.career_level_service import get_career_level_info

            return get_career_level_info(report, from_cache=from_cache, callback=cb)

        deps = ScholarPipelineDeps(
            data_fetcher=self.data_fetcher,
            analyzer=self.analyzer,
            tvly_client=self.tvly_client,
            tavily_id_extractor=self.extract_scholar_id_from_tavily_response,
            use_cache=self.use_cache,
            cache_max_age_days=self.cache_max_age_days,
            cache_get=get_scholar_from_cache if self.use_cache else None,
            cache_save=save_scholar_to_cache if self.use_cache else None,
            cache_validate=validate_and_complete_cache if self.use_cache else None,
            avatar_provider=get_random_avatar,
            description_provider=get_random_description,
            best_collaborator=get_best_collaborator,
            arxiv_finder=find_arxiv,
            news_provider=get_latest_news,
            role_model_provider=get_role_model,
            career_level_provider=_career_level,
            critical_evaluator=generate_critical_evaluation,
            paper_summary_provider=summarize_paper_of_year,
            logger=logger,
            max_enrich_workers=5,
        )

        logger.info(
            "Generating report for %s...",
            f"ID: {scholar_id}" if scholar_id else f"Name: {researcher_name}",
        )

        return run_scholar_pipeline(
            deps=deps,
            researcher_name=researcher_name,
            scholar_id=scholar_id,
            user_id=user_id,
            callback=callback,
            cancel_event=cancel_event,
            status_sender=send_status,
        )

    def export_report_json(self, report, filename):
        """
        Export the analysis report as JSON.

        Args:
            report (dict): Analysis report
            filename (str): Output filename

        Returns:
            bool: Success status
        """
        if not report:
            logger.error("No report data to export")
            return False

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"Report exported to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return False

def run_scholar_analysis(
    researcher_name=None,
    scholar_id=None,
    use_crawlbase=True,
    api_token=None,
    callback=None,
    use_cache=True,
    cache_max_age_days=3,
    cancel_event=None,
    user_id: Optional[str] = None,
):
    """
    Run a complete scholar analysis and print the results.

    Args:
        researcher_name (str, optional): Name of the researcher
        scholar_id (str, optional): Google Scholar ID
        use_crawlbase (bool): Whether to use Crawlbase API
        api_token (str, optional): API token for Crawlbase
        callback (callable, optional): A callback function that will be called with status updates
        use_cache (bool, optional): Whether to use database cache
        cache_max_age_days (int, optional): Maximum age of cache in days

    Returns:
        dict: Analysis report
    """
    # Initialize the service
    scholar_service = ScholarService(use_crawlbase=use_crawlbase, api_token=api_token, use_cache=use_cache, cache_max_age_days=cache_max_age_days)

    # 初始化author_info变量
    # author_info = {}

    # If no scholar_id but name is provided, try to get scholar_id from name
    # if not scholar_id and researcher_name:
    #     # 限制研究者名称的长度，防止上下文长度超限
    #     max_name_length = 150  # 设置一个合理的最大长度
    #     logger.info(f"Getting scholar information for researcher: {researcher_name} (length: {len(researcher_name)})")
    #     send_status(f"Getting scholar ID for: {researcher_name}", callback, progress=5.0)

    #     start_time = time.time()
    #     author_info = get_scholar_information(researcher_name.lower(), max_length=max_name_length)
    #     end_time = time.time()
    #     print(f"get_scholar_information time :{end_time - start_time}")
    #     print(author_info)
    #     scholar_id = author_info.get('scholar_id')

    #     # 检查是否有错误
    #     if 'error' in author_info and author_info.get('error'):
    #         error_msg = author_info.get('error')
    #         logger.warning(f"Error getting scholar information: {error_msg}")
    #         send_status(f"Warning: {error_msg}", callback)

    #     if scholar_id is None:
    #         send_status("No scholar ID found. Please manually input the scholar ID!", callback)
    #         return None

    # Start timing
    t1 = time.time()

    # Generate the report with callback
    report = scholar_service.generate_report(
        researcher_name=researcher_name,
        scholar_id=scholar_id,
        callback=callback,
        cancel_event=cancel_event,
        user_id=user_id,
    )
    if not report:
        return None

    # 删除缓存标志，不要暴露给外部
    if '_from_cache' in report:
        del report['_from_cache']

    # 计算总耗时
    elapsed_time = time.time() - t1
    logger.info(f"Total analysis time: {elapsed_time:.2f} seconds")

    # 返回报告
    return report

if __name__ == "__main__":
    # Example usage
    # Import API keys from centralized configuration
    from server.config.api_keys import API_KEYS

    # Crawlbase API configuration
    api_token = API_KEYS['CRAWLBASE_API_TOKEN']

    # Run analysis for a researcher
    researcher_name = "Peiqin Lin, LMU"
    run_scholar_analysis(researcher_name=researcher_name, use_crawlbase=True, api_token=api_token)
