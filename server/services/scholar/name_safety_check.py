#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
名字安全检查模块

这个模块提供了一个函数，用于检查两个名字是否属于同一个人，
特别是用于确保最佳合作者不是研究者自己。
"""

import logging
import re

# 获取日志记录器
logger = logging.getLogger('server.services.scholar.name_safety')

# 已知的研究者名字变体
KNOWN_RESEARCHERS = {
    "yann lecun": ["yann lecun", "y lecun", "y. lecun", "lecun", "yann a lecun", "yann a. lecun", "ya lecun"],
    "geoffrey hinton": ["geoffrey hinton", "g hinton", "g. hinton", "geoff hinton", "geoffrey e hinton", "geoffrey e. hinton", "g e hinton", "g. e. hinton", "ge hinton"],
    "yoshua bengio": ["yoshua bengio", "y bengio", "y. bengio"],
    "andrew ng": ["andrew ng", "a ng", "a. ng"],
    "fei-fei li": ["fei-fei li", "fei fei li", "f li", "f. li", "feifei li"],
    "ilya sutskever": ["ilya sutskever", "i sutskever", "i. sutskever"],
    "ian goodfellow": ["ian goodfellow", "i goodfellow", "i. goodfellow", "ian j goodfellow", "ian j. goodfellow"],
    "jeff dean": ["jeff dean", "j dean", "j. dean", "jeffrey dean", "jeffrey a dean", "jeffrey a. dean"],
    "andrej karpathy": ["andrej karpathy", "a karpathy", "a. karpathy"],
    "demis hassabis": ["demis hassabis", "d hassabis", "d. hassabis"],
}

def is_same_person_final_check(researcher_name, collaborator_name):
    """
    最终检查两个名字是否属于同一个人
    
    Args:
        researcher_name (str): 研究者姓名
        collaborator_name (str): 合作者姓名
        
    Returns:
        bool: 是否是同一个人
    """
    if not researcher_name or not collaborator_name:
        return False
        
    # 转换为小写
    researcher_lower = researcher_name.lower()
    collaborator_lower = collaborator_name.lower()
    
    # 如果名字完全相同，直接返回True
    if researcher_lower == collaborator_lower:
        return True
    
    # 检查是否是已知研究者的变体
    for known_name, variants in KNOWN_RESEARCHERS.items():
        if researcher_lower in variants and collaborator_lower in variants:
            logger.warning(f"Safety check: '{researcher_name}' and '{collaborator_name}' are variants of known researcher '{known_name}'")
            return True
    
    # 获取姓氏
    researcher_parts = researcher_lower.split()
    collaborator_parts = collaborator_lower.split()
    
    researcher_last = researcher_parts[-1] if researcher_parts else ""
    collaborator_last = collaborator_parts[-1] if collaborator_parts else ""
    
    # 如果姓氏相同
    if researcher_last == collaborator_last:
        # 获取名字部分
        researcher_first = " ".join(researcher_parts[:-1]) if len(researcher_parts) > 1 else ""
        collaborator_first = " ".join(collaborator_parts[:-1]) if len(collaborator_parts) > 1 else ""
        
        # 如果名字部分为空，可能是只有姓氏
        if not researcher_first or not collaborator_first:
            return True
            
        # 如果名字的第一个部分相同
        if researcher_parts[0] == collaborator_parts[0]:
            # 可能是中间名不同，如"Geoffrey Hinton"和"Geoffrey E. Hinton"
            logger.warning(f"Safety check: '{researcher_name}' and '{collaborator_name}' have same first name and last name")
            return True
            
        # 检查首字母缩写
        researcher_initials = "".join(p[0] for p in researcher_parts[:-1])
        collaborator_initials = "".join(p[0] for p in collaborator_parts[:-1])
        
        # 如果一方的首字母与另一方的首字母相同
        if researcher_initials == collaborator_initials:
            logger.warning(f"Safety check: '{researcher_name}' and '{collaborator_name}' have same initials and last name")
            return True
            
        # 检查特殊情况：全大写的首字母缩写，如"GE Hinton"
        if (len(researcher_parts[0]) > 1 and researcher_parts[0].isupper() and 
            len(collaborator_parts) > 1 and collaborator_parts[0][0].lower() == researcher_parts[0][0].lower()):
            logger.warning(f"Safety check: '{researcher_name}' may be initials of '{collaborator_name}'")
            return True
            
        if (len(collaborator_parts[0]) > 1 and collaborator_parts[0].isupper() and 
            len(researcher_parts) > 1 and researcher_parts[0][0].lower() == collaborator_parts[0][0].lower()):
            logger.warning(f"Safety check: '{collaborator_name}' may be initials of '{researcher_name}'")
            return True
    
    # 如果所有检查都通过，返回False
    return False

def ensure_different_person(researcher_name, collaborator_name):
    """
    确保研究者和合作者不是同一个人
    
    Args:
        researcher_name (str): 研究者姓名
        collaborator_name (str): 合作者姓名
        
    Returns:
        bool: 是否是不同的人
    """
    return not is_same_person_final_check(researcher_name, collaborator_name)
