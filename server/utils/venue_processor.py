#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Venue Processor

This module provides functions to process venue strings, particularly for handling
special cases like NeurIPS with page numbers.
"""

import re
from server.utils.conference_matcher import extract_conference_info_with_year

def handle_neurips_format(venue_str):
    """
    专门处理NeurIPS格式的venue字符串，特别是处理带有卷号和页码的格式
    例如："Advances in neural information processing systems 33, 1877-1901, 2020"

    Args:
        venue_str (str): 包含NeurIPS信息的venue字符串

    Returns:
        str: 处理后的格式，例如 "NeurIPS 2020"
    """
    if not venue_str or not isinstance(venue_str, str):
        return venue_str

    # 检查是否是NeurIPS格式
    if not re.search(r'(?i)neural information processing|neurips|nips', venue_str):
        return venue_str

    # 尝试提取年份，优先考虑2000年以后的年份
    year = None
    recent_year_match = re.search(r'(?:20)\d{2}', venue_str)
    if recent_year_match:
        year = recent_year_match.group(0)

    # 如果没有找到2000年以后的年份，再尝试匹配1900年代的年份，但要避免页码
    if not year:
        # 尝试匹配逗号后面的年份，这通常是出版年份
        comma_year_match = re.search(r',\s*(\d{4})(?:\s*$|[^\d])', venue_str)
        if comma_year_match:
            year = comma_year_match.group(1)
        else:
            # 尝试匹配其他位置的年份，但避免页码范围
            older_year_match = re.search(r'(?:19)\d{2}', venue_str)
            if older_year_match:
                # 检查是否在页码范围内
                page_range_match = re.search(r'\d+\s*[-–—]\s*' + older_year_match.group(0), venue_str)
                if not page_range_match:
                    year = older_year_match.group(0)

    # 返回标准化的格式
    if year:
        return f"NeurIPS {year}"
    else:
        return "NeurIPS"

def handle_arxiv_format(venue_str):
    """
    专门处理arXiv格式的venue字符串，避免重复年份和格式不一致
    例如："arXiv preprint arXiv:2005.05535, 2020 2005" -> "arXiv:2005.05535"

    Args:
        venue_str (str): 包含arXiv信息的venue字符串

    Returns:
        str: 处理后的格式，例如 "arXiv:2005.05535"
    """
    if not venue_str or not isinstance(venue_str, str):
        return venue_str

    # 检查是否是arXiv格式
    if not re.search(r'(?i)arxiv', venue_str):
        return venue_str

    # 提取arXiv ID - 支持多种格式
    arxiv_id_match = re.search(r'arxiv:[\s]*([\d\.v]+)', venue_str, re.IGNORECASE)
    if not arxiv_id_match:
        # 尝试匹配其他可能的格式
        arxiv_id_match = re.search(r'arxiv[\s/]+([\d\.v]+)', venue_str, re.IGNORECASE)

    arxiv_id = arxiv_id_match.group(1) if arxiv_id_match else ""

    # 提取年份 - 只提取一个年份，避免重复
    year_match = re.search(r'(?:19|20)\d{2}', venue_str)
    year = year_match.group(0) if year_match else ""

    # 构建清理后的格式
    if arxiv_id:
        # 如果有arXiv ID，优先使用ID格式
        return f"arXiv:{arxiv_id}"
    elif year:
        # 如果只有年份，使用年份格式
        return f"arXiv ({year})"
    else:
        # 如果什么都没有，返回简单格式
        return "arXiv"

def process_venue_string(venue_str):
    """
    处理venue字符串，特别处理NeurIPS和arXiv格式

    Args:
        venue_str (str): 原始venue字符串

    Returns:
        str: 处理后的venue字符串
    """
    if not venue_str or not isinstance(venue_str, str):
        return venue_str

    # 检查是否是NeurIPS格式
    if re.search(r'(?i)neural information processing|neurips|nips', venue_str):
        # 检查是否包含页码和卷号的特殊格式
        if re.search(r'(?i)advances in neural information processing systems \d+,.*\d{4}', venue_str):
            return handle_neurips_format(venue_str)

    # 检查是否是arXiv格式
    if re.search(r'(?i)arxiv', venue_str):
        return handle_arxiv_format(venue_str)

    # 对于其他格式，使用通用匹配函数
    return extract_conference_info_with_year(venue_str)

if __name__ == "__main__":
    # 测试NeurIPS格式处理
    test_venues = [
        "Advances in neural information processing systems 33, 1877-1901, 2020",
        "Advances in neural information processing systems 34, 123-456, 2021",
        "Neural Information Processing Systems, 2022",
        "NeurIPS 2023",
        "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, 2022"
    ]

    for venue in test_venues:
        print(f"Original: {venue}")
        print(f"Processed: {process_venue_string(venue)}")
        print()
