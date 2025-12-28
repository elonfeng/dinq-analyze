# coding: UTF-8
"""
    @File: template_figure_kimi.py
    @Author: Sam Gao
    @Date: 2025-03-22
    @Description: 使用OpenRouter API和GPT-4o模型找到模板人物: 姓名, 机构, 职位, 研究方向, 研究成果的图片
    @update:  2025-04-08 升级128k, 由于moonshot降价, 全量塞进去.
    @update:  2025-04-12 增加错误处理和备用模型支持
    @update:  2025-04-12 移动到server/services/scholar目录
    @update:  2025-04-22 从使用Kimi改为使用OpenRouter的GPT-4o模型，并确保输出英文
"""
import json
import os
import time
import logging
from server.llm.gateway import openrouter_chat
from server.config.llm_models import get_model
import pandas as pd

# 导入提示词模板
from server.prompts.researcher_prompts import get_role_model_prompt

# 设置日志记录器
logger = logging.getLogger(__name__)

# 从配置文件中加载API密钥
openrouter_api_key = None

def format_report_for_llm(report):
    """
    Convert report dictionary to a structured string format for LLMs.

    Args:
        report (dict): The report dictionary

    Returns:
        str: Formatted string representation of the report
    """
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
    # 检查是否有会议分布数据
    if 'conference_distribution' in pub_stats and pub_stats['conference_distribution']:
        output.append("\nTop Conference Publications:")
        for conf, count in pub_stats['conference_distribution'].items():
            output.append(f"- {conf}: {count}")
    else:
        output.append("\nTop Conference Publications: None")

    # 检查是否有期刊分布数据
    if 'journal_distribution' in pub_stats and pub_stats['journal_distribution']:
        output.append("\nTop Journal Publications:")
        for journal, count in pub_stats['journal_distribution'].items():
            output.append(f"- {journal}: {count}")
    else:
        output.append("\nTop Journal Publications: None")

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
        output.append(f"H-index: {collab['h_index']}")
        output.append(f"Total citations: {collab['total_citations']}")
        if collab['research_interests']:
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



def get_template_figure(author_info, max_retries=3):
    """
    根据研究者信息找到最合适的角色模型，使用OpenRouter的GPT-4o模型

    Args:
        author_info: 研究者信息字典
        max_retries: 最大重试次数

    Returns:
        dict: 角色模型信息，如果失败则返回默认值
    """
    try:
        # 读取学者数据
        try:
            file_path = os.path.join(os.path.dirname(__file__), "../../../top_ai_talents.csv")
            file_content = pd.read_csv(file_path, encoding='utf-8', encoding_errors='ignore')
            academic_data = file_content.to_dict(orient="records")
            logger.info(f"Successfully loaded {len(academic_data)} academic records")
        except Exception as e:
            logger.error(f"Failed to load academic data: {e}")
            # 尝试使用相对路径
            try:
                file_content = pd.read_csv("top_ai_talents.csv", encoding='utf-8', encoding_errors='ignore')
                academic_data = file_content.to_dict(orient="records")
                logger.info(f"Successfully loaded {len(academic_data)} academic records using relative path")
            except Exception as e2:
                logger.error(f"Failed to load academic data using relative path: {e2}")
                # 如果无法加载数据，返回默认角色模型
                return get_default_role_model(author_info)

        # 创建名人字典
        celeb_dict = {}
        for item in academic_data:
            celeb_dict[item["name"]] = item

        # 检查研究者是否已经是名人
        if author_info['researcher']['name'] in celeb_dict.keys() or author_info['researcher']['total_citations'] > 10000:
            logger.info(f"Researcher {author_info['researcher']['name']} is already a celebrity or has over 10,000 citations, no role model needed")
            return None

        # 格式化作者信息
        author_info_str = format_report_for_llm(author_info)
        author_info_str = clean_string_for_llm(author_info_str)

        # 使用OpenRouter API获取角色模型
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt+1}/{max_retries} to get role model using OpenRouter API with GPT-4o")

                # 准备消息
                try:
                    # 限制token数量以确保请求不会太大
                    messages = get_role_model_prompt(author_info_str, celeb_dict, max_tokens=8000)
                    logger.info(f"Successfully prepared messages with celebrity dictionary")
                except Exception as e:
                    logger.error(f"Error preparing messages with celebrity dictionary: {e}")
                    # 在出错时使用没有名人字典的提示词
                    try:
                        messages = get_role_model_prompt(author_info_str, None)
                        logger.info(f"Falling back to messages without celebrity dictionary")
                    except Exception as e2:
                        logger.error(f"Error preparing fallback messages: {e2}")
                        # 如果还是出错，返回默认角色模型
                        return get_default_role_model(author_info)

                # 记录消息大小
                messages_str = str(messages)
                messages_tokens = len(messages_str) / 4
                logger.info(f"OpenRouter API message size: {len(messages)} messages, {len(messages_str)} chars, est. {messages_tokens:.0f} tokens")

                content = openrouter_chat(
                    task="scholar_role_model",
                    messages=messages,
                    model=get_model("fast", task="scholar_role_model"),
                    temperature=0.3,
                    max_tokens=1000,
                )
                if content:

                    # 尝试解析JSON
                    try:
                        # 直接解析JSON内容
                        data = json.loads(content)

                        if 'role_model' in data and 'name' in data['role_model']:
                            role_model_name = data['role_model']['name']
                            logger.info(f"OpenRouter API returned role model: {role_model_name}")

                            # 检查返回的角色模型是否在原始表格中
                            if role_model_name in celeb_dict:
                                # 使用原始表格中的数据
                                original_data = celeb_dict[role_model_name]
                                logger.info(f"Found matching role model in original table: {role_model_name}")

                                # 保留模型生成的相似性原因，但使用原始表格中的其他数据
                                similarity_reason = data['role_model'].get('similarity_reason', 'This researcher has similar research interests to you.')

                                # 处理机构和图片URL
                                institution = original_data.get("institution", original_data.get("affiliation", ""))
                                institution_parts = institution.split(";", 1) if institution else [""]
                                clean_institution = institution_parts[0].strip()

                                # 获取图片URL
                                photo_url = original_data.get("photo_url", "")
                                # 如果photo_url为空，但institution包含图片URL，则使用institution中的图片URL
                                if not photo_url and len(institution_parts) > 1:
                                    institution_image = institution_parts[1].strip()
                                    if institution_image.startswith(" http"):
                                        photo_url = institution_image

                                # 如果还是没有图片，尝试使用image字段
                                if not photo_url:
                                    photo_url = original_data.get("image", "")

                                # 获取成就
                                achievement = original_data.get("achievement", "")
                                if not achievement:
                                    # 尝试使用famous_work或honor字段
                                    achievement = original_data.get("famous_work", original_data.get("honor", ""))

                                # 构建角色模型信息
                                role_model = {
                                    "name": original_data["name"],
                                    "institution": clean_institution,
                                    "position": original_data.get("position", ""),
                                    "photo_url": photo_url,
                                    "achievement": achievement,
                                    "similarity_reason": similarity_reason
                                }

                                logger.info(f"Returning role model based on original table: {role_model['name']} ({role_model['institution']})")
                                return role_model
                            else:
                                logger.warning(f"Role model '{role_model_name}' not found in original table, trying to find similar name")

                                # 尝试查找最相似的名称（简单的字符串匹配）
                                best_match = None
                                best_score = 0
                                for name in celeb_dict.keys():
                                    # 计算简单的相似度分数（共同字符的比例）
                                    common_chars = sum(c1 == c2 for c1, c2 in zip(name.lower(), role_model_name.lower()))
                                    max_len = max(len(name), len(role_model_name))
                                    score = common_chars / max_len if max_len > 0 else 0

                                    if score > best_score and score > 0.7:  # 设置一个阈值
                                        best_score = score
                                        best_match = name

                                if best_match:
                                    logger.info(f"Found similar role model: {best_match} (similarity: {best_score:.2f})")
                                    original_data = celeb_dict[best_match]
                                    similarity_reason = data['role_model'].get('similarity_reason', 'This researcher has similar research interests to you.')

                                    # 处理机构和图片URL
                                    institution = original_data.get("institution", original_data.get("affiliation", ""))
                                    institution_parts = institution.split(";", 1) if institution else [""]
                                    clean_institution = institution_parts[0].strip()

                                    # 获取图片URL
                                    photo_url = original_data.get("photo_url", "")
                                    # 如果photo_url为空，但institution包含图片URL，则使用institution中的图片URL
                                    if not photo_url and len(institution_parts) > 1:
                                        institution_image = institution_parts[1].strip()
                                        if institution_image.startswith(" http"):
                                            photo_url = institution_image

                                    # 如果还是没有图片，尝试使用image字段
                                    if not photo_url:
                                        photo_url = original_data.get("image", "")

                                    # 获取成就
                                    achievement = original_data.get("achievement", "")
                                    if not achievement:
                                        # 尝试使用famous_work或honor字段
                                        achievement = original_data.get("famous_work", original_data.get("honor", ""))

                                    # 构建角色模型信息
                                    role_model = {
                                        "name": original_data["name"],
                                        "institution": clean_institution,
                                        "position": original_data.get("position", ""),
                                        "photo_url": photo_url,
                                        "achievement": achievement,
                                        "similarity_reason": similarity_reason
                                    }

                                    logger.info(f"Returning role model based on similar name: {role_model['name']}")
                                    return role_model
                                else:
                                    logger.warning(f"No similar role model found for '{role_model_name}', using model-generated data")
                                    logger.info(f"Successfully got role model from OpenRouter API: {role_model_name}")
                                    return data['role_model']
                        else:
                            logger.warning(f"Invalid data format from OpenRouter API: {content[:100]}...")
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying... ({attempt+1}/{max_retries})")
                                time.sleep(2)  # 在重试前等待
                            else:
                                # 所有尝试都失败，返回默认角色模型
                                logger.error("All attempts failed, returning default role model")
                                return get_default_role_model(author_info)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        logger.error(f"Response content: {content[:200]}...")
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying... ({attempt+1}/{max_retries})")
                            time.sleep(2)  # 在重试前等待
                        else:
                            # 所有尝试都失败，返回默认角色模型
                            logger.error("All attempts failed, returning default role model")
                            return get_default_role_model(author_info)
                else:
                    logger.warning(f"No choices in OpenRouter API response")
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying... ({attempt+1}/{max_retries})")
                        time.sleep(2)  # 在重试前等待
                    else:
                        # 所有尝试都失败，返回默认角色模型
                        logger.error("All attempts failed, returning default role model")
                        return get_default_role_model(author_info)
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"OpenRouter API call failed (attempt {attempt+1}): {e}")
                logger.error(f"Error details: {error_trace}")

                # 检查是否是上下文长度限制错误
                error_str = str(e)
                if 'maximum context length' in error_str or 'context window' in error_str or 'token limit' in error_str:
                    logger.error(f"Context length error: {error_str}")
                    # 如果是上下文长度错误，尝试减少消息大小
                    try:
                        # 使用更小的token限制重新准备消息
                        messages = get_role_model_prompt(author_info_str, None, max_tokens=4000)
                        logger.info("Reduced message size due to context length error")
                        continue  # 使用新的消息重试
                    except Exception as e2:
                        logger.error(f"Failed to reduce message size: {e2}")
                        # 如果还是出错，返回默认角色模型
                        return get_default_role_model(author_info)

                if attempt < max_retries - 1:
                    logger.info(f"Retrying... ({attempt+1}/{max_retries})")
                    time.sleep(2)  # 在重试前等待
                else:
                    # 所有尝试都失败，返回默认角色模型
                    logger.error("All attempts failed, returning default role model")
                    return get_default_role_model(author_info)

        # 如果所有尝试都失败，返回默认角色模型
        logger.error("All attempts to get role model failed, returning default role model")
        return get_default_role_model(author_info)
    except Exception as e:
        logger.error(f"Unexpected error getting role model: {e}")
        return get_default_role_model(author_info)


# 删除不再需要的函数，因为我们已经直接在get_template_figure函数中使用OpenRouter API了


def get_default_role_model(author_info):
    """
    生成默认的角色模型

    Args:
        author_info: 研究者信息字典

    Returns:
        dict: 默认角色模型信息
    """
    logger.info("生成默认角色模型")

    # 从研究者信息中提取研究领域
    research_fields = author_info.get('researcher', {}).get('research_fields', [])
    if not research_fields:
        research_fields = ['Artificial Intelligence', 'Machine Learning']

    # 根据研究领域选择默认角色模型
    default_models = {
        'Computer Vision': {
            "name": "Fei-Fei Li",
            "institution": "Stanford University",
            "position": "Professor of Computer Science",
            "photo_url": "https://ai.stanford.edu/~feifeili/images/feifeili.jpg",
            "achievement": "Pioneer in computer vision and ImageNet creator",
            "similarity_reason": "Both focus on advancing computer vision research with practical applications."
        },
        'Natural Language Processing': {
            "name": "Christopher Manning",
            "institution": "Stanford University",
            "position": "Professor of Linguistics and Computer Science",
            "photo_url": "https://nlp.stanford.edu/~manning/manning-2019-500x500.jpg",
            "achievement": "Leading researcher in NLP and computational linguistics",
            "similarity_reason": "Both contribute to advancing natural language understanding and processing techniques."
        },
        'Machine Learning': {
            "name": "Andrew Ng",
            "institution": "Stanford University",
            "position": "Adjunct Professor",
            "photo_url": "https://ai.stanford.edu/~ang/andrew.jpg",
            "achievement": "Co-founder of Coursera and former head of Google Brain",
            "similarity_reason": "Both focus on practical applications of machine learning algorithms."
        },
        'Artificial Intelligence': {
            "name": "Yoshua Bengio",
            "institution": "University of Montreal",
            "position": "Professor of Computer Science",
            "photo_url": "https://mila.quebec/wp-content/uploads/2018/11/yoshua-bengio-2018-1.jpg",
            "achievement": "Turing Award winner for contributions to deep learning",
            "similarity_reason": "Both contribute to advancing AI research with innovative approaches."
        }
    }

    # 处理默认模型中的机构字段，确保格式一致
    for field, model in default_models.items():
        institution = model.get("institution", "")
        if ";" in institution:
            institution_parts = institution.split(";", 1)
            model["institution"] = institution_parts[0].strip()

            # 如果photo_url为空但institution包含图片URL，则使用institution中的图片URL
            if not model.get("photo_url") and len(institution_parts) > 1:
                institution_image = institution_parts[1].strip()
                if institution_image.startswith(" http"):
                    model["photo_url"] = institution_image

    # 查找匹配的研究领域
    for field in research_fields:
        for key in default_models.keys():
            if key.lower() in field.lower() or field.lower() in key.lower():
                logger.info(f"根据研究领域 '{field}' 选择默认角色模型: {default_models[key]['name']}")
                return default_models[key]

    # 如果没有匹配的研究领域，返回通用角色模型
    logger.info(f"没有匹配的研究领域，返回通用角色模型")
    return default_models['Artificial Intelligence']

# 使用示例
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 测试获取角色模型
    try:
        # 创建测试数据
        test_data = {
            "researcher": {
                "name": "Test Researcher",
                "affiliation": "Test University",
                "h_index": 10,
                "total_citations": 500,
                "research_fields": ["Computer Vision", "Machine Learning"]
            },
            "publication_stats": {
                "total_papers": 20,
                "first_author_papers": 10,
                "first_author_percentage": 50.0,
                "last_author_papers": 5,
                "last_author_percentage": 25.0,
                "top_tier_papers": 8,
                "top_tier_percentage": 40.0,
                "conference_distribution": {"CVPR": 3, "ICCV": 2, "NeurIPS": 3},
                "journal_distribution": {"TPAMI": 2, "IJCV": 1}
            }
        }

        # 获取角色模型
        result = get_template_figure(test_data)
        print("\n角色模型结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"测试失败: {e}")
