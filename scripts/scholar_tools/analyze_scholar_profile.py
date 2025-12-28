#!/usr/bin/env python3
"""
分析Google Scholar学者个人资料

这个脚本用于分析从fetch_full_scholar_profile.py获取的学者个人资料。
使用方法：python analyze_scholar_profile.py [profile_json_file]
默认文件：scholar_profile.json
"""

import json
import argparse
import matplotlib.pyplot as plt
from collections import Counter
import os

def load_profile(file_path):
    """加载个人资料JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载文件时出错: {e}")
        return None

def analyze_profile(profile):
    """分析学者个人资料"""
    if not profile:
        print("没有可分析的个人资料")
        return
    
    # 基本信息
    print("\n基本信息:")
    print(f"姓名: {profile.get('name', 'N/A')}")
    print(f"机构: {profile.get('affiliation', 'N/A')}")
    print(f"研究领域: {', '.join(profile.get('interests', []))}")
    
    # 引用统计
    print("\n引用统计:")
    citation_stats = profile.get('citation_stats', {})
    for stat_name, values in citation_stats.items():
        print(f"{stat_name.replace('_', ' ').title()}: 总计 {values.get('all', 'N/A')}, 自2018年起 {values.get('since_2018', 'N/A')}")
    
    # 论文统计
    papers = profile.get('papers', [])
    print(f"\n论文总数: {len(papers)}")
    
    # 按年份分布
    years = [int(paper.get('year', 0)) for paper in papers if paper.get('year', '').isdigit()]
    year_counter = Counter(years)
    
    print("\n论文年份分布:")
    for year in sorted(year_counter.keys()):
        print(f"{year}: {year_counter[year]}篇")
    
    # 引用次数统计
    citations = [paper.get('num_citations', 0) for paper in papers]
    total_citations = sum(citations)
    avg_citations = total_citations / len(papers) if papers else 0
    
    print(f"\n总引用次数: {total_citations}")
    print(f"平均每篇论文引用次数: {avg_citations:.2f}")
    
    # 引用次数最多的论文
    sorted_papers = sorted(papers, key=lambda x: x.get('num_citations', 0), reverse=True)
    
    print("\n引用次数最多的10篇论文:")
    for i, paper in enumerate(sorted_papers[:10]):
        print(f"{i+1}. {paper.get('title', 'N/A')} ({paper.get('year', 'N/A')}) - 引用: {paper.get('num_citations', 0)}")
    
    # 合作者统计
    coauthors = []
    for paper in papers:
        authors = paper.get('authors', [])
        if authors:
            # 假设第一个作者是学者本人
            coauthors.extend([author.strip() for author in authors if author.strip() != profile.get('name', '')])
    
    coauthor_counter = Counter(coauthors)
    
    print("\n最常合作的10位作者:")
    for author, count in coauthor_counter.most_common(10):
        print(f"{author}: {count}篇论文")
    
    # 期刊/会议统计
    venues = [paper.get('venue', '').strip() for paper in papers if paper.get('venue', '').strip()]
    venue_counter = Counter(venues)
    
    print("\n最常发表的10个期刊/会议:")
    for venue, count in venue_counter.most_common(10):
        print(f"{venue}: {count}篇论文")
    
    # 创建可视化目录
    os.makedirs('visualizations', exist_ok=True)
    
    # 绘制年份分布图
    plt.figure(figsize=(12, 6))
    years = sorted(year_counter.keys())
    counts = [year_counter[year] for year in years]
    plt.bar(years, counts)
    plt.xlabel('年份')
    plt.ylabel('论文数量')
    plt.title('论文年份分布')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig('visualizations/papers_by_year.png')
    print("\n已保存年份分布图到 visualizations/papers_by_year.png")
    
    # 绘制引用次数分布图
    plt.figure(figsize=(12, 6))
    plt.hist(citations, bins=20)
    plt.xlabel('引用次数')
    plt.ylabel('论文数量')
    plt.title('论文引用次数分布')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig('visualizations/citation_distribution.png')
    print("已保存引用次数分布图到 visualizations/citation_distribution.png")
    
    # 绘制最常合作的作者饼图
    plt.figure(figsize=(12, 8))
    top_coauthors = dict(coauthor_counter.most_common(10))
    plt.pie(top_coauthors.values(), labels=top_coauthors.keys(), autopct='%1.1f%%')
    plt.title('最常合作的10位作者')
    plt.savefig('visualizations/top_coauthors.png')
    print("已保存最常合作作者图到 visualizations/top_coauthors.png")
    
    # 绘制最常发表的期刊/会议饼图
    plt.figure(figsize=(12, 8))
    top_venues = dict(venue_counter.most_common(10))
    plt.pie(top_venues.values(), labels=top_venues.keys(), autopct='%1.1f%%')
    plt.title('最常发表的10个期刊/会议')
    plt.savefig('visualizations/top_venues.png')
    print("已保存最常发表期刊/会议图到 visualizations/top_venues.png")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='分析Google Scholar学者个人资料')
    parser.add_argument('profile_file', nargs='?', default='scholar_profile.json', help='个人资料JSON文件（默认：scholar_profile.json）')
    
    args = parser.parse_args()
    
    # 加载个人资料
    profile = load_profile(args.profile_file)
    
    # 分析个人资料
    analyze_profile(profile)

if __name__ == "__main__":
    main()
