import json
import time
from server.llm.gateway import openrouter_chat


def get_author_list(paper_name):
    content = openrouter_chat(
        task="author.list",
        model="perplexity/sonar-pro:online",
        messages=[
            {
                "role": "user",
                "content": "Please provide full author list of paper: {}, only output author name".format(paper_name),
            }
        ],
        temperature=0.2,
        max_tokens=400,
    )
    author_lst = str(content).split("\n")[-1] if content else ""

    return author_lst

def get_author_detail(info):
    import logging
    logger = logging.getLogger(__name__)
    try:
        content = openrouter_chat(
            task="author.detail",
            model="perplexity/sonar-reasoning-pro:online",
            messages=[
                {
                    "role": "user",
                    "content": f"""Please provide the photo, graduate_school, company, and one sentence description according to this AI researcher info: {info}

Return your response as a JSON object with exactly this structure:
{{
    "name": "value or 'Unknown'",
    "photo": "value or null",
    "graduate_school": "value or 'Unknown'",
    "company": "value or 'Unknown'",
    "description": "value or empty string",
    "affiliation": "value or 'Unknown'"
}}

Return only the JSON object, no additional text."""
                }
            ],
            temperature=0.2,
            max_tokens=800,
        )
        summary = str(content) if content else ""
        logger.debug(f"Received response: {summary[:100]}...")
        
        try:
            # 从返回的文本中提取JSON部分
            json_str = summary[summary.find('{'):summary.rfind('}')+1]
            
            # # 使用json_repair修复JSON
            # repaired_json = repair_json(json_str)
            # logger.debug(f"Repaired JSON: {repaired_json[:100]}...")
            #
            # # 解析修复后的JSON
            author_detail = json.loads(json_str)
            logger.info("Successfully parsed author detail")
            
            # 构建返回字典
            return author_detail
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse author detail response even after repair: {e}")
            logger.debug(f"Problematic JSON: {json_str}")
            return {
                'name': 'Unknown',
                'photo': None,
                'graduate_school': 'Unknown',
                'company': 'Unknown',
                'description': '',
                'affiliation': 'Unknown'
            }
        except Exception as e:
            logger.error(f"Error processing author detail: {e}", exc_info=True)
            return {
                'name': 'Unknown',
                'photo': None,
                'graduate_school': 'Unknown',
                'company': 'Unknown',
                'description': '',
                'affiliation': 'Unknown'
            }
    except Exception as e:
        logger.error(f"Error calling OpenRouter API: {e}", exc_info=True)
        return {
            'name': 'Unknown',
            'photo': None,
            'graduate_school': 'Unknown',
            'company': 'Unknown',
            'description': '',
            'affiliation': 'Unknown'
        }

if __name__ == "__main__":
    t1 = time.time()
    # print(get_author_list("Imagenet classification with deep convolutional neural networks"))
    print(get_author_detail("{'name': 'Bang Zhang', 'coauthored_papers': 9, 'best_paper': {'title': 'Multi-view consistent generative adversarial networks for 3d-aware image synthesis', 'year': '2022', 'venue': 'Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern\xa0…, 2022', 'citations': 54}}"))
    t2 = time.time()
    print("Time taken: ", t2 - t1)
