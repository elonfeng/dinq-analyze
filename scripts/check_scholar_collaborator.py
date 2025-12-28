#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查学者最佳合作者脚本

这个脚本接受一个学者ID作为参数，使用线上的代码处理方式获取该学者的最佳合作者信息，
并检查最佳合作者是否是学者自己。
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, Any, Optional
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 配置日志
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'scholar_collaborator_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('scholar_collaborator')

# 导入必要的模块
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.analyzer import ScholarAnalyzer
from server.services.scholar.collaborator_service import get_best_collaborator
from server.config.api_keys import API_KEYS

def is_same_person(researcher_name: str, collaborator_name: str) -> bool:
    """
    检查研究者和合作者是否是同一个人（使用简单的检查方法）

    Args:
        researcher_name: 研究者姓名
        collaborator_name: 合作者姓名

    Returns:
        bool: 是否是同一个人
    """
    # 如果名字完全相同，直接返回True
    if researcher_name.lower() == collaborator_name.lower():
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
        # 如果姓氏相同，检查名字部分

        # 情况1: 一方的名字是另一方名字的缩写
        # 例如: "John Smith" 和 "J. Smith"
        if researcher_first_parts and collaborator_first_parts:
            for r_part in researcher_first_parts:
                for c_part in collaborator_first_parts:
                    # 检查缩写情况
                    if (len(r_part) == 1 or r_part.endswith('.')) and c_part.startswith(r_part[0]):
                        return True
                    if (len(c_part) == 1 or c_part.endswith('.')) and r_part.startswith(c_part[0]):
                        return True

        # 情况2: 名字部分完全匹配
        if researcher_first_parts == collaborator_first_parts:
            return True

        # 情况3: 一方只有姓氏，另一方有完整名字
        if (not researcher_first_parts and collaborator_first_parts) or (researcher_first_parts and not collaborator_first_parts):
            return True

        # 情况4: 第一个名字相同，其他可能是中间名
        if researcher_first_parts and collaborator_first_parts:
            if researcher_first_parts[0] == collaborator_first_parts[0]:
                return True

    return False

def check_scholar_collaborator(scholar_id: str, use_analyzer: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """
    检查学者的最佳合作者

    Args:
        scholar_id: 学者ID
        use_analyzer: 是否使用ScholarAnalyzer的is_same_person方法
        verbose: 是否输出详细信息

    Returns:
        Dict[str, Any]: 检查结果
    """
    try:
        logger.info(f"正在处理学者ID: {scholar_id}")

        # 创建数据获取器
        api_token = API_KEYS.get('CRAWLBASE_API_TOKEN', '')
        data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)

        # 搜索学者
        author_info = data_fetcher.search_researcher(scholar_id=scholar_id)
        if not author_info:
            logger.error(f"无法找到学者信息: {scholar_id}")
            return {
                'scholar_id': scholar_id,
                'error': '无法找到学者信息',
                'status': 'error'
            }

        # 获取学者名称
        researcher_name = author_info.get('name', '')
        logger.info(f"找到学者: {researcher_name} (ID: {scholar_id})")

        # 获取完整资料
        author_data = data_fetcher.get_full_profile(author_info)
        if not author_data:
            logger.error(f"无法获取学者完整资料: {researcher_name} (ID: {scholar_id})")
            return {
                'name': researcher_name,
                'scholar_id': scholar_id,
                'error': '无法获取学者完整资料',
                'status': 'error'
            }

        # 分析合作者
        analyzer = ScholarAnalyzer()
        coauthor_stats = analyzer.analyze_coauthors(author_data)

        if not coauthor_stats:
            logger.error(f"无法分析合作者: {researcher_name} (ID: {scholar_id})")
            return {
                'name': researcher_name,
                'scholar_id': scholar_id,
                'error': '无法分析合作者',
                'status': 'error'
            }

        # 输出合作者统计信息
        if verbose:
            logger.info(f"合作者统计信息:")
            logger.info(f"  总合作者数: {coauthor_stats.get('total_coauthors', 0)}")
            logger.info(f"  合作指数: {coauthor_stats.get('collaboration_index', 0):.2f}")

            # 输出前5名合作者
            top_coauthors = coauthor_stats.get('top_coauthors', [])
            logger.info(f"  前{len(top_coauthors)}名合作者:")
            for i, coauthor in enumerate(top_coauthors[:5]):
                logger.info(f"    {i+1}. {coauthor.get('name', '')} ({coauthor.get('coauthored_papers', 0)}篇论文)")

        # 获取最佳合作者（使用线上的代码处理方式）
        most_frequent_collaborator = get_best_collaborator(data_fetcher, coauthor_stats)

        if not most_frequent_collaborator:
            logger.error(f"无法获取最佳合作者: {researcher_name} (ID: {scholar_id})")
            return {
                'name': researcher_name,
                'scholar_id': scholar_id,
                'error': '无法获取最佳合作者',
                'status': 'error'
            }

        # 检查是否是默认的空合作者对象
        if most_frequent_collaborator.get('full_name') == 'No frequent collaborator found':
            logger.warning(f"获取到默认的空合作者对象，尝试从coauthor_stats直接获取最佳合作者")

            # 尝试从coauthor_stats直接获取最佳合作者
            if coauthor_stats and 'most_frequent_collaborator' in coauthor_stats:
                most_frequent = coauthor_stats['most_frequent_collaborator']
                if most_frequent:
                    logger.info(f"从coauthor_stats获取到最佳合作者: {most_frequent.get('name', '')}")

                    # 创建一个基本的合作者对象
                    most_frequent_collaborator = {
                        'full_name': most_frequent.get('name', 'Unknown'),
                        'affiliation': 'Unknown',
                        'research_interests': [],
                        'scholar_id': '',
                        'coauthored_papers': most_frequent.get('coauthored_papers', 0),
                        'best_paper': most_frequent.get('best_paper', {}),
                        'h_index': 'N/A',
                        'total_citations': 'N/A'
                    }

        # 获取合作者信息
        collaborator_name = most_frequent_collaborator.get('full_name', '')
        collaborator_affiliation = most_frequent_collaborator.get('affiliation', '')
        coauthored_papers = most_frequent_collaborator.get('coauthored_papers', 0)
        best_paper = most_frequent_collaborator.get('best_paper', {})

        # 检查是否是同一个人
        is_same = False
        if use_analyzer:
            # 使用ScholarAnalyzer的is_same_person方法
            is_same = analyzer.is_same_person(researcher_name, collaborator_name)
        else:
            # 使用简单的检查方法
            is_same = is_same_person(researcher_name, collaborator_name)

        # 输出结果
        logger.info(f"学者 {researcher_name} 的最佳合作者是 {collaborator_name} ({collaborator_affiliation})")
        logger.info(f"合作论文数: {coauthored_papers}")
        logger.info(f"最佳合作论文: {best_paper.get('title', '')}")
        logger.info(f"是否是同一人: {is_same}")

        # 返回结果
        result = {
            'name': researcher_name,
            'scholar_id': scholar_id,
            'collaborator_name': collaborator_name,
            'collaborator_affiliation': collaborator_affiliation,
            'coauthored_papers': coauthored_papers,
            'best_paper': best_paper,
            'is_same_person': is_same,
            'status': 'success'
        }

        # 保存结果
        output_path = os.path.join(project_root, f'collaborator_{scholar_id}.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"已保存结果到: {output_path}")

        return result

    except Exception as e:
        logger.error(f"处理学者ID: {scholar_id} 时出错: {str(e)}")
        return {
            'scholar_id': scholar_id,
            'error': str(e),
            'status': 'error'
        }

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='检查学者最佳合作者')
    parser.add_argument('scholar_id', help='学者ID')
    parser.add_argument('--use-analyzer', action='store_true', help='使用ScholarAnalyzer的is_same_person方法')
    parser.add_argument('--verbose', action='store_true', help='输出详细信息')

    args = parser.parse_args()

    # 检查学者最佳合作者
    result = check_scholar_collaborator(args.scholar_id, args.use_analyzer, args.verbose)

    # 输出结果
    if result.get('status') == 'success':
        print("\n学者最佳合作者信息:")
        print(f"学者: {result.get('name', '')} (ID: {result.get('scholar_id', '')})")
        print(f"最佳合作者: {result.get('collaborator_name', '')} ({result.get('collaborator_affiliation', '')})")
        print(f"合作论文数: {result.get('coauthored_papers', 0)}")
        print(f"最佳合作论文: {result.get('best_paper', {}).get('title', '')}")
        print(f"是否是同一人: {result.get('is_same_person', False)}")
    else:
        print(f"\n处理失败: {result.get('error', '未知错误')}")

if __name__ == "__main__":
    main()
