"""
Role Model Service

This module handles the generation and management of role models for researchers.
It provides functions to find appropriate role models or create self-role models when needed.
"""

import logging
import traceback
from typing import Any, Callable, Dict, Optional

# 获取日志记录器
logger = logging.getLogger('server.services.scholar.role_model_service')

# 导入模板人物生成函数
from server.services.scholar.template_figure_kimi import get_template_figure

def get_role_model(report: Dict[str, Any], callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
    """
    获取研究者的角色模型。
    
    首先尝试找到外部角色模型；失败则返回 None（不要用 self-role-model 占位）。
    
    Args:
        report: 包含研究者信息的报告字典
        callback: 可选的状态回调函数
        
    Returns:
        包含角色模型信息的字典，或 None
    """
    try:
        # 尝试获取角色模型
        role_model = get_template_figure(report)

        # 如果成功获取了角色模型，将其返回
        if isinstance(role_model, dict) and role_model.get("name"):
            return role_model
        return None
            
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get role model: {e}")
        logger.error(f"Role model error details: {error_trace}")
        return None

def create_self_role_model(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用研究者自己的信息创建角色模型。
    
    Args:
        report: 包含研究者信息的报告字典
        
    Returns:
        以研究者自己为角色模型的字典
    """
    # 获取研究者的基本信息
    researcher_name = report.get('researcher', {}).get('name', 'Unknown Researcher')
    researcher_affiliation = report.get('researcher', {}).get('affiliation', '')
    researcher_avatar = report.get('researcher', {}).get('avatar', '')

    # 获取研究者的代表作
    representative_work = get_representative_work(report)

    # 创建以自己为角色模型的字典
    self_role_model = {
        "name": researcher_name,
        "institution": researcher_affiliation,
        "position": "Established Researcher",  # 默认职位
        "photo_url": researcher_avatar,
        "achievement": representative_work,
        "similarity_reason": "Congrats! You are already your own hero! Your unique research path and contributions have established you as a notable figure in your field."
    }
    
    return self_role_model

def get_representative_work(report: Dict[str, Any]) -> str:
    """
    从报告中获取研究者的代表作。
    
    首先尝试使用最引用论文，如果没有则尝试使用第一作者论文列表中的第一篇。
    
    Args:
        report: 包含研究者信息的报告字典
        
    Returns:
        代表作的字符串描述
    """
    # 首先尝试使用最引用论文
    if 'most_cited_paper' in report and report['most_cited_paper']:
        paper = report['most_cited_paper']
        return f"{paper.get('title', 'Unknown paper')} ({paper.get('year', '')})"
    
    # 如果没有最引用论文，尝试从出版统计中获取
    pub_stats = report.get('publication_stats', {})
    if pub_stats and 'first_author_papers_list' in pub_stats and pub_stats['first_author_papers_list']:
        paper = pub_stats['first_author_papers_list'][0]  # 第一作者论文列表中的第一篇
        return f"{paper.get('title', 'Unknown paper')} ({paper.get('year', '')})"
    
    # 如果都没有找到，返回空字符串
    return ""
