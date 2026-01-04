# coding: UTF-8
"""
Scholar Service - Main module for Scholar API service.
Integrates data fetching, analysis, and visualization components.
"""

import os
import json
import copy
import time
import sys
import random
import logging
from typing import Dict, Any, Optional, Callable

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# 导入环境变量加载模块
from server.config.env_loader import load_environment_variables, get_env_var, log_dinq_environment_variables

# 导入获取最佳合作者的函数
from server.services.scholar.collaborator_service import get_best_collaborator

# 导入缓存验证器
from server.services.scholar.cache_validator import validate_and_complete_cache

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
    report_initial_status,
    report_analysis_completion,
)
from server.services.scholar.role_model_service import get_role_model
from tavily import TavilyClient
import re
from urllib.parse import urlparse, parse_qs
        
class ScholarService:
    """
    Main service class for Scholar API functionality.
    Integrates data fetching, analysis, and visualization components.
    """

    def __init__(self, use_crawlbase=False, api_token=None, use_cache=True, cache_max_age_days=3):
        """
        Initialize the Scholar Service with customizable data retrieval methods.

        Args:
            use_crawlbase (bool): Whether to use Crawlbase API instead of scholarly
            api_token (str): API token for Crawlbase if use_crawlbase is True
            use_cache (bool): Whether to use database cache
            cache_max_age_days (int): Maximum age of cache in days
        """
        self.data_fetcher = ScholarDataFetcher(use_crawlbase, api_token)
        self.analyzer = ScholarAnalyzer()
        self.visualizer = ScholarVisualizer()

        # Tavily is optional (and should not carry a hard-coded default key).
        self.tvly_client = None
        try:
            tavily_key = os.getenv("TAVILY_API_KEY", "")
            self.tvly_client = TavilyClient(tavily_key) if tavily_key else None
        except Exception as e:
            logger.warning(f"Failed to initialize Tavily client: {e}")
            self.tvly_client = None
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

    def generate_report(self, researcher_name=None, scholar_id=None, callback=None, simplyfy_flag  = None, cancel_event=None, user_id: Optional[str] = None):
        """
        Generate a comprehensive analysis report for a researcher.

        Args:
            researcher_name (str, optional): Name of the researcher
            scholar_id (str, optional): Google Scholar ID
            callback (callable, optional): A callback function that will be called with status updates

        Returns:
            dict: Analysis report
        """
        # Validate input
        if not researcher_name and not scholar_id:
            logger.error("Either researcher name or scholar ID must be provided")
            return None

        # 报告初始状态
        report_initial_status(researcher_name, scholar_id, callback)
        logger.info(f"Generating report for {'ID: ' + scholar_id if scholar_id else 'Name: ' + researcher_name}...")

        # 如果启用缓存且提供了scholar_id，尝试从缓存获取
        if self.use_cache :
            logger.info(f"Checking cache for scholar ID: {scholar_id}...")
            cached_data = get_scholar_from_cache(scholar_id, self.cache_max_age_days,name=researcher_name)
            if cached_data:
                logger.info(f"Found recent data in cache for scholar ID: {scholar_id}")

                # 验证并补全缓存数据
                logger.info("Validating and completing cached data...")
                send_status("Validating cached data...", callback, progress=20.0)
                validated_data = validate_and_complete_cache(
                    cached_data,
                    self.data_fetcher,
                    self.analyzer,
                    callback
                )

                # 添加标志表示数据来自缓存
                if isinstance(validated_data, dict):
                    validated_data['_from_cache'] = True

                # 报告分析完成（从缓存）
                report_analysis_completion(0.0, True, callback)
                return validated_data

        # Step 1: Search for the researcher
        send_status(f"Getting scholar ID for: {researcher_name}", callback, progress=5.0)
        if not scholar_id and self.tvly_client is not None:
            response = self.tvly_client.search(query=researcher_name)
            scholar_id = self.extract_scholar_id_from_tavily_response(response)
        
        if scholar_id:
            author_info = {"scholar_id": scholar_id}
        else:
            author_info = self.data_fetcher.search_researcher(name=researcher_name, scholar_id=scholar_id)
        if not author_info:
            logger.error(f"Could not find researcher {'ID: ' + scholar_id if scholar_id else 'Name: ' + researcher_name}")
            send_status("No scholar ID found. Please manually input the scholar ID!", callback)
            return None
        if not scholar_id:
            scholar_id = author_info["scholar_id"]

        # Step 2: Get full profile with publications
        send_status("Retrieving full profile...", callback, progress=20.0)
        author_data = self.data_fetcher.get_full_profile(author_info)
        if not author_data:
            logger.error("Could not retrieve full profile")
            return None

        # 报告基本学者信息
        researcher_name = author_data.get('name', '')
        send_status(f"Found researcher: {researcher_name}", callback, progress=25.0)

        # Step 3: Analyze publications
        send_status("Analyzing publications...", callback, progress=35.0)
        pub_stats = self.analyzer.analyze_publications(author_data)

        # Step 4: Analyze co-authors
        coauthor_stats = {}
        if not simplyfy_flag:
            send_status("Analyzing co-authors...", callback, progress=45.0)
            coauthor_stats = self.analyzer.analyze_coauthors(author_data)

        
        # Step 5: Calculate researcher rating
        send_status("Calculating researcher rating...", callback, progress=50.0)
        rating = self.analyzer.calculate_researcher_rating(author_data, pub_stats)

        # Step 6: Find most frequent collaborator details
        send_status("Finding most frequent collaborator...", callback, progress=55.0)

        # 添加主要作者名称到coauthor_stats
        if not simplyfy_flag:
            coauthor_stats['main_author'] = author_data.get('name', '')

        # Get researcher name for description
        researcher_name = author_data.get('name', '')

        # Generate random avatar and description
        send_status("Generating avatar and description...", callback, progress=70.0)
        avatar_url = get_random_avatar()
        description = get_random_description(researcher_name) if researcher_name else "A brilliant researcher exploring the frontiers of knowledge."


        # Compile the report
        send_status("Compiling report...", callback, progress=75.0)
        report = {
            'researcher': {
                'name': researcher_name,
                'abbreviated_name': author_data.get('abbreviated_name', ''),
                'affiliation': author_data.get('affiliation', ''),
                'email': author_data.get('email', ''),
                'research_fields': author_data.get('research_fields', []),
                'total_citations': author_data.get('total_citations', 0),
                'citations_5y': author_data.get('citations_5y', 0),
                'h_index': author_data.get('h_index', 0),
                'h_index_5y': author_data.get('h_index_5y', 0),
                'yearly_citations': author_data.get('yearly_citations', {}),
                'scholar_id': scholar_id or author_data.get('scholar_id', ''),  # 添加学者ID
                'avatar': avatar_url,  # 添加头像URL
                'description': description  # 添加描述
            },
            'publication_stats': pub_stats,
            'coauthor_stats': coauthor_stats,
            'rating': rating,
            'most_frequent_collaborator': None,  # 稍后从线程结果中获取
            "paper_news": pub_stats.get('paper_news', {})
        }
        if not simplyfy_flag:
            # 多线程并行执行后续步骤
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import random

            # 用于存储线程执行结果
            thread_results = {}

            def get_arxiv_info(title):
                """获取arXiv信息的线程函数"""
                try:
                    most_cited_ai_paper = find_arxiv(title)
                    return ('arxiv', most_cited_ai_paper)
                except Exception as e:
                    logger.error(f"Error finding arxiv: {str(e)}")
                    return ('arxiv', {"name": title, "arxiv_url": "", "image": ""})
        
            def get_news_info(title):
                """获取新闻信息的线程函数"""
                try:
                    news_info = get_latest_news(title)
                    return ('news', news_info)
                except Exception as e:
                    logger.error(f"Error getting news information: {str(e)}")
                    return ('news', "No related news found.")

            def summarize_paper_of_year_thread(paper):
                """生成当年代表论文摘要的线程函数"""
                try:
                    summary = summarize_paper_of_year(paper)
                    return ('paper_of_year_summary', summary)
                except Exception as e:
                    logger.error(f"Error summarizing paper of year: {e}")
                    return ('paper_of_year_summary', '')

            def get_role_model_info(report_data):
                """获取角色模型信息的线程函数"""
                try:
                    role_model = get_role_model(report_data)
                    return ('role_model', role_model)
                except Exception as e:
                    logger.error(f"Error getting role model: {str(e)}")
                    return ('role_model', None)

            def get_career_level_info_thread(report_data):
                """获取职级信息的线程函数"""
                try:
                    from server.services.scholar.career_level_service import get_career_level_info
                    get_career_level_info(report_data, False, callback)
                    return ('career_level', True)
                except Exception as e:
                    logger.error(f"Error getting career level info: {str(e)}")
                    return ('career_level', False)

            def generate_critical_evaluation_thread(report_data):
                """生成学者评价的线程函数"""
                try:
                    critical_evaluation = generate_critical_evaluation(report_data)
                    return ('critical_evaluation', critical_evaluation)
                except Exception as e:
                    logger.error(f"Error generating critical evaluation: {e}")
                    return ('critical_evaluation', "Error generating critical evaluation.")

            def get_best_collaborator_thread(data_fetcher, coauthor_stats, callback, analyzer):
                """获取最佳合作者的线程函数"""
                try:
                    most_frequent_collaborator = get_best_collaborator(
                        data_fetcher,
                        coauthor_stats,
                        callback=callback,
                        analyzer=analyzer
                    )
                    return ('most_frequent_collaborator', most_frequent_collaborator)
                except Exception as e:
                    logger.error(f"Error getting best collaborator: {e}")
                    return ('most_frequent_collaborator', None)

            # 准备并行执行的任务
            tasks = []

            # 添加get_best_collaborator任务
            tasks.append(('best_collaborator', get_best_collaborator_thread, (self.data_fetcher, coauthor_stats, callback, self.analyzer)))

            # 如果有最具引用论文，添加arXiv和新闻获取任务
            if 'most_cited_paper' in pub_stats and pub_stats['most_cited_paper']:
                most_cited = pub_stats['most_cited_paper']
                title = most_cited.get('title', 'Unknown Title')

                tasks.append(('arxiv', get_arxiv_info, (title,)))
                tasks.append(('news', get_news_info, (title,)))

            # 添加其他任务
            tasks.append(('role_model', get_role_model_info, (report,)))
            tasks.append(('career_level', get_career_level_info_thread, (report,)))
            tasks.append(('critical_evaluation', generate_critical_evaluation_thread, (report,)))

            paper_of_year = pub_stats.get('paper_of_year')
            if paper_of_year:
                tasks.append(('paper_of_year_summary', summarize_paper_of_year_thread, (paper_of_year,)))

            # 状态更新消息
            status_messages = [
                ("Finding most frequent collaborator...", 55.0),
                ("Processing most cited paper information...", 60.0),
                ("Finding arXiv information...", 62.0),
                ("Getting news related to paper...", 65.0),
                ("Getting role model information...", 80.0),
                ("Calculating career level information...", 85.0),
                ("Generating critical evaluation...", 90.0)
            ]
        
            # 同时启动业务逻辑和状态更新
            parallel_start = time.time()
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 提交所有业务任务
                future_to_task = {}
                for task_name, func, args in tasks:
                    future = executor.submit(func, *args)
                    future_to_task[future] = task_name

                # 在主线程中发送状态更新（与业务逻辑并行）
                status_index = 0
                while status_index < len(status_messages):
                    message, progress = status_messages[status_index]
                    send_status(message, callback, progress=progress)
                    time.sleep(random.uniform(2.0, 3.0))
                    status_index += 1

                # 等待所有业务任务完成
                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        result_type, result_data = future.result()
                        thread_results[result_type] = result_data
                        logger.info(f"Thread task {task_name} completed successfully")
                    except Exception as e:
                        logger.error(f"Thread task {task_name} failed: {str(e)}")
                        thread_results[task_name] = None
        
            parallel_elapsed = time.time() - parallel_start
            print(f"[计时] 多线程并行处理总耗时: {parallel_elapsed:.2f}秒")
        
            # 将结果整合到报告中
            if 'most_frequent_collaborator' in thread_results and thread_results['most_frequent_collaborator']:
                report['most_frequent_collaborator'] = thread_results['most_frequent_collaborator']

            if 'arxiv' in thread_results and thread_results['arxiv']:
                pub_stats['most_cited_ai_paper'] = thread_results['arxiv']

            if 'news' in thread_results and thread_results['news']:
                pub_stats['paper_news'] = thread_results['news']

            if 'role_model' in thread_results and thread_results['role_model']:
                report['role_model'] = thread_results['role_model']

            if 'critical_evaluation' in thread_results and thread_results['critical_evaluation']:
                report['critical_evaluation'] = thread_results['critical_evaluation']

            if 'paper_of_year_summary' in thread_results and pub_stats.get('paper_of_year'):
                summary_text = thread_results['paper_of_year_summary']
                if summary_text:
                    pub_stats['paper_of_year']['summary'] = summary_text

            # 更新报告中的paper_news
            report["paper_news"] = pub_stats.get('paper_news', {})
        

            # 如果启用缓存且有scholar_id，将数据保存到缓存
            # 但如果数据本身就来自缓存，就不需要再保存了
            if self.use_cache and (scholar_id or author_data.get('scholar_id')) and not report.get('_from_cache', False):
                cache_scholar_id = scholar_id or author_data.get('scholar_id')
                logger.info(f"Saving data to cache for scholar ID: {cache_scholar_id}")
                send_status("Saving data to cache...", callback, progress=95.0)
                save_scholar_to_cache(report, cache_scholar_id)

        # 如果有_from_cache标志，在返回前删除它，不要暴露给外部
        if '_from_cache' in report:
            del report['_from_cache']

        # 报告分析完成
        elapsed_time = 0.0  # 这里不计算时间，因为我们在函数内部无法知道开始时间
        report_analysis_completion(elapsed_time, False, callback)
        send_status("Analysis complete!", callback, progress=100.0)
  
        return report

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
    simplyfy_flag=None,
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
        simplyfy_flag=simplyfy_flag,
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
