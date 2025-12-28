"""
Career Level Service

This module handles the generation and management of career level information for researchers.
It provides functions to determine researcher's career level, earnings, and research style.
"""

import logging
from typing import Dict, Any, Optional, Callable

# 获取日志记录器
logger = logging.getLogger('server.services.scholar.career_level_service')

# 导入职级评估函数
from account.juris_people import three_card_juris_people
from server.services.scholar.status_reporter import send_status

def get_career_level_info(report: Dict[str, Any], from_cache: bool = False, callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    获取研究者的职业水平信息。

    首先检查缓存，如果没有则调用评估函数获取职级信息。
    同时处理研究风格信息的提取。

    Args:
        report: 包含研究者信息的报告字典
        from_cache: 数据是否来自缓存
        callback: 可选的状态回调函数

    Returns:
        包含职级信息的字典
    """
    # 如果数据来自缓存，并且已经包含了level_info信息，就不需要再查询了
    if from_cache and 'level_info' in report:
        level_info = report.get('level_info', {})
        if not level_info:  # 如果level_info为None或空字典
            level_info = {}
        logger.info("Using cached career level information")
    else:
        # 获取出版统计信息
        pub_stats = report.get('publication_stats', {})

        # 获取职业水平信息
        try:
            # 检查报告中是否有足够的数据来生成职业水平信息
            if pub_stats.get('total_papers', 0) > 0:
                send_status("Calculating career level information...", callback)
                level_info = three_card_juris_people(report)
                if not level_info:  # 如果level_info为None或空字典
                    level_info = {}
                    logger.warning("three_card_juris_people returned empty result")
            else:
                # 如果没有足够的数据，创建一个默认的level_info
                level_info = create_default_level_info("No papers found")
                logger.info("No papers found, using default level info")

            # 将结果保存到报告中，便于缓存
            report['level_info'] = level_info

            # 处理研究风格信息
            process_research_style(report, level_info)

        except Exception as e:
            logger.error(f"Error getting career level information: {e}", exc_info=True)
            send_status(f"Error getting career level information: {e}", callback)
            level_info = create_default_level_info(f"Error: {str(e)}")
            report['level_info'] = level_info

    return level_info

def create_default_level_info(reason: str) -> Dict[str, Any]:
    """
    创建默认的职级信息字典。

    当无法获取真实职级信息时使用。

    Args:
        reason: 无法获取职级信息的原因

    Returns:
        默认的职级信息字典
    """
    return {
        'level_cn': f'N/A ({reason})',
        'level_us': f'N/A ({reason})',
        'earnings': 'N/A',
        'justification': f'Cannot determine career level: {reason}'
    }

def process_research_style(report: Dict[str, Any], level_info: Dict[str, Any]) -> None:
    """
    从职级信息中提取研究风格数据并添加到报告中。

    Args:
        report: 研究者报告字典，将被修改
        level_info: 职级信息字典
    """
    # 创建默认的研究风格评估
    default_research_style = {
        'depth_vs_breadth': {
            'score': 5,
            'explanation': 'Based on available publication data, the researcher shows a balanced approach between depth and breadth in their research focus.'
        },
        'theory_vs_practice': {
            'score': 5,
            'explanation': 'The researcher demonstrates a balance between theoretical contributions and practical applications in their published work.'
        },
        'individual_vs_team': {
            'score': 5,
            'explanation': 'Publication patterns suggest the researcher balances individual work and collaborative research with various team sizes.'
        },
        'justification': level_info.get('justification', 'Analysis based on available publication data and research patterns.')
    }

    # 如果有evaluation_bars数据，将其设置到research_style字段中
    if level_info and 'evaluation_bars' in level_info:
        evaluation_bars = level_info['evaluation_bars']
        logger.info(f"Setting research_style from evaluation_bars: {evaluation_bars}")

        # 创建研究风格字典，包含详细的解释
        research_style = {
            'depth_vs_breadth': {
                'score': evaluation_bars.get('depth_vs_breadth', {}).get('score', 5),
                'explanation': evaluation_bars.get('depth_vs_breadth', {}).get('explanation', default_research_style['depth_vs_breadth']['explanation'])
            },
            'theory_vs_practice': {
                'score': evaluation_bars.get('theory_vs_practice', {}).get('score', 5),
                'explanation': evaluation_bars.get('theory_vs_practice', {}).get('explanation', default_research_style['theory_vs_practice']['explanation'])
            },
            'individual_vs_team': {
                'score': evaluation_bars.get('individual_vs_team', {}).get('score', 5),
                'explanation': evaluation_bars.get('individual_vs_team', {}).get('explanation', default_research_style['individual_vs_team']['explanation'])
            },
            'justification': level_info.get('justification', default_research_style['justification'])
        }

        # 检查并替换任何"No data"或空解释
        for dimension in ['depth_vs_breadth', 'theory_vs_practice', 'individual_vs_team']:
            if (research_style[dimension]['explanation'] == 'No data' or
                research_style[dimension]['explanation'] == 'No explanation provided' or
                not research_style[dimension]['explanation']):
                research_style[dimension]['explanation'] = default_research_style[dimension]['explanation']

        # 设置到报告中
        report['research_style'] = research_style
        logger.info(f"Set research_style in report: {research_style}")
    else:
        logger.info("No evaluation_bars found in level_info, creating default research_style")
        # 如果没有评估条数据，使用默认值
        report['research_style'] = default_research_style
        logger.info(f"Set default research_style in report: {default_research_style}")
