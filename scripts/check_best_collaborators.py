#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量检查学者的最佳合作者脚本

这个脚本读取 top_ai_talents.csv 文件中的所有学者ID，
为每个学者获取最佳合作者信息，并检查是否存在学者的最佳合作者是自己的情况。
"""

import os
import sys
import csv
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 配置日志
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'collaborator_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('collaborator_check')

# 导入必要的模块
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.collaborator_service import get_best_collaborator
from server.config.api_keys import API_KEYS

def load_scholars_from_csv(csv_path: str) -> List[Dict[str, str]]:
    """
    从CSV文件加载学者信息
    
    Args:
        csv_path: CSV文件路径
        
    Returns:
        List[Dict[str, str]]: 学者信息列表
    """
    scholars = []
    
    try:
        # 尝试不同的编码
        encodings = ['utf-8', 'latin-1', 'gbk', 'gb2312', 'gb18030', 'big5']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        scholars.append(row)
                
                logger.info(f"成功使用 {encoding} 编码读取CSV文件，共 {len(scholars)} 条记录")
                break
            except UnicodeDecodeError:
                logger.warning(f"使用 {encoding} 编码读取CSV文件失败")
                continue
        
        if not scholars:
            logger.error("无法使用任何编码读取CSV文件")
            return []
            
        return scholars
    except Exception as e:
        logger.error(f"读取CSV文件时出错: {str(e)}")
        return []

def is_same_person(researcher_name: str, collaborator_name: str) -> bool:
    """
    检查研究者和合作者是否是同一个人
    
    Args:
        researcher_name: 研究者姓名
        collaborator_name: 合作者姓名
        
    Returns:
        bool: 是否是同一个人
    """
    # 如果名字完全相同，直接返回True
    if researcher_name.lower() == collaborator_name.lower():
        return True
    
    # 获取研究者姓氏
    researcher_last_name = researcher_name.split()[-1].lower() if researcher_name else ''
    
    # 检查合作者名字是否以研究者姓氏结尾
    if researcher_last_name and collaborator_name.lower().endswith(researcher_last_name):
        # 进一步检查是否是常见的名字变体格式
        name_parts = collaborator_name.split()
        if len(name_parts) >= 2:
            # 检查是否是 "X. LastName" 或 "X LastName" 格式
            first_part = name_parts[0]
            if len(first_part) <= 2 and first_part[0].isalpha():
                return True
    
    return False

def process_scholar(scholar: Dict[str, str], data_fetcher: ScholarDataFetcher) -> Dict[str, Any]:
    """
    处理单个学者，获取其最佳合作者
    
    Args:
        scholar: 学者信息
        data_fetcher: ScholarDataFetcher实例
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    scholar_id = scholar.get('google_scholar', '')
    name = scholar.get('name', '')
    
    if not scholar_id:
        return {
            'name': name,
            'scholar_id': '',
            'error': '缺少学者ID',
            'status': 'error'
        }
    
    try:
        logger.info(f"正在处理学者: {name} (ID: {scholar_id})")
        
        # 搜索学者
        author_info = data_fetcher.search_researcher(scholar_id=scholar_id)
        if not author_info:
            return {
                'name': name,
                'scholar_id': scholar_id,
                'error': '无法找到学者信息',
                'status': 'error'
            }
        
        # 获取完整资料
        author_data = data_fetcher.get_full_profile(author_info)
        if not author_data:
            return {
                'name': name,
                'scholar_id': scholar_id,
                'error': '无法获取学者完整资料',
                'status': 'error'
            }
        
        # 分析合作者
        from server.services.scholar.analyzer import ScholarAnalyzer
        analyzer = ScholarAnalyzer()
        coauthor_stats = analyzer.analyze_coauthors(author_data)
        
        if not coauthor_stats:
            return {
                'name': name,
                'scholar_id': scholar_id,
                'error': '无法分析合作者',
                'status': 'error'
            }
        
        # 获取最佳合作者
        most_frequent_collaborator = get_best_collaborator(data_fetcher, coauthor_stats)
        
        if not most_frequent_collaborator:
            return {
                'name': name,
                'scholar_id': scholar_id,
                'error': '无法获取最佳合作者',
                'status': 'error'
            }
        
        # 检查是否是同一个人
        collaborator_name = most_frequent_collaborator.get('full_name', '')
        is_same = is_same_person(name, collaborator_name)
        
        result = {
            'name': name,
            'scholar_id': scholar_id,
            'collaborator_name': collaborator_name,
            'collaborator_affiliation': most_frequent_collaborator.get('affiliation', ''),
            'coauthored_papers': most_frequent_collaborator.get('coauthored_papers', 0),
            'best_paper': most_frequent_collaborator.get('best_paper', {}),
            'is_same_person': is_same,
            'status': 'success'
        }
        
        logger.info(f"学者 {name} 的最佳合作者是 {collaborator_name}" + (" (可能是同一人)" if is_same else ""))
        return result
    
    except Exception as e:
        logger.error(f"处理学者 {name} (ID: {scholar_id}) 时出错: {str(e)}")
        return {
            'name': name,
            'scholar_id': scholar_id,
            'error': str(e),
            'status': 'error'
        }

def main():
    """主函数"""
    # 获取CSV文件路径
    csv_path = os.path.join(project_root, 'top_ai_talents.csv')
    
    # 检查文件是否存在
    if not os.path.exists(csv_path):
        logger.error(f"CSV文件不存在: {csv_path}")
        return
    
    # 加载学者信息
    scholars = load_scholars_from_csv(csv_path)
    if not scholars:
        logger.error("未能加载任何学者信息")
        return
    
    logger.info(f"共加载 {len(scholars)} 名学者")
    
    # 创建数据获取器
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN', '')
    data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
    
    # 处理结果
    results = []
    same_person_count = 0
    error_count = 0
    
    # 处理每个学者
    for i, scholar in enumerate(scholars):
        logger.info(f"处理进度: {i+1}/{len(scholars)}")
        
        result = process_scholar(scholar, data_fetcher)
        results.append(result)
        
        if result.get('status') == 'error':
            error_count += 1
        elif result.get('is_same_person', False):
            same_person_count += 1
        
        # 每处理10个学者保存一次结果
        if (i + 1) % 10 == 0 or i == len(scholars) - 1:
            # 保存结果
            output_path = os.path.join(project_root, 'collaborator_results.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存处理结果到: {output_path}")
        
        # 避免请求过于频繁
        time.sleep(2)
    
    # 统计结果
    logger.info(f"处理完成! 共处理 {len(scholars)} 名学者")
    logger.info(f"其中 {same_person_count} 名学者的最佳合作者可能是自己 ({same_person_count/len(scholars):.2%})")
    logger.info(f"处理失败: {error_count} 名学者 ({error_count/len(scholars):.2%})")
    
    # 保存最终结果
    output_path = os.path.join(project_root, 'collaborator_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"已保存最终处理结果到: {output_path}")
    
    # 生成报告
    generate_report(results, os.path.join(project_root, 'collaborator_report.md'))

def generate_report(results: List[Dict[str, Any]], output_path: str):
    """
    生成报告
    
    Args:
        results: 处理结果
        output_path: 输出文件路径
    """
    total = len(results)
    success = sum(1 for r in results if r.get('status') == 'success')
    error = total - success
    same_person = sum(1 for r in results if r.get('is_same_person', False))
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 学者最佳合作者分析报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 统计摘要\n\n")
        f.write(f"- 总学者数: {total}\n")
        f.write(f"- 成功处理: {success} ({success/total:.2%})\n")
        f.write(f"- 处理失败: {error} ({error/total:.2%})\n")
        f.write(f"- 最佳合作者可能是自己: {same_person} ({same_person/total:.2%})\n\n")
        
        f.write("## 最佳合作者是自己的学者\n\n")
        f.write("| 学者姓名 | 学者ID | 最佳合作者姓名 | 合作论文数 | 最佳合作论文 |\n")
        f.write("|---------|-------|--------------|-----------|------------|\n")
        
        for result in results:
            if result.get('is_same_person', False):
                name = result.get('name', '')
                scholar_id = result.get('scholar_id', '')
                collaborator_name = result.get('collaborator_name', '')
                coauthored_papers = result.get('coauthored_papers', 0)
                best_paper = result.get('best_paper', {}).get('title', '')
                
                f.write(f"| {name} | {scholar_id} | {collaborator_name} | {coauthored_papers} | {best_paper} |\n")
        
        f.write("\n## 处理失败的学者\n\n")
        f.write("| 学者姓名 | 学者ID | 错误信息 |\n")
        f.write("|---------|-------|----------|\n")
        
        for result in results:
            if result.get('status') == 'error':
                name = result.get('name', '')
                scholar_id = result.get('scholar_id', '')
                error = result.get('error', '')
                
                f.write(f"| {name} | {scholar_id} | {error} |\n")
    
    logger.info(f"已生成报告: {output_path}")

if __name__ == "__main__":
    main()
