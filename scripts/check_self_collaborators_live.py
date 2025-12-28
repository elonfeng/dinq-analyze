#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时检查最佳合作者是自己的学者

这个脚本直接使用 ScholarAnalyzer 和 ScholarDataFetcher 来检查指定的学者列表，
找出最佳合作者是自己的学者，并以易于复制的格式列出他们的名称、学者ID和合作者名称。
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List, Optional

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('check_self_collaborators')

# 导入必要的模块
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.analyzer import ScholarAnalyzer
from server.config.api_keys import API_KEYS

def check_scholar(scholar_id: str, name: str, data_fetcher: ScholarDataFetcher, name_matcher: ScholarAnalyzer) -> Dict[str, Any]:
    """
    检查学者的最佳合作者是否是自己
    
    Args:
        scholar_id: 学者ID
        name: 学者姓名
        data_fetcher: ScholarDataFetcher实例
        name_matcher: ScholarAnalyzer实例
        
    Returns:
        Dict[str, Any]: 检查结果
    """
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
        coauthor_stats = name_matcher.analyze_coauthors(author_data)
        
        if not coauthor_stats:
            return {
                'name': name,
                'scholar_id': scholar_id,
                'error': '无法分析合作者',
                'status': 'error'
            }
        
        # 获取最佳合作者
        most_frequent = coauthor_stats.get('most_frequent_collaborator', {})
        if not most_frequent:
            return {
                'name': name,
                'scholar_id': scholar_id,
                'error': '无法获取最佳合作者',
                'status': 'error'
            }
        
        # 检查是否是同一个人
        collaborator_name = most_frequent.get('name', '')
        is_same = name_matcher.is_same_person(name, collaborator_name)
        
        result = {
            'name': name,
            'scholar_id': scholar_id,
            'collaborator_name': collaborator_name,
            'coauthored_papers': most_frequent.get('coauthored_papers', 0),
            'best_paper': most_frequent.get('best_paper', {}),
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
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python check_self_collaborators_live.py <学者ID1> [<学者ID2> ...]")
        print("或者: python check_self_collaborators_live.py --file <学者ID文件>")
        return
    
    # 创建数据获取器和名字匹配器
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN', '')
    data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
    name_matcher = ScholarAnalyzer()
    
    # 获取学者ID列表
    scholar_ids = []
    if sys.argv[1] == '--file':
        if len(sys.argv) < 3:
            print("请指定学者ID文件")
            return
        
        file_path = sys.argv[2]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            name = parts[0]
                            scholar_id = parts[1]
                            scholar_ids.append((scholar_id, name))
                        else:
                            scholar_ids.append((line, ''))
        except Exception as e:
            print(f"读取文件时出错: {str(e)}")
            return
    else:
        for scholar_id in sys.argv[1:]:
            scholar_ids.append((scholar_id, ''))
    
    if not scholar_ids:
        print("未找到任何学者ID")
        return
    
    # 处理每个学者
    results = []
    self_collaborators = []
    
    for scholar_id, name in scholar_ids:
        # 如果没有提供名字，尝试获取
        if not name:
            try:
                author_info = data_fetcher.search_researcher(scholar_id=scholar_id)
                if author_info:
                    name = author_info.get('name', scholar_id)
            except:
                name = scholar_id
        
        # 检查学者
        result = check_scholar(scholar_id, name, data_fetcher, name_matcher)
        results.append(result)
        
        # 如果最佳合作者是自己，添加到列表
        if result.get('is_same_person', False):
            self_collaborators.append(result)
        
        # 避免请求过于频繁
        time.sleep(2)
    
    # 打印结果
    print("\n最佳合作者是自己的学者:")
    print("=" * 80)
    print("学者姓名\t学者ID\t合作者姓名\t合作论文数")
    print("-" * 80)
    
    for item in self_collaborators:
        name = item.get('name', '')
        scholar_id = item.get('scholar_id', '')
        collaborator_name = item.get('collaborator_name', '')
        coauthored_papers = item.get('coauthored_papers', 0)
        
        print(f"{name}\t{scholar_id}\t{collaborator_name}\t{coauthored_papers}")
    
    print("-" * 80)
    print(f"共找到 {len(self_collaborators)} 个最佳合作者是自己的学者")
    
    # 保存结果
    output_file = 'self_collaborators_live.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("学者姓名\t学者ID\t合作者姓名\t合作论文数\n")
        for item in self_collaborators:
            name = item.get('name', '')
            scholar_id = item.get('scholar_id', '')
            collaborator_name = item.get('collaborator_name', '')
            coauthored_papers = item.get('coauthored_papers', 0)
            
            f.write(f"{name}\t{scholar_id}\t{collaborator_name}\t{coauthored_papers}\n")
    
    print(f"已将结果保存到文件: {output_file}")

if __name__ == "__main__":
    main()
