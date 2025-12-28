#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
激活码管理脚本

这个脚本提供了一个命令行界面，用于管理激活码。
支持创建激活码、查询激活码状态和列出激活码。

使用方法:
    python activation_code_manager.py create [--expires-days DAYS] [--batch-id ID] [--notes NOTES]
    python activation_code_manager.py verify CODE
    python activation_code_manager.py list [--status STATUS] [--batch-id ID] [--limit LIMIT]
    python activation_code_manager.py batch-create COUNT [--expires-days DAYS] [--batch-id ID] [--notes NOTES]
"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime
import getpass
import csv
from typing import Dict, List, Any, Optional, Union
import configparser
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('activation_code_manager')

# 默认配置
DEFAULT_CONFIG = {
    'api': {
        'base_url': 'http://localhost:5001/api',
        'user_id': '',
        'token': ''
    }
}

# 配置文件路径
CONFIG_FILE = os.path.expanduser('~/.activation_code_manager.ini')


def load_config() -> configparser.ConfigParser:
    """
    加载配置文件，如果不存在则创建默认配置
    
    Returns:
        configparser.ConfigParser: 配置对象
    """
    config = configparser.ConfigParser()
    
    # 如果配置文件存在，则加载
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        # 否则使用默认配置
        config['api'] = DEFAULT_CONFIG['api']
        
        # 提示用户输入用户ID
        user_id = input("请输入您的用户ID: ")
        config['api']['user_id'] = user_id
        
        # 保存配置
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
        
        logger.info(f"已创建配置文件: {CONFIG_FILE}")
    
    return config


def save_config(config: configparser.ConfigParser) -> None:
    """
    保存配置到文件
    
    Args:
        config: 配置对象
    """
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)
    logger.info(f"已更新配置文件: {CONFIG_FILE}")


def get_headers(config: configparser.ConfigParser) -> Dict[str, str]:
    """
    获取API请求头
    
    Args:
        config: 配置对象
        
    Returns:
        Dict[str, str]: 请求头字典
    """
    headers = {
        'Content-Type': 'application/json'
    }
    
    # 添加用户ID
    user_id = config['api'].get('user_id', '')
    if not user_id:
        user_id = input("请输入您的用户ID: ")
        config['api']['user_id'] = user_id
        save_config(config)
    
    headers['Userid'] = user_id
    
    # 添加令牌（如果有）
    token = config['api'].get('token', '')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    return headers


def create_code(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    """
    创建一个新的激活码
    
    Args:
        args: 命令行参数
        config: 配置对象
    """
    # 准备请求数据
    data = {}
    if args.expires_days is not None:
        data['expires_in_days'] = args.expires_days
    if args.batch_id:
        data['batch_id'] = args.batch_id
    if args.notes:
        data['notes'] = args.notes
    
    # 发送请求
    try:
        response = requests.post(
            f"{config['api']['base_url']}/activation-codes/create",
            headers=get_headers(config),
            json=data
        )
        
        # 检查响应
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            code = result.get('code', '')
            created_at = result.get('created_at', '')
            expires_at = result.get('expires_at', '')
            
            print("\n=== 激活码创建成功 ===")
            print(f"激活码: {code}")
            print(f"创建时间: {format_date(created_at)}")
            if expires_at:
                print(f"过期时间: {format_date(expires_at)}")
            else:
                print("过期时间: 永不过期")
            
            # 询问是否保存到文件
            save_to_file = input("\n是否将激活码保存到文件? (y/n): ").lower() == 'y'
            if save_to_file:
                filename = input("请输入文件名 (默认: activation_code.txt): ") or "activation_code.txt"
                with open(filename, 'w') as f:
                    f.write(f"激活码: {code}\n")
                    f.write(f"创建时间: {format_date(created_at)}\n")
                    if expires_at:
                        f.write(f"过期时间: {format_date(expires_at)}\n")
                    else:
                        f.write("过期时间: 永不过期\n")
                    
                    if args.batch_id:
                        f.write(f"批次ID: {args.batch_id}\n")
                    if args.notes:
                        f.write(f"备注: {args.notes}\n")
                
                print(f"激活码已保存到文件: {filename}")
        else:
            print(f"创建激活码失败: {result.get('error', '未知错误')}")
    
    except requests.RequestException as e:
        print(f"请求错误: {e}")


def batch_create_codes(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    """
    批量创建激活码
    
    Args:
        args: 命令行参数
        config: 配置对象
    """
    count = args.count
    if count <= 0:
        print("错误: 数量必须大于0")
        return
    
    if count > 100:
        confirm = input(f"警告: 您正在创建 {count} 个激活码，这可能需要一些时间。是否继续? (y/n): ")
        if confirm.lower() != 'y':
            print("已取消批量创建")
            return
    
    # 准备请求数据
    data = {}
    if args.expires_days is not None:
        data['expires_in_days'] = args.expires_days
    if args.batch_id:
        data['batch_id'] = args.batch_id
    if args.notes:
        data['notes'] = args.notes
    
    # 生成批次ID（如果未提供）
    if not args.batch_id:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data['batch_id'] = f"batch_{timestamp}"
    
    print(f"开始创建 {count} 个激活码...")
    codes = []
    
    # 发送请求
    try:
        for i in range(count):
            response = requests.post(
                f"{config['api']['base_url']}/activation-codes/create",
                headers=get_headers(config),
                json=data
            )
            
            # 检查响应
            response.raise_for_status()
            result = response.json()
            
            if result.get('success'):
                code_info = {
                    'code': result.get('code', ''),
                    'created_at': result.get('created_at', ''),
                    'expires_at': result.get('expires_at', '')
                }
                codes.append(code_info)
                print(f"已创建 ({i+1}/{count}): {code_info['code']}")
            else:
                print(f"创建第 {i+1} 个激活码失败: {result.get('error', '未知错误')}")
        
        print(f"\n成功创建了 {len(codes)} 个激活码")
        
        # 询问是否保存到文件
        if codes:
            save_to_file = input("\n是否将激活码保存到文件? (y/n): ").lower() == 'y'
            if save_to_file:
                # 询问文件格式
                format_choice = input("选择文件格式 (1: TXT, 2: CSV, 3: JSON) [默认: 1]: ") or "1"
                
                if format_choice == "1":  # TXT
                    filename = input("请输入文件名 (默认: activation_codes.txt): ") or "activation_codes.txt"
                    with open(filename, 'w') as f:
                        f.write(f"批次ID: {data['batch_id']}\n")
                        f.write(f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        if args.expires_days is not None:
                            f.write(f"过期天数: {args.expires_days}\n")
                        if args.notes:
                            f.write(f"备注: {args.notes}\n")
                        f.write("\n激活码列表:\n")
                        
                        for code_info in codes:
                            f.write(f"{code_info['code']}\n")
                    
                elif format_choice == "2":  # CSV
                    filename = input("请输入文件名 (默认: activation_codes.csv): ") or "activation_codes.csv"
                    with open(filename, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['激活码', '创建时间', '过期时间', '批次ID', '备注'])
                        
                        for code_info in codes:
                            writer.writerow([
                                code_info['code'],
                                format_date(code_info['created_at']),
                                format_date(code_info['expires_at']) if code_info['expires_at'] else '永不过期',
                                data['batch_id'],
                                args.notes or ''
                            ])
                
                else:  # JSON
                    filename = input("请输入文件名 (默认: activation_codes.json): ") or "activation_codes.json"
                    with open(filename, 'w') as f:
                        json_data = {
                            'batch_id': data['batch_id'],
                            'created_at': datetime.now().isoformat(),
                            'expires_days': args.expires_days,
                            'notes': args.notes,
                            'codes': codes
                        }
                        json.dump(json_data, f, indent=2, ensure_ascii=False)
                
                print(f"激活码已保存到文件: {filename}")
    
    except requests.RequestException as e:
        print(f"请求错误: {e}")


def verify_code(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    """
    验证激活码状态
    
    Args:
        args: 命令行参数
        config: 配置对象
    """
    code = args.code
    if not code:
        print("错误: 请提供激活码")
        return
    
    # 发送请求
    try:
        response = requests.get(
            f"{config['api']['base_url']}/activation-codes/verify",
            headers=get_headers(config),
            params={'code': code}
        )
        
        # 检查响应
        response.raise_for_status()
        result = response.json()
        
        print("\n=== 激活码验证结果 ===")
        
        if result.get('success'):
            print("状态: 有效")
            print(f"激活码: {code}")
            print(f"创建时间: {format_date(result.get('created_at'))}")
            
            if result.get('expires_at'):
                print(f"过期时间: {format_date(result.get('expires_at'))}")
            else:
                print("过期时间: 永不过期")
        else:
            print(f"状态: 无效")
            print(f"原因: {result.get('error', '未知错误')}")
            
            if result.get('used_by'):
                print(f"使用者: {result.get('used_by')}")
                if result.get('used_at'):
                    print(f"使用时间: {format_date(result.get('used_at'))}")
            
            if result.get('expires_at'):
                print(f"过期时间: {format_date(result.get('expires_at'))}")
    
    except requests.RequestException as e:
        print(f"请求错误: {e}")


def list_codes(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    """
    列出激活码
    
    Args:
        args: 命令行参数
        config: 配置对象
    """
    # 准备查询参数
    params = {
        'limit': args.limit,
        'offset': 0
    }
    
    if args.status:
        if args.status.lower() in ['used', 'true']:
            params['is_used'] = 'true'
        elif args.status.lower() in ['available', 'false']:
            params['is_used'] = 'false'
    
    if args.batch_id:
        params['batch_id'] = args.batch_id
    
    # 发送请求
    try:
        response = requests.get(
            f"{config['api']['base_url']}/activation-codes",
            headers=get_headers(config),
            params=params
        )
        
        # 检查响应
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            codes = result.get('codes', [])
            total = result.get('total', 0)
            
            if not codes:
                print("没有找到符合条件的激活码")
                return
            
            print(f"\n=== 激活码列表 (显示 {len(codes)}/{total}) ===")
            
            # 打印表头
            header = f"{'激活码':<10} | {'状态':<10} | {'创建时间':<19} | {'过期时间':<19} | {'使用者':<15} | {'批次ID':<15} | {'备注':<20}"
            print(header)
            print('-' * len(header))
            
            # 打印数据
            for code in codes:
                status = "已使用" if code.get('is_used') else "可用"
                if not code.get('is_used') and code.get('expires_at') and parse_date(code.get('expires_at')) < datetime.now():
                    status = "已过期"
                
                created_at = format_date(code.get('created_at'))
                expires_at = format_date(code.get('expires_at')) if code.get('expires_at') else "永不过期"
                used_by = code.get('used_by', '') or ''
                batch_id = code.get('batch_id', '') or ''
                notes = code.get('notes', '') or ''
                
                # 截断过长的字段
                if len(notes) > 20:
                    notes = notes[:17] + "..."
                if len(batch_id) > 15:
                    batch_id = batch_id[:12] + "..."
                if len(used_by) > 15:
                    used_by = used_by[:12] + "..."
                
                print(f"{code.get('code', ''):<10} | {status:<10} | {created_at:<19} | {expires_at:<19} | {used_by:<15} | {batch_id:<15} | {notes:<20}")
            
            # 询问是否导出
            export = input("\n是否导出这些激活码? (y/n): ").lower() == 'y'
            if export:
                export_codes(codes)
        else:
            print(f"获取激活码列表失败: {result.get('error', '未知错误')}")
    
    except requests.RequestException as e:
        print(f"请求错误: {e}")


def export_codes(codes: List[Dict[str, Any]]) -> None:
    """
    导出激活码列表到文件
    
    Args:
        codes: 激活码列表
    """
    # 询问文件格式
    format_choice = input("选择文件格式 (1: TXT, 2: CSV, 3: JSON) [默认: 2]: ") or "2"
    
    if format_choice == "1":  # TXT
        filename = input("请输入文件名 (默认: exported_codes.txt): ") or "exported_codes.txt"
        with open(filename, 'w') as f:
            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"激活码数量: {len(codes)}\n\n")
            
            # 打印表头
            f.write(f"{'激活码':<10} | {'状态':<10} | {'创建时间':<19} | {'过期时间':<19} | {'使用者':<15} | {'批次ID':<15} | {'备注':<20}\n")
            f.write('-' * 100 + '\n')
            
            # 打印数据
            for code in codes:
                status = "已使用" if code.get('is_used') else "可用"
                if not code.get('is_used') and code.get('expires_at') and parse_date(code.get('expires_at')) < datetime.now():
                    status = "已过期"
                
                created_at = format_date(code.get('created_at'))
                expires_at = format_date(code.get('expires_at')) if code.get('expires_at') else "永不过期"
                used_by = code.get('used_by', '') or ''
                batch_id = code.get('batch_id', '') or ''
                notes = code.get('notes', '') or ''
                
                f.write(f"{code.get('code', ''):<10} | {status:<10} | {created_at:<19} | {expires_at:<19} | {used_by:<15} | {batch_id:<15} | {notes:<20}\n")
    
    elif format_choice == "2":  # CSV
        filename = input("请输入文件名 (默认: exported_codes.csv): ") or "exported_codes.csv"
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['激活码', '状态', '创建时间', '过期时间', '使用者', '使用时间', '批次ID', '备注'])
            
            for code in codes:
                status = "已使用" if code.get('is_used') else "可用"
                if not code.get('is_used') and code.get('expires_at') and parse_date(code.get('expires_at')) < datetime.now():
                    status = "已过期"
                
                writer.writerow([
                    code.get('code', ''),
                    status,
                    format_date(code.get('created_at')),
                    format_date(code.get('expires_at')) if code.get('expires_at') else '永不过期',
                    code.get('used_by', ''),
                    format_date(code.get('used_at')) if code.get('used_at') else '',
                    code.get('batch_id', ''),
                    code.get('notes', '')
                ])
    
    else:  # JSON
        filename = input("请输入文件名 (默认: exported_codes.json): ") or "exported_codes.json"
        with open(filename, 'w') as f:
            json_data = {
                'exported_at': datetime.now().isoformat(),
                'count': len(codes),
                'codes': codes
            }
            json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"激活码已导出到文件: {filename}")


def format_date(date_str: Optional[str]) -> str:
    """
    格式化日期字符串
    
    Args:
        date_str: ISO格式的日期字符串
        
    Returns:
        str: 格式化后的日期字符串
    """
    if not date_str:
        return ""
    
    try:
        dt = parse_date(date_str)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return date_str


def parse_date(date_str: Optional[str]) -> datetime:
    """
    解析日期字符串为datetime对象
    
    Args:
        date_str: ISO格式的日期字符串
        
    Returns:
        datetime: 解析后的datetime对象
    """
    if not date_str:
        return datetime.now()
    
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        # 尝试其他格式
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # 如果所有格式都失败，返回当前时间
        return datetime.now()


def configure(args: argparse.Namespace, config: configparser.ConfigParser) -> None:
    """
    配置工具
    
    Args:
        args: 命令行参数
        config: 配置对象
    """
    print("\n=== 配置激活码管理工具 ===")
    
    # 配置API基础URL
    current_base_url = config['api'].get('base_url', DEFAULT_CONFIG['api']['base_url'])
    new_base_url = input(f"API基础URL [当前: {current_base_url}]: ") or current_base_url
    config['api']['base_url'] = new_base_url
    
    # 配置用户ID
    current_user_id = config['api'].get('user_id', '')
    new_user_id = input(f"用户ID [当前: {current_user_id}]: ") or current_user_id
    config['api']['user_id'] = new_user_id
    
    # 配置令牌（可选）
    current_token = config['api'].get('token', '')
    new_token = input(f"认证令牌 [当前: {'已设置' if current_token else '未设置'}]: ") or current_token
    config['api']['token'] = new_token
    
    # 保存配置
    save_config(config)
    print("配置已更新")


def main():
    """主函数"""
    # 创建解析器
    parser = argparse.ArgumentParser(description='激活码管理工具')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # 创建激活码命令
    create_parser = subparsers.add_parser('create', help='创建一个新的激活码')
    create_parser.add_argument('--expires-days', type=int, help='激活码过期天数')
    create_parser.add_argument('--batch-id', help='批次ID')
    create_parser.add_argument('--notes', help='备注')
    
    # 批量创建激活码命令
    batch_parser = subparsers.add_parser('batch-create', help='批量创建激活码')
    batch_parser.add_argument('count', type=int, help='创建数量')
    batch_parser.add_argument('--expires-days', type=int, help='激活码过期天数')
    batch_parser.add_argument('--batch-id', help='批次ID')
    batch_parser.add_argument('--notes', help='备注')
    
    # 验证激活码命令
    verify_parser = subparsers.add_parser('verify', help='验证激活码状态')
    verify_parser.add_argument('code', help='要验证的激活码')
    
    # 列出激活码命令
    list_parser = subparsers.add_parser('list', help='列出激活码')
    list_parser.add_argument('--status', choices=['all', 'used', 'available'], default='all', help='激活码状态')
    list_parser.add_argument('--batch-id', help='按批次ID筛选')
    list_parser.add_argument('--limit', type=int, default=20, help='返回的最大数量')
    
    # 配置命令
    config_parser = subparsers.add_parser('config', help='配置工具')
    
    # 解析参数
    args = parser.parse_args()
    
    # 如果没有提供命令，显示帮助
    if not args.command:
        parser.print_help()
        return
    
    # 加载配置
    config = load_config()
    
    # 执行命令
    if args.command == 'create':
        create_code(args, config)
    elif args.command == 'batch-create':
        batch_create_codes(args, config)
    elif args.command == 'verify':
        verify_code(args, config)
    elif args.command == 'list':
        list_codes(args, config)
    elif args.command == 'config':
        configure(args, config)


if __name__ == '__main__':
    main()
