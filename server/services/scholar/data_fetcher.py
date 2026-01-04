# coding: UTF-8
"""
Data fetcher module for Scholar API service.
Handles retrieving data from Google Scholar using either scholarly or Crawlbase.
"""

import re
import os
import sys
import time
import urllib.parse
import copy
import logging
import requests
# 导入日志配置
from server.utils.logging_config import setup_logging
import logging.handlers  # 导入 handlers 模块用于 RotatingFileHandler
from firecrawl import FirecrawlApp
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

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from bs4 import BeautifulSoup
# ProxyGenerator is imported but not used as we're disabling proxies
from scholarly import scholarly
from crawlbase import CrawlingAPI
from server.utils.utils import has_chinese, fuzzy_match_name, fuzzy_match_name_improved
from onepage.author_paper import find_authors_from_title

class ScholarDataFetcher:
    """
    Handles fetching data from Google Scholar using either scholarly or Crawlbase.
    """

    def __init__(self, use_crawlbase=False, api_token=None):
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


        self.use_crawlbase = use_crawlbase
        self.api_token = api_token
        self.scholar_name = None  # 添加scholar_name属性
        
        if use_crawlbase:
            if not api_token:
                raise ValueError("API token is required when using Crawlbase")
            self.crawling_api = CrawlingAPI({'token': api_token})
            self.firecrawl_app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY", "fc-de49de4454504bceae80d34c35f45791"))
            logger.info(f"Crawlbase API initialized successfully with token: {api_token[:5]}...")
        else:
            # 完全禁用代理功能，直接使用无代理模式
            logger.info("Using scholarly without proxy (completely disabled for testing)")

        logger.info(f"DataFetcher initialized with use_crawlbase={use_crawlbase}")

    def fetch_html(self, url):
        """
        Fetch HTML content from a URL using Crawlbase.

        Args:
            url (str): URL to fetch

        Returns:
            str: HTML content
        """
        try:
            response = self.crawling_api.get(url)

            # Handle different response formats
            if isinstance(response, dict) and 'headers' in response and 'pc_status' in response['headers']:
                if response['headers']['pc_status'] == '200':
                    return response['body'].decode('utf-8')
                else:
                    logger.error(f"Failed to fetch the page. Crawlbase status code: {response['headers']['pc_status']}")
                    return None
            else:
                # Check response status code
                if hasattr(response, 'status_code'):
                    if response.status_code == 200:
                        return response.text
                    else:
                        logger.error(f"Failed to fetch the page. Status code: {response.status_code}")
                        return None
                elif isinstance(response, dict) and 'body' in response:
                    # Handle alternative response format
                    try:
                        return response['body'].decode('utf-8')
                    except (AttributeError, UnicodeDecodeError):
                        if isinstance(response['body'], str):
                            return response['body']
                        else:
                            logger.error("Failed to decode response body")
                            return None
                else:
                    logger.error("Unexpected response format from Crawlbase API")
                    return None
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
        
    def fetch_html_firecrawl(self, url):
        """
        Fetch HTML content from a URL using Firecrawl.

        Args:
            url (str): URL to fetch

        Returns:
            str: HTML content
        """
        try:
            response = self.firecrawl_app.scrape_url(url, 
                formats=['html'],           # 直接作为参数
                onlyMainContent=False       # 直接作为参数
            )

            if response and response.html:
                return response.html
            else:
                print(f"Failed to fetch the page. Invalid response format for URL: {url}")
                return None

        except Exception as e:
            print(f"Error fetching URL {url}: {e}")
            return None

    def search_researcher(self, name=None, scholar_id=None):
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
                authors = self.search_author_by_name_new(name)
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

    def search_author_by_name(self, author_name, paper_title=None):
        """
        Search for an author by name on Google Scholar.

        Args:
            author_name (str): Author name to search for
            paper_title (str, optional): Title of a paper by this author, used to get full name

        Returns:
            list: List of matching author information
        """
        logger.info(f"Searching for author: {author_name}")

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

        # Fetch the search results page
        html_content = self.fetch_html_firecrawl(search_url)
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

        return authors_info
    
    def search_author_by_name_new(self, author_name, paper_title=None):
        """
        Search for an author by name on Google Scholar.

        Args:
            author_name (str): Author name to search for
            paper_title (str, optional): Title of a paper by this author, used to get full name

        Returns:
            list: List of matching author information
        """
        logger.info(f"Searching for author: {author_name}")
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
        html_content = self.fetch_html(search_url)

        if not html_content:
            logger.error(f"Failed to fetch author search results for: {author_name}")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
    
    # 直接找第一个符合条件的链接
        first_link = soup.select_one('#gs_res_ccl_mid table h4 a')
        print(first_link)
        authors_info = []
        if first_link:
            match = re.search(r'user=([^&]+)', first_link.get('href') or '')
            if match:
                scholar_id = match.group(1)
            print(scholar_id)
            authors_info.append({
                'name': author_name,
                'scholar_id': scholar_id
            })
        else:
            logger.warning(f"No authors found for: {author_name}")

        return authors_info

    def parse_google_scholar_html(self, html_content, page_index=0, first_page=True):
        print(f"111: {111}")
        """
        Parse Google Scholar HTML content to extract researcher information.

        Args:
            html_content (str): HTML content from Google Scholar
            page_index (int): Current page index for pagination (0-based)
            first_page (bool): Whether this is the first page, if True extract all info, if False only extract papers

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
                    logger.warning("Could not find scholar name element")
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
            print(f"222: {22}")
            publications_table = soup.find('table', id='gsc_a_t')
            if publications_table:
                publications = publications_table.find_all('tr', class_='gsc_a_tr')
                papers = []

                for pub in publications:
                    try:
                        title_element = pub.find('a', class_='gsc_a_at')
                        if not title_element:
                            continue

                        title = title_element.text.strip()
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

                # Check if there might be more papers (if we have 100 papers, there might be more)
                scholar_data['has_next_page'] = len(papers) == 100
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

    def get_full_profile(self, author_info, max_papers=500):
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

            logger.info(f"[Scholar ID: {scholar_id}] Fetching profile (max papers: {max_papers})")

            # 初始化结果
            full_profile = None
            papers_collected = 0
            current_page = 0
            start_index = 0

            while papers_collected < max_papers:
                # 构建URL（每页100篇论文）
                url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en&oi=ao&cstart={start_index}&pagesize=100"

                logger.info(f"[Scholar ID: {scholar_id}] Fetching page {current_page+1} (start index: {start_index})")

                # 获取HTML内容
                max_retries = 3
                retry_count = 0
                html_content = None

                # 添加重试逻辑
                while retry_count < max_retries and not html_content:
                    html_content = self.fetch_html(url)
                    if not html_content:
                        retry_count += 1
                        logger.warning(f"[Scholar ID: {scholar_id}] Retry {retry_count} for page {current_page+1}")
                        time.sleep(2)

                if not html_content:
                    logger.error(f"[Scholar ID: {scholar_id}] Failed to fetch page {current_page+1} after {max_retries} retries")
                    break

                try:
                    # 第一页获取完整个人资料，后续页面只获取论文
                    is_first_page = (current_page == 0)

                    # 解析HTML内容
                    page_data = self.parse_google_scholar_html(html_content, page_index=current_page, first_page=is_first_page)

                    if not page_data:
                        logger.error(f"[Scholar ID: {scholar_id}] Failed to parse page {current_page+1}")
                        break

                    # 如果是第一页，初始化完整个人资料
                    if full_profile is None:
                        # 使用深拷贝解决数据引用问题，避免后续修改影响原始数据
                        full_profile = copy.deepcopy(page_data)
                        papers_collected = len(full_profile.get('papers', []))
                        logger.info(f"[Scholar ID: {scholar_id}] Page {current_page+1} fetched {papers_collected} papers")
                    else:
                        # 如果不是第一页，只添加论文
                        new_papers = page_data.get('papers', [])

                        # 检查是否有新论文
                        if len(new_papers) == 0:
                            logger.info(f"[Scholar ID: {scholar_id}] No papers found on page {current_page+1}, stopping")
                            break

                        full_profile['papers'].extend(new_papers)
                        papers_collected += len(new_papers)
                        logger.info(f"[Scholar ID: {scholar_id}] Page {current_page+1} fetched {len(new_papers)} papers, total: {papers_collected}")

                    # 检查是否有下一页
                    if not page_data.get('has_next_page', False):
                        logger.info(f"[Scholar ID: {scholar_id}] No more pages available")
                        break

                    # 更新下一页的起始索引
                    start_index += 100
                    current_page += 1

                    # 在请求之间添加延迟，避免被封
                    time.sleep(3)

                except Exception as e:
                    logger.error(f"[Scholar ID: {scholar_id}] Error processing page {current_page+1}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    break

            # 处理完成后，更新年份分布
            if full_profile:
                # 验证数据完整性
                total_papers = len(full_profile.get('papers', []))
                logger.info(f"[Scholar ID: {scholar_id}] Profile fetching completed")
                logger.info(f"[Scholar ID: {scholar_id}] Total papers found: {total_papers}")

                # 正确地统计年份分布
                years_of_papers = {}
                for paper in full_profile.get('papers', []):
                    year = paper.get('year', '')
                    if year and year.strip() and year.strip().isdigit():
                        year = int(year.strip())
                        years_of_papers[year] = years_of_papers.get(year, 0) + 1

                # 确保字段名称使用 years_of_papers
                full_profile['years_of_papers'] = years_of_papers

                logger.info(f"[Scholar ID: {scholar_id}] Year distribution of papers:")
                for year in sorted(years_of_papers.keys()):
                    logger.debug(f"[Scholar ID: {scholar_id}] Year {year}: {years_of_papers[year]} papers")

                logger.info(f"[Scholar ID: {scholar_id}] Successfully fetched profile with {total_papers} papers")
                return full_profile
            else:
                logger.error(f"[Scholar ID: {scholar_id}] Failed to fetch profile")
                return None
        else:
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
