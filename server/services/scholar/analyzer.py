# coding: UTF-8
"""
Analyzer module for Scholar API service.
Handles analyzing publication data and co-authorship networks.
"""

import copy
import os
import re
# import numpy as np  # 不再需要
import networkx as nx
import logging
import logging.handlers
from collections import Counter
from server.utils.utils import fuzzy_match_name_improved
# 导入日志配置
from server.utils.logging_config import setup_logging

# 确保日志目录存在
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs'))
os.makedirs(log_dir, exist_ok=True)

# 初始化日志配置
# 注意：如果日志配置已经在其他地方初始化，这里的调用不会有副作用
setup_logging(log_dir)

# 创建模块日志记录器（支持trace ID）
try:
    from server.utils.trace_context import get_trace_logger, get_real_logger
    logger = get_trace_logger('server.services.scholar.analyzer')
    # 获取底层的真实logger来添加handler
    real_logger = get_real_logger('server.services.scholar.analyzer')
except ImportError:
    # Fallback to regular logger if trace context is not available
    logger = logging.getLogger('server.services.scholar.analyzer')
    real_logger = logger

# 确保模块日志记录器有文件处理器
# 创建一个新的文件处理器，专门用于这个模块
module_log_file = os.path.join(log_dir, 'analyzer.log')
file_handler = logging.handlers.RotatingFileHandler(
    module_log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.DEBUG)  # 设置为 DEBUG 级别，捕获所有日志

# 添加处理器到真实的logger对象
real_logger.addHandler(file_handler)

# 设置日志级别
real_logger.setLevel(logging.DEBUG)

# 导入路径设置

from server.utils.conference_matcher import ConferenceMatcher
from server.services.scholar.config import TOP_TIER_CONFERENCES, TOP_TIER_JOURNALS, TOP_TIER_VENUES
from server.services.scholar.publication_analyzer import PublicationAnalyzer
from server.services.scholar.cancel import raise_if_cancelled

class ScholarAnalyzer:
    """
    Handles analyzing publication data and co-authorship networks.
    """

    def __init__(self):
        """
        Initialize the analyzer with conference and journal lists.
        """
        # 测试日志系统

        self.top_tier_conferences = TOP_TIER_CONFERENCES
        self.top_tier_journals = TOP_TIER_JOURNALS
        self.top_tier_venues = TOP_TIER_VENUES

        # 初始化会议匹配器
        self.matcher = ConferenceMatcher()

        # 初始化出版物分析器
        self.publication_analyzer = PublicationAnalyzer()

        logger.info("ScholarAnalyzer initialized successfully")

    def analyze_publications(self, author_data, cancel_event=None):
        """
        Analyze publication data to extract statistics.

        Args:
            author_data (dict): Author data including publications

        Returns:
            dict: Publication statistics
        """
        # 使用专用的 PublicationAnalyzer 类来分析出版物
        return self.publication_analyzer.analyze_publications(author_data, cancel_event=cancel_event)

    def analyze_coauthors(self, author_data, cancel_event=None):
        """
        Analyze co-authorship network.

        Args:
            author_data (dict): Full author profile

        Returns:
            dict: Co-author statistics
        """
        raise_if_cancelled(cancel_event)
        if not author_data:
            logger.warning("No author data provided for co-author analysis")
            return None

        logger.info(f"Starting co-author analysis for {author_data.get('name', 'unknown researcher')}")

        # Extract coauthors from publication data.
        #
        # IMPORTANT (product/cost):
        # - Scholar paper count can be unbounded; do NOT store per-coauthor paper lists (explodes memory/DB/LLM context).
        # - Keep only aggregated counts + best paper per coauthor for stable output size.
        papers = author_data.get('papers', [])
        logger.debug(f"Found {len(papers)} papers for co-author analysis")

        main_author_full = author_data.get('name', '')
        main_author_abbrev = author_data.get('abbreviated_name', '')
        main_author_last = main_author_full.split()[-1] if main_author_full else ''

        exclude_names = {main_author_full, main_author_abbrev}
        if main_author_last:
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                exclude_names.add(f"{c}. {main_author_last}")
                exclude_names.add(f"{c} {main_author_last}")

        coauthor_counter = Counter()
        best_paper_by_coauthor = {}
        best_citations_by_coauthor = {}

        for idx, paper in enumerate(papers):
            if idx % 25 == 0:
                raise_if_cancelled(cancel_event)

            authors = paper.get('authors', []) or []
            title = paper.get('title', '') or ''
            year = paper.get('year', '') or ''
            original_venue = paper.get('venue', '') or ''
            venue_display = original_venue
            try:
                matched = self.matcher.match_conference(original_venue) if original_venue else original_venue
                year_str = str(year).strip()
                if matched and matched != original_venue and year_str.isdigit():
                    venue_display = f"{matched} {year_str}"
                elif matched:
                    venue_display = matched
            except Exception:  # noqa: BLE001
                venue_display = original_venue
            raw_citations = paper.get('citations', 0)
            try:
                citations = int(raw_citations)
            except (TypeError, ValueError):
                citations = 0

            for author in authors:
                if not author or author == "..." or not str(author).strip():
                    continue
                if author in exclude_names:
                    continue
                if main_author_full and self.is_same_person(main_author_full, author):
                    continue

                name = str(author).strip()
                coauthor_counter[name] += 1

                prev_best = best_citations_by_coauthor.get(name, -1)
                if citations > prev_best:
                    best_citations_by_coauthor[name] = citations
                    best_paper_by_coauthor[name] = {
                        'title': title,
                        'year': year,
                        'venue': venue_display,
                        'original_venue': original_venue,
                        'citations': citations,
                    }

        try:
            top_limit = int(os.getenv("DINQ_SCHOLAR_TOP_COAUTHORS_LIMIT", "20") or "20")
        except (TypeError, ValueError):
            top_limit = 20
        top_limit = max(1, min(top_limit, 50))

        top_coauthors = []
        logger.info(f"Finding top coauthors from {len(coauthor_counter)} total coauthors")
        for idx, (coauthor, count) in enumerate(coauthor_counter.most_common(top_limit)):
            if idx % 10 == 0:
                raise_if_cancelled(cancel_event)
            top_coauthors.append(
                {
                    'name': coauthor,
                    'coauthored_papers': int(count),
                    'best_paper': best_paper_by_coauthor.get(coauthor) or {'title': 'Unknown', 'citations': 0},
                }
            )

        # Pick most frequent collaborator (first non-self coauthor).
        most_frequent = None
        for coauthor_info in top_coauthors:
            coauthor_name = coauthor_info.get('name', '')
            if not main_author_full or not self.is_same_person(main_author_full, coauthor_name):
                most_frequent = coauthor_info
                break

        if most_frequent is None:
            most_frequent = {
                'name': 'No suitable collaborator found',
                'coauthored_papers': 0,
                'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
            }

        coauthor_stats = {
            'main_author': main_author_full,
            'total_coauthors': int(len(coauthor_counter)),
            'top_coauthors': top_coauthors,
            'collaboration_index': (len(coauthor_counter) / len(papers)) if papers else 0,
            'most_frequent_collaborator': most_frequent,
        }

        return coauthor_stats

    def generate_coauthor_network(self, author_data):
        """
        Generate a network visualization of co-authors.

        Args:
            author_data (dict): Full author profile

        Returns:
            networkx.Graph: Co-author network graph
        """
        if not author_data or 'papers' not in author_data:
            return None

        # Create a graph
        G = nx.Graph()

        # Add the main author as the central node
        main_author = author_data.get('name', 'Unknown')
        G.add_node(main_author, size=20, color='red', main=True)

        # Get papers and process coauthors
        papers = author_data.get('papers', [])
        coauthor_counter = Counter()

        for paper in papers:
            authors = paper.get('authors', [])

            # Skip papers with no authors
            if not authors:
                continue

            # Add coauthors as nodes and create edges
            for coauthor in authors:
                # Skip if it's the main author
                if coauthor == main_author:
                    continue

                # Count this coauthor
                coauthor_counter[coauthor] += 1

                # Add node if not already in graph
                if not G.has_node(coauthor):
                    G.add_node(coauthor, size=10, color='blue', main=False)

                # Add edge between main author and coauthor
                if not G.has_edge(main_author, coauthor):
                    G.add_edge(main_author, coauthor, weight=1)
                else:
                    # Increase edge weight for repeat collaborations
                    G[main_author][coauthor]['weight'] += 1

        # Update node sizes based on collaboration frequency
        for coauthor, count in coauthor_counter.items():
            # Skip if node doesn't exist (shouldn't happen, but just in case)
            if not G.has_node(coauthor):
                continue

            # Scale node size based on collaboration count
            G.nodes[coauthor]['size'] = 5 + (count * 2)
            G.nodes[coauthor]['collaborations'] = count

        return G

    def calculate_researcher_rating(self, author_data, pub_stats):
        """
        Calculate an overall rating for the researcher based on various metrics.

        Args:
            author_data (dict): Full author profile
            pub_stats (dict): Publication statistics

        Returns:
            dict: Rating details
        """
        if not author_data or not pub_stats:
            return None

        # Initialize rating components
        h_index_score = 0
        citation_score = 0
        publication_score = 0
        top_tier_score = 0
        first_author_score = 0

        # H-index rating (0-10)
        h_index = author_data.get('h_index', 0)
        if h_index >= 40:
            h_index_score = 10
        elif h_index >= 30:
            h_index_score = 9
        elif h_index >= 20:
            h_index_score = 8
        elif h_index >= 15:
            h_index_score = 7
        elif h_index >= 10:
            h_index_score = 6
        elif h_index >= 7:
            h_index_score = 5
        elif h_index >= 5:
            h_index_score = 4
        elif h_index >= 3:
            h_index_score = 3
        elif h_index >= 1:
            h_index_score = 2
        else:
            h_index_score = 1

        # Citation rating (0-10)
        total_citations = author_data.get('total_citations', 0)
        if total_citations >= 10000:
            citation_score = 10
        elif total_citations >= 5000:
            citation_score = 9
        elif total_citations >= 2000:
            citation_score = 8
        elif total_citations >= 1000:
            citation_score = 7
        elif total_citations >= 500:
            citation_score = 6
        elif total_citations >= 200:
            citation_score = 5
        elif total_citations >= 100:
            citation_score = 4
        elif total_citations >= 50:
            citation_score = 3
        elif total_citations >= 10:
            citation_score = 2
        else:
            citation_score = 1

        # Publication quantity rating (0-10)
        total_papers = pub_stats.get('total_papers', 0)
        if total_papers >= 100:
            publication_score = 10
        elif total_papers >= 70:
            publication_score = 9
        elif total_papers >= 50:
            publication_score = 8
        elif total_papers >= 30:
            publication_score = 7
        elif total_papers >= 20:
            publication_score = 6
        elif total_papers >= 15:
            publication_score = 5
        elif total_papers >= 10:
            publication_score = 4
        elif total_papers >= 5:
            publication_score = 3
        elif total_papers >= 2:
            publication_score = 2
        else:
            publication_score = 1

        # Top-tier publication rating (0-10)
        top_tier_papers = pub_stats.get('top_tier_papers', 0)
        if top_tier_papers >= 20:
            top_tier_score = 10
        elif top_tier_papers >= 15:
            top_tier_score = 9
        elif top_tier_papers >= 10:
            top_tier_score = 8
        elif top_tier_papers >= 7:
            top_tier_score = 7
        elif top_tier_papers >= 5:
            top_tier_score = 6
        elif top_tier_papers >= 3:
            top_tier_score = 5
        elif top_tier_papers >= 2:
            top_tier_score = 4
        elif top_tier_papers >= 1:
            top_tier_score = 3
        else:
            top_tier_score = 1

        # First-author publication rating (0-10)
        first_author_papers = pub_stats.get('first_author_papers', 0)
        first_author_percentage = pub_stats.get('first_author_percentage', 0)

        if first_author_papers >= 10 and first_author_percentage >= 40:
            first_author_score = 10
        elif first_author_papers >= 7 and first_author_percentage >= 35:
            first_author_score = 9
        elif first_author_papers >= 5 and first_author_percentage >= 30:
            first_author_score = 8
        elif first_author_papers >= 4 and first_author_percentage >= 25:
            first_author_score = 7
        elif first_author_papers >= 3 and first_author_percentage >= 20:
            first_author_score = 6
        elif first_author_papers >= 2 and first_author_percentage >= 15:
            first_author_score = 5
        elif first_author_papers >= 1 and first_author_percentage >= 10:
            first_author_score = 4
        elif first_author_papers >= 1:
            first_author_score = 3
        else:
            first_author_score = 1

        # Calculate overall score (weighted average)
        overall_score = (
            (h_index_score * 0.25) +
            (citation_score * 0.25) +
            (publication_score * 0.15) +
            (top_tier_score * 0.2) +
            (first_author_score * 0.15)
        )

        # Determine researcher level based on overall score
        if overall_score >= 9:
            level = "Distinguished Researcher"
        elif overall_score >= 8:
            level = "Senior Researcher"
        elif overall_score >= 7:
            level = "Established Researcher"
        elif overall_score >= 6:
            level = "Mid-Career Researcher"
        elif overall_score >= 5:
            level = "Early-Career Researcher"
        elif overall_score >= 3:
            level = "Junior Researcher"
        else:
            level = "Emerging Researcher"

        # Compile rating details
        rating = {
            'h_index_score': h_index_score,
            'citation_score': citation_score,
            'publication_score': publication_score,
            'top_tier_score': top_tier_score,
            'first_author_score': first_author_score,
            'overall_score': overall_score,
            'level': level
        }

        return rating

    def is_same_person(self, researcher_name, collaborator_name):
        """
        改进的方法来检查研究者和合作者是否是同一个人

        Args:
            researcher_name (str): 研究者姓名
            collaborator_name (str): 合作者姓名

        Returns:
            bool: 是否是同一个人
        """
        # 记录详细日志，帮助调试
        logger.debug(f"Checking if '{researcher_name}' and '{collaborator_name}' are the same person")

        # 如果任一名字为空，返回False
        if not researcher_name or not collaborator_name:
            logger.debug("One of the names is empty, returning False")
            return False

        # 如果名字完全相同，直接返回True
        if researcher_name.lower() == collaborator_name.lower():
            logger.debug("Names are identical (case-insensitive), returning True")
            return True
        # 首先使用 fuzzy_match_name_improved 进行匹配
        
        if fuzzy_match_name_improved(researcher_name, [collaborator_name]):
            logger.debug(f"Names matched using fuzzy_match_name_improved")
            return True
        # 特殊情况：处理"Yann LeCun"这样的特殊名字
        # 这些名字在学术界非常知名，可能有特殊的变体
        known_researchers = {
            "yann lecun": ["yann lecun", "y lecun", "y. lecun", "lecun"],
            "geoffrey hinton": ["geoffrey hinton", "g hinton", "g. hinton", "geoff hinton", "geoffrey e hinton", "geoffrey e. hinton", "g e hinton", "g. e. hinton", "ge hinton"],
            "yoshua bengio": ["yoshua bengio", "y bengio", "y. bengio"],
            "andrew ng": ["andrew ng", "a ng", "a. ng"],
            "fei-fei li": ["fei-fei li", "fei fei li", "f li", "f. li", "feifei li"],
            "ilya sutskever": ["ilya sutskever", "i sutskever", "i. sutskever"],
        }

        # 检查是否是已知研究者的变体
        researcher_lower = researcher_name.lower()
        collaborator_lower = collaborator_name.lower()

        for known_name, variants in known_researchers.items():
            if researcher_lower in variants and collaborator_lower in variants:
                logger.debug(f"Both names are variants of known researcher '{known_name}', returning True")
                return True

        # 获取研究者姓氏和名字部分
        researcher_parts = researcher_name.split()
        researcher_last_name = researcher_parts[-1].lower() if researcher_parts else ''
        researcher_first_parts = [p.lower() for p in researcher_parts[:-1]] if len(researcher_parts) > 1 else []

        # 获取合作者姓氏和名字部分
        collaborator_parts = collaborator_name.split()
        collaborator_last_name = collaborator_parts[-1].lower() if collaborator_parts else ''
        collaborator_first_parts = [p.lower() for p in collaborator_parts[:-1]] if len(collaborator_parts) > 1 else []

        # 检查姓氏是否相同
        if researcher_last_name == collaborator_last_name:
            logger.debug(f"Last names match: '{researcher_last_name}'")

            # 情况1: 一方的名字是另一方名字的缩写
            # 例如: "John Smith" 和 "J. Smith"
            if researcher_first_parts and collaborator_first_parts:
                for r_part in researcher_first_parts:
                    for c_part in collaborator_first_parts:
                        # 检查缩写情况
                        if (len(r_part) == 1 or r_part.endswith('.')) and c_part.startswith(r_part[0]):
                            logger.debug(f"Abbreviation match: '{r_part}' is abbreviation of '{c_part}'")
                            return True
                        if (len(c_part) == 1 or c_part.endswith('.')) and r_part.startswith(c_part[0]):
                            logger.debug(f"Abbreviation match: '{c_part}' is abbreviation of '{r_part}'")
                            return True

            # 情况2: 名字部分完全匹配
            if researcher_first_parts == collaborator_first_parts:
                logger.debug("First name parts match exactly")
                return True

            # 情况3: 一方只有姓氏，另一方有完整名字
            if (not researcher_first_parts and collaborator_first_parts) or (researcher_first_parts and not collaborator_first_parts):
                logger.debug("One name has only last name, the other has full name")
                return True

            # 情况4: 处理首字母缩写形式，如"GE Hinton"和"Geoffrey E Hinton"
            if len(researcher_first_parts) > 0 and len(collaborator_first_parts) > 0:
                # 获取所有首字母
                researcher_initials = ''.join(p[0].lower() for p in researcher_first_parts)
                collaborator_initials = ''.join(p[0].lower() for p in collaborator_first_parts)

                logger.debug(f"Checking initials: '{researcher_initials}' vs '{collaborator_initials}'")

                # 检查一个名字是否是另一个名字的首字母缩写
                if (len(''.join(collaborator_first_parts)) <= len(researcher_first_parts) and
                    collaborator_initials == ''.join(p[0].lower() for p in researcher_first_parts[:len(collaborator_initials)])):
                    logger.debug(f"Initials match: '{collaborator_initials}' matches first letters of '{researcher_first_parts}'")
                    return True

                if (len(''.join(researcher_first_parts)) <= len(collaborator_first_parts) and
                    researcher_initials == ''.join(p[0].lower() for p in collaborator_first_parts[:len(researcher_initials)])):
                    logger.debug(f"Initials match: '{researcher_initials}' matches first letters of '{collaborator_first_parts}'")
                    return True

            # 情况5: 检查第一个名字是否相同，其他名字是中间名
            # 例如: "Geoffrey Hinton" 和 "Geoffrey E. Hinton"
            if researcher_first_parts and collaborator_first_parts:
                if researcher_first_parts[0] == collaborator_first_parts[0]:
                    logger.debug(f"First name parts match: '{researcher_first_parts[0]}' == '{collaborator_first_parts[0]}'")
                    return True

        # 特殊情况: 处理"GE Hinton"这样的形式
        # 检查是否是首字母缩写形式，如"GE"代表"Geoffrey E"
        if len(researcher_parts) >= 2 and len(collaborator_parts) >= 2:
            # 检查是否有一个部分看起来像是首字母缩写（没有点号的多个大写字母）
            r_first = researcher_parts[0]
            c_first = collaborator_parts[0]

            # 检查是否是全大写的首字母缩写
            r_is_initials = len(r_first) > 1 and r_first.isupper() and '.' not in r_first
            c_is_initials = len(c_first) > 1 and c_first.isupper() and '.' not in c_first

            logger.debug(f"Checking for uppercase initials: r_is_initials={r_is_initials}, c_is_initials={c_is_initials}")

            if r_is_initials or c_is_initials:
                # 如果一方是首字母缩写，另一方是完整名字
                if r_is_initials and not c_is_initials:
                    # 检查"GE"是否匹配"Geoffrey E"的首字母
                    c_initials = ''.join(p[0].upper() for p in collaborator_first_parts)
                    logger.debug(f"Checking if '{r_first}' matches initials '{c_initials}'")
                    if r_first == c_initials and researcher_last_name == collaborator_last_name:
                        logger.debug(f"Uppercase initials match: '{r_first}' == '{c_initials}'")
                        return True
                elif c_is_initials and not r_is_initials:
                    # 检查"GE"是否匹配"Geoffrey E"的首字母
                    r_initials = ''.join(p[0].upper() for p in researcher_first_parts)
                    logger.debug(f"Checking if '{c_first}' matches initials '{r_initials}'")
                    if c_first == r_initials and researcher_last_name == collaborator_last_name:
                        logger.debug(f"Uppercase initials match: '{c_first}' == '{r_initials}'")
                        return True

        # 特殊情况: 处理名字中包含连字符或空格的情况
        # 例如: "Jean-Baptiste" 可能被写作 "Jean Baptiste"
        r_name_no_hyphen = researcher_name.replace('-', ' ').lower()
        c_name_no_hyphen = collaborator_name.replace('-', ' ').lower()

        if r_name_no_hyphen == c_name_no_hyphen:
            logger.debug(f"Names match after removing hyphens")
            return True

        # 特殊情况: 处理名字中包含缩写的情况
        # 例如: "J.B. Smith" 和 "Jean-Baptiste Smith"
        if researcher_last_name == collaborator_last_name:
            # 获取首字母缩写
            r_initials = ''.join(p[0].lower() for p in researcher_first_parts)
            c_initials = ''.join(p[0].lower() for p in collaborator_first_parts)

            # 检查缩写是否匹配
            if r_initials and c_initials and (r_initials == c_initials):
                logger.debug(f"First name initials match: '{r_initials}' == '{c_initials}'")
                return True

        # 特殊情况: 处理名字中包含中间名首字母的情况
        # 例如: "Geoffrey E Hinton" 和 "Geoffrey Hinton"
        if researcher_last_name == collaborator_last_name and researcher_first_parts and collaborator_first_parts:
            # 如果一方的名字是另一方名字的子集
            r_first_set = set(researcher_first_parts)
            c_first_set = set(collaborator_first_parts)

            # 检查一方的名字是否是另一方名字的子集
            if r_first_set.issubset(c_first_set) or c_first_set.issubset(r_first_set):
                logger.debug(f"One name is subset of the other: {r_first_set} vs {c_first_set}")
                return True

            # 检查第一个名字是否相同，其他名字是中间名首字母
            if researcher_first_parts[0] == collaborator_first_parts[0]:
                # 如果第一个名字相同，检查其他部分是否可能是中间名首字母
                if len(researcher_first_parts) > 1 and len(collaborator_first_parts) == 1:
                    # 例如: "Geoffrey E" 和 "Geoffrey"
                    logger.debug(f"First name matches, one has middle initial: {researcher_first_parts} vs {collaborator_first_parts}")
                    return True
                elif len(collaborator_first_parts) > 1 and len(researcher_first_parts) == 1:
                    # 例如: "Geoffrey" 和 "Geoffrey E"
                    logger.debug(f"First name matches, one has middle initial: {researcher_first_parts} vs {collaborator_first_parts}")
                    return True

        # 如果所有检查都失败，返回False
        logger.debug(f"No match found between '{researcher_name}' and '{collaborator_name}'")
        return False

    def is_same_author(self, name1, name2):
        """
        Check if two author names likely refer to the same person.

        Args:
            name1 (str): First author name
            name2 (str): Second author name

        Returns:
            bool: True if names likely refer to same person
        """
        # 使用改进的方法
        return self.is_same_person(name1, name2)

    def match_author_name(self, abbreviated_name, full_author_details):
        """
        Match an abbreviated author name with full author details.

        Args:
            abbreviated_name (str): Abbreviated author name (e.g., "D. Gao")
            full_author_details (dict): Dictionary of author details keyed by scholar_id

        Returns:
            str or None: Scholar ID if match found, None otherwise
        """
        # Check if the name is already in abbreviated format (e.g., "D. Gao")
        name_parts = abbreviated_name.split()

        # If we have at least a first initial and last name
        if len(name_parts) >= 2:
            first_part = name_parts[0]
            last_part = name_parts[-1]

            # Check if first part is an initial (e.g., "D." or "D")
            is_initial = len(first_part) <= 2 and first_part[0].isalpha()

            if is_initial:
                initial = first_part[0].lower()
                last_name = last_part.lower()

                # Look through all author details for a match
                for scholar_id, details in full_author_details.items():
                    full_name = details.get('full_name', '')
                    if not full_name:
                        continue

                    full_name_parts = full_name.split()
                    if len(full_name_parts) >= 2:
                        # Check if first initial and last name match
                        if full_name_parts[0][0].lower() == initial and full_name_parts[-1].lower() == last_name:
                            return scholar_id
            else:
                # If not an initial, try matching the full name
                for scholar_id, details in full_author_details.items():
                    if self.is_same_author(abbreviated_name, details.get('full_name', '')):
                        return scholar_id
        else:
            # If name only has one part, just match by last name
            for scholar_id, details in full_author_details.items():
                full_name = details.get('full_name', '')
                if full_name and full_name.lower().endswith(abbreviated_name.lower()):
                    return scholar_id

        return None
