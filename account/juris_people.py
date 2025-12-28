# coding: UTF-8
"""
    @author: Sam Gao
    @date:   2025-03-24
    @func:   Given Name, return Google Scholar ID, Personal Website, Email and Personal Image.
    @update: 2025-04-22 Changed from Gemini to OpenRouter's GPT-4o model, ensuring English output.
"""
import time
import json
import logging
import os

from server.config.llm_models import get_model

# 导入日志配置
# 使用server/utils/logging_config.py中的日志配置，将日志输出到文件中
from server.utils.logging_config import setup_logging

# 导入json_repair库，用于修复JSON解析错误
try:
    from json_repair import repair_json
except ImportError:
    # 如果json_repair库未安装，定义一个简单的替代函数
    def repair_json(json_str, **kwargs):
        logging.warning("json-repair library not available, using fallback")
        return json_str

# 设置日志记录器
logger = logging.getLogger('account.juris_people')

# 确保日志目录存在
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../logs'))
os.makedirs(log_dir, exist_ok=True)

# 如果日志器没有处理器，说明还没有初始化，调用setup_logging
if not logger.handlers:
    # 初始化日志配置
    setup_logging(log_dir=log_dir)

    # 为account模块创建一个专门的日志记录器
    from server.utils.logging_config import create_module_logger
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    create_module_logger('account', log_dir, logging.INFO, formatter)

    logger.debug("Juris people logger initialized")

# 导入提示词模板
from server.prompts.researcher_prompts import get_salary_evaluation_prompt, get_career_level_prompt, get_evaluation_bars_prompt


def get_fame_score_with_perplexity(author_info):
    """
    Use Perplexity to assess researcher's fame/recognition score with real-time web search

    Args:
        researcher_name: Name of the researcher
        researcher_info: Basic researcher information

    Returns:
        Fame score (1-10)
    """
    try:
        import json
        from server.llm.gateway import openrouter_chat

        # Create prompt for fame assessment
        prompt = f"""
Please assess the fame/recognition level of researcher using real-time web search.

Basic info: {author_info}

Search for recent news, awards, media coverage, Wikipedia entries, and public recognition.

Rate their fame/recognition from 1-10:
- 1-2: Unknown researcher, no significant public recognition
- 3-4: Some recognition within academic field only
- 5-6: Well-known in academic field, some industry recognition
- 7-8: Notable public recognition, media coverage, or major awards
- 9-10: Famous researcher with significant media presence, major awards (Nobel, Turing, etc.)

Return ONLY a complete JSON object :
{{"fame_score": [1-10], "reasoning": "Brief explanation of fame level based on search results"}}

CRITICAL: You must return a complete, valid JSON object. Do not return partial JSON or empty content. 
"""

        content = openrouter_chat(
            task="juris.fame",
            model=get_model("reasoning_fast", task="juris.fame"),
            messages=[
                {"role": "system", "content": "You are an expert at assessing researcher fame and recognition using real-time web search."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            cache=False,
            timeout_seconds=float(os.getenv("DINQ_JURIS_FAME_TIMEOUT_SECONDS", "12") or "12"),
        )

        content = str(content) if content else ""
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        logger.info(f"fame content:{content}")
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            json_content = content[first_brace:last_brace + 1]
            logger.info(f"Extracted JSON content: {json_content}")
            fame_data = json.loads(json_content)
        else:
            logger.error(f"No valid JSON braces found in content: {content}")
            return 1
        fame_score = fame_data.get('fame_score', 1)
        reasoning = fame_data.get('reasoning', 'Default assessment')

        logger.info(f"Fame assessment for {author_info}: {fame_score}/10 - {reasoning}")
        return fame_score

    except Exception as e:
        logger.info(f"Error in fame assessment for {author_info}: {e}")
        return 1  # Default score

def calculate_programmatic_salary(level_info, author_info=None):
    """
    Programmatically calculate salary based on AI-scored factors + Perplexity fame assessment.
    Only replaces earnings, keeps all other fields unchanged.

    Args:
        level_info: Contains level and compensation_factors from AI analysis
        researcher_name: Name for fame assessment
        researcher_info: Info for fame assessment

    Returns:
        Updated level_info with calculated earnings
    """
    try:
        # Software Engineer baseline salaries by level
        swe_baselines = {
            "L3": 193944,
            "L4": 286816,
            "L5": 376619,
            "L6": 561825,
            "L7": 779143,
            "L8": 1110786,
            "L9": 2358451
        }

        # Get base salary from level
        level_us = level_info.get('level_us', 'L5')
        base_salary = swe_baselines.get(level_us, swe_baselines['L5'])

        # Get AI-scored factors
        factors = level_info.get('compensation_factors', {})
        research_impact = factors.get('research_impact_score', 5)
        field_premium = factors.get('field_premium_score', 5)
        role_seniority = factors.get('role_seniority_score', 5)
        industry_leadership = factors.get('industry_leadership_score', 5)
        market_competition = factors.get('market_competition_score', 5)

        # Get fame score using Perplexity web search
        if author_info:
            fame_recognition = get_fame_score_with_perplexity(author_info)

        else:
            fame_recognition = 1  # Default if no name provided

        # Calculate additive bonuses based on scores (累加方式)
        # Each dimension contributes 0% to 50% bonus (score 1-10)
        research_bonus = (research_impact - 1) * 0.04
        field_bonus = (field_premium - 1) * 0.07
        role_bonus = (role_seniority - 1) * 0.03
        industry_bonus = (industry_leadership - 1) * 0.02
        market_bonus = (market_competition - 1) * 0.02

        # Total additive bonus (max ~150%)
        total_bonus = research_bonus + field_bonus + role_bonus + industry_bonus + market_bonus

        # Calculate salary with additive bonuses
        salary_with_bonuses = base_salary * (1 + total_bonus)

        # Fame/Recognition multiplier with significant boost for high fame (7+)
        fame_multiplier = None
        if fame_recognition >= 8:
            # 7-8分: 2.5x to 5.0x (显著知名)
            fame_multiplier = 1.0 + (fame_recognition - 6) * 1.0
        # else:
        #     # 1-6分: 1.0x to 2.5x (普通到小有名气)
        #     fame_multiplier = 1.0 + (fame_recognition - 1) * 0.08

        # Apply fame multiplier to final salary
        if fame_multiplier:
            final_salary = salary_with_bonuses * fame_multiplier
        else:
            final_salary = salary_with_bonuses

        # Create salary range (±15%)
        min_salary = int(final_salary * 0.85)
        max_salary = int(final_salary * 1.15)

        # Format earnings (same format as before)
        earnings = f"{min_salary}-{max_salary}"

        # Only update earnings, keep AI-generated justification unchanged
        level_info['earnings'] = earnings

        # Keep the AI-generated justification as is (don't overwrite it)

        # Remove compensation_factors from final output to match original structure
        if 'compensation_factors' in level_info:
            del level_info['compensation_factors']


        return level_info

    except Exception as e:
        logger.error(f"Error in programmatic salary calculation: {e}")
        # Fallback to default - only update earnings, keep AI justification
        level_info['earnings'] = "500000-800000"
        return level_info


def format_report_for_llm(report):
    """
    Convert report dictionary to a structured string format for LLMs.

    Args:
        report (dict): The report dictionary

    Returns:
        str: Formatted string representation of the report
    """
    if not report:
        logger.error("No report data provided")
        return ""

    if isinstance(report, str):
        logger.error("report data type: expected str, got {}".format(type(report)))
        return report
    output = []

    # Basic researcher info
    researcher = report['researcher']
    output.append("=== Researcher Information ===")
    output.append(f"Name: {researcher['name']}")
    output.append(f"Affiliation: {researcher['affiliation']}")
    output.append(f"H-index: {researcher['h_index']}")
    output.append(f"Total citations: {researcher['total_citations']}")
    if 'research_fields' in researcher:
        output.append(f"Research fields: {', '.join(researcher['research_fields'])}")

    # Publication statistics
    pub_stats = report['publication_stats']
    output.append("\n=== Publication Statistics ===")
    output.append(f"Total papers: {pub_stats['total_papers']}")
    output.append(f"First-author papers: {pub_stats['first_author_papers']} ({pub_stats['first_author_percentage']:.1f}%)")
    output.append(f"Last-author papers: {pub_stats['last_author_papers']} ({pub_stats['last_author_percentage']:.1f}%)")
    output.append(f"Top-tier papers: {pub_stats['top_tier_papers']} ({pub_stats['top_tier_percentage']:.1f}%)")

    # Conference and Journal distribution
    output.append("\nTop Conference Publications:")
    for conf, count in pub_stats['conference_distribution'].items():
        output.append(f"- {conf}: {count}")

    output.append("\nTop Journal Publications:")
    for journal, count in pub_stats['journal_distribution'].items():
        output.append(f"- {journal}: {count}")

    # Most cited paper
    if 'most_cited_paper' in pub_stats:
        paper = pub_stats['most_cited_paper']
        output.append("\n=== Most Cited Paper ===")
        output.append(f"Title: {paper['title']}")
        output.append(f"Year: {paper['year']}")
        output.append(f"Venue: {paper['venue']}")
        output.append(f"Citations: {paper['citations']}")

    # Collaboration information
    if 'most_frequent_collaborator' in report and report['most_frequent_collaborator']:
        collab = report['most_frequent_collaborator']
        output.append("\n=== Most Frequent Collaborator ===")
        output.append(f"Name: {collab['full_name']}")
        output.append(f"Affiliation: {collab['affiliation']}")
        output.append(f"Number of collaborations: {collab['coauthored_papers']}")
        output.append(f"H-index: {collab.get('h_index', 'N/A')}")
        output.append(f"Total citations: {collab.get('total_citations', 'N/A')}")
        if collab.get('research_interests'):
            output.append(f"Research interests: {', '.join(collab['research_interests'])}")

    # Join all lines with newlines
    return "\n".join(output)


def clean_string_for_llm(text):
    """
    Clean string to make it compatible with LLM processing.

    Args:
        text: Input text that might contain problematic characters

    Returns:
        str: Cleaned text
    """
    if isinstance(text, dict):
        # 如果是字典，先转换成字符串
        text = str(text)

    try:
        # 方法1：使用encode和decode组合，忽略无法解码的字符
        cleaned_text = text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    except UnicodeError:
        try:
            # 方法2：尝试使用其他编码
            cleaned_text = text.encode('ascii', errors='ignore').decode('ascii', errors='ignore')
        except UnicodeError:
            # 方法3：直接移除非ASCII字符
            cleaned_text = ''.join(char for char in text if ord(char) < 128)

    # 移除控制字符
    cleaned_text = ''.join(char for char in cleaned_text if char.isprintable())

    return cleaned_text


def juris_people_level(author_info):
    """
    Analyze researcher's profile and generate salary and level evaluation.

    Args:
        author_info (dict): Researcher's profile information

    Returns:
        dict: Evaluation results including salary level and years of experience
    """
    # 格式化和清理数据
    author_info = format_report_for_llm(author_info)[:5000]
    author_info = clean_string_for_llm(author_info)

    # 使用提示词模板
    salary_content = get_salary_evaluation_prompt(author_info)

    model = get_model("reasoning_fast", task="juris.salary_eval")
    logger.info("Sending request to OpenRouter API with model %s", model)

    # 准备请求数据
    request_data = {
        "model": model,
        "messages": [
          salary_content
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "max_tokens": 1000
    }

    # 记录请求大小
    request_json = json.dumps(request_data)
    request_size = len(request_json)
    logger.debug(f"API request size: {request_size} bytes")

    # 发送请求
    try:
        from server.llm.gateway import openrouter_chat

        summary = openrouter_chat(
            task="juris.salary_eval",
            model=request_data["model"],
            messages=request_data["messages"],
            temperature=request_data["temperature"],
            max_tokens=request_data["max_tokens"],
            extra={"response_format": {"type": "json_object"}},
            timeout_seconds=float(os.getenv("DINQ_JURIS_SALARY_TIMEOUT_SECONDS", "20") or "20"),
        )
        summary = str(summary).strip() if summary else ""
        logger.debug(f"Response content length: {len(summary)} chars")
    except Exception as e:
        logger.error(f"Error sending request to OpenRouter API: {e}")
        return None

    try:
        # 尝试直接解析JSON响应
        try:
            author_detail = json.loads(summary)
            logger.info("Successfully parsed JSON directly")
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试从文本中提取JSON部分
            logger.warning("Direct JSON parsing failed, trying to extract JSON from text")
            logger.debug(f"Response content: {summary[:200]}...")
            json_str = summary[summary.find('{'):summary.rfind('}')+1]
            logger.debug(f"Extracted JSON: {json_str[:200]}...")
            author_detail = json.loads(json_str)
        # import pdb; pdb.set_trace()

        # 确保其他必要字段也有默认值
        default_years_of_experience = {
            'years': 5,  # 默认5年经验
            'start_year': 2018,  # 默认从2018年开始
            'calculation_basis': 'Estimated based on publication history and career trajectory patterns in similar researchers.'
        }

        # 构建返回字典，确保所有字段都有值
        result = {
            'years_of_experience': author_detail.get('years_of_experience', default_years_of_experience),
            'level_cn': author_detail.get('level_cn', 'P7'),  # 默认P7级别
            'level_us': author_detail.get('level_us', 'L5'),  # 默认L5级别
            'earnings': author_detail.get('earnings', '350000'),  # 默认年薪35万美元
            'justification': author_detail.get('justification', 'The researcher demonstrates solid expertise in their field with impactful publications and growing citation metrics. Their work shows both depth and breadth, with potential for continued growth and influence in the research community.')
        }

        # 最终检查确保没有None值
        if not result['level_cn']:
            result['level_cn'] = 'P7'
        if not result['level_us']:
            result['level_us'] = 'L5'
        if not result['earnings']:
            result['earnings'] = '350000'
        if not result['justification']:
            result['justification'] = 'The researcher demonstrates solid expertise in their field with impactful publications and growing citation metrics. Their work shows both depth and breadth, with potential for continued growth and influence in the research community.'

        # 检查years_of_experience字段
        if not isinstance(result['years_of_experience'], dict):
            result['years_of_experience'] = default_years_of_experience
        else:
            for key in ['years', 'start_year', 'calculation_basis']:
                if key not in result['years_of_experience'] or result['years_of_experience'][key] is None:
                    result['years_of_experience'][key] = default_years_of_experience[key]

        logger.info(f"Final result with all fields populated: {result}")
        return result
    except json.JSONDecodeError:
        logger.error(f"Failed to parse author detail response: {summary[:200]}...")
        # 返回默认值而不是None
        return create_default_evaluation(with_evaluation_bars=False)
    except Exception as e:
        logger.error(f"Error processing author detail: {e}")
        # 返回默认值而不是None
        return create_default_evaluation(with_evaluation_bars=False)


def create_default_evaluation(with_evaluation_bars=True):
    """
    创建默认的评估结果，当API调用失败或解析错误时使用。

    Args:
        with_evaluation_bars (bool): 是否包含评估条数据

    Returns:
        dict: 包含默认值的评估结果字典
    """
    logger.info("Creating default evaluation data")

    # 基本默认值
    default_result = {
        'years_of_experience': {
            'years': 5,
            'start_year': 2018,
            'calculation_basis': 'Estimated based on typical career progression patterns in academia and industry.'
        },
        'level_cn': 'P7',
        'level_us': 'L5',
        'earnings': '350000',
        'justification': 'The researcher demonstrates solid expertise with impactful publications and growing citation metrics. Their work shows both depth and breadth, with potential for continued growth and influence in the research community.'
    }

    # 如果需要评估条数据
    if with_evaluation_bars:
        default_result['evaluation_bars'] = {
            'depth_vs_breadth': {
                'score': 5,
                'explanation': 'Based on publication data, the researcher shows a balanced approach between depth and breadth in their research focus. Their publication history indicates versatility while maintaining expertise in core areas.'
            },
            'theory_vs_practice': {
                'score': 5,
                'explanation': 'The researcher demonstrates a balance between theoretical contributions and practical applications in their published work. Their papers include both algorithmic innovations and implementations that address real-world problems.'
            },
            'individual_vs_team': {
                'score': 5,
                'explanation': 'Publication patterns suggest the researcher balances individual work and collaborative research with various team sizes. Their first-author papers demonstrate individual capability while co-authored works show effective collaboration.'
            }
        }

    return default_result


def three_card_juris_people(author_info):
    """
    Analyze researcher's profile and generate three evaluation bars.
    This optimized version splits the analysis into two separate API calls:
    1. Career level and earnings evaluation
    2. Three evaluation bars

    Args:
        author_info (dict): Researcher's profile information

    Returns:
        dict: Evaluation results including salary level and three evaluation bars
    """
    # 格式化和清理数据
    formatted_info = format_report_for_llm(author_info)[:5000]
    formatted_info = clean_string_for_llm(formatted_info)
    
    # 记录开始时间
    start_time = time.time()
    
    # 结果字典，用于合并两次API调用的结果
    final_result = {}
    
    # 第一次API调用：获取职级和收入信息
    career_level_result = get_career_level_info(formatted_info)
    if career_level_result:
        # 将结果合并到最终结果中
        final_result.update(career_level_result)
    else:
        # 如果第一次调用失败，使用默认值
        logger.warning("Career level API call failed, using default values")
        default_eval = create_default_evaluation(with_evaluation_bars=False)
        final_result.update({
            'years_of_experience': default_eval['years_of_experience'],
            'level_cn': default_eval['level_cn'],
            'level_us': default_eval['level_us'],
            'earnings': default_eval['earnings'],
            'justification': default_eval['justification']
        })
    
    # 记录第一次API调用完成时间
    mid_time = time.time()
    logger.info(f"Career level API call completed in {mid_time - start_time:.2f} seconds")
    
    # 第二次API调用：获取三个评估条信息
    evaluation_bars_result = get_evaluation_bars(formatted_info)
    if evaluation_bars_result and 'evaluation_bars' in evaluation_bars_result:
        # 将评估条结果合并到最终结果中
        final_result['evaluation_bars'] = evaluation_bars_result['evaluation_bars']
    else:
        # 如果第二次调用失败，使用默认评估条
        logger.warning("Evaluation bars API call failed, using default values")
        default_eval = create_default_evaluation(with_evaluation_bars=True)
        final_result['evaluation_bars'] = default_eval['evaluation_bars']
    
    # 记录结束时间
    end_time = time.time()
    logger.info(f"Evaluation bars API call completed in {end_time - mid_time:.2f} seconds")
    logger.info(f"Total processing time: {end_time - start_time:.2f} seconds")
    
    # 最终检查确保没有None值
    if not final_result.get('level_cn'):
        final_result['level_cn'] = 'P7'
    if not final_result.get('level_us'):
        final_result['level_us'] = 'L5'
    if not final_result.get('earnings'):
        final_result['earnings'] = '350000'
    if not final_result.get('justification'):
        final_result['justification'] = 'The researcher demonstrates solid expertise in their field with impactful publications and growing citation metrics.'
    
    # 检查years_of_experience字段
    default_years_of_experience = {
        'years': 5,  # 默认5年经验
        'start_year': 2018,  # 默认从2018年开始
        'calculation_basis': 'Estimated based on publication history and career trajectory patterns in similar researchers.'
    }
    
    if not isinstance(final_result.get('years_of_experience'), dict):
        final_result['years_of_experience'] = default_years_of_experience
    else:
        for key in ['years', 'start_year', 'calculation_basis']:
            if key not in final_result['years_of_experience'] or final_result['years_of_experience'][key] is None:
                final_result['years_of_experience'][key] = default_years_of_experience[key]
    
    # 构造最终的level_info结构
    final_result = {
        'earnings': final_result.pop('earnings'),
        'level_cn': final_result.pop('level_cn'),
        'level_us': final_result.pop('level_us'),
        'justification': final_result.pop('justification'),
        'evaluation_bars': final_result.pop('evaluation_bars'),
        'years_of_experience': final_result.pop('years_of_experience')
    }
    
    logger.info(f"Final result with all fields populated and structured")
    return final_result


def get_career_level_info(author_info):
    """
    获取研究者的职级和收入信息。
    这是第一个API调用，专注于基本职级评估。

    Args:
        author_info (str): 研究者简介信息

    Returns:
        dict: 包含职级和收入信息的字典，如果调用失败则返回None
    """
    # 使用提示词模板
    career_level_content = get_career_level_prompt(author_info)

    model = get_model("reasoning_fast", task="juris.career_level")
    logger.info("Sending request to OpenRouter API with model %s for career level evaluation", model)

    # 准备请求数据
    request_data = {
        "model": model,
        "messages": [
          career_level_content
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "max_tokens": 600  # 减少token数量，因为只需要基本信息
    }

    # 记录请求大小
    request_json = json.dumps(request_data)
    request_size = len(request_json)
    logger.debug(f"Career level API request size: {request_size} bytes")

    # 发送请求
    try:
        from server.llm.gateway import openrouter_chat

        summary = openrouter_chat(
            task="juris.career_level",
            model=request_data["model"],
            messages=request_data["messages"],
            temperature=request_data["temperature"],
            max_tokens=request_data["max_tokens"],
            extra={"response_format": {"type": "json_object"}},
            timeout_seconds=float(os.getenv("DINQ_JURIS_CAREER_LEVEL_TIMEOUT_SECONDS", "20") or "20"),
        )
        summary = str(summary).strip() if summary else ""
        logger.debug(f"Career level response length: {len(summary)} chars")
        
        # 使用json_repair修复可能的JSON格式问题
        try:
            # 尝试直接解析JSON
            career_info = json.loads(summary)
            logger.info("Successfully parsed career level JSON directly")
        except json.JSONDecodeError as e:
            logger.warning(f"Direct JSON parsing failed: {e}, trying to repair JSON")
            # 如果直接解析失败，尝试提取和修复JSON
            if '{' in summary and '}' in summary:
                json_str = summary[summary.find('{'):summary.rfind('}')+1]
                logger.debug(f"Extracted JSON from text: {json_str[:100]}...")
                
                # 使用json_repair修复JSON
                repaired_json = repair_json(json_str)
                logger.debug(f"Repaired JSON: {repaired_json[:100]}...")
                
                # 解析修复后的JSON
                career_info = json.loads(repaired_json)
                logger.info("Successfully parsed career level JSON after repair")
            else:
                logger.error("No JSON object found in career level response")
                return None
        
        # 在AI分析后立即调用程序化计算，传递研究者信息用于出名度评估
        career_info = calculate_programmatic_salary(career_info, author_info)

        # 返回解析后的职级信息
        return career_info
        
    except Exception as e:
        logger.error(f"Error processing career level response: {e}")
        return None


def get_evaluation_bars(author_info):
    """
    获取研究者的三个评估条信息。
    这是第二个API调用，专注于评估条分析。

    Args:
        author_info (str): 研究者简介信息

    Returns:
        dict: 包含评估条信息的字典，如果调用失败则返回None
    """
    # 使用提示词模板
    eval_bars_content = get_evaluation_bars_prompt(author_info)

    model = get_model("reasoning_fast", task="juris.eval_bars")
    logger.info("Sending request to OpenRouter API with model %s for evaluation bars", model)

    # 准备请求数据
    request_data = {
        "model": model,
        "messages": [
          eval_bars_content
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "max_tokens": 600  # 减少token数量，因为只需要评估条信息
    }

    # 记录请求大小
    request_json = json.dumps(request_data)
    request_size = len(request_json)
    logger.debug(f"Evaluation bars API request size: {request_size} bytes")

    # 发送请求
    try:
        from server.llm.gateway import openrouter_chat

        summary = openrouter_chat(
            task="juris.eval_bars",
            model=request_data["model"],
            messages=request_data["messages"],
            temperature=request_data["temperature"],
            max_tokens=request_data["max_tokens"],
            extra={"response_format": {"type": "json_object"}},
            timeout_seconds=float(os.getenv("DINQ_JURIS_EVAL_BARS_TIMEOUT_SECONDS", "20") or "20"),
        )
        summary = str(summary).strip() if summary else ""
        logger.debug(f"Evaluation bars response length: {len(summary)} chars")
        
        # 使用json_repair修复可能的JSON格式问题
        try:
            # 尝试直接解析JSON
            eval_bars = json.loads(summary)
            logger.info("Successfully parsed evaluation bars JSON directly")
        except json.JSONDecodeError as e:
            logger.warning(f"Direct JSON parsing failed: {e}, trying to repair JSON")
            # 如果直接解析失败，尝试提取和修复JSON
            if '{' in summary and '}' in summary:
                json_str = summary[summary.find('{'):summary.rfind('}')+1]
                logger.debug(f"Extracted JSON from text: {json_str[:100]}...")
                
                # 使用json_repair修复JSON
                repaired_json = repair_json(json_str)
                logger.debug(f"Repaired JSON: {repaired_json[:100]}...")
                
                # 解析修复后的JSON
                eval_bars = json.loads(repaired_json)
                logger.info("Successfully parsed evaluation bars JSON after repair")
            else:
                logger.error("No JSON object found in evaluation bars response")
                return None
        
        # 检查评估条数据是否有效，如果无效则提供默认值
        default_bars = {
            'depth_vs_breadth': {
                'score': 5,
                'explanation': 'Based on available publication data, the researcher shows a balanced approach between depth and breadth in their research focus.'
            },
            'theory_vs_practice': {
                'score': 5,
                'explanation': 'The researcher demonstrates a balance between theoretical contributions and practical applications in their published work.'
            },
            'individual_vs_team': {
                'score': 5,
                'explanation': 'Publication patterns suggest the researcher balances individual work and collaborative research with various team sizes.'
            }
        }
        
        # 确保evaluation_bars字段存在
        if 'evaluation_bars' not in eval_bars:
            logger.warning("No evaluation_bars field in response, using default structure")
            eval_bars['evaluation_bars'] = default_bars
        
        # 检查每个评估维度，如果缺失或无效，则使用默认值
        for dimension in ['depth_vs_breadth', 'theory_vs_practice', 'individual_vs_team']:
            if dimension not in eval_bars['evaluation_bars'] or not eval_bars['evaluation_bars'][dimension]:
                eval_bars['evaluation_bars'][dimension] = default_bars[dimension]
            elif 'explanation' not in eval_bars['evaluation_bars'][dimension] or not eval_bars['evaluation_bars'][dimension]['explanation']:
                eval_bars['evaluation_bars'][dimension]['explanation'] = default_bars[dimension]['explanation']
            if 'score' not in eval_bars['evaluation_bars'][dimension] or not isinstance(eval_bars['evaluation_bars'][dimension]['score'], (int, float)):
                eval_bars['evaluation_bars'][dimension]['score'] = default_bars[dimension]['score']
        
        # 返回处理后的评估条信息
        return eval_bars
        
    except Exception as e:
        logger.error(f"Error processing evaluation bars response: {e}")
        return None


if __name__ == "__main__":
    # 使用项目的日志配置
    # 注意：在模块导入时已经初始化了日志配置
    logger.info("Starting juris_people test")

    author_info = """Researcher: Daiheng Gao
                    Affiliation: Independent researcher
                    Photo: https://scholar.google.com/citations/images/avatar_scholar_256.png
                    Total paper: 21
                    Top-tier distribution (Conference): {'Arxiv': 7, 'ACM MM': 3, 'CVPR': 2, 'NeurIPS': 1, 'ICCV': 1, '2019 IEEE International Conference on Image Processing (ICIP), 1655-1659, 2019': 1, 'ICASSP': 1, 'International Workshop on Human Brain and Artificial Intelligence, 1-13, 2021': 1}
                    Top-tier distribution (Journel): {'IJCV': 1, 'Journal of Changjiang River Scientific Research Institute 36 (4), 118, 2019': 1, 'Journal of Changjiang River Scientific Research Institute 35 (3), 171, 2018': 1}
                    Colloborators: 77
                    H-index: 9
                    Total citations: 670
                    First-author papers: 10 (47.6%)
                    Last-author papers: 1 (4.8%)
                    Top-tier papers: 9 (42.9%)

                    === Most Cited Paper ===
                    Title: DeepFaceLab: Integrated, flexible and extensible face-swapping framework
                    搜索查询: Please gave me url link and icon with paper title: DeepFaceLab: Integrated, flexible and extensible face-swapping framework
                    Arxiv: {'name': 'DeepFaceLab: Integrated, flexible and extensible face-swapping framework', 'arxiv_url': 'https://best-of-web.builder.io/library/iperov/DeepFaceLab', 'image': 'https://d3i71xaburhd42.cloudfront.net/0d04729f05081172f6ebcbd4565dc7dc6474c95b/9-Figure6-1.png'}
                    Year: 2020
                    Venue: arXiv preprint arXiv:2005.05535, 2020
                    Citations: 478
                    Authors: I Perov, D Gao, N Chervoniy, K Liu, S Marangonda, C Umé, ...
                    === Most Frequent Collaborator ===
                    Name: bang zhang
                    Affiliation: Alibaba Group (Tongyi)
                    Number of collaborations: 9
                    H-index: N/A
                    Total citations: N/A

                    Best collaboration paper:
                    Title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    搜索查询: Please gave me url link and icon with paper title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    Arxiv: {'name': 'Multi-view consistent generative adversarial networks for 3d-aware image synthesis', 'arxiv_url': 'https://github.com/Xuanmeng-Zhang/MVCGAN', 'image': 'https://d3i71xaburhd42.cloudfront.net/03604c4e68211d1198a5f547c865ac453eec22aa/3-Figure3-1.png'}
                    Venue: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern …, 2022
                    Year: 2022
                    Affiliation: Alibaba Group (Tongyi)
                    Number of collaborations: 9
                    H-index: N/A
                    Total citations: N/A

                    Best collaboration paper:
                    Title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    搜索查询: Please gave me url link and icon with paper title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    Arxiv: {'name': 'Multi-view consistent generative adversarial networks for 3d-aware image synthesis', 'arxiv_url': 'https://github.com/Xuanmeng-Zhang/MVCGAN', 'image': 'https://d3i71xaburhd42.cloudfront.net/03604c4e68211d1198a5f547c865ac453eec22aa/3-Figure3-1.png'}
                    Venue: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern …, 2022
                    Year: 2022

                    Best collaboration paper:
                    Title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    搜索查询: Please gave me url link and icon with paper title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    Arxiv: {'name': 'Multi-view consistent generative adversarial networks for 3d-aware image synthesis', 'arxiv_url': 'https://github.com/Xuanmeng-Zhang/MVCGAN', 'image': 'https://d3i71xaburhd42.cloudfront.net/03604c4e68211d1198a5f547c865ac453eec22aa/3-Figure3-1.png'}
                    Venue: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern …, 2022
                    Year: 2022
                    搜索查询: Please gave me url link and icon with paper title: Multi-view consistent generative adversarial networks for 3d-aware image synthesis
                    Arxiv: {'name': 'Multi-view consistent generative adversarial networks for 3d-aware image synthesis', 'arxiv_url': 'https://github.com/Xuanmeng-Zhang/MVCGAN', 'image': 'https://d3i71xaburhd42.cloudfront.net/03604c4e68211d1198a5f547c865ac453eec22aa/3-Figure3-1.png'}
                    Venue: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern …, 2022
                    Year: 2022
                    Year: 2022
                    Citations: 54"""
    t1 = time.time()
    # result = juris_people_level(author_info)
    result = three_card_juris_people(author_info)
    t2 = time.time()
    logger.info(f"Result: {json.dumps(result, indent=2) if result else 'None'}")
    logger.info(f"Time taken: {t2 - t1:.2f} seconds")
