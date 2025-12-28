"""
AI Tools Module

This module contains utility functions for AI-related operations,
such as querying external AI services and generating summaries.
"""

import time
import json
import requests
from typing import Dict, Any, List, Optional

from server.config.llm_models import get_model
from server.llm.gateway import openrouter_chat

def generate_session_id() -> str:
    """Generate a unique session ID."""
    import random
    import time
    return f"session_{random.randint(1000, 9999)}_{int(time.time())}"


def is_query_about_samuel(query: str, max_retries=2, initial_timeout=10) -> Dict[str, Any]:
    """
    使用SiliconFlow API检查查询是否与Samuel相关

    Args:
        query: 用户查询
        max_retries: 最大重试次数
        initial_timeout: 初始超时时间（秒）

    Returns:
        Dict: 包含检查结果的字典，格式为 {"is_related": bool, "reason": str}
    """
    # 使用简单的关键词匹配作为备选方案（当API不可用时）
    samuel_keywords = ["samuel", "sam", "gao", "daiheng", "tomguluson", "deepfacelab", "deepfacelive"]
    query_lower = query.lower()

    # 检查是否包含关键词
    has_keyword = any(keyword in query_lower for keyword in samuel_keywords)

    # 如果包含关键词，则认为与Samuel相关
    if has_keyword:
        return {"is_related": True, "reason": f"查询包含与Samuel相关的关键词"}

    prompt = f"""请判断以下查询是否与Samuel (Sam Gao, Daiheng Gao, tomguluson92)相关。
Samuel是一位AI研究者，专注于计算机视觉和深度学习，是DeepFaceLab和DeepFaceLive项目的作者。
他在GitHub上的用户名是tomguluson92，发表过多篇CVPR和NeurIPS论文。

查询: "{query}"

请只回答"是"或"否"，并简要解释原因。"""

    # 发送请求并处理重试
    timeout = initial_timeout
    retries = 0

    while retries <= max_retries:
        try:
            content = openrouter_chat(
                task="samuel_match",
                messages=[{"role": "user", "content": prompt}],
                model=get_model("fast", task="samuel_match"),
                temperature=0.1,
                max_tokens=150,
            )
            if isinstance(content, str):
                content = content.lower()

                # 解析响应
                is_related = "是" in content[:10]  # 检查响应的开头

                return {
                    "is_related": is_related,
                    "reason": content
                }
            retries += 1
            timeout *= 2
            continue

        except requests.exceptions.RequestException as e:
            retries += 1
            timeout *= 2  # 增加超时时间

            if retries > max_retries:
                break

            time.sleep(1)  # 在重试前等待

    # 如果所有重试都失败，默认认为查询与Samuel相关
    return {"is_related": True, "reason": "达到最大重试次数后仍无法获取结果，默认继续分析"}


def generate_scholar_summary(report: Dict[str, Any], max_retries=2, initial_timeout=10) -> Dict[str, Any]:
    """
    使用大模型生成学者数据的总结

    Args:
        report: 学者分析报告
        max_retries: 最大重试次数
        initial_timeout: 初始超时时间（秒）

    Returns:
        Dict: 包含总结内容的字典，格式为 {"summary": str, "parts": List[str], "success": bool}
    """
    # 如果报告为空，返回错误
    if not report:
        return {
            "summary": "无法生成总结，因为学者数据不完整。",
            "parts": ["无法生成总结，因为学者数据不完整。"],
            "success": False
        }

    # 从报告中提取关键信息
    researcher = report.get("researcher", {})
    pub_stats = report.get("publication_stats", {})
    coauthor_stats = report.get("coauthor_stats", {})
    most_cited_paper = report.get("most_cited_paper", {})
    most_frequent_collaborator = report.get("most_frequent_collaborator", {})

    # 准备请求数据
    prompt = f"""请根据以下学者数据生成一个简洁而全面的学术总结。总结应该包括学者的学术影响力、研究方向和特点。

学者信息:
- 姓名: {researcher.get('name', '未知')}
- 机构: {researcher.get('affiliation', '未知')}
- h指数: {researcher.get('h_index', '未知')}
- 总引用数: {researcher.get('total_citations', '未知')}

发表统计:
- 总论文数: {pub_stats.get('total_papers', '未知')}
- 第一作者论文数: {pub_stats.get('first_author_papers', '未知')} ({pub_stats.get('first_author_percentage', 0):.1f}%)
- 最后作者论文数: {pub_stats.get('last_author_papers', '未知')} ({pub_stats.get('last_author_percentage', 0):.1f}%)
- 顶级会议/期刊论文数: {pub_stats.get('top_tier_papers', '未知')} ({pub_stats.get('top_tier_percentage', 0):.1f}%)

最高引用论文:
- 标题: {most_cited_paper.get('title', '未知')}
- 引用次数: {most_cited_paper.get('citations', '未知')}
- 发表年份: {most_cited_paper.get('year', '未知')}
- 发表地点: {most_cited_paper.get('venue', '未知')}

合作者信息:
- 总合作者数: {coauthor_stats.get('total_coauthors', '未知')}
- 最常合作者: {most_frequent_collaborator.get('full_name', '未知')}
- 合作论文数: {most_frequent_collaborator.get('coauthored_papers', '未知')}

请生成一个全面的学术总结，包括以下部分:
1. 学术影响力分析
2. 研究方向和特点
3. 合作网络分析
4. 总体评价

请将总结分成几个段落，每个段落不超过100个字。请使用中文回答。"""

    # 发送请求并处理重试
    timeout = initial_timeout
    retries = 0

    while retries <= max_retries:
        try:
            content = openrouter_chat(
                task="scholar_summary",
                messages=[{"role": "user", "content": prompt}],
                model="google/gemini-2.5-flash-lite",
                temperature=0.7,
                max_tokens=1500,
            )
            if not content:
                retries += 1
                timeout *= 2
                continue

            content = str(content)

            # 将内容分成段落
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

            # 如果段落太少，尝试按句子分割
            if len(paragraphs) < 3:
                paragraphs = [p.strip() for p in content.split('\n') if p.strip()]

                # 如果还是太少，按句号分割
                if len(paragraphs) < 3:
                    sentences = []
                    for p in paragraphs:
                        sentences.extend([s.strip() + "。" for s in p.split('。') if s.strip()])
                    paragraphs = sentences

            return {
                "summary": content,
                "parts": paragraphs,
                "success": True
            }

        except requests.exceptions.RequestException as e:
            retries += 1
            timeout *= 2  # 增加超时时间

            if retries > max_retries:
                break

            time.sleep(1)  # 在重试前等待

    # 如果所有重试都失败，返回默认总结
    default_summary = f"根据分析，{researcher.get('name', '该研究者')}是一位来自{researcher.get('affiliation', '未知机构')}的学者，共发表了{pub_stats.get('total_papers', '多')}篇论文，h指数为{researcher.get('h_index', '未知')}，总引用数为{researcher.get('total_citations', '未知')}。其研究工作已在学术界产生了一定影响。"

    default_parts = [
        f"{researcher.get('name', '该研究者')}是一位来自{researcher.get('affiliation', '未知机构')}的学者，共发表了{pub_stats.get('total_papers', '多')}篇论文。",
        f"其h指数为{researcher.get('h_index', '未知')}，总引用数为{researcher.get('total_citations', '未知')}，表明其研究工作已在学术界产生了一定影响。",
        f"其最高引用论文《{most_cited_paper.get('title', '未知')}》已被引用{most_cited_paper.get('citations', '多')}次，发表于{most_cited_paper.get('venue', '未知')}。",
        f"该研究者有{coauthor_stats.get('total_coauthors', '多位')}位合作者，其中与{most_frequent_collaborator.get('full_name', '未知')}合作最为频繁，共发表了{most_frequent_collaborator.get('coauthored_papers', '多')}篇论文。"
    ]

    return {
        "summary": default_summary,
        "parts": default_parts,
        "success": False
    }
