import json
from server.llm.gateway import openrouter_chat

def extract_json_from_text(text):
    """提取文本中第一个{和最后一个}之间的内容，包含{}"""
    start = text.find('{')
    end = text.rfind('}')
    
    if start != -1 and end != -1 and start < end:
        return text[start:end+1]
    return None

def enhance_talent_info_with_websearch(person_name, from_company, to_company, salary, tweet_text, linkedin_data=None):
    """使用AI websearch补充人才流动的详细信息"""
    
    # 构建LinkedIn信息字符串
    linkedin_info = ""
    if linkedin_data:
        # 提取LinkedIn关键信息
        experiences = linkedin_data.get('experiences', [])
        educations = linkedin_data.get('educations', [])
        about = linkedin_data.get('about', '')
        
        # 构建工作经历字符串
        work_experience_str = ""
        for exp in experiences[:5]:  # 只取最近5个工作经历
            title = exp.get('title', '')
            company = exp.get('subtitle', '').split('·')[0].strip() if exp.get('subtitle') else ''
            duration = exp.get('caption', '')
            work_experience_str += f"- {title} at {company} ({duration})\n"
        
        # 构建教育经历字符串
        education_str = ""
        for edu in educations:
            school = edu.get('title', '')
            degree = edu.get('subtitle', '')
            education_str += f"- {degree} from {school}\n"
        
        linkedin_info = f"""
LinkedIn Profile:
- About: {about}...
- Work Experience:
{work_experience_str}
- Education:
{education_str}
"""
    
    request_data = {
        "model": "perplexity/sonar-reasoning-pro:online",
        "messages": [
            {
                "role": "user",
                "content": f"""Based on the following information about a talent move and LinkedIn profile, please provide a comprehensive description including salary details, career background, and the significance of this move. Return in JSON format:

{{
    "person_name": "{person_name}",
    "from_company": "{from_company}",
    "to_company": "{to_company}",
    "salary": "{salary}",
    "tweet_text": "{tweet_text}"
}}

{linkedin_info}

Please search for additional information and provide a detailed description in this format:
{{
    "salary": "salary if found",
    "person_name": "person_name",
    "from_company": "from_company",
    "to_company": "to_company",
    "avatar_url": "avatar url of the person (or '' if uncertain)",
    "talent_description": "A comprehensive description (max 30 words) ",
    "age": 35,
    "work_experience": "[{{\"from\": \"2021\", \"to\": \"2024\", \"company\": \"Apple\", \"position\": \"Head of Foundation Models\"}}, {{\"from\": \"2006\", \"to\": \"2021\", \"company\": \"Google\", \"position\": \"Senior Research Scientist\"}}]",
    "education": "[{{\"school\": \"Stanford University\", \"major\": \"Computer Science\", \"time\": \"2002-2006\"}}, {{\"school\": \"MIT\", \"major\": \"Artificial Intelligence\", \"time\": \"2006-2010\"}}]",
    "major_achievement": "[{{\"title\": \"Led Apple's Foundation Models Team\", \"description\": \"Managed a team of 100 engineers developing large language models for Apple Intelligence\"}}, {{\"title\": \"Google Research Breakthrough\", \"description\": \"Published 50+ papers on AI and deep learning with 10,000+ citations\"}}]"
}}

Important notes:
1. age: Return as integer, estimate based on available information (especially LinkedIn work experience)
2. work_experience: JSON array with objects containing "from", "to", "company", "position" fields
3. education: JSON array with objects containing "school", "major", "time" fields  
4. major_achievement: JSON array with objects containing "title", "description" fields
5. talent_description: MUST be limited to maximum 100 words
6. If LinkedIn data is available, use it as the primary source for work experience and education
7. If information is not found, make reasonable estimates based on typical career patterns
8. All JSON arrays should be returned as strings, not actual JSON objects

Search for the latest information about this talent move and provide comprehensive details. Return ONLY the JSON string, no other text."""
            }
        ],
        "temperature": 0.3,
        "max_tokens": 4096
    }
    
    try:
        print(f"正在使用websearch补充信息: {person_name} 从 {from_company} 到 {to_company}")
        summary = openrouter_chat(
            task="talent.websearch",
            model=request_data["model"],
            messages=request_data["messages"],
            temperature=request_data["temperature"],
            max_tokens=request_data["max_tokens"],
            cache=False,
        )
        summary = str(summary).strip() if summary else ""
        
        
        try:
            # 提取JSON内容
            json_content = extract_json_from_text(summary)
            
            if json_content:
                result = json.loads(json_content)
            else:
                print(f"未找到有效的JSON内容:{summary}")
                result = json.loads(summary)
            
            return {
                "salary": result.get('salary', salary),
                "talent_description": result.get('talent_description', f"{person_name} moved from {from_company} to {to_company}. {tweet_text}"),
                "age": result.get('age', 30),
                "work_experience": result.get('work_experience', "[{\"from\": \"2020\", \"to\": \"2024\", \"company\": \"" + from_company + "\", \"position\": \"Senior Position\"}]"),
                "education": result.get('education', "[{\"school\": \"Top University\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]"),
                "major_achievement": result.get('major_achievement', "[{\"title\": \"Career Move\", \"description\": \"" + person_name + " moved from " + from_company + " to " + to_company + "\"}]")
            }
        except json.JSONDecodeError as e:
            print(f"Websearch JSON解析失败: {e}")
            return {
                "salary": salary,
                "talent_description": f"{person_name} moved from {from_company} to {to_company}. {tweet_text}",
                "age": 30,
                "work_experience": "[{\"from\": \"2020\", \"to\": \"2024\", \"company\": \"" + from_company + "\", \"position\": \"Senior Position\"}]",
                "education": "[{\"school\": \"Top University\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]",
                "major_achievement": "[{\"title\": \"Career Move\", \"description\": \"" + person_name + " moved from " + from_company + " to " + to_company + "\"}]"
            }
            
    except Exception as e:
        print(f"Websearch补充信息失败: {e}")
        return {
            "salary": salary,
            "talent_description": f"{person_name} moved from {from_company} to {to_company}. {tweet_text}",
            "age": 30,
            "work_experience": "[{\"from\": \"2020\", \"to\": \"2024\", \"company\": \"" + from_company + "\", \"position\": \"Senior Position\"}]",
            "education": "[{\"school\": \"Top University\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]",
            "major_achievement": "[{\"title\": \"Career Move\", \"description\": \"" + person_name + " moved from " + from_company + " to " + to_company + "\"}]"
        }

def analyze_tweet_with_ai(text,image_url):
    # 简化请求，移除可能导致问题的参数
    request_data = {
        "model": "openai/gpt-4o-mini",
        "messages": [
    {
        "role": "user", 
        "content": [
            {
                "type": "text",
                "text": f"""Analyze tweet content to determine if it contains information about AI talent transfers, job changes, or poaching.
                If such information is present and explicitly mentions talent names, 
                then identify information in the image to supplement the details and return JSON format:
{{
    "is_talent_move": true,
    "person_names": "Names of the persons - if single person use just the name, if multiple persons use comma separated names like 'Ruoming Pang, John Doe, Jane Smith'",
    "from_company": "Company the person is moving from (or '' if uncertain)",
    "to_company": "Company the person is moving to (or '' if uncertain)",
    "salary": "Salary information (or '' if uncertain)"
}}

If it's not related to talent movement, return:
{{
    "is_talent_move": false
}}

Tweet content: {text}"""
            }
        ] + ([{
            "type": "image_url",
            "image_url": {
                "url": image_url,
                "detail": "high"
            }
        }] if image_url else [])
    }
],
        "temperature": 0.3,
        "max_tokens": 600
    }
    
    try:
        summary = openrouter_chat(
            task="talent.tweet",
            model=request_data["model"],
            messages=request_data["messages"],
            temperature=request_data["temperature"],
            max_tokens=request_data["max_tokens"],
        )
        summary = str(summary).strip() if summary else ""
        
        try:
            print(f"AI分析结果: {summary}")
            summary_result=extract_json_from_text(summary)
            result = json.loads(summary_result)
            
            return result
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            # 尝试简单关键词匹配作为备用
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in ['join', 'joined', 'moved', 'transfer', 'hired', 'recruit']):
                return {"is_talent_move": True, "person_name": "未知", "from_company": "未知", "to_company": "未知"}
            return {"is_talent_move": False, "error": "JSON解析失败"}
            
    except Exception as e:
        print(f"AI分析失败: {e}")
        return {"is_talent_move": False, "error": f"未知错误: {e}"} 
