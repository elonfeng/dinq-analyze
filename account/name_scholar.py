# coding: UTF-8
"""
    @author:  Sam Gao
    @date:    2025-03-24
    @func:    Given Name, return Google Scholar ID, Personal Website, Email and Personal Image.
    @update:  Fix 重名问题, @justin提出, 20250331修复. Gemini -> Sonar Reasoning Pro. TODO: 太慢了...
"""

import os
import re  # Used for regular expressions throughout the code
import json
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from server.config.llm_models import get_model

# Import json-repair with fallback
try:
    from json_repair import repair_json
except ImportError:
    # Define a simple fallback function if json-repair is not installed
    def repair_json(json_str, **kwargs):
        logging.warning("json-repair library not available, using fallback")
        return json_str

import logging

# 设置日志记录器
logger = logging.getLogger('account.name_scholar')

def get_scholar_information(author_info: str, max_length: int = 500, max_retries: int = 3):
    """
    Get Google Scholar information for a researcher based on name and affiliation string.
    Args:
        author_info: str, format like "name, affiliation" (e.g., "qiang wang, apple ai")
        max_length: int, maximum length of author_info string (default: 500)
        max_retries: int, maximum number of retries with different models (default: 3)
    Returns:
        dict or None: Scholar profile information
    """
    # 限制输入长度
    original_length = len(author_info)
    if len(author_info) > max_length:
        author_info = author_info[:max_length]
        logger.warning(f"Input author_info truncated from {original_length} to {max_length} characters")

    logger.info(f"Getting scholar information for: {author_info}")

    # Model order (speed-first). De-dup in case env overrides collide.
    candidates = [
        get_model("fast", task="name_scholar.lookup"),
        get_model("balanced", task="name_scholar.lookup"),
        get_model("flash_preview", task="name_scholar.lookup"),
        get_model("reasoning_fast", task="name_scholar.lookup"),
    ]
    models = []
    seen = set()
    for m in candidates:
        if not m or m in seen:
            continue
        seen.add(m)
        models.append(m)

    # 记录错误
    errors = []
    # 准备API请求 - 超简化系统提示词以减少token使用
    system_prompt = """You are a helpful assistant that returns information in JSON format only. No explanations or other text."""

    # 准备用户提示词 - 保持简洁但指定格式
    user_prompt = f"Find Google Scholar profile for researcher: {author_info}. Return ONLY in this JSON format: {{\"profiles\":[{{\"name\":\"\",\"google_scholar_id\":\"\",\"photo\":\"\",\"affiliation\":\"\"}}]}}"

    # 尝试不同的模型
    for retry_count, model in enumerate(models[:max_retries]):
        try:
            from server.llm.gateway import openrouter_chat

            logger.info(f"Attempt {retry_count+1}/{max_retries} using model: {model}")

            # 准备请求数据
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # 记录请求大小
            request_size = len(json.dumps({"model": model, "messages": messages}, ensure_ascii=False))
            logger.info(f"API request size: {request_size} bytes")

            content = openrouter_chat(
                task="name_scholar.lookup",
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=2000,
                extra={"transforms": ["middle-out"]},
            )

            response_text = str(content).strip() if content else ""
            if not response_text:
                logger.error(f"Empty response received from model {model}")
                errors.append(f"Model {model}: Empty response")
                continue
                
            # 记录响应内容长度和预览
            # logger.info(f"API response content length: {len(response_text)} chars")
            # logger.info(f"API response content preview: {response_text}")
                
            output = {"choices": [{"message": {"content": response_text}}]}
            logger.info(f"Successfully got response from model {model}")
            return process_api_response(output, author_info)

        except Exception as e:
            # 处理其他异常
            logger.error(f"Unexpected error with model {model}: {e}")
            errors.append(f"Model {model}: Unexpected error - {str(e)}")
            continue

    # 所有模型都失败了，返回错误信息
    logger.error(f"All {max_retries} attempts failed with different models")
    return {
        'scholar_id': None,
        'photo': None,
        'name': author_info.split(',')[0].strip() if ',' in author_info else author_info,
        'affiliation': author_info.split(',')[1].strip() if ',' in author_info and len(author_info.split(',')) > 1 else None,
        'error': f'All models failed: {" | ".join(errors)}'
    }

def process_api_response(output, author_info):
    """
    Process the API response and extract scholar information.

    Args:
        output: API response JSON
        author_info: Original author info string

    Returns:
        dict: Scholar profile information
    """
    # Import re module at the function level to avoid scope issues
    import re

    try:
        # 检查是否有choices字段
        if 'choices' not in output or not output['choices']:
            logger.error("No 'choices' field in API response")
            return {
                'scholar_id': None,
                'photo': None,
                'name': author_info.split(',')[0].strip() if ',' in author_info else author_info,
                'affiliation': author_info.split(',')[1].strip() if ',' in author_info and len(author_info.split(',')) > 1 else None,
                'error': 'No choices in API response'
            }

        # 提取响应内容
        summary = output['choices'][0]['message']['content'].strip()
        logger.info(f"API response content length: {len(summary)} chars")
        logger.info(f"API response content preview: {summary[:200]}...")

        # 检查是否有效的JSON响应
        if '{' not in summary or '}' not in summary:
            logger.warning("No JSON object found in response")
            # 检查是否有任何可能的结构化信息
            if 'google_scholar_id' in summary or 'scholar_id' in summary or 'profiles' in summary:
                logger.info("Found potential structured information in non-JSON response, attempting extraction")
            else:
                logger.error(f"Response content: {summary[:500]}")
            # 直接尝试使用正则表达式提取信息
            raise json.JSONDecodeError("No JSON object found", summary, 0)

        # 处理可能的Markdown格式的JSON
        # 检查是否包含```json标记
        if '```json' in summary or '```' in summary:
            logger.info("Detected Markdown code block in response")
            # 尝试提取Markdown代码块中的JSON
            json_block_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', summary)
            if json_block_match:
                json_str = json_block_match.group(1)
                logger.info(f"Extracted JSON from Markdown block: {json_str[:100]}...")
            else:
                # 如果没有找到Markdown代码块，尝试常规方法
                json_str = summary[summary.find('{'):summary.rfind('}')+1]
                logger.info(f"Falling back to regular JSON extraction: {json_str[:100]}...")
        else:
            # 常规JSON提取
            json_str = summary[summary.find('{'):summary.rfind('}')+1]
            logger.info(f"Extracted JSON: {json_str[:100]}...")

        # 解析JSON
        try:
            data = json.loads(json_str)
            logger.info("Successfully parsed JSON")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            # 使用 json_repair 修复 JSON
            try:
                logger.info(f"Attempting to repair JSON with json_repair")
                repaired_json = repair_json(json_str)
                logger.info(f"Repaired JSON: {repaired_json[:100]}...")
                data = json.loads(repaired_json)
                logger.info("Successfully parsed repaired JSON")
            except Exception as repair_error:
                logger.error(f"JSON repair failed: {repair_error}")
                # 回退到基本清理方法
                cleaned_json_str = re.sub(r'[\n\r\t]', '', json_str)
                logger.info(f"Falling back to basic cleaning: {cleaned_json_str[:100]}...")
                data = json.loads(cleaned_json_str)

        # 处理未找到简介的情况
        if not data.get('profiles'):
            logger.warning("No profiles found in API response")
            return {
                'scholar_id': None,
                'photo': None,
                'name': author_info.split(',')[0].strip() if ',' in author_info else author_info,
                'affiliation': author_info.split(',')[1].strip() if ',' in author_info and len(author_info.split(',')) > 1 else None,
                'error': 'No profiles found'
            }

        # 按总分排序简介
        profiles = sorted(data['profiles'], key=lambda x: x.get('total_score', 0), reverse=True)

        # 返回最佳匹配
        best_match = profiles[0]
        logger.info(f"Found best match: {best_match.get('name')} with score {best_match.get('total_score')}")
        return {
            'scholar_id': best_match.get('google_scholar_id'),
            'photo': best_match.get('photo'),
            'name': best_match.get('name'),
            'affiliation': best_match.get('affiliation')
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        # 记录完整的响应内容，但限制长度以避免日志过大
        if len(summary) > 1000:
            logger.error(f"Response content (truncated): {summary[:1000]}...")
        else:
            logger.error(f"Response content: {summary}")
            
        # 尝试使用 json_repair 修复整个响应
        try:
            logger.info("Attempting to repair entire response with json_repair")
            # 尝试找到可能的JSON部分
            if '{' in summary and '}' in summary:
                potential_json = summary[summary.find('{'):summary.rfind('}')+1]
                repaired_json = repair_json(potential_json)
                data = json.loads(repaired_json)
                logger.info("Successfully repaired and parsed JSON from entire response")
                
                # 处理修复后的JSON
                if data.get('profiles'):
                    # 按总分排序简介
                    profiles = sorted(data['profiles'], key=lambda x: x.get('total_score', 0), reverse=True)
                    # 返回最佳匹配
                    best_match = profiles[0]
                    logger.info(f"Found best match after repair: {best_match.get('name')}")
                    return {
                        'scholar_id': best_match.get('google_scholar_id'),
                        'photo': best_match.get('photo'),
                        'name': best_match.get('name'),
                        'affiliation': best_match.get('affiliation')
                    }
            logger.warning("Could not find valid JSON structure even after repair attempt")
        except Exception as repair_error:
            logger.error(f"JSON repair for entire response failed: {repair_error}")

        # 尝试从文本中提取关键信息
        try:
            # 尝试提取Google Scholar ID - 支持多种可能的格式
            scholar_id_patterns = [
                r'google_scholar_id["\'::\s]+(\w+)',
                r'scholar_id["\'::\s]+(\w+)',
                r'id["\'::\s]+(\w+)',
                r'https?://scholar\.google\.com/citations\?user=(\w+)',
                r'user[=:]["\']?(\w+)'
            ]
            
            scholar_id = None
            for pattern in scholar_id_patterns:
                scholar_id_match = re.search(pattern, summary)
                if scholar_id_match:
                    scholar_id = scholar_id_match.group(1)
                    logger.info(f"Extracted scholar_id using pattern: {pattern}")
                    break

            # 尝试提取照片URL - 支持多种可能的格式
            photo_patterns = [
                r'photo["\'::\s]+(https?://[^\s"\',\}]+)',
                r'image["\'::\s]+(https?://[^\s"\',\}]+)',
                r'avatar["\'::\s]+(https?://[^\s"\',\}]+)',
                r'(https?://scholar\.googleusercontent\.com/[^\s"\',\}]+)'
            ]
            
            photo = None
            for pattern in photo_patterns:
                photo_match = re.search(pattern, summary)
                if photo_match:
                    photo = photo_match.group(1)
                    break

            # 尝试提取机构
            affiliation_patterns = [
                r'affiliation["\'::\s]+([^"\',\}]+)',
                r'institution["\'::\s]+([^"\',\}]+)',
                r'organization["\'::\s]+([^"\',\}]+)'
            ]
            
            affiliation = None
            for pattern in affiliation_patterns:
                affiliation_match = re.search(pattern, summary)
                if affiliation_match:
                    affiliation = affiliation_match.group(1).strip()
                    break

            # 如果成功提取了scholar_id，返回结果
            if scholar_id:
                logger.info(f"Extracted scholar_id using regex: {scholar_id}")
                return {
                    'scholar_id': scholar_id,
                    'photo': photo,
                    'name': author_info.split(',')[0].strip() if ',' in author_info else author_info,
                    'affiliation': affiliation or (author_info.split(',')[1].strip() if ',' in author_info and len(author_info.split(',')) > 1 else None)
                }
        except Exception as regex_error:
            logger.error(f"Failed to extract information using regex: {regex_error}")

        # 如果正则表达式提取失败，返回错误
        return {
            'scholar_id': None,
            'photo': None,
            'name': author_info.split(',')[0].strip() if ',' in author_info else author_info,
            'affiliation': author_info.split(',')[1].strip() if ',' in author_info and len(author_info.split(',')) > 1 else None,
            'error': 'JSON parse error'
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error processing scholar information: {e}")
        logger.error(f"Error details: {error_trace}")
        return {
            'scholar_id': None,
            'photo': None,
            'name': author_info.split(',')[0].strip() if ',' in author_info else author_info,
            'affiliation': author_info.split(',')[1].strip() if ',' in author_info and len(author_info.split(',')) > 1 else None,
            'error': f'Processing error: {str(e)}'
        }


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 字符串输入示例
    test_cases = [
        "qiang wang, apple ai, computer vision researcher",  # 正常测试用例
        "Timo Aila",  # 之前失败的用例
        "John Smith, MIT"  # 常见名字测试
    ]

    for i, author_info in enumerate(test_cases):
        print(f"\n\n=== Test Case {i+1}: {author_info} ===")
        try:
            result = get_scholar_information(author_info)
            if result:
                if 'error' in result and result['error']:
                    print(f"Error: {result['error']}")
                else:
                    print(f"Found scholar profile: {json.dumps(result, indent=2)}")
            else:
                print("No suitable profile found")
        except Exception as e:
            import traceback
            print(f"Test failed with exception: {e}")
            print(traceback.format_exc())
