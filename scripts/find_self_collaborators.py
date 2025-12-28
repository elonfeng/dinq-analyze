#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 collaborator_results.json 文件中找出最佳合作者是自己的学者

这个脚本读取 collaborator_results.json 文件，找出最佳合作者是自己的学者，
并以易于复制的格式列出他们的名称、学者ID和合作者名称。
"""

import os
import sys
import json
import argparse
from tabulate import tabulate

def find_self_collaborators(json_file):
    """
    从 JSON 文件中找出最佳合作者是自己的学者
    
    Args:
        json_file: JSON 文件路径
        
    Returns:
        list: 最佳合作者是自己的学者列表
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 找出最佳合作者是自己的学者
        self_collaborators = []
        for item in data:
            if item.get('is_same_person', False):
                self_collaborators.append(item)
        
        return self_collaborators
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return []

def print_self_collaborators(self_collaborators, output_format='table'):
    """
    打印最佳合作者是自己的学者
    
    Args:
        self_collaborators: 最佳合作者是自己的学者列表
        output_format: 输出格式，可选值: table, csv, tsv, markdown
    """
    if not self_collaborators:
        print("未找到最佳合作者是自己的学者")
        return
    
    # 准备表格数据
    table_data = []
    for item in self_collaborators:
        name = item.get('name', '')
        scholar_id = item.get('scholar_id', '')
        collaborator_name = item.get('collaborator_name', '')
        coauthored_papers = item.get('coauthored_papers', 0)
        
        table_data.append([name, scholar_id, collaborator_name, coauthored_papers])
    
    # 表格标题
    headers = ["学者姓名", "学者ID", "合作者姓名", "合作论文数"]
    
    # 根据输出格式打印表格
    if output_format == 'table':
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
    elif output_format == 'csv':
        print(','.join(headers))
        for row in table_data:
            print(','.join([str(cell) for cell in row]))
    elif output_format == 'tsv':
        print('\t'.join(headers))
        for row in table_data:
            print('\t'.join([str(cell) for cell in row]))
    elif output_format == 'markdown':
        print(tabulate(table_data, headers=headers, tablefmt='pipe'))
    elif output_format == 'simple':
        # 简单格式，方便复制
        for row in table_data:
            print(f"{row[0]}\t{row[1]}\t{row[2]}")
    else:
        print("不支持的输出格式")

def save_to_file(self_collaborators, output_file, output_format='table'):
    """
    将最佳合作者是自己的学者保存到文件
    
    Args:
        self_collaborators: 最佳合作者是自己的学者列表
        output_file: 输出文件路径
        output_format: 输出格式，可选值: table, csv, tsv, markdown
    """
    if not self_collaborators:
        print("未找到最佳合作者是自己的学者，不保存文件")
        return
    
    # 准备表格数据
    table_data = []
    for item in self_collaborators:
        name = item.get('name', '')
        scholar_id = item.get('scholar_id', '')
        collaborator_name = item.get('collaborator_name', '')
        coauthored_papers = item.get('coauthored_papers', 0)
        
        table_data.append([name, scholar_id, collaborator_name, coauthored_papers])
    
    # 表格标题
    headers = ["学者姓名", "学者ID", "合作者姓名", "合作论文数"]
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # 根据输出格式保存表格
            if output_format == 'table':
                f.write(tabulate(table_data, headers=headers, tablefmt='grid'))
            elif output_format == 'csv':
                f.write(','.join(headers) + '\n')
                for row in table_data:
                    f.write(','.join([str(cell) for cell in row]) + '\n')
            elif output_format == 'tsv':
                f.write('\t'.join(headers) + '\n')
                for row in table_data:
                    f.write('\t'.join([str(cell) for cell in row]) + '\n')
            elif output_format == 'markdown':
                f.write(tabulate(table_data, headers=headers, tablefmt='pipe'))
            elif output_format == 'simple':
                # 简单格式，方便复制
                for row in table_data:
                    f.write(f"{row[0]}\t{row[1]}\t{row[2]}\n")
            else:
                f.write("不支持的输出格式")
        
        print(f"已将结果保存到文件: {output_file}")
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='从 collaborator_results.json 文件中找出最佳合作者是自己的学者')
    parser.add_argument('--file', default='collaborator_results.json', help='JSON 文件路径')
    parser.add_argument('--format', choices=['table', 'csv', 'tsv', 'markdown', 'simple'], default='simple', help='输出格式')
    parser.add_argument('--output', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.file):
        print(f"文件不存在: {args.file}")
        return
    
    # 找出最佳合作者是自己的学者
    self_collaborators = find_self_collaborators(args.file)
    
    # 打印结果
    print_self_collaborators(self_collaborators, args.format)
    
    # 如果指定了输出文件，保存结果
    if args.output:
        save_to_file(self_collaborators, args.output, args.format)

if __name__ == "__main__":
    # 检查是否安装了 tabulate 库
    try:
        import tabulate
    except ImportError:
        print("请先安装 tabulate 库: pip install tabulate")
        sys.exit(1)
    
    main()
