#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：保存 Scholar 报告到 JSON 文件

此脚本运行 scholar_service 的 generate_report 函数，
并将结果保存为格式化的 JSON 文件，以便查看报告的结构。
"""

import os
import json
import time
from datetime import datetime

from server.services.scholar.scholar_service import ScholarService

def save_report_to_json(scholar_id=None, researcher_name=None, output_dir="./reports"):
    """
    生成学者报告并保存为JSON文件
    
    Args:
        scholar_id (str, optional): Google Scholar ID
        researcher_name (str, optional): 研究者姓名
        output_dir (str): 输出目录
    
    Returns:
        str: 保存的文件路径
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化服务
    api_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
    scholar_service = ScholarService(use_crawlbase=bool(api_token), api_token=api_token or None)
    
    # 如果没有提供scholar_id但提供了researcher_name，尝试获取scholar_id
    if not scholar_id and researcher_name:
        from server.services.scholar.data_fetcher import get_scholar_information
        print(f"正在搜索研究者: {researcher_name}")
        author_info = get_scholar_information(researcher_name.lower())
        scholar_id = author_info.get('scholar_id')
        if scholar_id is None:
            print("未找到学者ID。请手动输入学者ID！")
            return None
    
    if not scholar_id:
        print("错误: 必须提供scholar_id或researcher_name")
        return None
    
    # 开始计时
    t1 = time.time()
    
    print(f"正在为ID生成报告: {scholar_id}...")
    
    # 生成报告
    try:
        report = scholar_service.generate_report(scholar_id=scholar_id)
        if report is None:
            print(f"错误: 无法为ID {scholar_id} 生成报告")
            return None
        
        # 打印执行时间
        print(f"分析完成，耗时 {time.time() - t1:.2f} 秒")
    except Exception as e:
        print(f"生成报告时出错: {str(e)}")
        return None
    
    # 创建文件名
    researcher_name = report.get('researcher', {}).get('name', 'unknown')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{researcher_name.replace(' ', '_')}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # 保存为JSON文件
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"报告已保存到: {filepath}")
    
    # 打印报告的顶级键
    print("\n报告结构:")
    for key in report.keys():
        print(f"- {key}")
        if isinstance(report[key], dict):
            for subkey in report[key].keys():
                print(f"  - {subkey}")
    
    return filepath

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='保存Scholar报告为JSON文件')
    parser.add_argument('--id', type=str, help='Google Scholar ID')
    parser.add_argument('--name', type=str, help='研究者姓名')
    parser.add_argument('--output', type=str, default='./reports', help='输出目录')
    
    args = parser.parse_args()
    
    if not args.id and not args.name:
        # 如果没有提供参数，使用默认值
        # 这里使用之前成功运行过的ID作为示例 (Peiqin Lin)
        scholar_id = "ZUeyIxMAAAAJ"
        print(f"未提供ID或姓名，使用默认ID: {scholar_id} (Peiqin Lin)")
        result = save_report_to_json(scholar_id=scholar_id, output_dir=args.output)
        if result is None:
            # 尝试另一个ID
            scholar_id = "qDrpE-YAAAAJ"
            print(f"尝试另一个ID: {scholar_id} (Hinrich Schütze)")
            save_report_to_json(scholar_id=scholar_id, output_dir=args.output)
    else:
        save_report_to_json(scholar_id=args.id, researcher_name=args.name, output_dir=args.output)

if __name__ == "__main__":
    main()
