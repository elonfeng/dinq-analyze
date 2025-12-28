# coding: UTF-8
"""
Publication Analyzer module for Scholar API service.
Handles analyzing publication data with specialized functions.
"""

import os
import re
import copy
import logging
import logging.handlers
import numpy as np
from collections import Counter

# 导入日志配置
from server.utils.logging_config import setup_logging

# 确保日志目录存在
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs'))
os.makedirs(log_dir, exist_ok=True)

# 初始化日志配置
# 注意：如果日志配置已经在其他地方初始化，这里的调用不会有副作用
setup_logging(log_dir)

# 创建模块日志记录器
logger = logging.getLogger('server.services.scholar.publication_analyzer')

# 确保模块日志记录器有文件处理器
# 创建一个新的文件处理器，专门用于这个模块
module_log_file = os.path.join(log_dir, 'publication_analyzer.log')
file_handler = logging.handlers.RotatingFileHandler(
    module_log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.DEBUG)  # 设置为 DEBUG 级别，捕获所有日志

# 添加处理器到真实的logger对象
try:
    from server.utils.trace_context import get_real_logger
    real_logger = get_real_logger('server.services.scholar.publication_analyzer')
    real_logger.addHandler(file_handler)
    real_logger.setLevel(logging.DEBUG)
except ImportError:
    # Fallback: 如果是普通logger，直接添加
    if hasattr(logger, 'addHandler'):
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
    else:
        # 如果是TraceLoggerAdapter，获取底层logger
        real_logger = getattr(logger, 'logger', logging.getLogger('server.services.scholar.publication_analyzer'))
        real_logger.addHandler(file_handler)
        real_logger.setLevel(logging.DEBUG)

# 导入获取论文新闻的工具类
from onepage.signature_news import get_latest_news
from server.utils.conference_matcher import ConferenceMatcher
from server.services.scholar.config import TOP_TIER_CONFERENCES, TOP_TIER_JOURNALS, TOP_TIER_VENUES
from server.services.scholar.cancel import raise_if_cancelled

class PublicationAnalyzer:
    """
    Specialized class for analyzing publication data.
    """

    def __init__(self):
        """
        Initialize the publication analyzer.
        """
        logger.debug("PublicationAnalyzer initialization started")
        self.top_tier_conferences = TOP_TIER_CONFERENCES
        self.top_tier_journals = TOP_TIER_JOURNALS
        self.top_tier_venues = TOP_TIER_VENUES
        self.matcher = ConferenceMatcher()
        logger.info("PublicationAnalyzer initialized successfully")

    def analyze_publications(self, author_data, cancel_event=None):
        """
        Main method to analyze publication data.

        Args:
            author_data (dict): Author data including publications

        Returns:
            dict: Publication statistics
        """
        raise_if_cancelled(cancel_event)
        if not author_data or 'papers' not in author_data:
            logger.warning("No papers found in author data")
            return {}

        publications = author_data.get('papers', [])
        total_papers = len(publications)

        # 获取学者ID用于日志记录
        scholar_id = author_data.get('scholar_id', 'unknown_id')
        scholar_name = author_data.get('name', 'unknown_name')

        # 使用精简的日志格式，包含学者ID和关键信息
        logger.info(f"[Scholar ID: {scholar_id}] Analyzing {total_papers} publications for {scholar_name} "
                  f"(h-index: {author_data.get('h_index', 0)}, citations: {author_data.get('total_citations', 0)})")

        # 初始化计数器和统计数据
        counters = self._initialize_counters()

        # 分析年份分布
        year_distribution = self._analyze_year_distribution(author_data, scholar_id)

        # 分析每篇论文
        for idx, pub in enumerate(publications):
            if idx % 25 == 0:
                raise_if_cancelled(cancel_event)
            self._analyze_single_publication(pub, counters, scholar_id)

        # 处理arXiv论文 - 只有当Arxiv在顶级会议列表中时才加入conference_count
        if counters['arxiv_count'] > 0 and 'Arxiv' in self.top_tier_conferences:
            counters['conference_count']['Arxiv'] = counters['arxiv_count']

        # 计算引用速度
        citation_velocity = self._calculate_citation_velocity(author_data)

        # 排序顶级出版物
        self._sort_top_tier_publications(counters['top_tier_publications'])

        # 获取最引用论文的新闻
        paper_news = self._get_paper_news(counters['most_cited_paper'], scholar_id)

        # 最终检查最引用论文（大列表会导致额外 O(n) 扫描，超大论文量时跳过以保证性能）
        try:
            final_check_max = int(os.getenv("DINQ_SCHOLAR_FINAL_CHECK_MOST_CITED_MAX_PAPERS", "2000") or "2000")
        except (TypeError, ValueError):
            final_check_max = 2000
        if final_check_max > 0 and total_papers <= final_check_max:
            self._final_check_most_cited_paper(publications, counters, scholar_id)

        # 编译结果
        publication_stats = self._compile_results(
            total_papers,
            counters,
            year_distribution,
            citation_velocity,
            paper_news
        )

        # 记录分析完成的日志
        logger.info(f"[Scholar ID: {scholar_id}] Publication analysis completed for {scholar_name}")
        logger.info(f"[Scholar ID: {scholar_id}] Summary - Total papers: {total_papers}, First author: {counters['first_author_papers']}, Top-tier: {counters['top_tier_papers']}")

        # 记录最引用论文的详细信息
        self._log_most_cited_paper_details(counters['most_cited_paper'], scholar_id, scholar_name)

        logger.debug(f"[Scholar ID: {scholar_id}] Publication stats completed, year_distribution in stats: {publication_stats['year_distribution']}")

        return publication_stats

    def _initialize_counters(self):
        """
        Initialize counters for publication analysis.

        Returns:
            dict: Initialized counters
        """
        return {
            'first_author_papers': 0,
            'last_author_papers': 0,
            'top_tier_papers': 0,
            'conference_count': Counter(),
            'journal_count': Counter(),
            'year_count': Counter(),
            'citation_count': [],
            'first_author_citations': 0,
            'first_author_papers_list': [],
            'arxiv_count': 0,
            'most_cited_paper': None,
            'max_citations': -1,
            'top_tier_publications': {
                'conferences': [],
                'journals': []
            },
            'paper_of_year': {}
        }

    def _analyze_year_distribution(self, author_data, scholar_id):
        """
        Analyze the year distribution of publications.

        Args:
            author_data (dict): Author data
            scholar_id (str): Scholar ID for logging

        Returns:
            dict: Year distribution
        """
        # Check if we have the pre-computed years_of_papers from data_fetcher
        if 'years_of_papers' in author_data and isinstance(author_data['years_of_papers'], dict):
            logger.info(f"[Scholar ID: {scholar_id}] Using pre-computed year distribution")
            return author_data['years_of_papers']
        else:
            logger.info(f"[Scholar ID: {scholar_id}] No pre-computed year distribution found")
            return None

    def _analyze_single_publication(self, pub, counters, scholar_id):
        """
        Analyze a single publication.

        Args:
            pub (dict): Publication data
            counters (dict): Counters to update
            scholar_id (str): Scholar ID for logging
        """
        # Check author position
        self._analyze_author_position(pub, counters, scholar_id)

        # Extract and analyze venue
        self._analyze_venue(pub, counters)

        # Record publication year
        self._record_publication_year(pub, counters)

        # Track paper-of-year candidate
        self._update_paper_of_year(pub, counters)

        # Track most cited paper
        self._track_most_cited_paper(pub, counters, scholar_id)

    def _analyze_author_position(self, pub, counters, scholar_id):
        """
        Analyze author position in a publication.

        Args:
            pub (dict): Publication data
            counters (dict): Counters to update
            scholar_id (str): Scholar ID for logging
        """
        # Check if first author
        author_position = pub.get('author_position', 0)

        if author_position == 1:
            counters['first_author_papers'] += 1
            # Add citations for first author papers
            try:
                citations = int(pub.get('citations', 0))
                counters['first_author_citations'] += citations
                counters['first_author_papers_list'].append({
                    'title': pub.get('title', ''),
                    'year': pub.get('year', ''),
                    'venue': pub.get('venue', ''),
                    'citations': citations
                })
            except (ValueError, TypeError):
                pass

        # Check if last author
        authors = pub.get('authors', [])
        if authors and author_position == len(authors):
            counters['last_author_papers'] += 1

    def _analyze_venue(self, pub, counters):
        """
        Analyze publication venue.

        Args:
            pub (dict): Publication data
            counters (dict): Counters to update
        """
        # Extract venue and match conference
        venue = pub.get('venue', '')

        # Check if it's an arXiv paper
        if 'arxiv' in venue.lower() or 'arXiv' in venue:
            counters['arxiv_count'] += 1
            return  # Skip further venue processing for arXiv papers

        matched_conf = self.matcher.match_conference(venue.lower())

        # If it's a top-tier venue, update counters
        if matched_conf in self.top_tier_venues:
            counters['top_tier_papers'] += 1

            # Create publication details
            pub_details = {
                'title': pub.get('title', ''),
                'year': pub.get('year', ''),
                'venue': matched_conf,
                'citations': pub.get('citations', 0),
                'author_position': pub.get('author_position', 0)
            }

            if matched_conf in self.top_tier_conferences:
                counters['conference_count'][matched_conf] += 1
                counters['top_tier_publications']['conferences'].append(pub_details)
            else:
                counters['journal_count'][matched_conf] += 1
                counters['top_tier_publications']['journals'].append(pub_details)
        # Note: Only top-tier venues are counted in conference/journal distributions
        # Non-top-tier venues are not included to maintain consistency with top_tier_papers count

    def _record_publication_year(self, pub, counters):
        """
        Record publication year.

        Args:
            pub (dict): Publication data
            counters (dict): Counters to update
        """
        year = pub.get('year', '')
        if year and str(year).isdigit():
            counters['year_count'][str(year)] += 1

    def _track_most_cited_paper(self, pub, counters, scholar_id):
        """
        Track the most cited paper.

        Args:
            pub (dict): Publication data
            counters (dict): Counters to update
            scholar_id (str): Scholar ID for logging
        """
        try:
            # 获取论文引用数并转换为整数
            raw_citations = pub.get('citations', 0)
            citations = int(raw_citations)

            # 记录论文信息用于调试
            paper_title = pub.get('title', '')
            paper_year = pub.get('year', '')
            paper_venue = pub.get('venue', '')

            # 记录当前论文的引用数
            logger.debug(f"[Scholar ID: {scholar_id}] Paper: '{paper_title}' ({paper_year}) in '{paper_venue}' has {citations} citations (raw value: {raw_citations})")

            # 如果引用数超过当前最大值，更新最引用论文
            if citations > counters['max_citations']:
                # 记录旧的最大引用数，用于日志
                prev_max_citations = counters['max_citations']
                counters['max_citations'] = citations
                old_paper_title = counters['most_cited_paper'].get('title') if counters['most_cited_paper'] else 'None'
                old_paper_citations = counters['most_cited_paper'].get('citations') if counters['most_cited_paper'] else 0

                # logger.info(f"[Scholar ID: {scholar_id}] Found new most cited paper: '{paper_title}' with {citations} citations (increase of {citations - prev_max_citations})")
                # logger.info(f"[Scholar ID: {scholar_id}] Previous most cited: '{old_paper_title}' with {old_paper_citations} citations")

                counters['most_cited_paper'] = {
                    'title': paper_title,
                    'year': paper_year,
                    'venue': paper_venue,
                    'citations': citations,
                    'authors': pub.get('authors', []),
                    'author_position': pub.get('author_position', 0)
                }
            counters['citation_count'].append(citations)
        except (ValueError, TypeError) as e:
            # 记录转换引用数时的错误
            paper_title = pub.get('title', '')
            raw_citations = pub.get('citations', 'N/A')
            logger.warning(f"[Scholar ID: {scholar_id}] Could not convert citations to integer for paper '{paper_title}': {raw_citations}, Error: {e}")

            # 尝试更强大的转换方法
            try:
                # 尝试处理带有非数字字符的引用数
                if isinstance(raw_citations, str):
                    # 提取所有数字
                    digits = re.findall(r'\d+', raw_citations)
                    if digits:
                        # 使用第一个数字序列
                        citations = int(digits[0])
                        logger.info(f"[Scholar ID: {scholar_id}] Successfully extracted citation count {citations} from '{raw_citations}' for paper '{paper_title}'")

                        # 如果引用数超过当前最大值，更新最引用论文
                        if citations > counters['max_citations']:
                            prev_max_citations = counters['max_citations']
                            counters['max_citations'] = citations
                            old_paper_title = counters['most_cited_paper'].get('title') if counters['most_cited_paper'] else 'None'
                            old_paper_citations = counters['most_cited_paper'].get('citations') if counters['most_cited_paper'] else 0

                            logger.info(f"[Scholar ID: {scholar_id}] Found new most cited paper (after extraction): '{paper_title}' with {citations} citations")

                            counters['most_cited_paper'] = {
                                'title': paper_title,
                                'year': paper_year,
                                'venue': paper_venue,
                                'citations': citations,
                                'authors': pub.get('authors', []),
                                'author_position': pub.get('author_position', 0)
                            }
                        counters['citation_count'].append(citations)
            except Exception as e2:
                logger.warning(f"[Scholar ID: {scholar_id}] Failed second attempt to extract citations for paper '{paper_title}': {e2}")

    def _calculate_citation_velocity(self, author_data):
        """
        Calculate citation velocity.

        Args:
            author_data (dict): Author data

        Returns:
            float or None: Citation velocity
        """
        citation_velocity = None
        yearly_citations = author_data.get('yearly_citations', {})
        if yearly_citations and len(yearly_citations) >= 3:
            years = sorted(yearly_citations.keys())[-3:]
            citations = [yearly_citations[year] for year in years]

            growth_rates = []
            for i in range(1, len(citations)):
                if citations[i-1] > 0:
                    growth_rate = (citations[i] - citations[i-1]) / citations[i-1]
                    growth_rates.append(growth_rate)

            if growth_rates:
                citation_velocity = sum(growth_rates) / len(growth_rates)

        return citation_velocity

    def _sort_top_tier_publications(self, top_tier_publications):
        """
        Sort top-tier publications by year.

        Args:
            top_tier_publications (dict): Top-tier publications
        """
        # Sort top-tier publications by year (newest first)
        for category in top_tier_publications:
            top_tier_publications[category] = sorted(
                top_tier_publications[category],
                key=lambda x: (x.get('year', '0') or '0', x.get('citations', 0) or 0),
                reverse=True
            )

    def _get_paper_news(self, most_cited_paper, scholar_id):
        """
        Get news for the most cited paper.

        Args:
            most_cited_paper (dict): Most cited paper
            scholar_id (str): Scholar ID for logging

        Returns:
            dict or None: Paper news
        """
        paper_news = None
        if most_cited_paper and most_cited_paper.get('title'):
            logger.info(f"[Scholar ID: {scholar_id}] Getting news for most cited paper: {most_cited_paper.get('title')}")
            try:
                # 使用工具类中的get_latest_news函数获取论文新闻
                paper_news = get_latest_news(most_cited_paper.get('title'))
                if paper_news:
                    logger.info(f"[Scholar ID: {scholar_id}] Successfully retrieved news for most cited paper")
                else:
                    logger.warning(f"[Scholar ID: {scholar_id}] No news found for most cited paper")
            except Exception as e:
                logger.error(f"[Scholar ID: {scholar_id}] Error getting news for most cited paper: {e}")
        else:
            logger.warning(f"[Scholar ID: {scholar_id}] No most cited paper found, skipping news retrieval")

        return paper_news

    def _update_paper_of_year(self, pub, counters):
        """Track the highest cited paper for each publication year."""
        year = pub.get('year')
        if not year:
            return

        year_str = str(year).strip()
        if not year_str.isdigit():
            return

        raw_citations = pub.get('citations', 0)
        citations_val = 0
        try:
            citations_val = int(raw_citations)
        except (ValueError, TypeError):
            try:
                citations_val = int(float(raw_citations))
            except (ValueError, TypeError):
                digits = re.findall(r'\d+', str(raw_citations)) if isinstance(raw_citations, str) else []
                citations_val = int(digits[0]) if digits else 0

        year_int = int(year_str)
        stored = counters['paper_of_year'].get(year_int)
        if stored and citations_val <= stored.get('citations', 0):
            return

        counters['paper_of_year'][year_int] = {
            'title': pub.get('title', ''),
            'year': year_str,
            'venue': pub.get('venue', ''),
            'citations': citations_val,
            'authors': pub.get('authors', []),
            'author_position': pub.get('author_position')
        }

    def _build_paper_of_year_entry(self, paper_of_year_map):
        """Return the latest year's top paper details."""
        if not paper_of_year_map:
            return None

        latest_year = max(paper_of_year_map.keys())
        paper = paper_of_year_map.get(latest_year)
        if not paper:
            return None

        return {
            'title': paper.get('title', ''),
            'year': paper.get('year', str(latest_year)),
            'venue': paper.get('venue', ''),
            'citations': paper.get('citations', 0),
            'authors': paper.get('authors', []),
            'author_position': paper.get('author_position'),
            'summary': ''
        }

    def _final_check_most_cited_paper(self, publications, counters, scholar_id):
        """
        Final check to ensure most_cited_paper is the paper with the most citations.

        Args:
            publications (list): List of publications
            counters (dict): Counters with citation data
            scholar_id (str): Scholar ID for logging
        """
        # If we don't have a most cited paper yet, try to find one
        if 'most_cited_paper' not in counters or counters['most_cited_paper'] is None:
            logger.info(f"[Scholar ID: {scholar_id}] No most cited paper found in initial analysis, performing final check")
            max_citations = 0
            most_cited = None

            for pub in publications:
                try:
                    citations = int(pub.get('citations', 0))
                    if citations > max_citations:
                        max_citations = citations
                        # Create a copy of the publication with only the fields we need
                        most_cited = {
                            'title': pub.get('title', 'Unknown Title'),
                            'year': pub.get('year', 'Unknown Year'),
                            'venue': pub.get('venue', 'Unknown Venue'),
                            'citations': citations,
                            'authors': pub.get('authors', []),
                            'url': pub.get('url', ''),
                            'abstract': pub.get('abstract', ''),
                            'is_first_author': pub.get('is_first_author', False)
                        }

                        # Add additional fields if available
                        if 'arxiv_id' in pub:
                            most_cited['arxiv_id'] = pub['arxiv_id']

                        if 'doi' in pub:
                            most_cited['doi'] = pub['doi']
                except (ValueError, TypeError):
                    continue

            if most_cited:
                counters['most_cited_paper'] = most_cited
                # 简化日志，不记录完整论文标题
                title = most_cited['title']
                if len(title) > 50:
                    title = title[:47] + '...'
                logger.info(f"[Scholar ID: {scholar_id}] Found most cited paper in final check with {max_citations} citations")

        # Double-check that we have the paper with the most citations
        elif counters['most_cited_paper']:
            current_max = int(counters['most_cited_paper'].get('citations', 0))

            # 不记录详细的验证过程
            found_better = False
            for pub in publications:
                try:
                    citations = int(pub.get('citations', 0))
                    if citations > current_max:
                        current_max = citations
                        # Create a copy of the publication with only the fields we need
                        most_cited = {
                            'title': pub.get('title', 'Unknown Title'),
                            'year': pub.get('year', 'Unknown Year'),
                            'venue': pub.get('venue', 'Unknown Venue'),
                            'citations': citations,
                            'authors': pub.get('authors', []),
                            'url': pub.get('url', ''),
                            'abstract': pub.get('abstract', ''),
                            'is_first_author': pub.get('is_first_author', False)
                        }

                        # Add additional fields if available
                        if 'arxiv_id' in pub:
                            most_cited['arxiv_id'] = pub['arxiv_id']

                        if 'doi' in pub:
                            most_cited['doi'] = pub['doi']

                        # Update the counter
                        counters['most_cited_paper'] = most_cited
                        found_better = True
                except (ValueError, TypeError):
                    continue
                    logger.warning(f"[Scholar ID: {scholar_id}] Final check: most_cited_paper has {counters['most_cited_paper'].get('citations', 0)} citations, but max citation is {max_citation}")
                    logger.warning(f"[Scholar ID: {scholar_id}] Searching for the paper with {max_citation} citations...")

                    # 再次遍历所有论文，找到引用数为 max_citation 的论文
                    for pub in publications:
                        try:
                            citations = int(pub.get('citations', 0))
                            if citations == max_citation:
                                counters['most_cited_paper'] = {
                                    'title': pub.get('title', ''),
                                    'year': pub.get('year', ''),
                                    'venue': pub.get('venue', ''),
                                    'citations': citations,
                                    'authors': pub.get('authors', []),
                                    'author_position': pub.get('author_position', 0)
                                }
                                logger.info(f"[Scholar ID: {scholar_id}] Final fix: Updated most cited paper to '{counters['most_cited_paper']['title']}' with {citations} citations")
                                break
                        except (ValueError, TypeError):
                            continue

    def _log_most_cited_paper_details(self, most_cited_paper, scholar_id, scholar_name):
        """
        Log details about the most cited paper.

        Args:
            most_cited_paper (dict): Most cited paper
            scholar_id (str): Scholar ID for logging
            scholar_name (str): Scholar name
        """
        if most_cited_paper:
            # 将多行日志合并为一行，减少日志量
            title = most_cited_paper.get('title', 'Unknown')
            if len(title) > 50:  # 截断过长的标题
                title = title[:47] + '...'

            # 仅显示前三位作者
            authors = most_cited_paper.get('authors', [])[:3]
            author_text = ', '.join(authors)
            if len(most_cited_paper.get('authors', [])) > 3:
                author_text += '...'

            logger.info(f"[Scholar ID: {scholar_id}] Most cited paper: '{title}' ({most_cited_paper.get('year')}), "
                      f"venue: '{most_cited_paper.get('venue')}', citations: {most_cited_paper.get('citations')}, "
                      f"authors: {author_text}")
        else:
            logger.warning(f"[Scholar ID: {scholar_id}] No most cited paper found for {scholar_name}")

    def _compile_results(self, total_papers, counters, year_distribution, citation_velocity, paper_news):
        """
        Compile analysis results.

        Args:
            total_papers (int): Total number of papers
            counters (dict): Analysis counters
            year_distribution (dict): Year distribution
            citation_velocity (float): Citation velocity
            paper_news (dict): Paper news

        Returns:
            dict: Compiled publication statistics
        """
        # If no pre-computed years_of_papers was found, use the manually calculated year_count
        if not year_distribution:
            # 简化日志，不记录具体年份分布数据
            logger.info("Using manually calculated year distribution")
            year_distribution = dict(sorted(counters['year_count'].items()))

        # Compact large lists (keep output stable and LLM-friendly even with unlimited papers).
        def _read_int_env(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return int(default)
            try:
                return int(raw)
            except (TypeError, ValueError):
                return int(default)

        first_author_limit = max(0, _read_int_env("DINQ_SCHOLAR_FIRST_AUTHOR_PAPERS_LIST_LIMIT", 50))
        top_tier_limit = max(0, _read_int_env("DINQ_SCHOLAR_TOP_TIER_PUBLICATIONS_LIST_LIMIT", 50))

        first_author_list = sorted(
            counters['first_author_papers_list'],
            key=lambda x: int(x.get('citations', 0) or 0),
            reverse=True,
        )
        if first_author_limit:
            first_author_list = first_author_list[:first_author_limit]

        top_tier_publications = counters.get('top_tier_publications') or {'conferences': [], 'journals': []}
        if top_tier_limit:
            top_tier_publications = {
                'conferences': list((top_tier_publications.get('conferences') or [])[:top_tier_limit]),
                'journals': list((top_tier_publications.get('journals') or [])[:top_tier_limit]),
            }

        # Compile results
        publication_stats = {
            'total_papers': total_papers,
            'first_author_papers': counters['first_author_papers'],
            'first_author_percentage': (counters['first_author_papers'] / total_papers * 100) if total_papers > 0 else 0,
            'first_author_citations': counters['first_author_citations'],
            'first_author_papers_list': first_author_list,
            'first_author_avg_citations': (counters['first_author_citations'] / counters['first_author_papers']) if counters['first_author_papers'] > 0 else 0,
            'last_author_papers': counters['last_author_papers'],
            'last_author_percentage': (counters['last_author_papers'] / total_papers * 100) if total_papers > 0 else 0,
            'top_tier_papers': counters['top_tier_papers'],
            'top_tier_percentage': (counters['top_tier_papers'] / total_papers * 100) if total_papers > 0 else 0,
            'conference_distribution': dict(counters['conference_count'].most_common(10)),
            'journal_distribution': dict(counters['journal_count'].most_common(10)),
            'year_distribution': year_distribution,
            'citation_stats': {
                'total_citations': sum(counters['citation_count']),
                'max_citations': max(counters['citation_count']) if counters['citation_count'] else 0,
                'avg_citations': sum(counters['citation_count']) / len(counters['citation_count']) if counters['citation_count'] else 0,
                'median_citations': np.median(counters['citation_count']) if counters['citation_count'] else 0
            },
            'top_tier_publications': top_tier_publications,
            'most_cited_paper': counters['most_cited_paper'],
            'paper_news': paper_news
        }

        if citation_velocity is not None:
            publication_stats['citation_velocity'] = citation_velocity

        paper_of_year_entry = self._build_paper_of_year_entry(counters.get('paper_of_year', {}))
        if paper_of_year_entry:
            publication_stats['paper_of_year'] = paper_of_year_entry

        return publication_stats
