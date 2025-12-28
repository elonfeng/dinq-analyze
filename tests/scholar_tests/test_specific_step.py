#!/usr/bin/env python
# coding: UTF-8
"""
针对特定步骤的测试脚本。
该脚本可以针对单个学者运行特定的测试步骤。
"""

import os
import sys
import re
import json
import glob
import argparse
import importlib
import traceback

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 导入必要的组件
from server.config.api_keys import API_KEYS

def extract_scholar_id(url):
    """从Google Scholar URL中提取学者ID。"""
    match = re.search(r'user=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def run_step(step, name=None, scholar_id=None, url=None, input_file=None, output_dir='reports/tests/steps'):
    """运行特定步骤的测试。"""
    # 如果提供了URL，提取学者ID
    if url and not scholar_id:
        scholar_id = extract_scholar_id(url)
        if not scholar_id:
            print(f"错误: 无法从URL提取学者ID: {url}")
            return None
    
    # 如果既没有提供名称也没有提供ID，则无法继续
    if not name and not scholar_id:
        print("错误: 必须提供学者名称或ID")
        return None
    
    # 创建输出目录
    step_output_dir = os.path.join(output_dir, f"step{step}")
    os.makedirs(step_output_dir, exist_ok=True)
    
    # 创建基本文件名
    if name:
        base_name = name.replace(' ', '_').replace(',', '').replace('.', '')
    else:
        base_name = "scholar"
    
    if scholar_id:
        base_name = f"{base_name}_{scholar_id}"
    
    # 尝试自动补齐输入文件（用于batch脚本的step测试）
    base_output_dir = os.path.abspath(output_dir)
    base_name_dir = os.path.basename(base_output_dir)
    if base_name_dir.startswith("step"):
        base_output_dir = os.path.abspath(os.path.join(base_output_dir, os.pardir))
    root_dir = os.path.abspath(os.path.join(base_output_dir, os.pardir))

    def _first_match(patterns):
        for pattern in patterns:
            if not pattern:
                continue
            matches = glob.glob(pattern)
            if matches:
                return sorted(matches)[0]
        return None

    def _resolve_author_data():
        return _first_match([
            os.path.join(base_output_dir, "step1_2", f"{base_name}_author_data.json"),
            os.path.join(base_output_dir, "step1_2", "*_author_data.json"),
            os.path.join(base_output_dir, "step1_2", "step1_2", f"{base_name}_author_data.json"),
            os.path.join(base_output_dir, "step1_2", "step1_2", "*_author_data.json"),
            os.path.join(base_output_dir, "steps", f"{base_name}_author_data.json"),
        ])

    def _resolve_pub_stats():
        return _first_match([
            os.path.join(base_output_dir, "step3", f"{base_name}_pub_stats.json"),
            os.path.join(base_output_dir, "step3", "*_pub_stats.json"),
            os.path.join(base_output_dir, "step3", "step3", f"{base_name}_pub_stats.json"),
            os.path.join(base_output_dir, "step3", "step3", "*_pub_stats.json"),
            os.path.join(base_output_dir, "steps", f"{base_name}_step3_pub_stats.json"),
            os.path.join(base_output_dir, "steps", "*_step3_pub_stats.json"),
        ])

    def _resolve_coauthor_stats():
        return _first_match([
            os.path.join(base_output_dir, "step4_5", f"{base_name}_coauthor_stats.json"),
            os.path.join(base_output_dir, "step4_5", "*_coauthor_stats.json"),
            os.path.join(base_output_dir, "step4_5", "step4_5", f"{base_name}_coauthor_stats.json"),
            os.path.join(base_output_dir, "step4_5", "step4_5", "*_coauthor_stats.json"),
            os.path.join(base_output_dir, "steps", f"{base_name}_step4_coauthor_stats.json"),
            os.path.join(base_output_dir, "steps", "*_step4_coauthor_stats.json"),
        ])

    def _resolve_report():
        return _first_match([
            os.path.join(base_output_dir, "full", f"{base_name}.json"),
            os.path.join(base_output_dir, "full", f"{base_name}_{scholar_id}.json") if scholar_id else None,
            os.path.join(base_output_dir, "full", "*_*.json"),
            os.path.join(base_output_dir, "steps", f"{base_name}_report.json"),
            os.path.join(base_output_dir, "steps", "*_report.json"),
            os.path.join(root_dir, "full", f"{base_name}.json"),
            os.path.join(root_dir, "full", "*_*.json"),
        ])

    if not input_file:
        if step in ("3", "4_5"):
            input_file = _resolve_author_data()
        elif step == "6":
            author_data_file = _resolve_author_data()
            pub_stats_file = _resolve_pub_stats()
            coauthor_stats_file = _resolve_coauthor_stats()
            if author_data_file and pub_stats_file and coauthor_stats_file:
                input_file = ",".join([author_data_file, pub_stats_file, coauthor_stats_file])
        elif step == "7":
            input_file = _resolve_coauthor_stats()
        elif step in ("8", "11", "12"):
            input_file = _resolve_report()
        elif step in ("9", "10"):
            input_file = _resolve_pub_stats()

    # 根据步骤选择要运行的函数
    try:
        # 动态导入相应的模块
        if step == '1' or step == '1_2':
            from server.services.scholar.data_fetcher import ScholarDataFetcher
            
            # 获取API令牌
            api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
            
            # 初始化数据获取器
            data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
            
            print(f"\n=== 步骤 {step}: 搜索学者并获取资料 ===")
            
            # 步骤1: 搜索学者
            author_info = data_fetcher.search_researcher(name=name, scholar_id=scholar_id)
            if not author_info:
                print(f"错误: 找不到学者 {'ID: ' + scholar_id if scholar_id else '名称: ' + name}")
                return None
            
            # 保存学者信息
            author_info_file = os.path.join(step_output_dir, f"{base_name}_author_info.json")
            with open(author_info_file, 'w', encoding='utf-8') as f:
                json.dump(author_info, f, ensure_ascii=False, indent=2)
            
            print(f"学者信息已保存到 {author_info_file}")
            
            if step == '1_2':
                # 步骤2: 获取完整资料和论文
                author_data = data_fetcher.get_full_profile(author_info)
                if not author_data:
                    print("错误: 无法获取完整资料")
                    return author_info
                
                # 保存学者数据
                author_data_file = os.path.join(step_output_dir, f"{base_name}_author_data.json")
                with open(author_data_file, 'w', encoding='utf-8') as f:
                    json.dump(author_data, f, ensure_ascii=False, indent=2)
                
                print(f"学者数据已保存到 {author_data_file}")
                return author_data
            
            return author_info
            
        elif step == '3':
            from server.services.scholar.analyzer import ScholarAnalyzer
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    author_data = json.load(f)
            else:
                print("错误: 步骤3需要输入文件")
                return None
            
            # 初始化分析器
            analyzer = ScholarAnalyzer()
            
            print(f"\n=== 步骤 {step}: 分析论文 ===")
            
            # 分析论文
            pub_stats = analyzer.analyze_publications(author_data)
            if not pub_stats:
                print("错误: 无法分析论文")
                return None
            
            # 保存论文统计数据
            pub_stats_file = os.path.join(step_output_dir, f"{base_name}_pub_stats.json")
            with open(pub_stats_file, 'w', encoding='utf-8') as f:
                json.dump(pub_stats, f, ensure_ascii=False, indent=2)
            
            print(f"论文统计数据已保存到 {pub_stats_file}")
            return pub_stats
            
        elif step == '4_5':
            from server.services.scholar.analyzer import ScholarAnalyzer
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    author_data = json.load(f)
            else:
                print("错误: 步骤4_5需要输入文件")
                return None
            
            # 初始化分析器
            analyzer = ScholarAnalyzer()
            
            print(f"\n=== 步骤 4: 分析合著者 ===")
            
            # 分析合著者
            coauthor_stats = analyzer.analyze_coauthors(author_data)
            if not coauthor_stats:
                print("错误: 无法分析合著者")
                return None
            
            # 保存合著者统计数据
            coauthor_stats_file = os.path.join(step_output_dir, f"{base_name}_coauthor_stats.json")
            with open(coauthor_stats_file, 'w', encoding='utf-8') as f:
                json.dump(coauthor_stats, f, ensure_ascii=False, indent=2)
            
            print(f"合著者统计数据已保存到 {coauthor_stats_file}")
            
            print(f"\n=== 步骤 5: 生成合著者网络 ===")
            
            # 生成合著者网络
            try:
                coauthor_network = analyzer.generate_coauthor_network(author_data)
                if not coauthor_network:
                    print("错误: 无法生成合著者网络")
                    coauthor_network_info = {"error": "无法生成合著者网络"}
                else:
                    # 将网络转换为可序列化的格式
                    coauthor_network_info = {
                        "nodes": [str(node) for node in coauthor_network.nodes()],
                        "edges": [(str(u), str(v)) for u, v in coauthor_network.edges()]
                    }
            except Exception as e:
                print(f"生成合著者网络时出错: {e}")
                coauthor_network_info = {"error": str(e)}
            
            # 保存合著者网络信息
            coauthor_network_file = os.path.join(step_output_dir, f"{base_name}_coauthor_network.json")
            with open(coauthor_network_file, 'w', encoding='utf-8') as f:
                json.dump(coauthor_network_info, f, ensure_ascii=False, indent=2)
            
            print(f"合著者网络信息已保存到 {coauthor_network_file}")
            
            return {
                "coauthor_stats": coauthor_stats,
                "coauthor_network": coauthor_network_info
            }
            
        elif step == '6':
            from server.services.scholar.analyzer import ScholarAnalyzer
            
            # 需要至少两个输入文件
            if not input_file:
                print("错误: 步骤6需要输入文件")
                return None
            
            # 解析输入文件路径
            input_files = input_file.split(',')
            if len(input_files) < 2:
                print("错误: 步骤6需要至少两个输入文件: author_data, pub_stats")
                return None
            
            author_data_file, pub_stats_file = input_files[:2]
            
            # 加载输入数据
            try:
                with open(author_data_file, 'r', encoding='utf-8') as f:
                    author_data = json.load(f)
                
                with open(pub_stats_file, 'r', encoding='utf-8') as f:
                    pub_stats = json.load(f)
            except Exception as e:
                print(f"加载输入文件时出错: {e}")
                return None
            
            # 初始化分析器
            analyzer = ScholarAnalyzer()
            
            print(f"\n=== 步骤 {step}: 计算学者评分 ===")
            
            # 计算学者评分
            rating = analyzer.calculate_researcher_rating(author_data, pub_stats)
            if not rating:
                print("错误: 无法计算学者评分")
                return None
            
            # 保存学者评分
            rating_file = os.path.join(step_output_dir, f"{base_name}_rating.json")
            with open(rating_file, 'w', encoding='utf-8') as f:
                json.dump(rating, f, ensure_ascii=False, indent=2)
            
            print(f"学者评分已保存到 {rating_file}")
            return rating
            
        elif step == '7':
            from server.services.scholar.data_fetcher import ScholarDataFetcher
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    coauthor_stats = json.load(f)
            else:
                print("错误: 步骤7需要输入文件")
                return None
            
            # 获取API令牌
            api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
            
            # 初始化数据获取器
            data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
            
            print(f"\n=== 步骤 {step}: 查找最常合作的合著者详情 ===")
            
            # 查找最常合作的合著者详情
            most_frequent_collaborator = None
            if coauthor_stats and 'top_coauthors' in coauthor_stats and coauthor_stats['top_coauthors']:
                try:
                    top_coauthor = coauthor_stats['top_coauthors'][0]
                    coauthor_name = top_coauthor['name']
                    best_paper_title = top_coauthor.get('best_paper', {}).get('title', '')
                    
                    # 使用最佳论文标题在Google Scholar上搜索该合著者以获取全名
                    coauthor_search_results = data_fetcher.search_author_by_name(coauthor_name, paper_title=best_paper_title)
                    
                    if coauthor_search_results:
                        # 获取第一个结果（最相关）
                        coauthor_id = coauthor_search_results[0]['scholar_id']
                        coauthor_details = data_fetcher.get_author_details_by_id(coauthor_id)
                        
                        if coauthor_details:
                            most_frequent_collaborator = {
                                'full_name': coauthor_details.get('full_name', coauthor_name),
                                'affiliation': coauthor_details.get('affiliation', 'Unknown'),
                                'research_interests': coauthor_details.get('research_interests', []),
                                'scholar_id': coauthor_id,
                                'coauthored_papers': top_coauthor['coauthored_papers'],
                                'best_paper': top_coauthor['best_paper'],
                                'h_index': coauthor_details.get('h_index', 'N/A'),
                                'total_citations': coauthor_details.get('total_citations', 'N/A')
                            }
                except Exception as e:
                    print(f"查找最常合作的合著者时出错: {e}")
                    most_frequent_collaborator = None
            
            # 如果没有找到最常合作的合著者，创建一个空的合著者对象
            if most_frequent_collaborator is None:
                print("未找到最常合作的合著者或出现错误。创建空的合著者对象。")
                most_frequent_collaborator = {
                    'full_name': '未找到常合作的合著者',
                    'affiliation': 'N/A',
                    'research_interests': [],
                    'scholar_id': '',
                    'coauthored_papers': 0,
                    'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
                    'h_index': 'N/A',
                    'total_citations': 'N/A'
                }
            
            # 保存最常合作的合著者详情
            collaborator_file = os.path.join(step_output_dir, f"{base_name}_collaborator.json")
            with open(collaborator_file, 'w', encoding='utf-8') as f:
                json.dump(most_frequent_collaborator, f, ensure_ascii=False, indent=2)
            
            print(f"最常合作的合著者详情已保存到 {collaborator_file}")
            return most_frequent_collaborator
            
        elif step == '8':
            from server.utils.kimi_evaluator import generate_critical_evaluation
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
            else:
                print("错误: 步骤8需要输入文件")
                return None
            
            print(f"\n=== 步骤 {step}: 生成批判性评价 ===")
            
            # 生成批判性评价
            try:
                print("生成批判性评价...")
                critical_evaluation = generate_critical_evaluation(report)
                print(f"批判性评价已生成: {critical_evaluation[:50]}...")
            except Exception as e:
                print(f"生成批判性评价时出错: {e}")
                critical_evaluation = "生成批判性评价时出错。"
            
            # 保存批判性评价
            evaluation_file = os.path.join(step_output_dir, f"{base_name}_evaluation.txt")
            with open(evaluation_file, 'w', encoding='utf-8') as f:
                f.write(critical_evaluation)
            
            print(f"批判性评价已保存到 {evaluation_file}")
            return critical_evaluation
            
        elif step == '9':
            from server.utils.find_arxiv import find_arxiv
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    pub_stats = json.load(f)
            else:
                print("错误: 步骤9需要输入文件")
                return None
            
            print(f"\n=== 步骤 {step}: 查找arxiv信息 ===")
            
            # 获取最被引用论文的标题
            most_cited_paper = pub_stats.get('most_cited_paper', {})
            title = most_cited_paper.get('title', '未知标题')
            
            # 查找arxiv信息
            try:
                print(f"查找论文的arxiv信息: {title}")
                most_cited_ai_paper = find_arxiv(title)
                print(f"arxiv信息已获取")
            except Exception as e:
                print(f"查找arxiv时出错: {e}")
                most_cited_ai_paper = {"name": title, "arxiv_url": "", "image": ""}
            
            # 保存arxiv信息
            arxiv_file = os.path.join(step_output_dir, f"{base_name}_arxiv.json")
            with open(arxiv_file, 'w', encoding='utf-8') as f:
                json.dump(most_cited_ai_paper, f, ensure_ascii=False, indent=2)
            
            print(f"arxiv信息已保存到 {arxiv_file}")
            return most_cited_ai_paper
            
        elif step == '10':
            from onepage.signature_news import get_latest_news
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    pub_stats = json.load(f)
            else:
                print("错误: 步骤10需要输入文件")
                return None
            
            print(f"\n=== 步骤 {step}: 获取论文新闻 ===")
            
            # 获取最被引用论文的标题
            most_cited_paper = pub_stats.get('most_cited_paper', {})
            title = most_cited_paper.get('title', '未知标题')
            
            # 获取论文新闻
            try:
                print(f"获取论文的新闻: {title}")
                news_info = get_latest_news(title)
                print(f"论文新闻信息已生成")
            except Exception as e:
                print(f"获取新闻信息时出错: {e}")
                news_info = "未找到相关新闻。"
            
            # 保存论文新闻信息
            news_file = os.path.join(step_output_dir, f"{base_name}_news.txt")
            with open(news_file, 'w', encoding='utf-8') as f:
                if isinstance(news_info, str):
                    f.write(news_info)
                else:
                    json.dump(news_info, f, ensure_ascii=False, indent=2)
            
            print(f"论文新闻信息已保存到 {news_file}")
            return news_info
            
        elif step == '11':
            from server.services.scholar.template_figure_kimi import get_template_figure
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
            else:
                print("错误: 步骤11需要输入文件")
                return None
            
            print(f"\n=== 步骤 {step}: 获取角色模型信息 ===")
            
            # 获取角色模型信息
            try:
                print("生成角色模型信息...")
                role_model = get_template_figure(report)
                print(f"角色模型信息已生成")
            except Exception as e:
                print(f"获取角色模型信息时出错: {e}")
                role_model = None
            
            if role_model:
                # 保存角色模型信息
                role_model_file = os.path.join(step_output_dir, f"{base_name}_role_model.json")
                with open(role_model_file, 'w', encoding='utf-8') as f:
                    json.dump(role_model, f, ensure_ascii=False, indent=2)
                
                print(f"角色模型信息已保存到 {role_model_file}")
            else:
                print("未生成角色模型信息")
            
            return role_model
            
        elif step == '12':
            from account.juris_people import three_card_juris_people
            
            # 加载输入数据
            if input_file:
                with open(input_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
            else:
                print("错误: 步骤12需要输入文件")
                return None
            
            print(f"\n=== 步骤 {step}: 获取职业水平信息 ===")
            
            # 获取职业水平信息
            try:
                # 检查报告中是否有足够的数据来生成职业水平信息
                pub_stats = report.get('publication_stats', {})
                if pub_stats.get('total_papers', 0) > 0:
                    print("生成职业水平信息...")
                    level_info = three_card_juris_people(report)
                    if not level_info:  # 如果level_info为None或空字典
                        level_info = {}
                    print(f"职业水平信息已生成")
                else:
                    # 如果没有足够的数据，创建一个默认的level_info
                    level_info = {
                        'level_cn': 'N/A (未找到论文)',
                        'level_us': 'N/A (未找到论文)',
                        'earnings': 'N/A',
                        'justification': '没有论文数据，无法确定职业水平'
                    }
            except Exception as e:
                print(f"获取职业水平信息时出错: {e}")
                level_info = {
                    'level_cn': 'N/A (错误)',
                    'level_us': 'N/A (错误)',
                    'earnings': 'N/A',
                    'justification': f'错误: {str(e)}'
                }
            
            # 保存职业水平信息
            level_info_file = os.path.join(step_output_dir, f"{base_name}_level_info.json")
            with open(level_info_file, 'w', encoding='utf-8') as f:
                json.dump(level_info, f, ensure_ascii=False, indent=2)
            
            print(f"职业水平信息已保存到 {level_info_file}")
            return level_info
            
        else:
            print(f"错误: 无效的步骤 '{step}'")
            return None
            
    except Exception as e:
        print(f"运行步骤 {step} 时出错:")
        traceback.print_exc()
        return None

def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description='针对特定步骤的测试')
    parser.add_argument('--name', type=str, help='学者名称')
    parser.add_argument('--id', type=str, help='Google Scholar ID')
    parser.add_argument('--url', type=str, help='Google Scholar URL')
    parser.add_argument('--step', type=str, required=True, help='要运行的步骤 (1, 1_2, 3, 4_5, 6, 7, 8, 9, 10, 11, 12)')
    parser.add_argument('--input-file', type=str, help='输入文件路径')
    parser.add_argument('--output-dir', type=str, default='reports/tests/steps', help='输出目录')
    
    args = parser.parse_args()
    
    # 验证步骤
    valid_steps = ['1', '1_2', '3', '4_5', '6', '7', '8', '9', '10', '11', '12']
    if args.step not in valid_steps:
        print(f"错误: 无效的步骤 '{args.step}'。有效的步骤: {', '.join(valid_steps)}")
        return
    
    # 运行测试
    run_step(args.step, args.name, args.id, args.url, args.input_file, args.output_dir)

if __name__ == "__main__":
    main()
