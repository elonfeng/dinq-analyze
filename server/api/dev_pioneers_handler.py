"""
开发先驱数据处理器

这个模块提供从CSV文件中检索开发先驱数据的功能。
"""

import os
import csv
import random
from typing import List, Dict, Any, Optional

def get_csv_path() -> str:
    """
    获取dev_pioneers.csv文件的路径。

    Returns:
        str: CSV文件的绝对路径
    """
    # 获取当前文件的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 构建CSV文件路径
    csv_path = os.path.join(current_dir, '..', 'github_analyzer', 'dev_pioneers.csv')
    
    # 返回规范化的绝对路径
    return os.path.abspath(csv_path)

def read_pioneers_from_csv() -> List[Dict[str, str]]:
    """
    从CSV文件中读取所有开发先驱数据。

    Returns:
        List[Dict[str, str]]: 开发先驱数据列表
    """
    csv_path = get_csv_path()

    # 检查文件是否存在
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    # 尝试不同的编码
    encodings = ['utf-8', 'latin-1', 'gbk', 'gb2312', 'gb18030', 'big5']

    for encoding in encodings:
        try:
            # 读取CSV文件
            pioneers = []
            with open(csv_path, 'r', encoding=encoding) as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 跳过空行
                    if not any(row.values()):
                        continue
                    pioneers.append(row)

            print(f"Successfully read CSV with encoding: {encoding}")
            return pioneers
        except UnicodeDecodeError:
            print(f"Failed to read CSV with encoding: {encoding}")
            continue

    # 如果所有编码都失败，抛出异常
    raise UnicodeDecodeError("csv", b"", 0, 1, "Failed to decode CSV file with any encoding")

def process_pioneer_data(pioneer: Dict[str, str]) -> Dict[str, str]:
    """
    处理单个开发先驱数据，清理和标准化字段。

    Args:
        pioneer (Dict[str, str]): 原始开发先驱数据

    Returns:
        Dict[str, str]: 处理后的开发先驱数据
    """
    # 复制数据以避免修改原始数据
    processed_pioneer = pioneer.copy()

    # 清理字段中的多余空格和换行符
    for key, value in processed_pioneer.items():
        if isinstance(value, str):
            processed_pioneer[key] = value.strip().replace('\n', ' ').replace('\r', '')

    # 处理GitHub链接，确保格式正确
    if 'github' in processed_pioneer and processed_pioneer['github']:
        github_url = processed_pioneer['github']
        if not github_url.startswith('http'):
            processed_pioneer['github'] = f"https://github.com/{github_url.lstrip('/')}"

    # 处理个人页面链接
    if 'personal_page' in processed_pioneer and processed_pioneer['personal_page']:
        personal_page = processed_pioneer['personal_page']
        if personal_page and not personal_page.startswith('http'):
            processed_pioneer['personal_page'] = f"https://{personal_page}"

    # 处理Twitter链接
    if 'twitter' in processed_pioneer and processed_pioneer['twitter']:
        twitter_url = processed_pioneer['twitter']
        if twitter_url and not twitter_url.startswith('http'):
            processed_pioneer['twitter'] = f"https://twitter.com/{twitter_url.lstrip('@/')}"

    # 处理LinkedIn链接
    if 'linkedin' in processed_pioneer and processed_pioneer['linkedin']:
        linkedin_url = processed_pioneer['linkedin']
        if linkedin_url and not linkedin_url.startswith('http'):
            processed_pioneer['linkedin'] = f"https://linkedin.com/in/{linkedin_url.lstrip('/')}"

    # 处理著名作品链接
    if 'link' in processed_pioneer and processed_pioneer['link']:
        link_url = processed_pioneer['link']
        if link_url and not link_url.startswith('http'):
            processed_pioneer['link'] = f"https://github.com/{link_url.lstrip('/')}"

    # 添加一些计算字段
    processed_pioneer['has_github'] = bool(processed_pioneer.get('github', '').strip())
    processed_pioneer['has_personal_page'] = bool(processed_pioneer.get('personal_page', '').strip())
    processed_pioneer['has_twitter'] = bool(processed_pioneer.get('twitter', '').strip())
    processed_pioneer['has_linkedin'] = bool(processed_pioneer.get('linkedin', '').strip())
    processed_pioneer['has_image'] = bool(processed_pioneer.get('image', '').strip())

    return processed_pioneer

def filter_pioneers(pioneers: List[Dict[str, str]], area_filter: str = '', company_filter: str = '') -> List[Dict[str, str]]:
    """
    根据技术领域和公司过滤开发先驱数据。

    Args:
        pioneers (List[Dict[str, str]]): 开发先驱数据列表
        area_filter (str): 技术领域过滤器
        company_filter (str): 公司过滤器

    Returns:
        List[Dict[str, str]]: 过滤后的开发先驱数据列表
    """
    filtered_pioneers = pioneers

    # 按技术领域过滤
    if area_filter:
        area_filter_lower = area_filter.lower()
        filtered_pioneers = [
            pioneer for pioneer in filtered_pioneers
            if area_filter_lower in pioneer.get('area', '').lower()
        ]

    # 按公司过滤
    if company_filter:
        company_filter_lower = company_filter.lower()
        filtered_pioneers = [
            pioneer for pioneer in filtered_pioneers
            if company_filter_lower in pioneer.get('Company', '').lower()
        ]

    return filtered_pioneers

def get_random_pioneers(pioneers: List[Dict[str, str]], count: int) -> List[Dict[str, str]]:
    """
    从开发先驱列表中随机选择指定数量的数据。

    Args:
        pioneers (List[Dict[str, str]]): 开发先驱数据列表
        count (int): 要选择的数量

    Returns:
        List[Dict[str, str]]: 随机选择的开发先驱数据列表
    """
    if len(pioneers) <= count:
        return pioneers
    else:
        return random.sample(pioneers, count)

def get_top_pioneers(pioneers: List[Dict[str, str]], count: int) -> List[Dict[str, str]]:
    """
    获取前N个开发先驱数据（按CSV文件中的顺序）。

    Args:
        pioneers (List[Dict[str, str]]): 开发先驱数据列表
        count (int): 要返回的数量

    Returns:
        List[Dict[str, str]]: 前N个开发先驱数据列表
    """
    return pioneers[:count]

def get_available_areas(pioneers: List[Dict[str, str]]) -> List[str]:
    """
    获取所有可用的技术领域列表。

    Args:
        pioneers (List[Dict[str, str]]): 开发先驱数据列表

    Returns:
        List[str]: 技术领域列表
    """
    areas = set()
    for pioneer in pioneers:
        area = pioneer.get('area', '').strip()
        if area:
            # 分割多个技术领域（用逗号分隔）
            for single_area in area.split(','):
                areas.add(single_area.strip())
    
    return sorted(list(areas))

def get_available_companies(pioneers: List[Dict[str, str]]) -> List[str]:
    """
    获取所有可用的公司列表。

    Args:
        pioneers (List[Dict[str, str]]): 开发先驱数据列表

    Returns:
        List[str]: 公司列表
    """
    companies = set()
    for pioneer in pioneers:
        company = pioneer.get('Company', '').strip()
        if company and company.lower() not in ['unknown', 'retired', 'pass away', 'self-employed']:
            companies.add(company)
    
    return sorted(list(companies))

def get_dev_pioneers_data(
    count: int = 10,
    random_selection: bool = False,
    area_filter: str = '',
    company_filter: str = ''
) -> Dict[str, Any]:
    """
    获取开发先驱数据的主函数。

    Args:
        count (int): 返回的数量 (默认: 10)
        random_selection (bool): 是否随机选择 (默认: False)
        area_filter (str): 技术领域过滤器 (可选)
        company_filter (str): 公司过滤器 (可选)

    Returns:
        Dict[str, Any]: API响应数据
    """
    try:
        # 读取所有开发先驱数据
        all_pioneers = read_pioneers_from_csv()

        # 处理数据
        processed_pioneers = [process_pioneer_data(pioneer) for pioneer in all_pioneers]

        # 应用过滤器
        filtered_pioneers = filter_pioneers(processed_pioneers, area_filter, company_filter)

        # 选择数据
        if random_selection:
            selected_pioneers = get_random_pioneers(filtered_pioneers, count)
        else:
            selected_pioneers = get_top_pioneers(filtered_pioneers, count)

        # 获取统计信息
        available_areas = get_available_areas(processed_pioneers)
        available_companies = get_available_companies(processed_pioneers)

        # 准备响应
        response = {
            "success": True,
            "count": len(selected_pioneers),
            "total_available": len(filtered_pioneers),
            "total_in_database": len(processed_pioneers),
            "pioneers": selected_pioneers,
            "filters_applied": {
                "area": area_filter if area_filter else None,
                "company": company_filter if company_filter else None,
                "random_selection": random_selection
            },
            "metadata": {
                "available_areas": available_areas,
                "available_companies": available_companies,
                "csv_file_path": get_csv_path()
            }
        }

        return response

    except Exception as e:
        # 返回错误响应
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to retrieve dev pioneers data"
        }
