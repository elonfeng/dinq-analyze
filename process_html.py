import os
import json
import re
from bs4 import BeautifulSoup

def extract_twitter_personality_data(html_file_path):
    """
    从Twitter Personality HTML文件中提取核心内容
    
    Args:
        html_file_path (str): HTML文件路径
        
    Returns:
        dict: 包含提取内容的字典
    """
    try:
        # 读取HTML文件
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        # 初始化结果字典
        result = {
            'basic_info': {},
            'analysis': {},
            'sections': {}
        }
        
        # 直接使用正则表达式提取JSON数据
        # 查找包含"analysis"的JSON对象
        analysis_pattern = re.compile(r'"analysis"\s*:\s*({.+?}),\s*"followers"', re.DOTALL)
        match = analysis_pattern.search(html_content)
        
        if match:
            # 提取JSON字符串
            json_str = match.group(1)
            
            # 清理JSON字符串，处理转义字符
            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
            
            # 尝试直接提取各个字段，不依赖于JSON解析
            # 提取名称
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', json_str)
            if name_match:
                result['analysis']['name'] = name_match.group(1)
            
            # 提取关于信息
            about_match = re.search(r'"about"\s*:\s*"([^"]+)"', json_str)
            if about_match:
                result['analysis']['about'] = about_match.group(1)
            
            # 提取其他字段
            fields = [
                'money', 'roast', 'animal', 'career', 'emojis', 'health', 
                'loveLife', 'biggestGoal', 'previousLife', 'lifeSuggestion', 
                'fiftyDollarThing', 'colleaguePerspective', 'famousPersonComparison'
            ]
            
            for field in fields:
                # 使用非贪婪匹配和前瞻断言来确保正确提取字段内容
                field_pattern = fr'"{field}"\s*:\s*"(.*?)(?:(?<!\\)"(?:,|\}}|$))'
                field_match = re.search(field_pattern, json_str, re.DOTALL)
                
                if field_match:
                    # 转换驼峰命名为下划线命名
                    field_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', field).lower()
                    # 处理转义的引号和换行符
                    field_value = field_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                    result['analysis'][field_name] = field_value
            
            # 提取优势和劣势数组
            strengths_pattern = r'"strengths"\s*:\s*(\[.+?\])(?=,\s*")'
            strengths_match = re.search(strengths_pattern, json_str, re.DOTALL)
            if strengths_match:
                strengths_json = strengths_match.group(1).replace('\\"', '"')
                try:
                    # 尝试解析JSON数组
                    strengths_list = []
                    # 提取每个优势项
                    strength_items = re.findall(r'{.+?}', strengths_json)
                    for item in strength_items:
                        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', item)
                        subtitle_match = re.search(r'"subtitle"\s*:\s*"([^"]+)"', item)
                        
                        if title_match and subtitle_match:
                            strengths_list.append({
                                "title": title_match.group(1),
                                "subtitle": subtitle_match.group(1)
                            })
                    
                    result['analysis']['strengths'] = strengths_list
                except Exception as e:
                    print(f"解析优势数组时出错: {e}")
            
            weaknesses_pattern = r'"weaknesses"\s*:\s*(\[.+?\])(?=,\s*")'
            weaknesses_match = re.search(weaknesses_pattern, json_str, re.DOTALL)
            if weaknesses_match:
                weaknesses_json = weaknesses_match.group(1).replace('\\"', '"')
                try:
                    # 尝试解析JSON数组
                    weaknesses_list = []
                    # 提取每个劣势项
                    weakness_items = re.findall(r'{.+?}', weaknesses_json)
                    for item in weakness_items:
                        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', item)
                        subtitle_match = re.search(r'"subtitle"\s*:\s*"([^"]+)"', item)
                        
                        if title_match and subtitle_match:
                            weaknesses_list.append({
                                "title": title_match.group(1),
                                "subtitle": subtitle_match.group(1)
                            })
                    
                    result['analysis']['weaknesses'] = weaknesses_list
                except Exception as e:
                    print(f"解析劣势数组时出错: {e}")
            
            # 提取搭讪语数组
            pickup_lines_pattern = r'"pickupLines"\s*:\s*(\[.+?\])(?=,\s*")'
            pickup_lines_match = re.search(pickup_lines_pattern, json_str, re.DOTALL)
            if pickup_lines_match:
                pickup_lines_json = pickup_lines_match.group(1).replace('\\"', '"')
                try:
                    # 提取每个搭讪语
                    pickup_lines = re.findall(r'"([^"]+)"', pickup_lines_json)
                    result['analysis']['pickup_lines'] = pickup_lines
                except Exception as e:
                    print(f"解析搭讪语数组时出错: {e}")
        
        # 创建BeautifulSoup对象
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取基本信息
        # 从标题中提取用户名
        title_element = soup.find('title')
        if title_element:
            title_text = title_element.text.strip()
            name_match = re.search(r'(.*?)\'s Twitter Personality', title_text)
            if name_match:
                result['basic_info']['name'] = name_match.group(1)
        
        # 从meta标签中提取描述
        meta_description = soup.find('meta', attrs={'name': 'description'})
        if meta_description and 'content' in meta_description.attrs:
            result['basic_info']['description'] = meta_description['content']
        
        # 提取Twitter用户名
        # 尝试从URL或其他地方提取
        username_pattern = r'twitter\.wordware\.ai/([^/?]+)'
        username_match = re.search(username_pattern, html_content)
        if username_match:
            result['basic_info']['handle'] = '@' + username_match.group(1)
        
        # 提取头像URL
        img_pattern = r'profile_images/[^"\']+\.jpg'
        img_match = re.search(img_pattern, html_content)
        if img_match:
            result['basic_info']['profile_image'] = 'https://pbs.twimg.com/' + img_match.group(0)
        
        # 提取关注者数量
        followers_pattern = r'"followers"\s*:\s*(\d+)'
        followers_match = re.search(followers_pattern, html_content)
        if followers_match:
            result['basic_info']['followers'] = int(followers_match.group(1))
        
        # 如果分析内容为空，尝试从HTML中提取
        if not result['analysis']:
            # 提取各个部分的内容
            section_headers = soup.find_all(['h2', 'h3'])
            for header in section_headers:
                section_name = header.text.strip()
                if section_name and not section_name.startswith(('This is a', 'Word...', 'WORDWARE', 'WHO IS IT FOR', 'WHY')):
                    section_content = ""
                    
                    # 获取该部分的内容（通常是下一个元素）
                    next_element = header.find_next_sibling()
                    if next_element:
                        # 如果是列表，提取列表项
                        if next_element.name == 'ul':
                            list_items = next_element.find_all('li')
                            section_content = [item.text.strip() for item in list_items]
                        else:
                            section_content = next_element.text.strip()
                    
                    # 转换部分名称为标准格式
                    section_key = section_name.lower().replace(' ', '_')
                    result['sections'][section_key] = section_content
        
        return result
        
    except Exception as e:
        print(f"提取内容时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

# 使用示例
if __name__ == "__main__":
    # 替换为实际的HTML文件路径
    html_file_path = "wordview_twitter.html"
    
    if os.path.exists(html_file_path):
        data = extract_twitter_personality_data(html_file_path)
        
        # 打印提取的数据
        print("基本信息:")
        for key, value in data['basic_info'].items():
            print(f"{key}: {value}")
        
        print("\n分析内容:")
        for key, value in data['analysis'].items():
            if isinstance(value, str) and len(value) > 100:
                print(f"{key}: {value[:100]}...")
            elif isinstance(value, list) and len(value) > 0:
                print(f"{key}: {len(value)} 项")
                # 打印第一项作为示例
                if value:
                    print(f"  示例: {value[0]}")
            else:
                print(f"{key}: {value}")
        
        print("\n各部分内容:")
        for key, value in data['sections'].items():
            if isinstance(value, list):
                print(f"{key}: {len(value)} 项")
            elif isinstance(value, str) and len(value) > 100:
                print(f"{key}: {value[:100]}...")
            else:
                print(f"{key}: {value}")
        
        # 保存为JSON文件
        output_file = "twitter_personality_data.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n数据已保存到: {output_file}")
    else:
        print(f"文件不存在: {html_file_path}")