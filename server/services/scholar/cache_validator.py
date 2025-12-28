# coding: UTF-8
"""
Cache Validator - Module for validating and completing cached scholar data.
This module checks if cached data is complete and valid, and recalculates missing or invalid parts.
"""

import logging
import copy
from typing import Dict, Any, Optional, Callable

# 获取缓存验证器的日志记录器
logger = logging.getLogger('server.services.scholar.cache_validator')

# 导入状态报告函数
from server.services.scholar.status_reporter import send_status

# 导入获取最佳合作者的函数
from server.services.scholar.collaborator_service import get_best_collaborator

# 导入角色模型相关功能
from server.services.scholar.role_model_service import get_role_model

# 导入职级评估相关功能
from server.services.scholar.career_level_service import get_career_level_info

# 导入学者评价生成功能
from server.prompts.researcher_evaluator import generate_critical_evaluation
from server.services.scholar.cancel import raise_if_cancelled

def is_valid_collaborator(collaborator: Dict[str, Any]) -> bool:
    """
    检查合作者数据是否有效

    Args:
        collaborator: 合作者数据

    Returns:
        bool: 数据是否有效
    """
    # 检查合作者数据是否为空
    if not collaborator:
        return False

    # 检查是否是默认的"未找到"对象
    if collaborator.get('full_name', '').strip() in ['No frequent collaborator found', 'No suitable collaborator found', '']:
        return False

    # 检查是否有必要的字段（根据字段结构判断是哪种格式）
    if 'full_name' in collaborator:
        # 根级别的most_frequent_collaborator格式
        required_fields = ['full_name', 'affiliation']
        for field in required_fields:
            if field not in collaborator:
                return False

    elif 'name' in collaborator:
        # coauthor_stats.most_frequent_collaborator格式
        required_fields = ['name', 'coauthored_papers', 'best_paper']
        for field in required_fields:
            if field not in collaborator:
                return False

    else:
        # 未知格式
        return False

    # 检查best_paper是否有效
    best_paper = collaborator.get('best_paper', {})
    if not best_paper:
        return False

    # 检查best_paper的字段
    if 'title' in best_paper and (not best_paper.get('title') or best_paper.get('title') == 'N/A'):
        return False

    return True

def is_valid_role_model(role_model: Dict[str, Any]) -> bool:
    """
    检查角色模型数据是否有效

    Args:
        role_model: 角色模型数据

    Returns:
        bool: 数据是否有效
    """
    # 检查角色模型数据是否为空
    if not role_model:
        return False

    # 检查是否有必要的字段
    required_fields = ['name', 'achievement']
    for field in required_fields:
        if field not in role_model:
            return False

    # 检查字段是否有内容
    if not role_model.get('name'):
        return False

    return True

def is_valid_critical_evaluation(evaluation: str) -> bool:
    """
    检查学者评价是否有效

    Args:
        evaluation: 学者评价

    Returns:
        bool: 数据是否有效
    """
    # 检查评价是否为空
    if not evaluation:
        return False

    # 检查评价是否是错误消息
    if evaluation == "Error generating critical evaluation.":
        return False

    # 检查评价长度是否合理（至少50个字符）
    if len(evaluation) < 50:
        return False

    return True

def validate_and_complete_cache(
    cached_data: Dict[str, Any],
    data_fetcher,
    analyzer,
    callback: Optional[Callable] = None,
    cancel_event=None,
) -> Dict[str, Any]:
    """
    验证并补全缓存数据

    Args:
        cached_data: 缓存的学者数据
        data_fetcher: ScholarDataFetcher实例
        analyzer: ScholarAnalyzer实例
        callback: 回调函数，用于报告状态

    Returns:
        Dict[str, Any]: 验证并补全后的学者数据
    """
    raise_if_cancelled(cancel_event)
    # 创建数据的深拷贝，避免修改原始数据
    data = copy.deepcopy(cached_data)

    # 标记数据是否已修改
    data_modified = False

    # 1. 验证并补全最佳合作者数据
    root_collaborator_valid = 'most_frequent_collaborator' in data and is_valid_collaborator(data.get('most_frequent_collaborator'))

    # 如果根级别的最佳合作者无效，尝试从coauthor_stats中获取数据
    if not root_collaborator_valid and 'coauthor_stats' in data and 'most_frequent_collaborator' in data['coauthor_stats']:
        logger.info("根级别的最佳合作者数据无效，尝试从coauthor_stats中获取")
        
        # 从coauthor_stats中获取最佳合作者数据
        coauthor_stats_collaborator = data['coauthor_stats']['most_frequent_collaborator']
        
        if coauthor_stats_collaborator:
            collaborator_name = coauthor_stats_collaborator.get('name', '')
            coauthored_papers = coauthor_stats_collaborator.get('coauthored_papers', 0)
            best_paper = coauthor_stats_collaborator.get('best_paper', {})
            
            # 构建完整的最佳合作者数据
            most_frequent_collaborator = {
                "full_name": collaborator_name,
                "h_index": "N/A",  # 默认值
                "scholar_id": "",  # 默认值
                "affiliation": "Unknown",  # 默认值
                "total_citations": "N/A",  # 默认值
                "coauthored_papers": coauthored_papers,
                "best_paper": best_paper,
                "research_interests": []  # 默认值
            }
            
            # 更新数据
            data['most_frequent_collaborator'] = most_frequent_collaborator
            data_modified = True
            
            logger.info(f"已使用coauthor_stats中的数据更新最佳合作者: {collaborator_name}")
            
            # 尝试获取更多合作者信息
            try:
                # 使用合作者名称搜索学者
                send_status(f"Retrieving more information about collaborator {collaborator_name}...", callback, progress=60.0)
                # 添加主要作者名称到coauthor_stats
                coauthor_stats = data['coauthor_stats']
                coauthor_stats['main_author'] = data.get('researcher', {}).get('name', '')
                
                # 重新计算最佳合作者
                raise_if_cancelled(cancel_event)
                most_frequent_collaborator = get_best_collaborator(
                    data_fetcher,
                    coauthor_stats,
                    callback=callback,
                    analyzer=analyzer
                )
                data['most_frequent_collaborator'] = most_frequent_collaborator
            except Exception as e:
                logger.error(f"获取合作者 {collaborator_name} 的更多信息时出错: {e}")
                # 继续使用已有的合作者数据
        else:
            logger.warning("coauthor_stats中没有有效的最佳合作者数据")
            
    # 如果根级别的最佳合作者仍然无效，且无法从coauthor_stats获取，重新计算
    elif not root_collaborator_valid:
        logger.info("缓存中的最佳合作者数据无效或不存在，重新计算")
        send_status("Recalculating collaborator information...", callback, progress=55.0)
        
        # 确保coauthor_stats存在
        if 'coauthor_stats' in data:
            # 添加主要作者名称到coauthor_stats
            coauthor_stats = data['coauthor_stats']
            coauthor_stats['main_author'] = data.get('researcher', {}).get('name', '')
            
            # 重新计算最佳合作者
            raise_if_cancelled(cancel_event)
            most_frequent_collaborator = get_best_collaborator(
                data_fetcher,
                coauthor_stats,
                callback=callback,
                analyzer=analyzer
            )
            
            # 更新数据
            data['most_frequent_collaborator'] = most_frequent_collaborator
            data_modified = True
            
            logger.info("已重新计算最佳合作者数据")
        else:
            logger.warning("无法重新计算最佳合作者，缺少coauthor_stats数据")

    # 2. 验证并补全角色模型数据
    if 'role_model' not in data or not is_valid_role_model(data.get('role_model')):
        logger.info("缓存中的角色模型数据无效或不存在，重新计算")
        send_status("Recalculating role model information...", callback, progress=80.0)

        # 重新计算角色模型
        raise_if_cancelled(cancel_event)
        role_model = get_role_model(data)

        # 更新数据
        data['role_model'] = role_model
        data_modified = True

        logger.info("已重新计算角色模型数据")

    # 3. 验证并补全职级信息
    if 'level_info' not in data or not data.get('level_info'):
        logger.info("缓存中的职级信息无效或不存在，重新计算")
        send_status("Recalculating career level information...", callback, progress=85.0)

        # 重新计算职级信息
        raise_if_cancelled(cancel_event)
        level_info = get_career_level_info(data, False, callback)

        # 更新数据
        data['level_info'] = level_info
        data_modified = True

        logger.info("已重新计算职级信息")

    # 4. 验证并补全学者评价
    if 'critical_evaluation' not in data or not is_valid_critical_evaluation(data.get('critical_evaluation')):
        logger.info("缓存中的学者评价无效或不存在，重新计算")
        send_status("Regenerating critical evaluation...", callback, progress=90.0)

        try:
            # 重新生成学者评价
            raise_if_cancelled(cancel_event)
            critical_evaluation = generate_critical_evaluation(data)

            # 更新数据
            data['critical_evaluation'] = critical_evaluation
            data_modified = True

            logger.info("已重新生成学者评价")
        except Exception as e:
            logger.error(f"重新生成学者评价时出错: {e}")
            # 如果生成失败，保留原有评价或设置默认值
            if 'critical_evaluation' not in data:
                data['critical_evaluation'] = "Error generating critical evaluation."

    # 5. 验证并补全论文新闻
    if 'paper_news' not in data or not data.get('paper_news'):
        logger.info("缓存中的论文新闻无效或不存在，重新获取")
        send_status("Retrieving paper news...", callback, progress=65.0)

        # 获取最具引用论文信息
        if 'publication_stats' in data and 'most_cited_paper' in data['publication_stats']:
            most_cited = data['publication_stats']['most_cited_paper']

            # 获取论文标题
            title = most_cited.get('title', 'Unknown Title')

            # 获取论文相关新闻
            try:
                from onepage.signature_news import get_latest_news
                raise_if_cancelled(cancel_event)
                news_info = get_latest_news(title)
                data['paper_news'] = news_info
                data_modified = True

                logger.info("已重新获取论文新闻")
            except Exception as e:
                logger.error(f"重新获取论文新闻时出错: {e}")
                # 如果获取失败，设置默认值
                data['paper_news'] = "No related news found."

    # 返回验证并补全后的数据
    if data_modified:
        logger.info("缓存数据已被修改和补全")
    else:
        logger.info("缓存数据已验证，无需修改")

    return data
