import json
import argparse
import os
import random
import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

# Import venue processor
from server.utils.venue_processor import process_venue_string

from dotenv import load_dotenv

# Import logging configuration
from server.utils.logging_config import setup_logging, create_module_logger

# Load environment variables
load_dotenv()

# Set up logging
# 确保日志目录存在
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../logs'))
os.makedirs(log_dir, exist_ok=True)

# 创建模块特定的日志器
logger = logging.getLogger('server.transform_profile')

# 如果日志器没有处理器，说明还没有初始化，调用setup_logging
if not logger.handlers:
    setup_logging(log_dir=log_dir)
    # 为transform_profile模块创建一个专门的日志记录器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    create_module_logger('server.transform_profile', log_dir, logging.INFO, formatter)
    logger.info("Transform profile logger initialized")

# 使用环境变量加载模块获取 BASE_URL
from server.config.env_loader import get_env_var

# Get base URL from environment variables
BASE_URL = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')
logger.info(f"Transform profile using BASE_URL: {BASE_URL}")

# 更新 profile_utils 中的 BASE_URL
from server.utils.profile_utils import update_base_url
update_base_url(BASE_URL)

# 导入头像和描述相关工具函数
from server.utils.profile_utils import (
    get_random_avatar, get_random_description, get_advisor_avatar,
    PREFERRED_CONFERENCE_ACRONYMS
)

# 这些函数已经移动到 server.utils.profile_utils 模块
# 使用导入的 get_random_avatar 和 get_random_description 函数

# Kimi API configuration has been moved to server/utils/kimi_evaluator.py

# --- Helper Functions (Keep existing clean_number, clean_year) ---

def clean_number(value, return_type=int, default=None):
    """Attempts to convert a value to the specified numeric type (int or float).
       Handles various formats of numeric strings including:
       - Strings with commas, periods, or spaces as thousand separators
       - Strings with currency symbols/codes (USD, $, €, etc.)
       - Ranges (e.g., "300,000-400,000 USD") - takes the average
       - Scientific notation
       - 'N/A', empty strings, or other non-numeric values
    """
    if isinstance(value, (int, float)):
        return return_type(value)

    if not isinstance(value, str):
        return default

    # Strip whitespace and handle empty or N/A values
    value = value.strip()
    if value.lower() in ['n/a', '', 'none', 'null', 'undefined']:
        return default

    # Handle ranges (e.g., "300,000-400,000 USD") - take the average
    if '-' in value and not value.startswith('-'):
        try:
            parts = value.split('-')
            if len(parts) == 2:
                # Recursively clean both parts and take the average
                low = clean_number(parts[0], float, 0)
                high = clean_number(parts[1], float, 0)
                if low is not None and high is not None:
                    return return_type((low + high) / 2)
        except Exception:
            pass  # If range processing fails, continue with normal processing

    # Remove currency symbols and codes
    # Common currency symbols and codes
    currency_pattern = r'[$€£¥₹₽₩₺₴₦₱₲₪₫₭₮₯₰₸₹₺₼₽₾₿]|\b(USD|EUR|GBP|JPY|CNY|INR|RUB|KRW|TRY|UAH|NGN|PHP|PYG|ILS|VND|LAK|MNT|GRD|CZK|PLN|SEK|NOK|DKK|HUF|AUD|CAD|NZD|CHF)\b'
    value = re.sub(currency_pattern, '', value, flags=re.IGNORECASE)

    # Remove thousand separators (commas, periods, spaces depending on locale)
    # This handles both 1,000.00 and 1.000,00 formats
    # First, identify if it's using period as decimal or thousand separator
    decimal_count = value.count('.')
    comma_count = value.count(',')

    # If there's only one period and it's near the end, it's likely a decimal point
    if decimal_count == 1 and '.' in value and len(value) - value.rindex('.') <= 4:
        # Format like 1,000.00 - remove commas
        value = value.replace(',', '')
    # If there's only one comma and it's near the end, it's likely a decimal point
    elif comma_count == 1 and ',' in value and len(value) - value.rindex(',') <= 4:
        # Format like 1.000,00 - remove periods and convert comma to period
        value = value.replace('.', '')
        value = value.replace(',', '.')
    else:
        # Remove all commas, periods, and spaces that might be thousand separators
        value = re.sub(r'[,\. ]', '', value)

    # Try to convert to number
    try:
        # Handle scientific notation and regular numbers
        return return_type(float(value))
    except (ValueError, TypeError):
        # If all else fails, try to extract any number from the string
        try:
            # Find all numbers in the string and use the first one
            numbers = re.findall(r'\d+\.?\d*', value)
            if numbers:
                return return_type(float(numbers[0]))
        except (ValueError, TypeError, IndexError):
            pass

        return default

def clean_year(value, default=None):
    """Attempts to convert a value to an integer year."""
    return clean_number(value, return_type=int, default=default)

def clean_arxiv_venue(venue_str):
    """专门处理 arXiv 格式的 venue 字符串

    Args:
        venue_str (str): 包含 arXiv 信息的 venue 字符串

    Returns:
        str: 清理后的 arXiv 格式，例如 "arXiv:2005.05535" 或 "arXiv (2020)"
    """
    if not isinstance(venue_str, str):
        return venue_str

    # 如果不包含 arXiv，直接返回原字符串
    if 'arxiv' not in venue_str.lower():
        return venue_str

    # 提取 arXiv ID - 支持多种格式
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

def simplify_venue(venue_str):
    """Provides a basic simplification for common venue names.
       Tries to extract known acronyms or return a cleaned version.
    """
    if not isinstance(venue_str, str):
        return venue_str

    # 首先检查是否是 arXiv 格式，如果是则使用专门的处理函数
    if 'arxiv' in venue_str.lower():
        return clean_arxiv_venue(venue_str)

    venue_str_lower = venue_str.lower()

    # Check against preferred list first for exact/common variations
    mapping = {
        "cvpr": "CVPR", "computer vision and pattern recognition": "CVPR",
        "iccv": "ICCV", "international conference on computer vision": "ICCV",
        "neurips": "NeurIPS", "advances in neural information processing systems": "NeurIPS", "nips": "NeurIPS",
        "acm mm": "ACM MM", "acm international conference on multimedia": "ACM MM",
        "icassp": "ICASSP", "international conference on acoustics, speech, and signal processing": "ICASSP",
        "icip": "ICIP", "international conference on image processing": "ICIP",
        "eccv": "ECCV", "european conference on computer vision": "ECCV",
        "aaai": "AAAI", "aaai conference on artificial intelligence": "AAAI",
        "ijcai": "IJCAI", "international joint conference on artificial intelligence": "IJCAI",
        "iclr": "ICLR", "international conference on learning representations": "ICLR",
        "siggraph": "SIGGRAPH",
        "kdd": "KDD", "conference on knowledge discovery and data mining": "KDD",
        "arxiv": "arXiv" # Include Arxiv here for potential simplification use, but handle separately in refine step
    }

    for key, simplified in mapping.items():
        if key in venue_str_lower:
            return simplified # Return the canonical preferred acronym

    # Fallback: Maybe just take the first part if it looks like an acronym (e.g., 3-6 uppercase letters)
    match_acronym = re.match(r'^([A-Z]{3,6})\b', venue_str.strip())
    if match_acronym:
        return match_acronym.group(1)

    # Last resort: return a cleaned version of the beginning
    cleaned = venue_str.split(',')[0].split('(')[0].strip()
    return cleaned if len(cleaned) < 50 else "Long Venue Name" # Avoid returning very long strings

# --- NEW/REFINED Helper Function for Conference Distribution ---
def refine_conference_distribution(dist_dict, preferred_acronyms):
    """
    Refines the conference distribution dictionary.
    Keeps only preferred acronyms, groups Arxiv and others into "Others".
    """
    if not isinstance(dist_dict, dict):
        return {}

    refined_dist = {}
    others_count = 0

    for raw_venue, count_val in dist_dict.items():
        count = clean_number(count_val, default=0) # Ensure count is numeric
        if count == 0:
            continue

        # 1. Handle Arxiv explicitly (case-insensitive check)
        if "arxiv" in raw_venue.lower():
            others_count += count
            continue

        # 2. Simplify the venue name to try and match preferred acronyms
        simplified_venue = simplify_venue(raw_venue)

        # 3. Check if the simplified venue is in the preferred list
        if simplified_venue in preferred_acronyms:
            refined_dist[simplified_venue] = refined_dist.get(simplified_venue, 0) + count
        else:
            # 4. If not Arxiv and not preferred, add to Others
            others_count += count

    # 5. Add the "Others" category if it has counts
    if others_count > 0:
        refined_dist["Others"] = others_count

    # Optional: Sort the result for consistency (e.g., by count descending)
    # sorted_dist = dict(sorted(refined_dist.items(), key=lambda item: item[1], reverse=True))
    # return sorted_dist
    return refined_dist

# --- Main Transformation Function (Modified Call) ---
def transform_data(source_data):
    """Transforms the source JSON data structure to the target structure."""

    def _as_dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _as_list(value: Any) -> List[Any]:
        return value if isinstance(value, list) else []

    if not isinstance(source_data, dict):
        source_data = {}

    # (Keep the initialization of target_data as before)
    target_data = {
        "researcherProfile": {
            "researcherInfo": { # ... (same as before) ...
                "name": None, "abbreviatedName": None, "affiliation": None, "email": None,
                "researchFields": [], "totalCitations": None, "citations5y": None,
                "hIndex": None, "hIndex5y": None, "yearlyCitations": {},
                "scholarId": None
            },
            "dataBlocks": {
                "publicationStats": { # ... (same as before) ...
                    "blockTitle": "Papers", "totalPapers": None, "totalCitations": None,
                    "hIndex": None, "yearlyCitations": {}, "yearlyPapers": {}
                },
                "publicationInsight": {
                    "blockTitle": "Insight", "totalPapers": None, "topTierPapers": None,
                    "firstAuthorPapers": None, "firstAuthorCitations": None, "totalCoauthors": None,
                    "lastAuthorPapers": None, "conferenceDistribution": {} # Target field
                },
                "roleModel": { # ... (same as before) ...
                    "blockTitle": "Role Model", "found": False, "name": None, "institution": None,
                    "position": None, "photoUrl": None, "achievement": None, "similarityReason": None
                },
                "closestCollaborator": { # ... (added avatar field) ...
                     "blockTitle": "Closest Collaborator", "fullName": None, "affiliation": None,
                     "researchInterests": [], "scholarId": None, "coauthoredPapers": None, "avatar": None,
                     "bestCoauthoredPaper": {"title": None, "year": None, "venue": None, "fullVenue": None, "citations": None},
                     "connectionAnalysis": None
                },
                "estimatedSalary": { # ... (same as before) ...
                    "blockTitle": "Estimated Salary", "earningsPerYearUSD": None,
                    "levelEquivalency": {"us": None, "cn": None}, "reasoning": None
                },
                "researcherCharacter": { # ... (same as before) ...
                    "blockTitle": "Researcher Character", "depthVsBreadth": None, "theoryVsPractice": None,
                    "soloVsTeamwork": None, "justification": None
                },
                "paperOfYear": {
                    "blockTitle": "Paper of Year", "title": None, "year": None, "venue": None,
                    "citations": None, "authorPosition": None, "summary": None
                },
                "representativePaper": { # ... (same as before) ...
                    "blockTitle": "Representative Paper", "title": None, "year": None, "venue": None,
                    "fullVenue": None, "citations": None, "authorPosition": None, "paper_news": None
                },
                "criticalReview": { # ... (same as before) ...
                     "blockTitle": "Roast",
                     "evaluation": None
                }
            },
            "configInfo": { # ... (same as before) ...
                "comment": "Placeholder for bottom/page configuration data"
            }
        }
    }

    # --- Populate Researcher Info (Added avatar and description) ---
    researcher_src = _as_dict(source_data.get('researcher'))
    researcher_info_target = target_data['researcherProfile']['researcherInfo']

    # Get researcher name for avatar and description
    researcher_name = str(researcher_src.get('name') or '')

    # Add avatar and description fields
    avatar_url = researcher_src.get('avatar')

    # 如果有 avatar URL，检查其域名前缀是否与当前环境的 BASE_URL 匹配
    if avatar_url:
        # 检查是否是完整的 URL（包含 http:// 或 https://）
        if avatar_url.startswith('http'):
            try:
                # 解析 URL 获取域名部分
                from urllib.parse import urlparse
                parsed_url = urlparse(avatar_url)
                current_base = f"{parsed_url.scheme}://{parsed_url.netloc}"

                # 仅对“我们自己托管的图片路径”做 base 替换（用于环境迁移）。
                # 外部头像（如 scholar.googleusercontent.com）必须保留原始域名，否则会变成死链。
                is_internal_image = bool((parsed_url.path or "").startswith("/images/"))
                if is_internal_image and current_base != BASE_URL:
                    logger.info(f"Replacing avatar URL base from {current_base} to {BASE_URL}")
                    avatar_url = avatar_url.replace(current_base, BASE_URL)
            except Exception as e:
                logger.warning(f"Error processing avatar URL: {e}")

    # 如果没有 avatar URL，使用随机头像
    if not avatar_url:
        avatar_url = get_random_avatar()

    description = researcher_src.get('description')
    if not description and researcher_name:
        description = get_random_description(researcher_name)
    elif not description:
        description = "A brilliant researcher exploring the frontiers of knowledge."

    # Add the fields to the target data
    researcher_info_target['name'] = researcher_name
    researcher_info_target['abbreviatedName'] = researcher_src.get('abbreviated_name')
    researcher_info_target['affiliation'] = researcher_src.get('affiliation')
    researcher_info_target['email'] = researcher_src.get('email')
    researcher_info_target['researchFields'] = _as_list(researcher_src.get('research_fields'))
    researcher_info_target['totalCitations'] = clean_number(researcher_src.get('total_citations'))
    researcher_info_target['citations5y'] = clean_number(researcher_src.get('citations_5y'))
    researcher_info_target['hIndex'] = clean_number(researcher_src.get('h_index'))
    researcher_info_target['hIndex5y'] = clean_number(researcher_src.get('h_index_5y'))
    yearly_citations_src = _as_dict(researcher_src.get('yearly_citations'))
    researcher_info_target['yearlyCitations'] = {str(k): clean_number(v) for k, v in yearly_citations_src.items()}
    researcher_info_target['avatar'] = avatar_url
    researcher_info_target['description'] = description
    researcher_info_target['scholarId'] = researcher_src.get('scholar_id')

    # --- Populate Publication Stats Block (Same as before) ---
    pub_stats_src = _as_dict(source_data.get('publication_stats'))
    pub_stats_target = target_data['researcherProfile']['dataBlocks']['publicationStats']
    pub_stats_target['totalPapers'] = clean_number(pub_stats_src.get('total_papers'))
    pub_stats_target['totalCitations'] = researcher_info_target['totalCitations']
    pub_stats_target['hIndex'] = researcher_info_target['hIndex']
    pub_stats_target['yearlyCitations'] = researcher_info_target['yearlyCitations']
    yearly_papers_src = _as_dict(pub_stats_src.get('year_distribution'))
    pub_stats_target['yearlyPapers'] = {str(k): clean_number(v) for k, v in yearly_papers_src.items()}


    # --- Populate Publication Insight Block (MODIFIED PART) ---
    pub_insight_target = target_data['researcherProfile']['dataBlocks']['publicationInsight']
    coauthor_stats_src = _as_dict(source_data.get('coauthor_stats'))

    pub_insight_target['totalPapers'] = pub_stats_target['totalPapers']
    pub_insight_target['topTierPapers'] = clean_number(pub_stats_src.get('top_tier_papers'))
    pub_insight_target['firstAuthorPapers'] = clean_number(pub_stats_src.get('first_author_papers'))
    pub_insight_target['firstAuthorCitations'] = clean_number(pub_stats_src.get('first_author_citations'))
    pub_insight_target['totalCoauthors'] = clean_number(coauthor_stats_src.get('total_coauthors'))
    pub_insight_target['lastAuthorPapers'] = clean_number(pub_stats_src.get('last_author_papers'))

    # *** Use the new refining function ***
    raw_conf_dist = _as_dict(pub_stats_src.get('conference_distribution'))
    pub_insight_target['conferenceDistribution'] = refine_conference_distribution(
        raw_conf_dist, PREFERRED_CONFERENCE_ACRONYMS
    )
    # **********************************


    # --- Populate Role Model Block ---
    role_model_src = _as_dict(source_data.get('role_model'))
    role_model_target = target_data['researcherProfile']['dataBlocks']['roleModel']

    has_valid_role_model = bool(role_model_src.get('name'))
    role_model_target['found'] = bool(has_valid_role_model)

    if not has_valid_role_model:
        role_model_target['name'] = None
        role_model_target['institution'] = None
        role_model_target['position'] = None
        role_model_target['photoUrl'] = None
        role_model_target['achievement'] = None
        role_model_target['similarityReason'] = None
        role_model_target['isSelf'] = False
    else:
        role_model_target['name'] = role_model_src.get('name')
        role_model_target['institution'] = role_model_src.get('institution')
        role_model_target['position'] = role_model_src.get('position')
        role_model_target['photoUrl'] = role_model_src.get('photo_url') or None
        role_model_target['achievement'] = role_model_src.get('achievement')
        role_model_target['similarityReason'] = role_model_src.get('similarity_reason')
        role_model_target['isSelf'] = bool(researcher_name and researcher_name == role_model_src.get('name'))


    # --- Populate Closest Collaborator Block (Added avatar field) ---
    collaborator_src = _as_dict(source_data.get('most_frequent_collaborator'))
    if not collaborator_src or not collaborator_src.get("full_name"):
        # Back-compat: older reports only have coauthor_stats.most_frequent_collaborator (name/count/best_paper).
        mf = _as_dict(coauthor_stats_src.get("most_frequent_collaborator"))
        mf_name = str(mf.get("name") or "").strip()
        if mf_name and mf_name.lower() not in ("no suitable collaborator found", "no frequent collaborator found"):
            collaborator_src = {
                "full_name": mf_name,
                "affiliation": None,
                "research_interests": [],
                "scholar_id": None,
                "coauthored_papers": mf.get("coauthored_papers"),
                "best_paper": mf.get("best_paper") if isinstance(mf.get("best_paper"), dict) else {},
            }
    collaborator_target = target_data['researcherProfile']['dataBlocks']['closestCollaborator']

    # Check if there is a valid collaborator
    has_collaborator = collaborator_src and collaborator_src.get('full_name') and collaborator_src.get('full_name') != 'No frequent collaborator found'

    collaborator_target['fullName'] = collaborator_src.get('full_name')
    collaborator_target['affiliation'] = collaborator_src.get('affiliation')
    collaborator_target['researchInterests'] = _as_list(collaborator_src.get('research_interests'))
    collaborator_target['scholarId'] = collaborator_src.get('scholar_id')
    collaborator_target['coauthoredPapers'] = clean_number(collaborator_src.get('coauthored_papers'))

    # Add avatar field for collaborator
    if has_collaborator:
        collaborator_target['avatar'] = get_advisor_avatar()
    else:
        collaborator_target['avatar'] = None

    best_paper_src = _as_dict(collaborator_src.get('best_paper'))
    best_paper_venue = best_paper_src.get('venue')
    best_paper_title = best_paper_src.get('title')
    best_paper_year = clean_year(best_paper_src.get('year'))

    # 使用会议匹配功能处理Venue字段
    # 首先尝试从venue匹配，使用专门的venue处理器
    matched_venue = process_venue_string(best_paper_venue) if best_paper_venue else None

    # 如果venue没有匹配到或者匹配结果与原始venue相同，尝试从title匹配
    if not matched_venue or matched_venue == best_paper_venue:
        if best_paper_title:
            title_matched_venue = process_venue_string(best_paper_title)
            # 只有当title匹配结果不等于title本身时才使用
            if title_matched_venue != best_paper_title:
                matched_venue = title_matched_venue

    # 如果匹配成功但没有年份，而paper有年份，则添加年份
    if matched_venue and best_paper_year and ' ' + str(best_paper_year) not in matched_venue:
        # 检查匹配结果是否已经包含年份
        if not re.search(r'\d{4}', matched_venue):
            matched_venue = f"{matched_venue} {best_paper_year}"

    collaborator_target['bestCoauthoredPaper']['title'] = best_paper_title
    collaborator_target['bestCoauthoredPaper']['year'] = best_paper_year
    collaborator_target['bestCoauthoredPaper']['fullVenue'] = best_paper_venue

    # 使用venue_processor处理venue字段，它已经包含了对arXiv的特殊处理
    if matched_venue and matched_venue != best_paper_venue:
        collaborator_target['bestCoauthoredPaper']['venue'] = matched_venue
    else:
        # 如果匹配失败，使用简化的venue
        collaborator_target['bestCoauthoredPaper']['venue'] = simplify_venue(best_paper_venue)

    collaborator_target['bestCoauthoredPaper']['citations'] = clean_number(best_paper_src.get('citations'))


    # --- Populate Estimated Salary Block (MODIFIED to handle various earnings formats) ---
    salary_target = target_data['researcherProfile']['dataBlocks']['estimatedSalary']

    # 首先尝试从 earnings_per_year 获取薪资
    earnings = clean_number(source_data.get('earnings_per_year'), return_type=int)

    # 如果没有 earnings_per_year 或者为空，尝试从 level_info.earnings 获取
    level_info_src = _as_dict(source_data.get('level_info'))
    # if earnings is None and level_info_src:
    #     # earnings = clean_number(level_info_src.get('earnings'), return_type=int)
    earnings = level_info_src.get('earnings')

    # 设置薪资值
    salary_target['earningsPerYearUSD'] = earnings

    # 设置其他字段
    salary_target['levelEquivalency']['us'] = level_info_src.get('level_us') or level_info_src.get('us')
    salary_target['levelEquivalency']['cn'] = level_info_src.get('level_cn') or level_info_src.get('cn')

    # 获取推理说明
    reasoning = level_info_src.get('justification') or source_data.get('reason')
    salary_target['reasoning'] = reasoning


    # --- Populate Researcher Character Block (Modified to prioritize level_info) ---
    character_target = target_data['researcherProfile']['dataBlocks']['researcherCharacter']

    # 首先从level_info中获取评估数据，这是优先数据源
    level_info = _as_dict(source_data.get('level_info'))
    evaluation_bars = _as_dict(level_info.get('evaluation_bars'))

    # 只有当level_info中没有evaluation_bars时，才使用research_style
    if not evaluation_bars:
        logger.info("No evaluation_bars found in level_info, falling back to research_style")
        style_src = _as_dict(source_data.get('research_style'))
    else:
        logger.info(f"Using evaluation_bars from level_info as primary data source: {evaluation_bars}")
        style_src = evaluation_bars

    # 检查style_src是否有有效的研究风格数据
    has_valid_style = style_src and isinstance(style_src, dict)

    # 准备提取解释文本和分数
    justification = level_info.get('justification', 'Based on the researcher\'s publication record and citation metrics.')

    # 如果style_src是从evaluation_bars获取的，提取解释文本
    if has_valid_style and evaluation_bars:
        logger.info(f"Extracting data from evaluation_bars")

        # 提取所有评估条的解释并合并
        explanations = []

        # 从每个评估条中提取解释
        for dimension in ['depth_vs_breadth', 'theory_vs_practice', 'individual_vs_team']:
            if dimension in style_src and isinstance(style_src[dimension], dict) and 'explanation' in style_src[dimension]:
                explanation = style_src[dimension].get('explanation')
                if explanation:
                    explanations.append(explanation)

        # 合并所有解释，如果有的话
        if explanations:
            justification = ' '.join(explanations)
            logger.info(f"Combined justification from explanations: {justification}")

    # 如果没有有效的研究风格数据，使用默认值
    if not has_valid_style:
        logger.warning(f"No valid research style data found, using default values")
        style_src = {
            'depth_vs_breadth': {'score': 5},
            'theory_vs_practice': {'score': 5},
            'individual_vs_team': {'score': 5}
        }

    # 设置研究者特征字段
    # 确保正确处理各种可能的数据类型
    depth_value = style_src.get('depth_vs_breadth')
    theory_value = style_src.get('theory_vs_practice')
    team_value = style_src.get('individual_vs_team')

    # 记录原始值以便调试
    logger.info(f"Original style values - depth: {depth_value}, theory: {theory_value}, team: {team_value}")

    # 处理可能的字典类型（如果直接从evaluation_bars获取）
    if isinstance(depth_value, dict):
        depth_value = depth_value.get('score', 5)
    if isinstance(theory_value, dict):
        theory_value = theory_value.get('score', 5)
    if isinstance(team_value, dict):
        team_value = team_value.get('score', 5)

    # 清理并设置最终值
    character_target['depthVsBreadth'] = clean_number(depth_value, default=5)
    character_target['theoryVsPractice'] = clean_number(theory_value, default=5)
    character_target['soloVsTeamwork'] = clean_number(team_value, default=5)
    character_target['justification'] = justification  # 使用前面提取的justification

    # 记录最终设置的值
    logger.info(f"Final character values - depth: {character_target['depthVsBreadth']}, theory: {character_target['theoryVsPractice']}, team: {character_target['soloVsTeamwork']}")
    logger.info(f"Final justification: {character_target['justification']}")


    # --- Populate Paper of Year Block ---
    pub_stats = _as_dict(source_data.get('publication_stats'))
    paper_of_year_target = target_data['researcherProfile']['dataBlocks']['paperOfYear']
    paper_of_year_src = _as_dict(pub_stats.get('paper_of_year') or source_data.get('paper_of_year'))

    if paper_of_year_src:
        paper_of_year_venue = paper_of_year_src.get('venue')
        paper_of_year_title = paper_of_year_src.get('title')
        paper_of_year_year = clean_year(paper_of_year_src.get('year'))

        # 使用会议匹配功能处理Venue字段（与representativePaper相同的逻辑）
        # 首先尝试从venue匹配，使用专门的venue处理器
        matched_venue = process_venue_string(paper_of_year_venue) if paper_of_year_venue else None

        # 如果venue没有匹配到或者匹配结果与原始venue相同，尝试从title匹配
        if not matched_venue or matched_venue == paper_of_year_venue:
            if paper_of_year_title:
                title_matched_venue = process_venue_string(paper_of_year_title)
                # 只有当title匹配结果不等于title本身时才使用
                if title_matched_venue != paper_of_year_title:
                    matched_venue = title_matched_venue

        # 如果匹配成功但没有年份，而paper有年份，则添加年份
        if matched_venue and paper_of_year_year and ' ' + str(paper_of_year_year) not in matched_venue:
            # 检查匹配结果是否已经包含年份
            if not re.search(r'\d{4}', matched_venue):
                matched_venue = f"{matched_venue} {paper_of_year_year}"

        paper_of_year_target['title'] = paper_of_year_title
        paper_of_year_target['year'] = paper_of_year_year

        # 使用venue_processor处理venue字段，它已经包含了对arXiv的特殊处理
        if matched_venue and matched_venue != paper_of_year_venue:
            paper_of_year_target['venue'] = matched_venue
        else:
            # 如果匹配失败，使用简化的venue
            paper_of_year_target['venue'] = simplify_venue(paper_of_year_venue)

        paper_of_year_target['citations'] = clean_number(paper_of_year_src.get('citations'))
        paper_of_year_target['authorPosition'] = clean_number(paper_of_year_src.get('author_position'))
        paper_of_year_target['summary'] = paper_of_year_src.get('summary') or ''
    else:
        logger.info("No paper_of_year data found in report")

    # --- Populate Representative Paper Block (Modified to use conference matcher) ---
    # 首先尝试从 publication_stats 中获取 most_cited_paper
    rep_paper_src = _as_dict(pub_stats.get('most_cited_paper'))

    # 如果在 publication_stats 中没有找到，尝试从根级别获取
    if not rep_paper_src:
        rep_paper_src = _as_dict(source_data.get('most_cited_paper'))
        logger.info(f"Using most_cited_paper from root level: {rep_paper_src}")
    else:
        logger.info(f"Using most_cited_paper from publication_stats: {rep_paper_src}")

    rep_paper_target = target_data['researcherProfile']['dataBlocks']['representativePaper']
    rep_paper_venue = rep_paper_src.get('venue')
    rep_paper_title = rep_paper_src.get('title')
    rep_paper_year = clean_year(rep_paper_src.get('year'))

    # 使用会议匹配功能处理Venue字段
    # 首先尝试从venue匹配，使用专门的venue处理器
    matched_venue = process_venue_string(rep_paper_venue) if rep_paper_venue else None

    # 如果venue没有匹配到或者匹配结果与原始venue相同，尝试从title匹配
    if not matched_venue or matched_venue == rep_paper_venue:
        if rep_paper_title:
            title_matched_venue = process_venue_string(rep_paper_title)
            # 只有当title匹配结果不等于title本身时才使用
            if title_matched_venue != rep_paper_title:
                matched_venue = title_matched_venue

    # 如果匹配成功但没有年份，而paper有年份，则添加年份
    if matched_venue and rep_paper_year and ' ' + str(rep_paper_year) not in matched_venue:
        # 检查匹配结果是否已经包含年份
        if not re.search(r'\d{4}', matched_venue):
            matched_venue = f"{matched_venue} {rep_paper_year}"

    rep_paper_target['title'] = rep_paper_title
    rep_paper_target['year'] = rep_paper_year
    rep_paper_target['fullVenue'] = rep_paper_venue

    # 使用venue_processor处理venue字段，它已经包含了对arXiv的特殊处理
    if matched_venue and matched_venue != rep_paper_venue:
        rep_paper_target['venue'] = matched_venue
    else:
        # 如果匹配失败，使用简化的venue
        rep_paper_target['venue'] = simplify_venue(rep_paper_venue)

    rep_paper_target['citations'] = clean_number(rep_paper_src.get('citations'))
    rep_paper_target['authorPosition'] = clean_number(rep_paper_src.get('author_position'))

    # Add paper_news from report if available
    # 首先尝试从 publication_stats 中获取 paper_news
    paper_news = pub_stats.get('paper_news')

    # 如果在 publication_stats 中没有找到，尝试从根级别获取
    if not paper_news:
        paper_news = source_data.get('paper_news')
        if paper_news:
            logger.info(f"Using paper_news from root level")
    else:
        logger.info(f"Using paper_news from publication_stats")

    rep_paper_target['paper_news'] = paper_news


    # --- Populate Critical Review Block (MODIFIED to use pre-generated evaluation) ---
    critical_review_target = target_data['researcherProfile']['dataBlocks']['criticalReview']
    # 使用预先生成的评价，如果没有则使用默认值
    if 'critical_evaluation' in source_data:
        critical_review_target['evaluation'] = source_data['critical_evaluation']
    else:
        # 如果没有预先生成的评价，使用默认值
        critical_review_target['evaluation'] = "A critical analysis would be included here, but our roast-bot is currently on vacation. Publication patterns and citation metrics show room for growth."

    return target_data
