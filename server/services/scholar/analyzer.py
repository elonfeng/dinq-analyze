# coding: UTF-8
"""
Analyzer module for Scholar API service.
Handles analyzing publication data and co-authorship networks.
"""

import copy
import os
import sys
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

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from server.utils.conference_matcher import ConferenceMatcher
from server.services.scholar.config import TOP_TIER_CONFERENCES, TOP_TIER_JOURNALS, TOP_TIER_VENUES
from server.services.scholar.publication_analyzer import PublicationAnalyzer

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

    def analyze_publications(self, author_data):
        """
        Analyze publication data to extract statistics.

        Args:
            author_data (dict): Author data including publications

        Returns:
            dict: Publication statistics
        """
        # 使用专用的 PublicationAnalyzer 类来分析出版物
        return self.publication_analyzer.analyze_publications(author_data)

    def analyze_coauthors(self, author_data):
        """
        Analyze co-authorship network.

        Args:
            author_data (dict): Full author profile

        Returns:
            dict: Co-author statistics
        """
        if not author_data:
            logger.warning("No author data provided for co-author analysis")
            return None

        logger.info(f"Starting co-author analysis for {author_data.get('name', 'unknown researcher')}")

        # Extract coauthors from publication data
        coauthor_counter = Counter()
        coauthor_papers = {}  # Dictionary to store papers by each coauthor
        papers = author_data.get('papers', [])
        logger.debug(f"Found {len(papers)} papers for co-author analysis")

        # Get all possible forms of the main author's name
        main_author_full = author_data.get('name', '')
        main_author_abbrev = author_data.get('abbreviated_name', '')
        main_author_last = main_author_full.split()[-1] if main_author_full else ''

        # Create a set of names to exclude (all forms of the main author)
        exclude_names = {main_author_full, main_author_abbrev}
        # Also exclude any name that matches the pattern "X. Last_name" or "X Last_name"
        if main_author_last:
            exclude_patterns = []
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                exclude_patterns.append(f"{c}. {main_author_last}")
                exclude_patterns.append(f"{c} {main_author_last}")
            for pattern in exclude_patterns:
                exclude_names.add(pattern)

        for paper in papers:
            authors = paper.get('authors', [])
            # Remove the main author from the list (all forms) and filter out "..." placeholders
            filtered_authors = [a for a in authors if a not in exclude_names and a != "..." and not a.strip() == ""]

            for coauthor in filtered_authors:
                coauthor_counter[coauthor] += 1

                # Store paper details for this coauthor
                if coauthor not in coauthor_papers:
                    coauthor_papers[coauthor] = []

                # 获取论文信息
                paper_title = paper.get('title', '')
                paper_year = paper.get('year', '')
                original_venue = paper.get('venue', '')
                paper_citations = paper.get('citations', 0)

                # 记录原始论文信息
                logger.debug(f"Processing paper: '{paper_title}' ({paper_year}) in venue: '{original_venue}'")

                # 使用会议匹配功能处理venue字段
                matched_venue = self.matcher.match_conference_with_year(original_venue) if original_venue else original_venue

                # 如果venue没有匹配到或者匹配结果与原始venue相同，尝试从title匹配
                if matched_venue == original_venue and paper_title:
                    logger.debug(f"Attempting to match from title: '{paper_title}'")
                    title_matched_venue = self.matcher.match_conference_with_year(paper_title)

                    # 只有当title匹配结果不等于title本身时才使用
                    if title_matched_venue != paper_title:
                        logger.info(f"Title matched venue: '{paper_title}' -> '{title_matched_venue}'")
                        matched_venue = title_matched_venue
                    else:
                        logger.debug(f"No title match for: '{paper_title}'")

                # 如果匹配成功但没有年份，而paper有年份，则添加年份
                original_matched_venue = matched_venue
                if matched_venue != original_venue and paper_year and ' ' + str(paper_year) not in matched_venue:
                    # 检查匹配结果是否已经包含年份
                    if not re.search(r'\d{4}', matched_venue):
                        matched_venue = f"{matched_venue} {paper_year}"
                        logger.info(f"Added year to venue: '{original_matched_venue}' -> '{matched_venue}'")

                # 无论是否匹配成功，都添加论文到合作者的论文列表中
                coauthor_papers[coauthor].append({
                    'title': paper_title,
                    'year': paper_year,
                    'venue': matched_venue,
                    'original_venue': original_venue,
                    'citations': paper_citations
                })

        # Get top coauthors
        top_coauthors = []
        logger.info(f"Finding top coauthors from {len(coauthor_counter)} total coauthors")

        for coauthor, count in coauthor_counter.most_common(10):
            logger.debug(f"Processing coauthor: {coauthor} with {count} papers")

            # Find the most cited paper with this coauthor
            best_paper = None
            max_citations = -1

            for paper in coauthor_papers.get(coauthor, []):
                try:
                    citations = int(paper.get('citations', 0))
                    if citations > max_citations:
                        max_citations = citations
                        best_paper = paper
                        logger.debug(f"Found better paper for {coauthor}: '{paper.get('title', '')}' with {citations} citations")
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert citations to integer for paper: {paper.get('title', '')}")
                    continue

            # 记录最佳合作者信息
            if best_paper:
                logger.info(f"Best paper with {coauthor}: '{best_paper.get('title', '')}' in {best_paper.get('venue', '')} with {max_citations} citations")
            else:
                logger.warning(f"No valid papers found for coauthor {coauthor}")

            top_coauthors.append({
                'name': coauthor,
                'coauthored_papers': count,
                'best_paper': best_paper or {'title': 'Unknown', 'citations': 0}
            })

        # 记录最频繁合作者
        most_frequent = None
        if top_coauthors:
            # 确保最佳合作者不是作者自己
            for coauthor_info in top_coauthors:
                coauthor_name = coauthor_info['name']
                # 使用改进的方法检查是否是作者自己
                is_same = self.is_same_person(main_author_full, coauthor_name)
                logger.info(f"Checking if '{main_author_full}' and '{coauthor_name}' are the same person: {is_same}")

                if not is_same:
                    most_frequent = coauthor_info
                    logger.info(f"Most frequent collaborator: {most_frequent['name']} with {most_frequent['coauthored_papers']} papers")
                    logger.info(f"Best paper with most frequent collaborator: '{most_frequent['best_paper'].get('title', '')}' in {most_frequent['best_paper'].get('venue', '')}")
                    break
                else:
                    logger.info(f"Skipping '{coauthor_name}' as it appears to be the same person as '{main_author_full}'")

            # 如果所有合作者都被排除了（极少见的情况）
            if not most_frequent and top_coauthors:
                logger.warning(f"All top coauthors appear to be variants of the main author's name. Searching for next best collaborator.")
                # 尝试找到第二批合作者
                for coauthor, count in coauthor_counter.most_common(20)[10:]:
                    # 跳过已经在top_coauthors中的合作者
                    if any(info['name'] == coauthor for info in top_coauthors):
                        continue

                    # 检查是否是作者自己
                    if self.is_same_person(main_author_full, coauthor):
                        continue

                    # 找到最佳论文
                    best_paper = None
                    max_citations = -1
                    for paper in coauthor_papers.get(coauthor, []):
                        try:
                            citations = int(paper.get('citations', 0))
                            if citations > max_citations:
                                max_citations = citations
                                best_paper = paper
                        except (ValueError, TypeError):
                            continue

                    if best_paper:
                        most_frequent = {
                            'name': coauthor,
                            'coauthored_papers': count,
                            'best_paper': best_paper
                        }
                        logger.info(f"Using alternative collaborator: {most_frequent['name']} with {most_frequent['coauthored_papers']} papers")
                        break

                # 如果仍然没有找到合适的合作者，创建一个空的结果
                if not most_frequent:
                    logger.warning(f"Could not find any suitable collaborator. Creating empty result.")
                    most_frequent = {
                        'name': 'No suitable collaborator found',
                        'coauthored_papers': 0,
                        'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0}
                    }

        # Compile results
        coauthor_stats = {
            'main_author': main_author_full,  # 添加主要作者的名字
            'total_coauthors': len(coauthor_counter),
            'top_coauthors': top_coauthors,
            'collaboration_index': len(coauthor_counter) / len(papers) if papers else 0,
            'most_frequent_collaborator': most_frequent,
            'all_coauthors': coauthor_counter,  # 添加所有合作者的计数
            'coauthor_papers': coauthor_papers  # 添加合作者的论文
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
