# coding: UTF-8
"""
Collaborator Service - Module for handling collaborator-related functionality.
Provides functions to find and process information about a researcher's collaborators.
"""

import json
import logging
from typing import Dict, Any, Optional

# 获取collaborator服务的日志记录器
logger = logging.getLogger('server.services.scholar.collaborator')

# 导入获取作者详情的函数
from onepage.openrouter_author_list import get_author_detail
# 导入模糊匹配和从论文中获取作者的函数
from server.utils.utils import fuzzy_match_name
from onepage.author_paper import find_authors_from_title_new
# 导入改进的名字匹配方法
from server.services.scholar.analyzer import ScholarAnalyzer

def get_best_collaborator(data_fetcher, coauthor_stats: Dict[str, Any], callback=None, analyzer=None) -> Dict[str, Any]:
    """
    获取研究者的最佳合作者信息。

    首先尝试使用 get_author_detail 函数获取作者详情，如果失败则回退到使用 data_fetcher。
    确保返回的合作者不是研究者自己，通过多种方法验证。

    Args:
        data_fetcher: ScholarDataFetcher 实例，用于获取学者数据
        coauthor_stats (Dict[str, Any]): 合作者统计信息
        callback (callable, optional): 回调函数，用于报告状态
        analyzer (ScholarAnalyzer, optional): 分析器实例，用于名字匹配

    Returns:
        Dict[str, Any]: 最佳合作者信息，如果没有找到则返回默认对象
    """
    # 导入状态报告函数
    from server.services.scholar.status_reporter import send_status
    # 导入名字安全检查函数
    from server.services.scholar.name_safety_check import ensure_different_person
    most_frequent_collaborator = None

    # 使用传入的分析器或创建新的ScholarAnalyzer实例
    name_matcher = analyzer if analyzer else ScholarAnalyzer()

    if coauthor_stats and 'top_coauthors' in coauthor_stats and coauthor_stats['top_coauthors']:
        try:
            # 获取主要作者的名字
            main_author_name = coauthor_stats.get('main_author', '')
            if not main_author_name:
                logger.warning("Main author name not found in coauthor_stats")
                if callback:
                    send_status("Warning: Main author name not found", callback)

            # 遍历合作者列表，找到第一个不是主要作者自己的合作者
            selected_coauthor = None
            for top_coauthor in coauthor_stats['top_coauthors']:
                coauthor_name = top_coauthor['name']

                # 使用多种方法检查合作者是否是主要作者自己
                is_same_analyzer = main_author_name and name_matcher.is_same_person(main_author_name, coauthor_name)
                is_same_safety = main_author_name and not ensure_different_person(main_author_name, coauthor_name)

                if is_same_analyzer or is_same_safety:
                    logger.warning(f"Skipping collaborator '{coauthor_name}' as it appears to be the same person as '{main_author_name}'")
                    if callback:
                        send_status(f"Skipping collaborator '{coauthor_name}' (appears to be the researcher)", callback)
                    continue

                # 找到了不是主要作者自己的合作者
                logger.info(f"Selected collaborator: {coauthor_name}")
                if callback:
                    send_status(f"Selected collaborator: {coauthor_name}", callback)
                selected_coauthor = top_coauthor
                break

            # 如果没有找到合适的合作者，尝试在更多的合作者中查找
            if not selected_coauthor and len(coauthor_stats.get('all_coauthors', [])) > len(coauthor_stats['top_coauthors']):
                logger.warning("No suitable collaborator found in top coauthors, searching in more coauthors")
                if callback:
                    send_status("Searching among more collaborators...", callback)

                # 按合作次数排序
                sorted_coauthors = sorted(coauthor_stats.get('all_coauthors', {}).items(), key=lambda x: x[1], reverse=True)

                # 跳过前几名（已经在top_coauthors中检查过）
                top_count = len(coauthor_stats['top_coauthors'])
                for coauthor_name, count in sorted_coauthors[top_count:top_count+20]:  # 只检查接下来的20个合作者
                    # 跳过已经在top_coauthors中检查过的合作者
                    if any(c['name'] == coauthor_name for c in coauthor_stats['top_coauthors']):
                        continue

                    # 使用多种方法检查合作者是否是主要作者自己
                    is_same_analyzer = main_author_name and name_matcher.is_same_person(main_author_name, coauthor_name)
                    is_same_safety = main_author_name and not ensure_different_person(main_author_name, coauthor_name)

                    if is_same_analyzer or is_same_safety:
                        logger.warning(f"Skipping alternative collaborator '{coauthor_name}' as it appears to be the same person as '{main_author_name}'")
                        continue

                    # 找到了不是主要作者自己的合作者
                    logger.info(f"Selected alternative collaborator: {coauthor_name}")
                    if callback:
                        send_status(f"Found alternative collaborator: {coauthor_name}", callback)

                    # 找到这个合作者的最佳论文
                    best_paper = None
                    for paper in coauthor_stats.get('coauthor_papers', {}).get(coauthor_name, []):
                        if not best_paper or int(paper.get('citations', 0)) > int(best_paper.get('citations', 0)):
                            best_paper = paper

                    if best_paper:
                        selected_coauthor = {
                            'name': coauthor_name,
                            'coauthored_papers': count,
                            'best_paper': best_paper
                        }
                        break

            # 如果仍然没有找到合适的合作者，返回空结果
            if not selected_coauthor:
                logger.warning("No suitable collaborator found")
                if callback:
                    send_status("Could not find suitable collaborator, using default", callback)
                return {
                    'full_name': 'No suitable collaborator found',
                    'affiliation': 'N/A',
                    'research_interests': [],
                    'scholar_id': '',
                    'coauthored_papers': 0,
                    'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
                    'h_index': 'N/A',
                    'total_citations': 'N/A'
                }

            # 使用选定的合作者信息
            coauthor_name = selected_coauthor['name']
            best_paper_title = selected_coauthor.get('best_paper', {}).get('title', '')

            # 从论文中获取作者列表
            logger.info(f"Finding authors from paper title: {best_paper_title}")
            candidate_author_list = find_authors_from_title_new(best_paper_title)

            # 检查 candidate_author_list 是否为 None
            if candidate_author_list is None:
                logger.warning(f"Could not find authors from paper title: {best_paper_title}")
                candidate_author_list = []

            # 过滤掉 "..." 这样的占位符和空字符串
            candidate_author_list = [author for author in candidate_author_list if author != "..." and author.strip() != ""]
            logger.info(f"Filtered author list: {candidate_author_list}")

            # 模糊匹配合作者
            full_name = coauthor_name
            if candidate_author_list:
                closest_match = fuzzy_match_name(coauthor_name, candidate_author_list)

                if closest_match:
                    closest_match = closest_match.strip()
                    # 处理“Alexander and ...”这样的情况，可能会触发bug
                    if " and " in closest_match:
                        closest_match = closest_match.split("and")[-1].strip()

                    logger.info(f"Found full name match: {closest_match} for {coauthor_name}")
                    full_name = closest_match

            # 首先尝试使用 get_author_detail 函数获取作者详情
            logger.info(f"Attempting to get details for collaborator {full_name} using get_author_detail")

            # 准备传递给 get_author_detail 的信息
            coauthor_info = json.dumps({
                'name': full_name,  # 使用匹配到的全名
                'coauthored_papers': selected_coauthor['coauthored_papers'],
                'best_paper': selected_coauthor.get('best_paper', {})
            })

            try:
                # 使用 get_author_detail 函数获取作者详情
                import time
                author_details = get_author_detail(coauthor_info)
                if author_details and author_details.get('name') != 'Unknown':
                    logger.info(f"Successfully retrieved details for collaborator {full_name} using get_author_detail")

                    # 创建最佳合作者对象
                    most_frequent_collaborator = {
                        'full_name': full_name,  # 使用我们匹配到的全名，不使用AI返回的名字
                        'affiliation': author_details.get('affiliation', 'Unknown'),
                        'research_interests': [],  # get_author_detail 不提供研究兴趣
                        'scholar_id': '',  # get_author_detail 不提供学者ID
                        'coauthored_papers': selected_coauthor['coauthored_papers'],
                        'best_paper': selected_coauthor['best_paper'],
                        'h_index': 'N/A',
                        'total_citations': 'N/A',
                        'photo': author_details.get('photo'),  # 添加照片URL
                        'graduate_school': author_details.get('graduate_school'),  # 添加毕业学校
                        'description': author_details.get('description')  # 添加描述
                    }
                else:
                    logger.warning(f"Failed to get meaningful details for collaborator {full_name} using get_author_detail, falling back to data_fetcher")
                    # 如果 get_author_detail 失败，回退到使用 data_fetcher
                                        # 创建最佳合作者对象
                    most_frequent_collaborator = {
                        'full_name': full_name,
                        'affiliation': '',
                        'research_interests': [],  # get_author_detail 不提供研究兴趣
                        'scholar_id': '',  # get_author_detail 不提供学者ID
                        'coauthored_papers': selected_coauthor['coauthored_papers'],
                        'best_paper': selected_coauthor['best_paper'],
                        'h_index': 'N/A',
                        'total_citations': 'N/A'
                    }
            except Exception as e:
                logger.error(f"Error using get_author_detail for collaborator {full_name}: {e}")
                most_frequent_collaborator = None

            #如果 get_author_detail 失败，使用原有的方式
        #     if most_frequent_collaborator is None:
        #         logger.info(f"Falling back to data_fetcher for collaborator {full_name}")

        #         # Search for this coauthor on Google Scholar using the best paper title to get full name
        #         # 使用模糊匹配到的全名进行搜索
        #         coauthor_search_results = data_fetcher.search_author_by_name_new(full_name, paper_title=best_paper_title)

        #         if coauthor_search_results:
        #             # Get the first result (most relevant)
        #             coauthor_id = coauthor_search_results[0]['scholar_id']
        #             print(f"coauthor_id::{coauthor_id}")
        #             coauthor_details = data_fetcher.get_author_details_by_id(coauthor_id)

        #             if coauthor_details:
        #                 logger.info(f"Successfully retrieved details for collaborator {full_name} using data_fetcher")
        #                 most_frequent_collaborator = {
        #                     'full_name': coauthor_details.get('full_name', full_name),
        #                     'affiliation': coauthor_details.get('affiliation', 'Unknown'),
        #                     'research_interests': coauthor_details.get('research_interests', []),
        #                     'scholar_id': coauthor_id,
        #                     'coauthored_papers': selected_coauthor['coauthored_papers'],
        #                     'best_paper': selected_coauthor['best_paper'],
        #                     'h_index': 'N/A',  # Add default h_index
        #                     'total_citations': 'N/A'  # Add default total_citations
        #                 }
        #             else:
        #                 logger.warning(f"Failed to get author details for collaborator {full_name} using data_fetcher")
        #         else:
        #             logger.warning(f"No search results found for collaborator {full_name} using data_fetcher")
        except Exception as e:
            logger.error(f"Error finding most frequent collaborator: {e}")
            # 如果出现错误，创建一个空的合作者对象
            most_frequent_collaborator = None

    # 如果没有找到最佳合作者，创建一个空的合作者对象
    if most_frequent_collaborator is None:
        logger.warning("No most frequent collaborator found or error occurred. Creating empty collaborator object.")
        if callback:
            send_status("Could not find collaborator information, using default", callback)
        most_frequent_collaborator = {
            'full_name': 'No frequent collaborator found',
            'affiliation': 'N/A',
            'research_interests': [],
            'scholar_id': '',
            'coauthored_papers': 0,
            'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
            'h_index': 'N/A',
            'total_citations': 'N/A'
        }

    return most_frequent_collaborator
