#!/usr/bin/env python3
"""
测试缓存验证器

这个脚本用于测试缓存验证器的功能，验证并补全缓存数据。
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
logger = logging.getLogger('test_cache_validator')

# 导入缓存验证器
from server.services.scholar.cache_validator import validate_and_complete_cache

# 导入数据获取器和分析器
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.analyzer import ScholarAnalyzer

# 导入缓存函数
from server.api.scholar.db_cache import get_scholar_from_cache, save_scholar_to_cache

def test_cache_validator(scholar_id, max_age_days=3, use_crawlbase=True, api_token=None):
    """
    测试缓存验证器

    Args:
        scholar_id: Google Scholar ID
        max_age_days: 缓存最大有效期（天）
        use_crawlbase: 是否使用Crawlbase API
        api_token: Crawlbase API令牌
    """
    logger.info(f"测试缓存验证器，Scholar ID: {scholar_id}")

    # 初始化数据获取器和分析器
    data_fetcher = ScholarDataFetcher(use_crawlbase=use_crawlbase, api_token=api_token)
    analyzer = ScholarAnalyzer()

    # 从缓存获取数据
    cached_data = get_scholar_from_cache(scholar_id, max_age_days)
    if not cached_data:
        logger.error(f"缓存中没有找到Scholar ID: {scholar_id}的数据")
        return

    logger.info("从缓存获取到数据，开始验证和补全")

    # 验证并补全缓存数据
    validated_data = validate_and_complete_cache(cached_data, data_fetcher, analyzer)

    # 检查数据是否被修改
    if validated_data != cached_data:
        logger.info("缓存数据已被修改和补全")

        # 保存修改后的数据到缓存
        logger.info("保存修改后的数据到缓存")
        save_scholar_to_cache(validated_data, scholar_id)

        # 输出修改前后的差异
        logger.info("修改前后的差异:")

        # 检查最佳合作者
        if validated_data.get('most_frequent_collaborator') != cached_data.get('most_frequent_collaborator'):
            logger.info("最佳合作者数据已更新")

            # 检查是否使用了coauthor_stats中的数据
            if ('coauthor_stats' in cached_data and 'most_frequent_collaborator' in cached_data['coauthor_stats'] and
                validated_data.get('most_frequent_collaborator', {}).get('full_name') ==
                cached_data.get('coauthor_stats', {}).get('most_frequent_collaborator', {}).get('name')):
                logger.info("使用了coauthor_stats中的最佳合作者数据")

            # 输出更新前后的差异
            old_collaborator = cached_data.get('most_frequent_collaborator', {})
            new_collaborator = validated_data.get('most_frequent_collaborator', {})

            logger.info("更新前:")
            if 'full_name' in old_collaborator:
                logger.info(f"  姓名: {old_collaborator.get('full_name')}")
            elif 'name' in old_collaborator:
                logger.info(f"  姓名: {old_collaborator.get('name')}")
            logger.info(f"  合著论文数: {old_collaborator.get('coauthored_papers')}")

            logger.info("更新后:")
            if 'full_name' in new_collaborator:
                logger.info(f"  姓名: {new_collaborator.get('full_name')}")
            elif 'name' in new_collaborator:
                logger.info(f"  姓名: {new_collaborator.get('name')}")
            logger.info(f"  合著论文数: {new_collaborator.get('coauthored_papers')}")

        # 检查角色模型
        if validated_data.get('role_model') != cached_data.get('role_model'):
            logger.info("角色模型数据已更新")

        # 检查学者评价
        if validated_data.get('critical_evaluation') != cached_data.get('critical_evaluation'):
            logger.info("学者评价已更新")

        # 检查论文新闻
        if validated_data.get('paper_news') != cached_data.get('paper_news'):
            logger.info("论文新闻已更新")
    else:
        logger.info("缓存数据已验证，无需修改")

    # 保存验证后的数据到文件
    output_file = f"{scholar_id}_validated.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(validated_data, f, ensure_ascii=False, indent=2)

    logger.info(f"验证后的数据已保存到: {output_file}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='测试缓存验证器')
    parser.add_argument('scholar_id', help='Google Scholar ID')
    parser.add_argument('--max-age-days', type=int, default=3, help='缓存最大有效期（天）')
    parser.add_argument('--no-crawlbase', action='store_true', help='不使用Crawlbase API')
    parser.add_argument('--api-token', help='Crawlbase API令牌')

    args = parser.parse_args()

    # 导入API密钥
    if not args.api_token and not args.no_crawlbase:
        try:
            from server.config.api_keys import API_KEYS
            api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')
        except ImportError:
            logger.warning("无法导入API密钥，将不使用Crawlbase API")
            api_token = None
    else:
        api_token = args.api_token

    # 测试缓存验证器
    test_cache_validator(
        args.scholar_id,
        max_age_days=args.max_age_days,
        use_crawlbase=not args.no_crawlbase,
        api_token=api_token
    )

if __name__ == "__main__":
    main()
