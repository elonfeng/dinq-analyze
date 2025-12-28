#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复学者最佳合作者是自己的问题

这个脚本提供了一个改进的方法来检测和修复学者的最佳合作者是自己的问题。
"""

import os
import sys
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

logger = logging.getLogger('fix_collaborator')

def is_same_person_improved(researcher_name: str, collaborator_name: str) -> bool:
    """
    改进的方法来检查研究者和合作者是否是同一个人
    
    Args:
        researcher_name: 研究者姓名
        collaborator_name: 合作者姓名
        
    Returns:
        bool: 是否是同一个人
    """
    # 如果名字完全相同，直接返回True
    if researcher_name.lower() == collaborator_name.lower():
        return True
    
    # 获取研究者姓氏和名字部分
    researcher_parts = researcher_name.split()
    researcher_last_name = researcher_parts[-1].lower() if researcher_parts else ''
    researcher_first_parts = [p.lower() for p in researcher_parts[:-1]] if len(researcher_parts) > 1 else []
    
    # 获取合作者姓氏和名字部分
    collaborator_parts = collaborator_name.split()
    collaborator_last_name = collaborator_parts[-1].lower() if collaborator_parts else ''
    collaborator_first_parts = [p.lower() for p in collaborator_parts[:-1]] if len(collaborator_parts) > 1 else []
    
    # 检查姓氏是否相同
    if researcher_last_name == collaborator_last_name:
        # 如果姓氏相同，检查名字部分
        
        # 情况1: 一方的名字是另一方名字的缩写
        # 例如: "John Smith" 和 "J. Smith"
        if researcher_first_parts and collaborator_first_parts:
            for r_part in researcher_first_parts:
                for c_part in collaborator_first_parts:
                    # 检查缩写情况
                    if (len(r_part) == 1 or r_part.endswith('.')) and c_part.startswith(r_part[0]):
                        return True
                    if (len(c_part) == 1 or c_part.endswith('.')) and r_part.startswith(c_part[0]):
                        return True
        
        # 情况2: 名字部分完全匹配
        if researcher_first_parts == collaborator_first_parts:
            return True
        
        # 情况3: 一方只有姓氏，另一方有完整名字
        if (not researcher_first_parts and collaborator_first_parts) or (researcher_first_parts and not collaborator_first_parts):
            return True
    
    # 检查名字的其他变体
    # 例如: "Geoffrey E. Hinton" 和 "Geoffrey Hinton"
    if researcher_first_parts and collaborator_first_parts:
        # 检查第一个名字部分是否相同
        if researcher_first_parts[0] == collaborator_first_parts[0]:
            # 如果第一个名字部分相同，并且姓氏相同
            if researcher_last_name == collaborator_last_name:
                return True
    
    return False

def fix_analyzer_coauthors_method():
    """
    提供修复 ScholarAnalyzer.analyze_coauthors 方法的代码
    """
    print("\n以下是修复 ScholarAnalyzer.analyze_coauthors 方法的代码片段：\n")
    
    code = """
    # 在 ScholarAnalyzer.analyze_coauthors 方法中，
    # 将以下代码段：
    
    # 确保最佳合作者不是作者自己
    for coauthor_info in top_coauthors:
        coauthor_name = coauthor_info['name']
        # 检查是否是作者自己的变体
        if coauthor_name not in exclude_names and not any(coauthor_name.lower().endswith(main_author_last.lower()) for main_author_last in [main_author_last] if main_author_last):
            most_frequent = coauthor_info
            logger.info(f"Most frequent collaborator: {most_frequent['name']} with {most_frequent['coauthored_papers']} papers")
            logger.info(f"Best paper with most frequent collaborator: '{most_frequent['best_paper'].get('title', '')}' in {most_frequent['best_paper'].get('venue', '')}")
            break
    
    # 替换为：
    
    # 确保最佳合作者不是作者自己
    for coauthor_info in top_coauthors:
        coauthor_name = coauthor_info['name']
        # 使用改进的方法检查是否是作者自己
        if not is_same_person_improved(main_author_full, coauthor_name):
            most_frequent = coauthor_info
            logger.info(f"Most frequent collaborator: {most_frequent['name']} with {most_frequent['coauthored_papers']} papers")
            logger.info(f"Best paper with most frequent collaborator: '{most_frequent['best_paper'].get('title', '')}' in {most_frequent['best_paper'].get('venue', '')}")
            break
    """
    
    print(code)
    
    print("\n然后，在 ScholarAnalyzer 类中添加以下方法：\n")
    
    is_same_person_code = """
    def is_same_person_improved(self, researcher_name: str, collaborator_name: str) -> bool:
        \"\"\"
        改进的方法来检查研究者和合作者是否是同一个人
        
        Args:
            researcher_name: 研究者姓名
            collaborator_name: 合作者姓名
            
        Returns:
            bool: 是否是同一个人
        \"\"\"
        # 如果名字完全相同，直接返回True
        if researcher_name.lower() == collaborator_name.lower():
            return True
        
        # 获取研究者姓氏和名字部分
        researcher_parts = researcher_name.split()
        researcher_last_name = researcher_parts[-1].lower() if researcher_parts else ''
        researcher_first_parts = [p.lower() for p in researcher_parts[:-1]] if len(researcher_parts) > 1 else []
        
        # 获取合作者姓氏和名字部分
        collaborator_parts = collaborator_name.split()
        collaborator_last_name = collaborator_parts[-1].lower() if collaborator_parts else ''
        collaborator_first_parts = [p.lower() for p in collaborator_parts[:-1]] if len(collaborator_parts) > 1 else []
        
        # 检查姓氏是否相同
        if researcher_last_name == collaborator_last_name:
            # 如果姓氏相同，检查名字部分
            
            # 情况1: 一方的名字是另一方名字的缩写
            # 例如: "John Smith" 和 "J. Smith"
            if researcher_first_parts and collaborator_first_parts:
                for r_part in researcher_first_parts:
                    for c_part in collaborator_first_parts:
                        # 检查缩写情况
                        if (len(r_part) == 1 or r_part.endswith('.')) and c_part.startswith(r_part[0]):
                            return True
                        if (len(c_part) == 1 or c_part.endswith('.')) and r_part.startswith(c_part[0]):
                            return True
            
            # 情况2: 名字部分完全匹配
            if researcher_first_parts == collaborator_first_parts:
                return True
            
            # 情况3: 一方只有姓氏，另一方有完整名字
            if (not researcher_first_parts and collaborator_first_parts) or (researcher_first_parts and not collaborator_first_parts):
                return True
        
        # 检查名字的其他变体
        # 例如: "Geoffrey E. Hinton" 和 "Geoffrey Hinton"
        if researcher_first_parts and collaborator_first_parts:
            # 检查第一个名字部分是否相同
            if researcher_first_parts[0] == collaborator_first_parts[0]:
                # 如果第一个名字部分相同，并且姓氏相同
                if researcher_last_name == collaborator_last_name:
                    return True
        
        return False
    """
    
    print(is_same_person_code)

def test_is_same_person():
    """
    测试改进的 is_same_person 方法
    """
    test_cases = [
        # 完全相同的名字
        ("John Smith", "John Smith", True),
        # 大小写不同
        ("John Smith", "john smith", True),
        # 缩写形式
        ("John Smith", "J. Smith", True),
        ("J. Smith", "John Smith", True),
        # 中间名缩写
        ("John A. Smith", "John Smith", True),
        ("John Smith", "John A. Smith", True),
        # 只有姓氏
        ("Smith", "John Smith", True),
        ("John Smith", "Smith", True),
        # 不同的人
        ("John Smith", "Jane Smith", False),
        ("John Smith", "John Doe", False),
        # 复杂情况
        ("Geoffrey E. Hinton", "Geoffrey Hinton", True),
        ("Geoffrey Hinton", "G. Hinton", True),
        ("Geoffrey Hinton", "G. E. Hinton", True),
        ("Geoffrey Hinton", "Geoff Hinton", False),  # 这个可能需要更复杂的逻辑
        # 中文名字
        ("张三", "张三", True),
        ("张三", "李四", False),
    ]
    
    print("\n测试改进的 is_same_person 方法：\n")
    print("| 研究者姓名 | 合作者姓名 | 预期结果 | 实际结果 | 是否通过 |")
    print("|------------|------------|----------|----------|----------|")
    
    for researcher_name, collaborator_name, expected in test_cases:
        actual = is_same_person_improved(researcher_name, collaborator_name)
        passed = "✓" if actual == expected else "✗"
        print(f"| {researcher_name} | {collaborator_name} | {expected} | {actual} | {passed} |")

def main():
    """主函数"""
    print("学者最佳合作者是自己的问题修复指南")
    print("=" * 50)
    
    print("\n问题描述：")
    print("在当前的实现中，有时候学者的最佳合作者会被错误地识别为学者自己，")
    print("这是因为在 ScholarAnalyzer.analyze_coauthors 方法中，用于排除学者自己的逻辑不够完善。")
    
    print("\n问题原因：")
    print("1. 名字变体识别不完整：当前代码尝试排除主要作者的各种形式，但可能无法覆盖所有可能的变体。")
    print("2. 姓氏检查逻辑问题：当前的检查只考虑了合作者名字是否以主要作者的姓氏结尾，但没有考虑其他可能的情况。")
    print("3. 回退逻辑问题：如果所有合作者都被排除了，代码会回退到使用第一个合作者，这可能导致选择了作者自己。")
    
    # 测试改进的方法
    test_is_same_person()
    
    # 提供修复代码
    fix_analyzer_coauthors_method()
    
    print("\n实施步骤：")
    print("1. 在 server/services/scholar/analyzer.py 文件中找到 ScholarAnalyzer 类")
    print("2. 添加上面的 is_same_person_improved 方法")
    print("3. 修改 analyze_coauthors 方法中的合作者筛选逻辑")
    print("4. 重新启动服务器，测试修复效果")
    
    print("\n注意事项：")
    print("1. 修改代码前请先备份原文件")
    print("2. 修改后请进行充分测试，确保不会引入新的问题")
    print("3. 如果有大量数据需要处理，可以使用 check_best_collaborators.py 脚本进行批量检查")

if __name__ == "__main__":
    main()
