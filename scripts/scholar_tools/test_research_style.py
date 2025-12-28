#!/usr/bin/env python3
"""
测试研究风格评估

这个脚本用于测试研究风格评估的功能，包括深度与广度、理论与实践、个人与团队三个维度。
"""

import os
import sys
import json
import logging
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 获取日志记录器
logger = logging.getLogger('test_research_style')

# 导入职级评估函数
from account.juris_people import three_card_juris_people
from server.services.scholar.career_level_service import process_research_style

def test_research_style(scholar_id, output_file=None):
    """
    测试研究风格评估
    
    Args:
        scholar_id: Google Scholar ID
        output_file: 输出文件名
    """
    logger.info(f"测试研究风格评估，Scholar ID: {scholar_id}")
    
    # 从缓存获取数据
    from server.api.scholar.db_cache import get_scholar_from_cache
    cached_data = get_scholar_from_cache(scholar_id)
    if not cached_data:
        logger.error(f"缓存中没有找到Scholar ID: {scholar_id}的数据")
        return
    
    logger.info("从缓存获取到数据，开始评估研究风格")
    
    # 获取职级信息
    level_info = three_card_juris_people(cached_data)
    if not level_info:
        logger.error("无法获取职级信息")
        return
    
    # 处理研究风格信息
    process_research_style(cached_data, level_info)
    
    # 输出研究风格信息
    research_style = cached_data.get('research_style', {})
    logger.info("研究风格评估结果:")
    
    # 深度与广度
    depth_vs_breadth = research_style.get('depth_vs_breadth', {})
    if isinstance(depth_vs_breadth, dict):
        score = depth_vs_breadth.get('score', 'N/A')
        explanation = depth_vs_breadth.get('explanation', 'No explanation provided')
        logger.info(f"深度与广度 (0=非常广泛, 10=非常深入): {score}")
        logger.info(f"解释: {explanation}")
    else:
        logger.info(f"深度与广度 (0=非常广泛, 10=非常深入): {depth_vs_breadth}")
    
    # 理论与实践
    theory_vs_practice = research_style.get('theory_vs_practice', {})
    if isinstance(theory_vs_practice, dict):
        score = theory_vs_practice.get('score', 'N/A')
        explanation = theory_vs_practice.get('explanation', 'No explanation provided')
        logger.info(f"理论与实践 (0=非常实践, 10=非常理论): {score}")
        logger.info(f"解释: {explanation}")
    else:
        logger.info(f"理论与实践 (0=非常实践, 10=非常理论): {theory_vs_practice}")
    
    # 个人与团队
    individual_vs_team = research_style.get('individual_vs_team', {})
    if isinstance(individual_vs_team, dict):
        score = individual_vs_team.get('score', 'N/A')
        explanation = individual_vs_team.get('explanation', 'No explanation provided')
        logger.info(f"个人与团队 (0=非常个人, 10=非常团队): {score}")
        logger.info(f"解释: {explanation}")
    else:
        logger.info(f"个人与团队 (0=非常个人, 10=非常团队): {individual_vs_team}")
    
    # 保存结果到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'scholar_id': scholar_id,
                'research_style': research_style
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"研究风格评估结果已保存到: {output_file}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='测试研究风格评估')
    parser.add_argument('scholar_id', help='Google Scholar ID')
    parser.add_argument('--output', help='输出文件名')
    
    args = parser.parse_args()
    
    # 测试研究风格评估
    test_research_style(args.scholar_id, args.output)

if __name__ == "__main__":
    main()
