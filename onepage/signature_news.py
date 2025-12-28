# coding: utf-8

"""
@author: Daiheng Gao
@date: 2025-03-28
@description: find the latest news of a top paper with a given title and author.
"""
import json
import logging
import os
from datetime import datetime

# Import json-repair with fallback
try:
    from json_repair import repair_json
except ImportError:
    # Define a simple fallback function if json-repair is not installed
    def repair_json(json_str, **kwargs):
        logging.warning("json-repair library not available, using fallback")
        return json_str

# 获取日志记录器
logger = logging.getLogger('server.services.scholar.news')


def get_latest_news(paper_info):
    """
    Get the latest news of a top paper with a given title and author.

    Args:
        paper_info (str): Paper title or paper information

    Returns:
        dict: News information including title, date, description, and URL
    """
    logger.info(f"Fetching latest news for paper: {paper_info}")
    
    # Define a unique error prefix for easier identification in logs
    ERROR_PREFIX = "[NEWS_ERROR]" 
    
    # Default fallback result when no news is found
    fallback_result = {
        'news': f"No recent news found for: {paper_info}",
        'date': datetime.now().strftime("%Y-%m-%d"),
        'description': "Our systems could not locate verified news about this paper. This could be because the paper is very recent, highly specialized, or not widely covered in accessible sources.",
        'url': None,
        'is_fallback': True
    }

    paper_content = {
        "role": "user",
        "content": """
        Find the latest news, social media discussions, or academic mentions about this paper with title: {}.

        IMPORTANT:
        - Only return REAL, VERIFIABLE news or mentions
        - The date MUST NOT be later than today's date
        - You MUST return a valid JSON response in ALL cases
        - If you cannot find reliable information, still return the JSON format with appropriate message

        Please return the information in the following JSON format:
        {{
            "news": "title or headline of the news/mention",
            "date": "YYYY-MM-DD format",
            "description": "brief description or summary",
            "url": "direct link to the source"
        }}

        If multiple news items exist, return the most recent and verified one.
        If NO news is found, still return the JSON with "news" field containing "No recent news found" and appropriate description.""".format(paper_info)
    }

    try:
        from server.llm.gateway import openrouter_chat

        logger.debug("Sending request to OpenRouter API")
        summary = openrouter_chat(
            task="signature.news",
            model="perplexity/sonar-pro:online",
            messages=[paper_content],
            temperature=0.2,
            max_tokens=800,
            timeout_seconds=float(os.getenv("DINQ_SIGNATURE_NEWS_TIMEOUT_SECONDS", "12") or "12"),
        )
        summary = str(summary).strip() if summary else ""
        logger.debug(f"Received response: {summary[:100]}...")

        try:
            # Extract potential JSON from response
            json_str = summary
            # If there's a JSON object embedded in text, extract it
            if '{' in summary and '}' in summary:
                json_str = summary[summary.find('{'):summary.rfind('}')+1]
            
            # Use json-repair to fix potential JSON issues
            from json_repair import repair_json
            repaired_json = repair_json(json_str)
            
            if not repaired_json:  # If repair returns empty string (super broken JSON)
                logger.warning(f"{ERROR_PREFIX} JSON repair returned empty string for: {json_str[:100]}...")
                return fallback_result
                
            # Parse the repaired JSON
            news_detail = json.loads(repaired_json)

            result = {
                'news': news_detail.get('news', fallback_result['news']),
                'date': news_detail.get('date', fallback_result['date']),
                'description': news_detail.get('description', fallback_result['description']),
                'url': news_detail.get('url', None),
                'is_fallback': False
            }

            # Check if we got actual news content
            if result['news'] and 'no' not in result['news'].lower() and 'not found' not in result['news'].lower():
                logger.info(f"Found news: {result['news']}")
                logger.info(f"Date: {result['date']}")
                logger.debug(f"Description: {result['description'][:100] if result['description'] else None}...")
                logger.info(f"URL: {result['url']}")
            else:
                logger.warning(f"{ERROR_PREFIX} No substantial news found for paper: {paper_info}")
                # If the model returned a "no news found" message, use our fallback
                if 'no' in result['news'].lower() or 'not found' in result['news'].lower():
                    return fallback_result

            return result
        except json.JSONDecodeError as e:
            logger.error(f"{ERROR_PREFIX} Failed to parse news response: {e}")
            logger.error(f"{ERROR_PREFIX} Original response: {summary[:200]}...")
            return fallback_result
        except ImportError as e:
            logger.error(f"{ERROR_PREFIX} JSON repair library not available: {e}")
            # Fallback to basic JSON parsing if json-repair is not available
            try:
                news_detail = json.loads(json_str)
                result = {
                    'news': news_detail.get('news', fallback_result['news']),
                    'date': news_detail.get('date', fallback_result['date']),
                    'description': news_detail.get('description', fallback_result['description']),
                    'url': news_detail.get('url', None),
                    'is_fallback': False
                }
                return result
            except:
                return fallback_result
        except Exception as e:
            logger.error(f"{ERROR_PREFIX} Error processing news detail: {e}")
            return fallback_result
    except Exception as e:
        logger.error(f"{ERROR_PREFIX} Error fetching news: {e}")
        return fallback_result


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    # 测试获取论文新闻
    paper_title = "Learning transferable architectures for scalable image recognition"
    logger.info(f"Testing get_latest_news with paper: {paper_title}")

    data = get_latest_news(paper_title)

    if data:
        logger.info("News data retrieved successfully:")
        logger.info(f"Title: {data.get('news')}")
        logger.info(f"Date: {data.get('date')}")
        logger.info(f"URL: {data.get('url')}")
    else:
        logger.warning("No news data retrieved")
