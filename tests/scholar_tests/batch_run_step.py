#!/usr/bin/env python
# coding: UTF-8
"""
批量运行特定步骤的测试脚本。
该脚本读取测试文件中的学者列表，并针对每个学者运行指定的测试步骤。
"""

import os
import sys
import re
import json
import argparse
import subprocess
from tqdm import tqdm

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def extract_scholar_id(url):
    """从Google Scholar URL中提取学者ID。"""
    match = re.search(r'user=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def read_test_file(test_file):
    """读取测试文件，返回学者名称和ID列表。"""
    scholars = []
    
    with open(test_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(', ', 1)
        
        if len(parts) != 2:
            print(f"无效的行格式: {line}")
            continue
        
        name = parts[0]
        url = parts[1]
        scholar_id = extract_scholar_id(url)
        
        if not scholar_id:
            print(f"无法从URL提取学者ID: {url}")
            continue
        
        scholars.append((name, scholar_id, url))
    
    return scholars

def run_step_for_scholar(name, scholar_id, url, step, output_dir, max_scholars=None, start_index=0):
    """为单个学者运行特定步骤的测试。"""
    # 构建命令
    if step == 'all':
        script_path = os.path.join('tests', 'scholar_tests', 'test_all_steps_single_scholar.py')
    else:
        script_path = os.path.join('tests', 'scholar_tests', f'test_step{step}_*.py')
    
    cmd = [sys.executable, script_path]
    
    if name:
        cmd.extend(['--name', name])
    if scholar_id:
        cmd.extend(['--id', scholar_id])
    if url:
        cmd.extend(['--url', url])
    if output_dir:
        cmd.extend(['--output-dir', output_dir])
    
    # 运行命令
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"成功为学者 {name} (ID: {scholar_id}) 运行步骤 {step}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"为学者 {name} (ID: {scholar_id}) 运行步骤 {step} 时出错:")
        print(f"错误代码: {e.returncode}")
        print(f"标准输出: {e.stdout}")
        print(f"标准错误: {e.stderr}")
        return False

def batch_run_step(test_file, step, output_dir, max_scholars=None, start_index=0):
    """批量运行特定步骤的测试。"""
    # 读取测试文件
    scholars = read_test_file(test_file)
    
    # 限制学者数量
    if max_scholars is not None:
        end_index = min(start_index + max_scholars, len(scholars))
        scholars = scholars[start_index:end_index]
    
    # 创建输出目录
    if step == 'all':
        step_output_dir = os.path.join(output_dir, 'all_steps')
    else:
        step_output_dir = os.path.join(output_dir, f'step{step}')
    
    os.makedirs(step_output_dir, exist_ok=True)
    
    # 运行测试
    results = []
    for name, scholar_id, url in tqdm(scholars, desc=f"运行步骤 {step} 测试"):
        success = run_step_for_scholar(name, scholar_id, url, step, step_output_dir)
        results.append((name, scholar_id, success))
    
    # 打印摘要
    print("\n测试摘要:")
    success_count = sum(1 for _, _, success in results if success)
    print(f"成功: {success_count}/{len(results)}")
    
    # 打印失败的学者
    if success_count < len(results):
        print("\n失败的学者:")
        for name, scholar_id, success in results:
            if not success:
                print(f"- {name} (ID: {scholar_id})")
    
    return results

def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description='批量运行特定步骤的测试')
    parser.add_argument('--test-file', type=str, default='tests/scholar_tests/0416测试.txt', help='测试文件路径')
    parser.add_argument('--step', type=str, required=True, help='要运行的步骤 (1, 1_2, 3, 4_5, 6, 7, 8, 9, 10, 11, 12, all)')
    parser.add_argument('--output-dir', type=str, default='reports/tests', help='输出目录')
    parser.add_argument('--max-scholars', type=int, help='最大学者数量')
    parser.add_argument('--start-index', type=int, default=0, help='起始学者索引')
    
    args = parser.parse_args()
    
    # 验证步骤
    valid_steps = ['1', '1_2', '3', '4_5', '6', '7', '8', '9', '10', '11', '12', 'all']
    if args.step not in valid_steps:
        print(f"错误: 无效的步骤 '{args.step}'。有效的步骤: {', '.join(valid_steps)}")
        return
    
    # 运行测试
    batch_run_step(args.test_file, args.step, args.output_dir, args.max_scholars, args.start_index)

if __name__ == "__main__":
    main()
