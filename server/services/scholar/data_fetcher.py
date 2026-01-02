# coding: UTF-8
"""
Data fetcher module for Scholar API service.
Handles retrieving data from Google Scholar using either scholarly or Crawlbase.
"""

import re
import os
import time
import urllib.parse
import copy
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional
import hashlib
# 导入日志配置
from server.utils.logging_config import setup_logging
import logging.handlers  # 导入 handlers 模块用于 RotatingFileHandler
try:
    from firecrawl import FirecrawlApp
except Exception:  # noqa: BLE001
    FirecrawlApp = None
# 确保日志目录存在
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs'))
os.makedirs(log_dir, exist_ok=True)

# 初始化日志配置
# 注意：如果日志配置已经在其他地方初始化，这里的调用不会有副作用
setup_logging(log_dir)

# 创建模块日志记录器（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger('server.services.scholar.data_fetcher')
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger('server.services.scholar.data_fetcher')

# 确保模块日志记录器有文件处理器
# 创建一个新的文件处理器，专门用于这个模块
module_log_file = os.path.join(log_dir, 'data_fetcher.log')
file_handler = logging.handlers.RotatingFileHandler(
    module_log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.DEBUG)  # 设置为 DEBUG 级别，捕获所有日志

# 添加处理器到真实的logger对象
try:
    from server.utils.trace_context import get_real_logger
    real_logger = get_real_logger('server.services.scholar.data_fetcher')
    real_logger.addHandler(file_handler)
    real_logger.setLevel(logging.DEBUG)
except ImportError:
    # Fallback: 如果是普通logger，直接添加
    if hasattr(logger, 'addHandler'):
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
    else:
        # 如果是TraceLoggerAdapter，获取底层logger
        real_logger = getattr(logger, 'logger', logging.getLogger('server.services.scholar.data_fetcher'))
        real_logger.addHandler(file_handler)
        real_logger.setLevel(logging.DEBUG)

from bs4 import BeautifulSoup
# ProxyGenerator is imported but not used as we're disabling proxies
try:
    from scholarly import scholarly
except Exception:  # noqa: BLE001
    scholarly = None
try:
    from crawlbase import CrawlingAPI
except Exception:  # noqa: BLE001
    CrawlingAPI = None
from server.utils.utils import has_chinese, fuzzy_match_name, fuzzy_match_name_improved
from onepage.author_paper import find_authors_from_title
from server.services.scholar.cancel import raise_if_cancelled
from server.services.scholar.text_normalize import normalize_scholar_paper_title
from server.services.scholar.http_fetcher import (
    CrawlbaseHTMLFetcher,
    FetcherPolicy,
    FirecrawlHTMLFetcher,
    RequestsHTMLFetcher,
    RequestsJSONFetcher,
    QuotaExceeded,
)
from server.config.env_loader import load_environment_variables
from server.utils.timing import elapsed_ms, now_perf

class ScholarDataFetcher:
    """
    Handles fetching data from Google Scholar using either scholarly or Crawlbase.
    """

    def __init__(
        self,
        use_crawlbase: bool = False,
        api_token: Optional[str] = None,
        *,
        fetch_timeout_seconds: Optional[float] = None,
        fetch_max_retries: Optional[int] = None,
    ):
        """
        Initialize the data fetcher with customizable retrieval methods.

        Args:
            use_crawlbase (bool): Whether to use Crawlbase API instead of scholarly
            api_token (str): API token for Crawlbase if use_crawlbase is True
        """
        # 测试日志系统
        logger.debug("DataFetcher initialization started - DEBUG level test")
        logger.info("DataFetcher initialization started - INFO level test")
        logger.warning("DataFetcher initialization started - WARNING level test")


        # Ensure .env files are loaded for scripts/tests that don't import API_KEYS.
        load_environment_variables(log_dinq_vars=False)

        if api_token is None:
            api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN")

        self.use_crawlbase = bool(use_crawlbase and api_token)
        self.api_token = api_token
        self.scholar_name = None  # 添加scholar_name属性

        # --- Fetching abstractions -------------------------------------------------
        # 统一：retry/backoff/timeout/cache/rate-limit + “更像真人”的访问节奏
        disk_cache_dir = os.getenv("DINQ_SCHOLAR_FETCH_DISK_CACHE_DIR")
        try:
            disk_cache_ttl_seconds = float(os.getenv("DINQ_SCHOLAR_FETCH_DISK_CACHE_TTL_SECONDS", "86400"))
        except (TypeError, ValueError):
            disk_cache_ttl_seconds = 86400.0

        timeout_seconds = None
        if fetch_timeout_seconds is not None:
            try:
                timeout_seconds = float(fetch_timeout_seconds)
            except (TypeError, ValueError):
                timeout_seconds = None
        if timeout_seconds is None:
            raw = os.getenv("DINQ_SCHOLAR_FETCH_TIMEOUT_SECONDS")
            if raw is not None:
                try:
                    timeout_seconds = float(raw)
                except (TypeError, ValueError):
                    timeout_seconds = None
        if timeout_seconds is None:
            timeout_seconds = 30.0
        timeout_seconds = max(1.0, min(float(timeout_seconds), 120.0))

        max_retries = None
        if fetch_max_retries is not None:
            try:
                max_retries = int(fetch_max_retries)
            except (TypeError, ValueError):
                max_retries = None
        if max_retries is None:
            raw = os.getenv("DINQ_SCHOLAR_FETCH_MAX_RETRIES")
            if raw is not None:
                try:
                    max_retries = int(raw)
                except (TypeError, ValueError):
                    max_retries = None
        if max_retries is None:
            max_retries = 3
        max_retries = max(0, min(int(max_retries), 5))

        try:
            max_inflight_per_domain = int(os.getenv("DINQ_SCHOLAR_FETCH_MAX_INFLIGHT_PER_DOMAIN", "1"))
        except (TypeError, ValueError):
            max_inflight_per_domain = 1

        try:
            quota_max_per_day = int(os.getenv("DINQ_SCHOLAR_FETCH_QUOTA_MAX_PER_DAY", "0"))
        except (TypeError, ValueError):
            quota_max_per_day = 0

        quota_state_path = os.getenv("DINQ_SCHOLAR_FETCH_QUOTA_STATE_PATH")
        if quota_state_path is None and disk_cache_dir:
            quota_state_path = os.path.join(disk_cache_dir, "quota.json")

        self._fetch_policy_direct = FetcherPolicy(
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            disk_cache_dir=disk_cache_dir,
            disk_cache_ttl_seconds=disk_cache_ttl_seconds,
            max_inflight_per_domain=max_inflight_per_domain,
            quota_max_requests_per_day=quota_max_per_day,
            quota_state_path=quota_state_path,
        )
        # Crawlbase/Firecrawl 通常更稳定：默认不做 pacing/配额限制，但可复用 disk cache。
        self._fetch_policy_crawlbase = FetcherPolicy(
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            min_interval_seconds=0.0,
            jitter_seconds=0.0,
            disk_cache_dir=disk_cache_dir,
            disk_cache_ttl_seconds=disk_cache_ttl_seconds,
            max_inflight_per_domain=max_inflight_per_domain,
        )
        self._fetch_policy_firecrawl = FetcherPolicy(
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            min_interval_seconds=0.0,
            jitter_seconds=0.0,
            disk_cache_dir=disk_cache_dir,
            disk_cache_ttl_seconds=disk_cache_ttl_seconds,
            max_inflight_per_domain=max_inflight_per_domain,
        )

        self._requests_session = requests.Session()
        self._requests_fetcher = RequestsHTMLFetcher(self._requests_session, policy=self._fetch_policy_direct)
        self._requests_json_fetcher = RequestsJSONFetcher(self._requests_session, policy=self._fetch_policy_direct)

        # Firecrawl 用于补全 author detail 等场景，和 use_crawlbase 无关
        firecrawl_api_key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
        if FirecrawlApp is None or not firecrawl_api_key:
            self.firecrawl_app = None
        else:
            self.firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
        self._firecrawl_fetcher = (
            FirecrawlHTMLFetcher(self.firecrawl_app, policy=self._fetch_policy_firecrawl)
            if self.firecrawl_app is not None
            else None
        )

        self.crawling_api = None
        self._crawlbase_fetcher = None
        if use_crawlbase:
            if CrawlingAPI is None:
                logger.warning("Crawlbase disabled (missing crawlbase dependency)")
                use_crawlbase = False
            elif not api_token:
                raise ValueError("API token is required when using Crawlbase")
            else:
                self.crawling_api = CrawlingAPI({'token': api_token})
                self._crawlbase_fetcher = CrawlbaseHTMLFetcher(self.crawling_api, policy=self._fetch_policy_crawlbase)
                logger.info("Crawlbase API initialized successfully")
        else:
            # 完全禁用代理功能，直接使用无代理模式
            logger.info("Using scholarly without proxy (completely disabled for testing)")

        logger.info(f"DataFetcher initialized with use_crawlbase={use_crawlbase}")

    def fetch_html(self, url, cancel_event=None, user_id=None):
        """
        Fetch HTML content from a URL.

        - use_crawlbase=True: Crawlbase（通常更稳）
        - use_crawlbase=False: requests + “更像真人”的节奏策略（降低封禁概率）

        Args:
            url (str): URL to fetch

        Returns:
            str: HTML content
        """
        try:
            raise_if_cancelled(cancel_event)
            fetcher = (
                self._crawlbase_fetcher
                if self.use_crawlbase and self._crawlbase_fetcher is not None
                else self._requests_fetcher
            )
            html_content = fetcher.fetch_html(url, cancel_event=cancel_event, user_id=user_id)
            if not html_content:
                logger.error("Failed to fetch HTML for URL: %s", url)
            return html_content
        except QuotaExceeded:
            raise
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
        
    def fetch_html_firecrawl(self, url, cancel_event=None, user_id=None):
        """
        Fetch HTML content from a URL using Firecrawl.

        Args:
            url (str): URL to fetch

        Returns:
            str: HTML content
        """
        try:
            raise_if_cancelled(cancel_event)
            if self._firecrawl_fetcher is None:
                logger.info("Firecrawl disabled (missing FIRECRAWL_API_KEY)")
                return None

            html_content = self._firecrawl_fetcher.fetch_html(url, cancel_event=cancel_event, user_id=user_id)
            if not html_content:
                logger.error("Failed to fetch HTML via Firecrawl for URL: %s", url)
            return html_content

        except QuotaExceeded:
            raise
        except Exception as e:
            logger.error("Error fetching URL %s via Firecrawl: %s", url, e)
            return None

    def fetch_json(self, url, cancel_event=None, user_id=None):
        """
        Fetch JSON data from a URL (requests-based).

        Args:
            url (str): URL to fetch

        Returns:
            Any: Parsed JSON (dict/list/primitive) or None
        """
        try:
            raise_if_cancelled(cancel_event)
            return self._requests_json_fetcher.fetch_json(url, cancel_event=cancel_event, user_id=user_id)
        except QuotaExceeded:
            raise
        except Exception as e:
            logger.error("Error fetching JSON %s: %s", url, e)
            return None

    def search_researcher(self, name=None, scholar_id=None, user_id=None):
        """
        Search for a researcher by name or Google Scholar ID.

        Args:
            name (str, optional): Name of the researcher
            scholar_id (str, optional): Google Scholar ID

        Returns:
            dict: Basic author information
        """
        if self.use_crawlbase:
            if scholar_id:
                # 如果提供了 scholar_id，直接使用它
                return {"scholar_id": scholar_id}
            elif name:
                # 如果只提供了姓名，使用 search_author_by_name 方法搜索
                logger.info(f"Searching for researcher by name: {name}...")
                authors = self.search_author_by_name_new(name, user_id=user_id)
                if authors and len(authors) > 0:
                    # 找到匹配的作者，使用第一个结果
                    scholar_id = authors[0].get('scholar_id')
                    logger.info(f"Found matching author with ID: {scholar_id}")
                    return {"scholar_id": scholar_id, "name": name}
                else:
                    logger.warning(f"No matching authors found for: {name}")
                    return None
            else:
                logger.error("Error: Either name or scholar_id must be provided")
                return None
        else:
            logger.info(f"Searching for researcher: {name or scholar_id}...")
            if scholar_id:
                # Search by ID if provided
                try:
                    author = scholarly.search_author_id(scholar_id)
                    logger.info(f"[Scholar ID: {scholar_id}] Found author data")
                    return author
                except Exception as e:
                    logger.error(f"[Scholar ID: {scholar_id}] Error searching by ID: {e}")
                    return None
            else:
                # Search by name
                search_query = scholarly.search_author(name)
                try:
                    author = next(search_query)
                    scholar_id = author.get('scholar_id', 'unknown_id')
                    logger.info(f"[Scholar ID: {scholar_id}] Found author data for {name}")
                    return author
                except StopIteration:
                    logger.warning(f"No results found for {name}")
                    return None

    def search_paper_authors(self, paper_title, exclude_scholar_id=None):
        """
        Search for authors of a specific paper by its title and get their Scholar IDs.

        Args:
            paper_title (str): Title of the paper
            exclude_scholar_id (str, optional): Scholar ID to exclude from results (e.g., the main researcher)

        Returns:
            list: List of authors with their Google Scholar IDs
        """
        if not paper_title:
            logger.error("Error: Empty paper title provided")
            return []

        logger.info(f"Searching for paper: {paper_title}...")

        # Encode the paper title for URL
        encoded_title = urllib.parse.quote(paper_title)
        search_url = f"https://scholar.google.com/scholar?q={encoded_title}"

        # Fetch the search results page
        html_content = self.fetch_html(search_url)

        if not html_content:
            logger.error(f"Failed to fetch search results for paper: {paper_title}")
            return []

        # Parse the search results
        soup = BeautifulSoup(html_content, 'html.parser')
        search_results = soup.find_all('div', class_='gs_ri')

        authors_info = []

        for result in search_results:
            title_element = result.find('h3', class_='gs_rt')
            if not title_element:
                continue

            # Check if this result matches our paper title
            result_title = title_element.get_text().strip()
            if paper_title.lower() in result_title.lower():
                # Found matching paper, extract authors
                authors_element = result.find('div', class_='gs_a')
                if not authors_element:
                    continue

                # Extract author links (authors_text is not used directly but kept for debugging if needed)
                _ = authors_element.get_text()  # Store in _ to indicate intentionally unused
                author_links = authors_element.find_all('a')

                for author_link in author_links:
                    href = author_link.get('href', '')
                    author_name = author_link.get_text().strip()

                    # Extract Scholar ID from the URL
                    user_id_match = re.search(r'user=([^&]+)', href)
                    if user_id_match:
                        scholar_id = user_id_match.group(1)

                        # Skip if this is the ID we want to exclude
                        if exclude_scholar_id and scholar_id == exclude_scholar_id:
                            logger.info(f"[Scholar ID: {scholar_id}] Excluding main researcher: {author_name}")
                            continue

                        authors_info.append({
                            'name': author_name,
                            'scholar_id': scholar_id,
                            'profile_url': f"https://scholar.google.com/citations?user={scholar_id}"
                        })

                # If we found the paper and extracted authors, we can stop
                if authors_info:
                    break

        # Log the results
        if authors_info:
            logger.info(f"Found {len(authors_info)} authors for paper: {paper_title}")
            for i, author in enumerate(authors_info, 1):
                logger.info(f"[Scholar ID: {author['scholar_id']}] Author {i}: {author['name']}")
        else:
            logger.warning(f"No authors found for paper: {paper_title}")

        return [author['scholar_id'] for author in authors_info]

    def search_author_by_name(self, author_name, paper_title=None, user_id=None):
        """
        Search for an author by name on Google Scholar.

        Args:
            author_name (str): Author name to search for
            paper_title (str, optional): Title of a paper by this author, used to get full name

        Returns:
            list: List of matching author information
        """
        logger.info(f"Searching for author: {author_name}")

        if "," in author_name:
            base_name = author_name.split(",", 1)[0].strip()
            if base_name:
                logger.info("Using base name '%s' from '%s'", base_name, author_name)
                author_name = base_name

        # If we have a paper title, try to find the full author name first
        if paper_title:
            logger.info(f"Trying to find full name for {author_name} using paper: {paper_title}")
            # Get the full author list from the paper
            candidate_author_list = find_authors_from_title(paper_title)

            if candidate_author_list:
                # Try to match the abbreviated name with a full name
                closest_match = fuzzy_match_name(author_name, candidate_author_list)

                if closest_match:
                    closest_match = closest_match.strip()
                    # Handle cases like "Alexander and ..." which can trigger bugs
                    if " and " in closest_match:
                        closest_match = closest_match.split("and")[-1].strip()

                    logger.info(f"Found full name match: {closest_match} for {author_name}")
                    # Use the full name for the search instead
                    author_name = closest_match

        # Encode the author name for URL
        encoded_name = urllib.parse.quote(author_name)
        search_url = f"https://scholar.google.com/citations?view_op=search_authors&mauthors={encoded_name}&hl=en"

        # Fetch the search results page (Firecrawl first, then fallback)
        html_content = self.fetch_html_firecrawl(search_url, user_id=user_id)
        if not html_content:
            html_content = self.fetch_html(search_url, user_id=user_id)
        if not html_content:
            logger.error(f"Failed to fetch author search results for: {author_name}")
            return []

        # Parse the search results
        soup = BeautifulSoup(html_content, 'html.parser')
        author_results = soup.find_all('div', class_='gsc_1usr')

        authors_info = []

        for result in author_results:
            name_element = result.find('h3', class_='gs_ai_name')
            if not name_element:
                continue

            name = name_element.text.strip()

            # Extract Scholar ID from the URL
            link_element = name_element.find('a')
            if not link_element:
                continue

            href = link_element.get('href', '')
            user_id_match = re.search(r'user=([^&]+)', href)
            if not user_id_match:
                continue

            scholar_id = user_id_match.group(1)

            # Extract affiliation
            affiliation_element = result.find('div', class_='gs_ai_aff')
            affiliation = affiliation_element.text.strip() if affiliation_element else "Unknown"

            # Extract research interests
            interests_element = result.find('div', class_='gs_ai_int')
            interests = interests_element.text.strip() if interests_element else ""

            authors_info.append({
                'name': name,
                'scholar_id': scholar_id,
                'affiliation': affiliation,
                'interests': interests,
                'profile_url': f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
            })

        if authors_info:
            logger.info(f"Found {len(authors_info)} matching authors for: {author_name}")
            for i, author in enumerate(authors_info[:3], 1):  # Show top 3 results
                scholar_id = author.get('scholar_id', 'unknown_id')
                logger.info(f"[Scholar ID: {scholar_id}] Author {i}: {author['name']} - {author['affiliation']}")
        else:
            logger.warning(f"No authors found for: {author_name}")
            # Fallback to alternative search if available
            fallback = self.search_author_by_name_new(author_name, paper_title=paper_title, user_id=user_id)
            if fallback:
                return fallback

        return authors_info
    
    def search_author_by_name_new(self, author_name, paper_title=None, user_id=None):
        """
        Search for an author by name on Google Scholar.

        Args:
            author_name (str): Author name to search for
            paper_title (str, optional): Title of a paper by this author, used to get full name

        Returns:
            list: List of matching author information
        """
        logger.info(f"Searching for author: {author_name}")
        if "," in author_name:
            base_name = author_name.split(",", 1)[0].strip()
            if base_name:
                logger.info("Using base name '%s' from '%s'", base_name, author_name)
                author_name = base_name
        if paper_title:
            logger.info(f"Trying to find full name for {author_name} using paper: {paper_title}")
            # Get the full author list from the paper
            candidate_author_list = find_authors_from_title(paper_title)

            if candidate_author_list:
                # Try to match the abbreviated name with a full name
                closest_match = fuzzy_match_name(author_name, candidate_author_list)

                if closest_match:
                    closest_match = closest_match.strip()
                    # Handle cases like "Alexander and ..." which can trigger bugs
                    if " and " in closest_match:
                        closest_match = closest_match.split("and")[-1].strip()

                    logger.info(f"Found full name match: {closest_match} for {author_name}")
                    # Use the full name for the search instead
                    author_name = closest_match
                    
        # Encode the author name for URL
        encoded_name = urllib.parse.quote(author_name)
        search_url = f"https://scholar.google.com/scholar?q=author%3A%22{encoded_name}%22&hl=en"

        # Fetch the search results page
        html_content = self.fetch_html(search_url, user_id=user_id)

        if not html_content:
            logger.error(f"Failed to fetch author search results for: {author_name}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
    
    # 直接找第一个符合条件的链接
        first_link = soup.select_one('#gs_res_ccl_mid table h4 a')
        authors_info = []
        if first_link:
            match = re.search(r'user=([^&]+)', first_link.get('href') or '')
            if match:
                scholar_id = match.group(1)
            authors_info.append({
                'name': author_name,
                'scholar_id': scholar_id,
                'affiliation': 'Unknown',
                'interests': '',
                'profile_url': f"https://scholar.google.com/citations?user={scholar_id}&hl=en" if match else ""
            })
        else:
            logger.warning(f"No authors found for: {author_name}")

        return authors_info

    def parse_google_scholar_html(self, html_content, page_index=0, first_page=True, page_size: int = 100):
        """
        Parse Google Scholar HTML content to extract researcher information.

        Args:
            html_content (str): HTML content from Google Scholar
            page_index (int): Current page index for pagination (0-based)
            first_page (bool): Whether this is the first page, if True extract all info, if False only extract papers
            page_size (int): Expected page size (used to infer has_next_page)

        Returns:
            dict: Extracted researcher data
        """
        if not html_content:
            return None
        # Log the current page being parsed
        logger.debug(f"Parsing Google Scholar HTML content (page index: {page_index}, first page: {first_page})")
        # Parse HTML content with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        scholar_data = {
            'page_index': page_index,
            'has_papers': False,
            'has_next_page': False,
            'papers': []
        }

        # Only extract basic info on the first page
        if first_page:
            try:
                # Scholar name
                name_element = soup.find(id='gsc_prf_in')
                if name_element:
                    self.scholar_name = name_element.text.strip()

                    # Handle Chinese names - remove parentheses content
                    if has_chinese(self.scholar_name):
                        self.scholar_name = re.sub(r'\s*\([^)]*\)', '', self.scholar_name)

                    scholar_data['name'] = self.scholar_name
                    scholar_data['abbreviated_name'] = self.scholar_name  # 直接使用完整名字
                else:
                    # This usually means the response is not a Scholar profile page (captcha/consent/404/etc).
                    try:
                        html_lower = html_content.lower()
                    except Exception:  # noqa: BLE001
                        html_lower = ""

                    reason = "non_profile_page"
                    if any(
                        token in html_lower
                        for token in (
                            "unusual traffic",
                            "automated queries",
                            "sorry, but your computer or network may be sending automated queries",
                            "detected unusual traffic",
                            "our systems have detected unusual traffic",
                            "not a robot",
                            "recaptcha",
                            "consent.google.com",
                        )
                    ):
                        reason = "blocked_or_consent"

                    snippet = ""
                    try:
                        snippet = re.sub(r"\\s+", " ", str(html_content)[:500]).strip()
                    except Exception:  # noqa: BLE001
                        snippet = ""

                    logger.warning(
                        "Could not find scholar name element (page=%s, first_page=%s, reason=%s, html_len=%s, snippet=%s)",
                        page_index,
                        first_page,
                        reason,
                        len(html_content) if isinstance(html_content, str) else None,
                        snippet,
                    )
                    return None

                # Scholar affiliation
                affiliation_div = soup.find(id='gsc_prf_i')
                if affiliation_div:
                    affiliation_divs = affiliation_div.find_all("div")
                    if len(affiliation_divs) >= 3:
                        if "Other" not in affiliation_divs[2].text:
                            affiliation = affiliation_divs[2].text.strip()
                        else:
                            affiliation = affiliation_divs[3].text.strip()
                        scholar_data['affiliation'] = affiliation

                # Scholar email
                email = None
                email_div = soup.find('div', class_='gsc_prf_il', string=lambda t: t and '@' in t)
                if email_div:
                    email = email_div.text.strip()
                    scholar_data['email'] = email

                # Research fields
                interests_div = soup.find(id='gsc_prf_int')
                if interests_div:
                    research_fields = interests_div.find_all('a')
                    fields = [field.text.strip() for field in research_fields]
                    scholar_data['research_fields'] = fields

                # Citation statistics
                stats_table = soup.find('table', id='gsc_rsb_st')
                if stats_table:
                    citation_stats = stats_table.find_all('td', class_='gsc_rsb_std')
                    if len(citation_stats) >= 4:
                        total_citations = int(citation_stats[0].text.strip())
                        citations_5y = int(citation_stats[1].text.strip())
                        h_index = int(citation_stats[2].text.strip())
                        h_index_5y = int(citation_stats[3].text.strip())

                        scholar_data['total_citations'] = total_citations
                        scholar_data['citations_5y'] = citations_5y
                        scholar_data['h_index'] = h_index
                        scholar_data['h_index_5y'] = h_index_5y

                # Citation growth (last 3 years)
                citation_by_year = soup.find_all('a', class_='gsc_g_a')
                year_labels = soup.find_all('span', class_='gsc_g_t')

                yearly_citations = {}
                for i, year_span in enumerate(year_labels):
                    year = year_span.text.strip()
                    if i < len(citation_by_year):
                        yearly_citations[year] = int(citation_by_year[i].text.strip())

                scholar_data['yearly_citations'] = yearly_citations
                scholar_data['papers'] = []
            except Exception as e:
                logger.error(f"Error parsing basic scholar info: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue to parse papers even if basic info fails

        # Parse publications (done on every page)
        try:
            publications_table = soup.find('table', id='gsc_a_t')
            if publications_table:
                publications = publications_table.find_all('tr', class_='gsc_a_tr')
                papers = []

                for pub in publications:
                    try:
                        title_element = pub.find('a', class_='gsc_a_at')
                        if not title_element:
                            continue

                        title = normalize_scholar_paper_title(title_element.text.strip())
                        citation_element = pub.find('a', class_='gsc_a_ac')
                        citation_count = citation_element.text.strip() if citation_element and citation_element.text.strip() else "0"
                        year_element = pub.find('span', class_='gsc_a_h')
                        year = year_element.text.strip() if year_element else ""

                        author_elements = pub.find_all('div', class_='gs_gray')
                        author_list = []
                        venue = ""

                        if author_elements and len(author_elements) >= 1:
                            author_text = author_elements[0].text.strip()
                            author_list = [a.strip() for a in author_text.split(',')]

                        if author_elements and len(author_elements) >= 2:
                            venue = author_elements[1].text.strip()

                        # Determine author order with improved matching
                        # use fuzzy_match_name
                        matched_author = None
                        author_position = -1
                        if self.scholar_name:  # 使用类属性self.scholar_name
                            matched_author = fuzzy_match_name_improved(self.scholar_name, author_list)
                            if matched_author:
                                author_position = author_list.index(matched_author) + 1



                        # Collect paper data
                        paper_data = {
                            "title": title,
                            "year": year,
                            "author_position": author_position,
                            "authors": author_list,
                            "venue": venue,
                            "citations": citation_count if citation_count else "0"
                        }

                        papers.append(paper_data)
                    except Exception as e:
                        logger.error(f"Error parsing paper: {e}")
                        continue

                # Add papers to scholar data
                if first_page:
                    scholar_data['papers'] = papers
                else:
                    scholar_data['papers'] = papers

                # Check if there are papers on this page
                scholar_data['has_papers'] = len(papers) > 0

                # Check if there might be more papers (heuristic: "full page" means there may be next page)
                try:
                    expected = max(1, int(page_size or 0))
                except Exception:
                    expected = 100
                scholar_data['has_next_page'] = len(papers) == expected
            else:
                logger.warning("Could not find publications table")
                scholar_data['has_papers'] = False
                scholar_data['has_next_page'] = False
                scholar_data['papers'] = []
        except Exception as e:
            logger.error(f"Error parsing publications: {e}")
            import traceback
            logger.error(traceback.format_exc())
            scholar_data['has_papers'] = False
            scholar_data['has_next_page'] = False
            scholar_data['papers'] = []

        return scholar_data

    def get_full_profile(
        self,
        author_info,
        max_papers=500,
        adaptive_max_papers: bool = False,
        cancel_event=None,
        user_id=None,
        progress_callback: Optional[Callable[[Any], None]] = None,
    ):
        """
        Get the full profile with publications for an author (up to max_papers papers).

        Args:
            author_info: Author basic information (different format based on retrieval method)
            max_papers: Maximum number of papers to fetch (default: 500)

        Returns:
            dict: Complete author profile
        """
        if self.use_crawlbase:
            scholar_id = author_info.get('scholar_id')
            if not scholar_id:
                return None

            # Treat max_papers <= 0 as "unlimited" (fetch until no more pages).
            try:
                max_papers = int(max_papers)
            except (TypeError, ValueError):
                max_papers = 500
            unlimited = max_papers <= 0
            logger.info(
                "[Scholar ID: %s] Fetching profile (max papers: %s)",
                scholar_id,
                "unlimited" if unlimited else str(max_papers),
            )

            full_profile = None
            papers_collected = 0
            current_page = 0
            start_index = 0
            years_of_papers: dict[int, int] = {}

            # Optional multi-page concurrency (Crawlbase path only).
            try:
                page_concurrency = int(os.getenv("DINQ_SCHOLAR_PAGE_CONCURRENCY", "3") or "3")
            except (TypeError, ValueError):
                page_concurrency = 3
            page_concurrency = max(1, min(int(page_concurrency), 8))
            # Keep pagesize bounded. For page0 (max_papers small), this also reduces response size
            # and improves first-screen latency under Crawlbase.
            try:
                page_size = 100 if unlimited else max(1, min(100, int(max_papers)))
            except Exception:  # noqa: BLE001
                page_size = 100
            executor = ThreadPoolExecutor(max_workers=page_concurrency) if page_concurrency > 1 else None

            try:
                preview_max = int(os.getenv("DINQ_SCHOLAR_PREVIEW_MAX_PAPERS", "30") or "30")
            except (TypeError, ValueError):
                preview_max = 30
            preview_max = max(0, min(int(preview_max), 200))
            preview_emitted = 0

            def _project_paper(paper: Any) -> Optional[dict]:
                if not isinstance(paper, dict):
                    return None
                title = str(paper.get("title") or "").strip()
                if not title:
                    return None
                year_raw = str(paper.get("year") or "").strip()
                year = int(year_raw) if year_raw.isdigit() else None
                venue = str(paper.get("venue") or "").strip() or None
                citations_raw = str(paper.get("citations") or "").strip()
                try:
                    citations = int(citations_raw) if citations_raw else 0
                except Exception:  # noqa: BLE001
                    citations = 0
                authors = paper.get("authors")
                if isinstance(authors, list):
                    authors = [str(a) for a in authors if str(a).strip()][:8]
                else:
                    authors = None

                raw_id = f"{scholar_id}|{title}|{year_raw}|{venue or ''}".encode("utf-8", errors="ignore")
                pid = hashlib.sha1(raw_id).hexdigest()[:16]
                out: dict[str, Any] = {
                    "id": f"scholar:{scholar_id}:{pid}",
                    "title": title,
                    "citations": citations,
                }
                if year is not None:
                    out["year"] = year
                if venue is not None:
                    out["venue"] = venue
                if authors is not None:
                    out["authors"] = authors
                if paper.get("author_position") is not None:
                    out["author_position"] = paper.get("author_position")
                return out

            def _emit(message: str, **extra: Any) -> None:
                if progress_callback is None:
                    return
                try:
                    progress_callback({"message": message, "progress": None, **extra})
                except Exception:  # noqa: BLE001
                    return

            def fetch_and_parse(page_start: int, page_idx: int, first_page: bool) -> Any:
                raise_if_cancelled(cancel_event)
                url = (
                    f"https://scholar.google.com/citations?user={scholar_id}&hl=en&oi=ao&"
                    f"cstart={page_start}&pagesize={page_size}"
                )
                t_fetch = now_perf()
                html_content = self.fetch_html(url, cancel_event=cancel_event, user_id=user_id)
                fetch_ms = elapsed_ms(t_fetch)

                # Best-effort fallback for page0:
                # - Crawlbase sometimes returns consent/captcha HTML (non-profile page)
                # - Requests sometimes gets blocked
                # Firecrawl is slower but can be more robust; only try for first page.
                fallback_used: Optional[str] = None
                fallback_fetch_ms: Optional[int] = None
                if not html_content and first_page:
                    t_fb = now_perf()
                    html_fb = self.fetch_html_firecrawl(url, cancel_event=cancel_event, user_id=user_id)
                    fallback_fetch_ms = int(elapsed_ms(t_fb))
                    if html_fb:
                        html_content = html_fb
                        fallback_used = "firecrawl"

                if not html_content:
                    _emit(
                        "Scholar page fetch failed",
                        kind="timing",
                        stage="fetch_profile",
                        page_idx=int(page_idx),
                        cstart=int(page_start),
                        fetch_ms=int(fetch_ms),
                        fallback=fallback_used,
                        fallback_fetch_ms=fallback_fetch_ms,
                        ok=False,
                    )
                    return None
                t_parse = now_perf()
                parsed = self.parse_google_scholar_html(
                    html_content,
                    page_index=page_idx,
                    first_page=first_page,
                    page_size=page_size,
                )
                parse_ms = elapsed_ms(t_parse)

                # If page0 HTML looks like a non-profile page (consent/captcha), try Firecrawl once.
                if first_page and not parsed and fallback_used is None:
                    t_fb2 = now_perf()
                    html_fb2 = self.fetch_html_firecrawl(url, cancel_event=cancel_event, user_id=user_id)
                    fb2_ms = int(elapsed_ms(t_fb2))
                    if html_fb2 and html_fb2 != html_content:
                        parsed_fb2 = self.parse_google_scholar_html(
                            html_fb2,
                            page_index=page_idx,
                            first_page=first_page,
                            page_size=page_size,
                        )
                        if parsed_fb2:
                            parsed = parsed_fb2
                            fallback_used = "firecrawl"
                            fallback_fetch_ms = fb2_ms

                _emit(
                    "Scholar page fetched",
                    kind="timing",
                    stage="fetch_profile",
                    page_idx=int(page_idx),
                    cstart=int(page_start),
                    fetch_ms=int(fetch_ms),
                    parse_ms=int(parse_ms),
                    duration_ms=int(fetch_ms + parse_ms),
                    fallback=fallback_used,
                    fallback_fetch_ms=fallback_fetch_ms,
                    ok=True,
                )

                # Phase-2 UX: emit early profile/metrics previews from page0 as soon as it's parsed.
                # This allows the UI to render key identity + core citation metrics without waiting for
                # the full multi-page fetch/analyze stages to finish.
                if first_page and isinstance(parsed, dict):
                    try:
                        papers = parsed.get("papers") if isinstance(parsed.get("papers"), list) else []
                        year_dist: dict[int, int] = {}
                        for p in papers:
                            if not isinstance(p, dict):
                                continue
                            year_raw = p.get("year")
                            if year_raw is None:
                                continue
                            year_s = str(year_raw).strip()
                            if not year_s.isdigit():
                                continue
                            y = int(year_s)
                            year_dist[y] = year_dist.get(y, 0) + 1

                        profile_preview = {
                            "name": parsed.get("name") or "",
                            "abbreviated_name": parsed.get("abbreviated_name") or "",
                            "affiliation": parsed.get("affiliation") or "",
                            "email": parsed.get("email") or "",
                            "research_fields": parsed.get("research_fields") or [],
                            "total_citations": parsed.get("total_citations") or 0,
                            "citations_5y": parsed.get("citations_5y") or 0,
                            "h_index": parsed.get("h_index") or 0,
                            "h_index_5y": parsed.get("h_index_5y") or 0,
                            "yearly_citations": parsed.get("yearly_citations") or {},
                            "scholar_id": parsed.get("scholar_id") or scholar_id,
                        }
                        metrics_preview = {
                            "papers_loaded": len(papers),
                            "year_distribution": year_dist,
                        }

                        _emit(
                            "Scholar page0 profile/metrics preview",
                            prefill_cards=[
                                {
                                    "card": "profile",
                                    "data": profile_preview,
                                    "meta": {"partial": True, "source": "page0"},
                                },
                                {
                                    "card": "metrics",
                                    "data": metrics_preview,
                                    "meta": {"partial": True, "source": "page0"},
                                },
                            ],
                        )
                    except Exception:  # noqa: BLE001
                        pass
                return parsed

            try:
                while True:
                    if not unlimited and max_papers > 0 and papers_collected >= max_papers:
                        break
                    raise_if_cancelled(cancel_event)

                    # First page is always fetched serially (profile fields live there).
                    if current_page == 0 or executor is None:
                        batch_starts = [start_index]
                    else:
                        batch_n = page_concurrency
                        if not unlimited and max_papers > 0:
                            remaining = max_papers - papers_collected
                            if remaining <= 0:
                                break
                            remaining_pages = (remaining + page_size - 1) // page_size
                            batch_n = max(1, min(batch_n, int(remaining_pages)))
                        batch_starts = [start_index + page_size * i for i in range(batch_n)]

                    results: list[tuple[int, Any]] = []
                    if executor is None or len(batch_starts) == 1:
                        s = int(batch_starts[0])
                        logger.info(f"[Scholar ID: {scholar_id}] Fetching page {current_page+1} (start index: {s})")
                        page_data = fetch_and_parse(s, current_page, first_page=(current_page == 0))
                        results.append((s, page_data))
                    else:
                        futures = {}
                        for i, s in enumerate(batch_starts):
                            page_idx = current_page + int(i)
                            logger.info(f"[Scholar ID: {scholar_id}] Fetching page {page_idx+1} (start index: {s})")
                            futures[executor.submit(fetch_and_parse, int(s), int(page_idx), False)] = int(s)
                        for fut in as_completed(futures):
                            s = futures[fut]
                            try:
                                page_data = fut.result()
                            except Exception as e:
                                logger.error(f"[Scholar ID: {scholar_id}] Error fetching page at start index {s}: {e}")
                                page_data = None
                            results.append((int(s), page_data))
                        results.sort(key=lambda t: t[0])

                    stop = False
                    for s, page_data in results:
                        if not page_data:
                            logger.error(f"[Scholar ID: {scholar_id}] Failed to fetch/parse page {current_page+1} (start index: {s})")
                            stop = True
                            break

                        page_papers = page_data.get('papers', []) or []
                        add_papers = page_papers
                        if not unlimited and max_papers > 0:
                            remaining = max_papers - papers_collected
                            if remaining <= 0:
                                add_papers = []
                            else:
                                add_papers = page_papers[:remaining]

                        if full_profile is None:
                            # Use deep copy to avoid accidental shared references across pages.
                            full_profile = copy.deepcopy(page_data)
                            full_profile['papers'] = list(add_papers)
                            papers_collected = len(add_papers)
                            logger.info(f"[Scholar ID: {scholar_id}] Page {current_page+1} fetched {papers_collected} papers")

                            # Adaptive mode: for small profiles, stop early even if caller asked for more pages.
                            if adaptive_max_papers and (not unlimited) and max_papers and int(max_papers) > page_size:
                                try:
                                    total_citations = int(page_data.get("total_citations") or 0)
                                except Exception:  # noqa: BLE001
                                    total_citations = 0
                                try:
                                    h_index = int(page_data.get("h_index") or 0)
                                except Exception:  # noqa: BLE001
                                    h_index = 0

                                # Heuristic thresholds (kept intentionally simple for speed-first UX).
                                if total_citations < 5000 and h_index < 20:
                                    max_papers = min(int(max_papers), page_size)
                                    logger.info(
                                        "[Scholar ID: %s] Adaptive max_papers enabled (citations=%s, h_index=%s) -> %s",
                                        scholar_id,
                                        total_citations,
                                        h_index,
                                        max_papers,
                                    )
                        else:
                            if len(add_papers) == 0:
                                logger.info(f"[Scholar ID: {scholar_id}] No more papers to add, stopping")
                                stop = True
                                break
                            full_profile['papers'].extend(add_papers)
                            papers_collected += len(add_papers)
                            logger.info(f"[Scholar ID: {scholar_id}] Page {current_page+1} fetched {len(add_papers)} papers, total: {papers_collected}")

                        if preview_max > 0 and preview_emitted < preview_max:
                            remaining = max(0, int(preview_max - preview_emitted))
                            batch = add_papers[:remaining] if remaining > 0 else []
                            projected = [x for x in (_project_paper(p) for p in batch) if x is not None]
                            if projected:
                                preview_emitted += len(projected)
                                _emit(
                                    "Scholar papers preview",
                                    append={
                                        "card": "papers",
                                        "path": "items",
                                        "items": projected,
                                        "dedup_key": "id",
                                        "cursor": {"cstart": int(s)},
                                        "partial": bool(page_data.get("has_next_page", False)),
                                    },
                                )

                        # Update year distribution incrementally (avoids an extra full scan later).
                        for idx, paper in enumerate(add_papers):
                            if idx % 50 == 0:
                                raise_if_cancelled(cancel_event)
                            year = paper.get('year', '')
                            if year and isinstance(year, str) and year.strip().isdigit():
                                y = int(year.strip())
                                years_of_papers[y] = years_of_papers.get(y, 0) + 1

                        # Advance to next page
                        start_index = int(s) + page_size
                        current_page += 1

                        has_next = bool(page_data.get('has_next_page', False))
                        if not has_next:
                            logger.info(f"[Scholar ID: {scholar_id}] No more pages available")
                            stop = True
                            break
                        if not unlimited and max_papers > 0 and papers_collected >= max_papers:
                            logger.info(f"[Scholar ID: {scholar_id}] Reached max papers limit: {max_papers}")
                            stop = True
                            break

                    if stop:
                        break
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)

            if full_profile:
                total_papers = len(full_profile.get('papers', []))
                logger.info(f"[Scholar ID: {scholar_id}] Profile fetching completed")
                logger.info(f"[Scholar ID: {scholar_id}] Total papers found: {total_papers}")
                full_profile['years_of_papers'] = years_of_papers
                logger.info(f"[Scholar ID: {scholar_id}] Successfully fetched profile with {total_papers} papers")
                return full_profile

            logger.error(f"[Scholar ID: {scholar_id}] Failed to fetch profile")
            return None

        if author_info:
            researcher_name = author_info.get('name', 'researcher')
            scholar_id = author_info.get('scholar_id', 'unknown_id')
            logger.info(f"[Scholar ID: {scholar_id}] Retrieving full profile for {researcher_name}")
            try:
                result = scholarly.fill(author_info, sections=['basics', 'publications', 'coauthors'])
                logger.info(f"[Scholar ID: {scholar_id}] Successfully retrieved full profile")
                return result
            except Exception as e:
                logger.error(f"[Scholar ID: {scholar_id}] Error retrieving full profile: {e}")
        return None

    def get_author_details_by_id(self, scholar_id):
        """
        Get full name and affiliation of an author by their Google Scholar ID.

        Args:
            scholar_id (str): Google Scholar ID

        Returns:
            dict: Author details including full name and affiliation
        """
        url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
        html_content = self.fetch_html_firecrawl(url)
        if not html_content:
            html_content = self.fetch_html(url)

        if not html_content:
            return None

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract name
            name_element = soup.find(id='gsc_prf_in')
            name = name_element.text.strip() if name_element else None

            # Extract affiliation
            affiliation = None
            affiliation_div = soup.find(id='gsc_prf_i')
            if affiliation_div:
                affiliation_elements = affiliation_div.find_all('div')
                if len(affiliation_elements) >= 3:
                    affiliation = affiliation_elements[2].text.strip()

            # Extract research interests
            interests = []
            interests_div = soup.find(id='gsc_prf_int')
            if interests_div:
                interest_links = interests_div.find_all('a')
                interests = [link.text.strip() for link in interest_links]

            return {
                'scholar_id': scholar_id,
                'full_name': name,
                'affiliation': affiliation,
                'research_interests': interests
            }
        except Exception as e:
            logger.error(f"[Scholar ID: {scholar_id}] Error extracting author details: {e}")
            return None

    def get_multiple_author_details(self, scholar_ids):
        """
        Get details for multiple authors by their Scholar IDs.

        Args:
            scholar_ids (list): List of Google Scholar IDs

        Returns:
            list: List of author details
        """
        author_details = []
        for scholar_id in scholar_ids:
            details = self.get_author_details_by_id(scholar_id)
            if details:
                author_details.append(details)
        return author_details

    def get_single_author_detail(self, scholar_id):
        """
        Get details for a single author by their Scholar ID.

        Args:
            scholar_id (str): Google Scholar ID

        Returns:
            dict: Author details
        """
        return self.get_author_details_by_id(scholar_id)
