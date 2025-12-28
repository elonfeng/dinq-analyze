#!/usr/bin/env python3
"""
获取Google Scholar学者完整个人资料脚本

这个脚本用于获取指定学者ID的完整个人资料，包括最多500篇论文。
脚本会在第一页获取完整的个人资料信息，然后在后续页面只获取论文信息，
直到没有更多论文或达到最大论文数量限制。

使用方法：python fetch_full_scholar_profile.py [scholar_id]
默认学者ID：0VAe-TQAAAAJ
"""

import os
import time
import json
import copy
import logging
import argparse
import requests
from bs4 import BeautifulSoup
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scholar_profile_fetcher.log')
    ]
)
logger = logging.getLogger('scholar_profile_fetcher')

class ScholarProfileFetcher:
    """Google Scholar个人资料获取器"""

    def __init__(self, use_crawlbase=True, api_token=None):
        """
        初始化获取器

        Args:
            use_crawlbase: 是否使用Crawlbase API
            api_token: Crawlbase API令牌
        """
        self.use_crawlbase = use_crawlbase
        self.api_token = api_token

        # 如果没有提供API令牌，尝试从环境变量获取
        if self.use_crawlbase and not self.api_token:
            self.api_token = os.environ.get('CRAWLBASE_API_TOKEN')
            if not self.api_token:
                logger.warning("未提供Crawlbase API令牌，将尝试直接访问Google Scholar")
                self.use_crawlbase = False

    def fetch_html(self, url):
        """
        获取URL的HTML内容

        Args:
            url: 要获取的URL

        Returns:
            str: HTML内容，如果失败则返回None
        """
        try:
            if self.use_crawlbase and self.api_token:
                # 使用Crawlbase API
                crawlbase_url = f"https://api.crawlbase.com/?token={self.api_token}&url={url}"
                logger.info(f"通过Crawlbase获取URL: {url}")
                response = requests.get(crawlbase_url, timeout=60)
            else:
                # 直接获取
                logger.info(f"直接获取URL: {url}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"获取URL失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取URL时发生错误: {e}")
            return None

    def parse_google_scholar_html(self, html_content, start_index=0, first_page=True):
        """
        解析Google Scholar HTML内容

        Args:
            html_content: HTML内容
            start_index: 开始索引（用于分页）
            first_page: 是否是第一页，如果是则解析完整个人资料，否则只解析论文列表

        Returns:
            dict: 解析后的个人资料数据
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 获取基本信息
            profile = {}

            # 如果是第一页，获取完整的个人资料信息
            if first_page:
                # 获取姓名
                name_tag = soup.find('div', id='gsc_prf_in')
                if name_tag:
                    profile['name'] = name_tag.text.strip()

                # 获取头像
                img_tag = soup.find('img', id='gsc_prf_pup-img')
                if img_tag and 'src' in img_tag.attrs:
                    profile['avatar_url'] = img_tag['src']

                # 获取机构
                affiliation_tag = soup.find('div', class_='gsc_prf_il')
                if affiliation_tag:
                    profile['affiliation'] = affiliation_tag.text.strip()

                # 获取研究领域
                interests_container = soup.find('div', id='gsc_prf_int')
                if interests_container:
                    interests = []
                    for interest_tag in interests_container.find_all('a'):
                        interests.append(interest_tag.text.strip())
                    profile['interests'] = interests

                # 获取引用统计
                citation_stats = {}
                stats_table = soup.find('table', id='gsc_rsb_st')
                if stats_table:
                    rows = stats_table.find_all('tr')
                    for row in rows[1:]:  # 跳过表头
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            stat_name = cells[0].text.strip().lower().replace(' ', '_')
                            all_time = cells[1].text.strip()
                            since_2018 = cells[2].text.strip()
                            citation_stats[stat_name] = {
                                'all': all_time,
                                'since_2018': since_2018
                            }
                profile['citation_stats'] = citation_stats

            # 无论是否是第一页，都获取论文列表
            papers = []
            paper_rows = soup.find_all('tr', class_='gsc_a_tr')

            for i, row in enumerate(paper_rows):
                paper = {}

                # 标题和链接
                title_tag = row.find('a', class_='gsc_a_at')
                if title_tag:
                    paper['title'] = title_tag.text.strip()
                    if 'href' in title_tag.attrs:
                        paper['url'] = 'https://scholar.google.com' + title_tag['href']
                        # 从URL中提取论文ID
                        paper_id_match = re.search(r'citation_for_view=([^:]+)', paper['url'])
                        if paper_id_match:
                            paper['paper_id'] = paper_id_match.group(1)

                # 作者、期刊和年份
                metadata_div = row.find('div', class_='gs_gray')
                if metadata_div:
                    authors_text = metadata_div.text.strip()
                    paper['authors'] = [author.strip() for author in authors_text.split(',')]

                venue_div = row.find_all('div', class_='gs_gray')
                if len(venue_div) > 1:
                    paper['venue'] = venue_div[1].text.strip()

                # 年份
                year_tag = row.find('span', class_='gsc_a_h')
                if year_tag:
                    year_text = year_tag.text.strip()
                    if year_text and year_text.isdigit():
                        paper['year'] = year_text

                # 引用次数
                citation_tag = row.find('a', class_='gsc_a_ac')
                if citation_tag:
                    citation_text = citation_tag.text.strip()
                    if citation_text and citation_text.isdigit():
                        paper['num_citations'] = int(citation_text)
                    else:
                        paper['num_citations'] = 0

                # 添加索引信息（用于调试）
                paper['index'] = start_index + i

                papers.append(paper)

            profile['papers'] = papers
            profile['total_papers_fetched'] = len(papers)

            # 检查是否有下一页（通过检查是否有100篇论文）
            # Google Scholar每页最多显示100篇论文，如果当前页有100篇，则可能有下一页
            has_next_page = len(papers) == 100
            profile['has_next_page'] = has_next_page

            # 如果没有论文，则肯定没有下一页
            if len(papers) == 0:
                profile['has_next_page'] = False

            return profile

        except Exception as e:
            logger.error(f"解析HTML时发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_full_profile(self, scholar_id, max_papers=500):
        """
        获取学者的完整个人资料，包括多页论文

        Args:
            scholar_id: Google Scholar ID
            max_papers: 最大论文数量

        Returns:
            dict: 完整的个人资料
        """
        if not scholar_id:
            logger.error("未提供学者ID")
            return None

        logger.info(f"[Scholar ID: {scholar_id}] 开始获取完整个人资料（最多{max_papers}篇论文）")

        # 初始化结果
        full_profile = None
        papers_collected = 0
        current_page = 0
        start_index = 0

        while papers_collected < max_papers:
            # 构建URL（每页100篇论文）
            url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en&oi=ao&cstart={start_index}&pagesize=100"

            logger.info(f"[Scholar ID: {scholar_id}] 获取第{current_page+1}页（从索引{start_index}开始）")

            # 获取HTML内容
            max_retries = 3
            retry_count = 0
            html_content = None

            # 添加重试逻辑
            while retry_count < max_retries and not html_content:
                html_content = self.fetch_html(url)
                if not html_content:
                    retry_count += 1
                    logger.warning(f"[Scholar ID: {scholar_id}] 第{retry_count}次重试获取第{current_page+1}页")
                    time.sleep(2)

            if not html_content:
                logger.error(f"[Scholar ID: {scholar_id}] 在{max_retries}次重试后仍无法获取第{current_page+1}页")
                break

            # 解析HTML内容
            try:
                # 第一页获取完整个人资料，后续页面只获取论文
                is_first_page = (current_page == 0)
                page_data = self.parse_google_scholar_html(html_content, start_index, first_page=is_first_page)

                if not page_data:
                    logger.error(f"[Scholar ID: {scholar_id}] 无法解析第{current_page+1}页")
                    break

                # 如果是第一页，初始化完整个人资料
                if full_profile is None:
                    full_profile = copy.deepcopy(page_data)
                    papers_collected = len(full_profile.get('papers', []))
                    logger.info(f"[Scholar ID: {scholar_id}] 第{current_page+1}页获取了{papers_collected}篇论文")
                else:
                    # 如果不是第一页，只添加论文
                    new_papers = page_data.get('papers', [])

                    # 检查是否有新论文
                    if len(new_papers) == 0:
                        logger.info(f"[Scholar ID: {scholar_id}] 第{current_page+1}页没有论文，停止获取")
                        break

                    full_profile['papers'].extend(new_papers)
                    full_profile['total_papers_fetched'] = len(full_profile['papers'])

                    papers_collected += len(new_papers)
                    logger.info(f"[Scholar ID: {scholar_id}] 第{current_page+1}页获取了{len(new_papers)}篇论文，累计{papers_collected}篇")

                # 检查是否有下一页
                if not page_data.get('has_next_page', False):
                    logger.info(f"[Scholar ID: {scholar_id}] 没有更多页面")
                    break

                # 更新下一页的起始索引
                start_index += 100
                current_page += 1

                # 在请求之间添加延迟，避免被封
                time.sleep(3)

            except Exception as e:
                logger.error(f"[Scholar ID: {scholar_id}] 处理第{current_page+1}页时发生错误: {e}")
                import traceback
                logger.error(traceback.format_exc())
                break

        # 处理完成后，更新年份分布
        if full_profile:
            # 正确地统计年份分布
            years_of_papers = {}
            for paper in full_profile.get('papers', []):
                year = paper.get('year', '')
                if year and year.strip() and year.strip().isdigit():
                    year = int(year.strip())
                    years_of_papers[year] = years_of_papers.get(year, 0) + 1

            # 确保字段名称使用 years_of_papers
            full_profile['years_of_papers'] = years_of_papers

            logger.info(f"[Scholar ID: {scholar_id}] 论文年份分布:")
            for year in sorted(years_of_papers.keys()):
                logger.info(f"[Scholar ID: {scholar_id}] {year}年: {years_of_papers[year]}篇论文")

            logger.info(f"[Scholar ID: {scholar_id}] 成功获取完整个人资料，共{len(full_profile.get('papers', []))}篇论文")

        return full_profile

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='获取Google Scholar学者完整个人资料')
    parser.add_argument('scholar_id', nargs='?', default='0VAe-TQAAAAJ', help='Google Scholar ID（默认：0VAe-TQAAAAJ）')
    parser.add_argument('--max-papers', type=int, default=500, help='最大论文数量（默认：500）')
    parser.add_argument('--api-token', help='Crawlbase API令牌')
    parser.add_argument('--no-crawlbase', action='store_true', help='不使用Crawlbase API')
    parser.add_argument('--output', default='scholar_profile.json', help='输出文件名（默认：scholar_profile.json）')

    args = parser.parse_args()

    # 创建获取器
    fetcher = ScholarProfileFetcher(
        use_crawlbase=not args.no_crawlbase,
        api_token=args.api_token
    )

    # 获取完整个人资料
    profile = fetcher.get_full_profile(args.scholar_id, args.max_papers)

    if profile:
        # 保存到文件
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

        logger.info(f"个人资料已保存到 {args.output}")

        # 打印摘要
        print("\n个人资料摘要:")
        print(f"姓名: {profile.get('name', 'N/A')}")
        print(f"机构: {profile.get('affiliation', 'N/A')}")
        print(f"研究领域: {', '.join(profile.get('interests', []))}")
        print(f"论文数量: {len(profile.get('papers', []))}")
        print(f"总引用次数: {profile.get('citation_stats', {}).get('citations', {}).get('all', 'N/A')}")

        # 打印前5篇论文
        print("\n前5篇论文:")
        for i, paper in enumerate(profile.get('papers', [])[:5]):
            print(f"{i+1}. {paper.get('title', 'N/A')} ({paper.get('year', 'N/A')}) - 引用: {paper.get('num_citations', 0)}")
    else:
        logger.error("获取个人资料失败")

if __name__ == "__main__":
    main()
