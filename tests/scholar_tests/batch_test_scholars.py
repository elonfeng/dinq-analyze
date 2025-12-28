#!/usr/bin/env python
# coding: UTF-8
"""
批量测试学者脚本。
该脚本可以批量运行学者测试，支持多种测试场景和配置选项。
"""

import os
import sys
import re
import json
import argparse
import subprocess
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def run_test_for_scholar(name, scholar_id, url, test_type, output_dir, step=None, timeout=300):
    """为单个学者运行测试。"""
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 构建命令
    if test_type == 'full':
        script_path = os.path.join('tests', 'scholar_tests', 'test_single_scholar.py')
        cmd = [sys.executable, script_path]
    elif test_type == 'steps':
        script_path = os.path.join('tests', 'scholar_tests', 'test_all_steps_single_scholar.py')
        cmd = [sys.executable, script_path]
    elif test_type == 'specific_step':
        if not step:
            print(f"错误: 运行特定步骤测试时必须指定步骤")
            return False
        script_path = os.path.join('tests', 'scholar_tests', 'test_specific_step.py')
        cmd = [sys.executable, script_path, '--step', step]
    else:
        print(f"错误: 无效的测试类型 '{test_type}'")
        return False
    
    # 添加参数
    if name:
        cmd.extend(['--name', name])
    if scholar_id:
        cmd.extend(['--id', scholar_id])
    if url:
        cmd.extend(['--url', url])
    
    # 添加输出目录
    cmd.extend(['--output-dir', output_dir])
    
    # 运行命令
    try:
        start_time = time.time()
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 创建日志文件
        log_file = os.path.join(output_dir, f"{name.replace(' ', '_')}_{scholar_id}_log.txt")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"运行命令: {' '.join(cmd)}\n\n")
            f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}\n\n")
            f.write("=== 标准输出 ===\n")
        
        # 设置超时
        elapsed = 0
        while process.poll() is None and elapsed < timeout:
            # 读取输出
            stdout_line = process.stdout.readline()
            if stdout_line:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(stdout_line)
                print(f"[{name}] {stdout_line.strip()}")
            
            # 检查是否超时
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                process.terminate()
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n=== 超时 ({timeout}秒) ===\n")
                print(f"[{name}] 超时 ({timeout}秒)")
                return False
            
            # 短暂休眠
            time.sleep(0.1)
        
        # 获取剩余输出
        stdout, stderr = process.communicate()
        
        # 写入日志
        with open(log_file, 'a', encoding='utf-8') as f:
            if stdout:
                f.write(stdout)
            f.write("\n\n=== 标准错误 ===\n")
            if stderr:
                f.write(stderr)
            
            # 写入结束信息
            end_time = time.time()
            f.write(f"\n\n结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}\n")
            f.write(f"总耗时: {end_time - start_time:.2f}秒\n")
            f.write(f"返回码: {process.returncode}\n")
        
        if process.returncode != 0:
            print(f"[{name}] 测试失败，返回码: {process.returncode}")
            print(f"[{name}] 错误信息: {stderr}")
            return False
        
        print(f"[{name}] 测试成功完成，耗时: {time.time() - start_time:.2f}秒")
        return True
    except Exception as e:
        print(f"[{name}] 运行测试时出错: {e}")
        return False

def batch_test_scholars(test_file, test_type, output_dir, step=None, max_scholars=None, start_index=0, 
                       parallel=False, max_workers=4, timeout=300):
    """批量测试学者。"""
    # 读取测试文件
    scholars = read_test_file(test_file)
    
    # 限制学者数量
    if max_scholars is not None:
        end_index = min(start_index + max_scholars, len(scholars))
        scholars = scholars[start_index:end_index]
    
    # 创建输出目录
    if test_type == 'full':
        test_output_dir = os.path.join(output_dir, 'full')
    elif test_type == 'steps':
        test_output_dir = os.path.join(output_dir, 'steps')
    elif test_type == 'specific_step':
        test_output_dir = os.path.join(output_dir, f'step{step}')
    else:
        test_output_dir = output_dir
    
    os.makedirs(test_output_dir, exist_ok=True)
    
    # 运行测试
    results = []
    
    if parallel:
        # 并行运行测试
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_scholar = {
                executor.submit(
                    run_test_for_scholar, name, scholar_id, url, test_type, 
                    test_output_dir, step, timeout
                ): (name, scholar_id) 
                for name, scholar_id, url in scholars
            }
            
            # 处理结果
            for future in tqdm(as_completed(future_to_scholar), total=len(scholars), desc="测试学者"):
                name, scholar_id = future_to_scholar[future]
                try:
                    success = future.result()
                    results.append((name, scholar_id, success))
                except Exception as e:
                    print(f"[{name}] 任务执行出错: {e}")
                    results.append((name, scholar_id, False))
    else:
        # 串行运行测试
        for name, scholar_id, url in tqdm(scholars, desc="测试学者"):
            success = run_test_for_scholar(name, scholar_id, url, test_type, test_output_dir, step, timeout)
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
    
    # 保存结果
    result_file = os.path.join(test_output_dir, 'test_results.json')
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_type': test_type,
            'step': step,
            'total': len(results),
            'success': success_count,
            'results': [
                {'name': name, 'scholar_id': scholar_id, 'success': success}
                for name, scholar_id, success in results
            ]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"测试结果已保存到 {result_file}")
    
    return results

def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description='批量测试学者')
    parser.add_argument('--test-file', type=str, default='tests/scholar_tests/0416测试.txt', help='测试文件路径')
    parser.add_argument('--test-type', type=str, default='full', choices=['full', 'steps', 'specific_step'], help='测试类型')
    parser.add_argument('--step', type=str, help='要运行的步骤 (1, 1_2, 3, 4_5, 6, 7, 8, 9, 10, 11, 12)')
    parser.add_argument('--output-dir', type=str, default='reports/tests', help='输出目录')
    parser.add_argument('--max-scholars', type=int, help='最大学者数量')
    parser.add_argument('--start-index', type=int, default=0, help='起始学者索引')
    parser.add_argument('--parallel', action='store_true', help='是否并行运行测试')
    parser.add_argument('--max-workers', type=int, default=4, help='最大并行工作线程数')
    parser.add_argument('--timeout', type=int, default=300, help='每个测试的超时时间（秒）')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.test_type == 'specific_step' and not args.step:
        print("错误: 运行特定步骤测试时必须指定步骤")
        return
    
    if args.step:
        valid_steps = ['1', '1_2', '3', '4_5', '6', '7', '8', '9', '10', '11', '12']
        if args.step not in valid_steps:
            print(f"错误: 无效的步骤 '{args.step}'。有效的步骤: {', '.join(valid_steps)}")
            return
    
    # 运行测试
    batch_test_scholars(
        args.test_file, args.test_type, args.output_dir, args.step,
        args.max_scholars, args.start_index, args.parallel, args.max_workers, args.timeout
    )

if __name__ == "__main__":
    main()
