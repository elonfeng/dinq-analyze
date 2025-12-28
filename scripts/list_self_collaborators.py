#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
列出最佳合作者是自己的学者

这个脚本读取 collaborator_results.json 文件，找出最佳合作者是自己的学者，
并以易于复制的格式列出他们的名称、学者ID和合作者名称。
"""

import os
import sys
import json

def main():
    """主函数"""
    # 默认文件路径
    json_file = 'collaborator_results.json'
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    
    # 检查文件是否存在
    if not os.path.exists(json_file):
        print(f"文件不存在: {json_file}")
        return
    
    try:
        # 读取 JSON 文件
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 找出最佳合作者是自己的学者
        self_collaborators = []
        for item in data:
            if item.get('is_same_person', False):
                self_collaborators.append(item)
        
        if not self_collaborators:
            print("未找到最佳合作者是自己的学者")
            return
        
        # 打印表头
        print("学者姓名\t学者ID\t合作者姓名\t合作论文数")
        print("-" * 80)
        
        # 打印每个学者的信息
        for item in self_collaborators:
            name = item.get('name', '')
            scholar_id = item.get('scholar_id', '')
            collaborator_name = item.get('collaborator_name', '')
            coauthored_papers = item.get('coauthored_papers', 0)
            
            print(f"{name}\t{scholar_id}\t{collaborator_name}\t{coauthored_papers}")
        
        # 打印统计信息
        print("-" * 80)
        print(f"共找到 {len(self_collaborators)} 个最佳合作者是自己的学者")
        
        # 保存到文件
        output_file = 'self_collaborators.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("学者姓名\t学者ID\t合作者姓名\t合作论文数\n")
            for item in self_collaborators:
                name = item.get('name', '')
                scholar_id = item.get('scholar_id', '')
                collaborator_name = item.get('collaborator_name', '')
                coauthored_papers = item.get('coauthored_papers', 0)
                
                f.write(f"{name}\t{scholar_id}\t{collaborator_name}\t{coauthored_papers}\n")
        
        print(f"已将结果保存到文件: {output_file}")
        
    except Exception as e:
        print(f"处理文件时出错: {str(e)}")

if __name__ == "__main__":
    main()
