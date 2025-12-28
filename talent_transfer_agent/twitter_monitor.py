import requests
import time
import sys
import os
import json
import logging
from datetime import datetime, timedelta, timezone
from tavily import TavilyClient
from typing import Dict, Any, List, Optional
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server.services.scholar.scholar_service import ScholarService, run_scholar_analysis
from src.utils.talent_move_repository import TalentMoveRepository
from talent_transfer_agent.ai_talent_analyzer import analyze_tweet_with_ai,enhance_talent_info_with_websearch
from server.services.scholar.data_fetcher import ScholarDataFetcher

# 配置日志
def setup_logger():
    """设置日志记录器"""
    logger = logging.getLogger('talent_monitor')
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    log_file = os.path.join(os.getcwd(), 'talent_monitor.log')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 初始化日志记录器
logger = setup_logger()

API_KEY = "8c75b8be78064a8688e89a94ad602d3a"
TARGET_ACCOUNTS = [
                   "tbpn","theinformation"
                   ]  # 可配置多个账号
TARGET_QUERIES = [
    # "join OpenAI","join DeepMind",
                #   "joined Meta"
                #   ,"poaching AI","join Google","join Anthropic","join Microsoft"
                #   ,"hires Meta scientist","researcher joins Google",
                #   "hires Anthropic researcher","Microsoft hires researcher","former OpenAI joins",
                #   "ex-Meta researcher hired","former Google scientist","ex-Anthropic joins","former DeepMind researcher",
                #   "head of AI hired","hires chief scientist","AI research director joins"
                  ]  # 可配置多个账号
CHECK_INTERVAL = 24*60*60  # 24小时检查一次

class TwitterMonitor:
    def __init__(self):
        self.repo = TalentMoveRepository()
        self.api_key = API_KEY
        self.target_accounts = TARGET_ACCOUNTS
        self.target_queries = TARGET_QUERIES
        self.check_interval = CHECK_INTERVAL
        # 初始化HTML获取器
        crawlbase_token = os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""
        self.data_fetcher = ScholarDataFetcher(use_crawlbase=bool(crawlbase_token), api_token=crawlbase_token or None)
        # 记录已处理的推文URL，避免重复处理
        self.processed_tweets = set()
        # 记录上次运行时间
        self.last_run_time = None
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        self.tvly_client = TavilyClient(tavily_key) if tavily_key else None
        self.scholar_service = ScholarService(use_crawlbase=bool(crawlbase_token), api_token=crawlbase_token or None)
    
    def load_processed_tweets(self):
        """从文件加载已处理的推文URL"""
        try:
            if os.path.exists('processed_tweets.json'):
                with open('processed_tweets.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed_tweets = set(data.get('processed_tweets', []))
                    self.last_run_time = datetime.fromisoformat(data.get('last_run_time', datetime.now().isoformat()))
                    print(f"加载了 {len(self.processed_tweets)} 条已处理的推文")
                    print(f"上次运行时间: {self.last_run_time}")
        except Exception as e:
            print(f"加载已处理推文失败: {e}")
            self.processed_tweets = set()
            self.last_run_time = None
    
    def save_processed_tweets(self):
        """保存已处理的推文URL到文件"""
        try:
            data = {
                'processed_tweets': list(self.processed_tweets),
                'last_run_time': datetime.now().isoformat()
            }
            with open('processed_tweets.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"保存了 {len(self.processed_tweets)} 条已处理的推文")
        except Exception as e:
            print(f"保存已处理推文失败: {e}")
    
    def get_today_time_range(self):
        """获取今天的时间范围（UTC）"""
        now = datetime.now(timezone.utc)
        # 获取今天的开始时间（00:00:00 UTC）
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # 获取今天的结束时间（23:59:59 UTC）
        today_end = today_start + timedelta(days=1) - timedelta(seconds=1)
        
        print(f"今天时间范围: {today_start} 到 {today_end}")
        return today_start, today_end
    
    def get_last_run_time_range(self):
        """获取上次运行时间到现在的范围"""
        if self.last_run_time is None:
            # 如果没有上次运行记录，使用今天的时间范围
            return self.get_today_time_range()
        
        now = datetime.now(timezone.utc)
        # 确保last_run_time是UTC时间
        if self.last_run_time.tzinfo is None:
            self.last_run_time = self.last_run_time.replace(tzinfo=timezone.utc)
        
        print(f"上次运行时间: {self.last_run_time}")
        print(f"当前时间: {now}")
        return self.last_run_time, now
    
    def simplify_tweet_data(self, tweets):
        """简化推文数据，只保留必要字段"""
        simplified_tweets = []
        for tweet in tweets:
            simplified_tweet = {
                "text": tweet.get("text", ""),
                "created_at": tweet.get("createdAt", ""),
                "url": tweet.get("url", "")
            }
            simplified_tweets.append(simplified_tweet)
        return simplified_tweets
    
    def save_tweets_to_file(self, account, tweets, query, since_str, until_str):
        """保存推文数据到本地JSON文件"""
        if not tweets:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"twitter_data_{account}_{timestamp}.json"
        
        # 确保data目录存在
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        filepath = os.path.join(data_dir, filename)
        
        # 简化推文数据
        simplified_tweets = self.simplify_tweet_data(tweets)
        
        # 构建保存数据
        save_data = {
            "account": account,
            "query": query,
            "since_time": since_str,
            "until_time": until_str,
            "total_tweets": len(tweets),
            "fetch_time": datetime.now().isoformat(),
            "tweets": simplified_tweets
        }
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"查询结果已保存到: {filepath}")
        print(f"共保存 {len(tweets)} 条推文")
    
    def fetch_new_tweets(self, account, query, since_time, until_time):
        """获取指定账号的新推文"""
        url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
        
        # 构建查询参数 - 修正时间格式
        since_str = since_time.strftime("%Y-%m-%d")
        until_str = until_time.strftime("%Y-%m-%d")
        
        if account:
            search_query = f"from:{account}"
        else:
            search_query = f"\"{query}\""
        
        # 添加时间范围到查询
        full_query = f"{search_query} since:{since_str} until:{until_str}"
        
        params = {"query": full_query, "queryType": "Latest"}
        headers = {"X-API-Key": self.api_key}
        print(f"查询语句: {full_query}")
        
        all_tweets = []
        next_cursor = ""
        
        # 分页获取所有推文
        while True:
            if next_cursor:
                params["cursor"] = next_cursor
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                tweets = data.get("tweets", [])
                
                if tweets:
                    all_tweets.extend(tweets)
                
                if data.get("has_next_page", False) and data.get("next_cursor"):
                    next_cursor = data.get("next_cursor")
                    continue
                else:
                    break
            else:
                print(f"Error: {response.status_code} - {response.text}")
                break
        
        # 保存推文到文件（可选）
        # self.save_tweets_to_file(account, all_tweets, query, since_str, until_str)
        
        return all_tweets
    
    def fetch_tweet_user_info(self, person_name):
        """获取指定用户的信息"""
        url = "https://api.twitterapi.io/twitter/user/search"
        
        params = {"query": person_name}
        headers = {"X-API-Key": self.api_key}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            users = data.get("users", [])
            if users:
                return users[0]
            else:
                return None
        else:
            return None
    
    def is_tweet_already_processed(self, tweet_url):
        """检查推文是否已经处理过"""
        return tweet_url in self.processed_tweets
    
    def mark_tweet_as_processed(self, tweet_url):
        """标记推文为已处理"""
        self.processed_tweets.add(tweet_url)
    
    def get_company_logo_url(self, company_name):
        """获取公司logo URL"""
        if not company_name:
            return None
        
        # 转换公司名为文件名格式（小写，空格转下划线）
        filename = company_name.lower().replace(' ', '_')
        
        # 检查当前目录下的 images/company 文件夹
        import os
        import glob
        
        company_images_dir = os.path.join(os.getcwd(), 'images', 'company')
        if os.path.exists(company_images_dir):
            # 查找匹配的图片文件
            pattern = os.path.join(company_images_dir, f"{filename}.*")
            matching_files = glob.glob(pattern)
            if matching_files:
                # 获取第一个匹配的文件
                file_path = matching_files[0]
                file_name = os.path.basename(file_path)
                return f"https://api.dinq.io/images/company/{file_name}"
        
        return None

    def get_school_logo_url(self, school_name):
        """获取学校logo URL"""
        if not school_name:
            return None
        
        # 转换学校名为文件名格式（小写，空格转下划线）
        filename = school_name.lower().replace(' ', '_')
        
        # 检查当前目录下的 images/school 文件夹
        import os
        import glob
        
        school_images_dir = os.path.join(os.getcwd(), 'images', 'school')
        if os.path.exists(school_images_dir):
            # 查找匹配的图片文件
            pattern = os.path.join(school_images_dir, f"{filename}.*")
            matching_files = glob.glob(pattern)
            if matching_files:
                # 获取第一个匹配的文件
                file_path = matching_files[0]
                file_name = os.path.basename(file_path)
                return f"https://api.dinq.io/images/school/{file_name}"
        
        return None

    def get_linkedin_data(self, person_name: str) -> Optional[Dict[str, Any]]:
        """获取LinkedIn数据"""
        try:
            from server.api.linkedin_analyzer_api import get_linkedin_analyzer
            linkedin_analyzer = get_linkedin_analyzer()

            # 搜索LinkedIn URL
            linkedin_results = linkedin_analyzer.search_linkedin_url(person_name)
            if linkedin_results and len(linkedin_results) > 0:
                linkedin_url = linkedin_results[0]['url']
                # 获取LinkedIn档案数据
                profile_data = linkedin_analyzer.get_linkedin_profile(linkedin_url)
                if profile_data:
                    logger.info(f"成功获取LinkedIn数据: {person_name}")
                    return profile_data
                else:
                    logger.warning(f"LinkedIn档案获取失败: {person_name}")
            else:
                logger.warning(f"未找到LinkedIn URL: {person_name}")
        except Exception as e:
            logger.error(f"LinkedIn数据获取失败: {person_name}, 错误: {e}")

        return None

    def convert_linkedin_to_talent_format(self, linkedin_profile: Dict[str, Any], from_company: str, to_company: str) -> Dict[str, Any]:
        """将LinkedIn数据转换为talent_move格式"""
        try:
            # 工作经历转换
            work_experience = []
            for exp in linkedin_profile.get('experiences', []):
                company_name = exp.get('subtitle', '').split('·')[0].strip() if exp.get('subtitle') else ''
                position = exp.get('title', '')
                duration = exp.get('caption', '')
                location = exp.get('metadata', '')
                company_logo = exp.get('logo', '')

                # 处理breakdown情况（多个子职位）- 只取第一个子分支
                if exp.get('breakdown') and exp.get('subComponents') and len(exp.get('subComponents', [])) > 0:
                    first_sub = exp.get('subComponents', [])[0]  # 只取第一个子分支
                    work_experience.append({
                        'company': company_name,
                        'position': first_sub.get('title', position),  # 使用第一个子分支的职位
                        'duration': first_sub.get('caption', duration),
                        'location': location,
                        'company_logo_url': company_logo  # 直接使用LinkedIn的logo
                    })
                else:
                    work_experience.append({
                        'company': company_name,
                        'position': position,
                        'duration': duration,
                        'location': location,
                        'company_logo_url': company_logo  # 直接使用LinkedIn的logo
                    })

            # 教育背景转换
            education = []
            for edu in linkedin_profile.get('educations', []):
                education.append({
                    'school': edu.get('title', ''),
                    'degree': edu.get('subtitle', ''),
                    'time': edu.get('caption', ''),
                    'school_logo_url': edu.get('logo', '')  # 直接使用LinkedIn的logo
                })

            # 人才描述
            headline = linkedin_profile.get('headline', '')
            about = linkedin_profile.get('about', '')
            talent_description = headline
            if about:
                talent_description += f". {about}..."

            return {
                'avatar_url': linkedin_profile.get('profilePic', '') or linkedin_profile.get('profilePicHighQuality', ''),
                'talent_description': talent_description,
                'work_experience': json.dumps(work_experience, ensure_ascii=False),
                'education': json.dumps(education, ensure_ascii=False)
            }

        except Exception as e:
            logger.error(f"LinkedIn数据转换失败: {e}")
            return {}

    def process_person_move(self, person_name, from_company, to_company, salary, tweet_text, tweet_url, post_image_url, account, created_at, like_count=0):
        """处理单个人才流动信息"""
        # 获取LinkedIn数据并转换
        linkedin_data = self.get_linkedin_data(person_name)
        linkedin_converted = {}
        if linkedin_data:
            linkedin_converted = self.convert_linkedin_to_talent_format(linkedin_data, from_company, to_company)

        # 使用Tavily搜索Google Scholar ID,对结果进行谷歌学术过滤
        response = self.tvly_client.search(
            query=person_name
        )
        scholar_id = self.scholar_service.extract_scholar_id_from_tavily_response(response)
        if not scholar_id:
            return False
        
        # 新增：LinkedIn数据获取
        linkedin_data = None
        try:
            from server.linkedin_analyzer.analyzer import LinkedInAnalyzer
            linkedin_analyzer = LinkedInAnalyzer(use_crawlbase=bool(crawlbase_token), api_token=crawlbase_token or None)
            
            # 搜索LinkedIn URL
            linkedin_results = linkedin_analyzer.search_linkedin_url(person_name)
            if linkedin_results and len(linkedin_results) > 0:
                linkedin_url = linkedin_results[0]['url']
                # 获取LinkedIn档案数据
                profile_data = linkedin_analyzer.get_linkedin_profile(linkedin_url)
                if profile_data:
                    linkedin_data = profile_data
                    logger.info(f"成功获取LinkedIn数据: {person_name}")
                else:
                    logger.warning(f"LinkedIn档案获取失败: {person_name}")
            else:
                logger.warning(f"未找到LinkedIn URL: {person_name}")
        except Exception as e:
            logger.error(f"LinkedIn数据获取失败: {person_name}, 错误: {e}")
            
        user_info = self.fetch_tweet_user_info(person_name)
        avatar_url = ""
        
        # 优先使用LinkedIn头像，如果没有则使用Twitter头像
        if linkedin_data:
            linkedin_avatar = linkedin_data.get('profilePic')
            if linkedin_avatar:
                avatar_url = linkedin_avatar
                logger.info(f"使用LinkedIn头像: {person_name}")
            elif user_info:
                avatar_url = user_info.get('profile_image_url_https')
                logger.info(f"LinkedIn无头像，使用Twitter头像: {person_name}")
        elif user_info:
            avatar_url = user_info.get('profile_image_url_https')
            logger.info(f"无LinkedIn数据，使用Twitter头像: {person_name}")

        # AI信息增强（基于LinkedIn数据）
        enhanced_info = enhance_talent_info_with_websearch(
            person_name, from_company, to_company, salary, tweet_text,
            linkedin_data=linkedin_data
        )

        # 确保enhanced_info不为None
        if enhanced_info is None:
            enhanced_info = {
                'salary': salary,
                'talent_description': f"{person_name} moved from {from_company} to {to_company}. {tweet_text}",
                'age': 30,
                'education': '[{"school": "Unknown University", "major": "Unknown", "time": "Unknown"}]',
                'work_experience': f'[{{"company": "{from_company}", "position": "Unknown Position", "duration": "Unknown"}}]',
                'major_achievement': f'[{{"title": "Career Move", "description": "{person_name} moved from {from_company} to {to_company}"}}]'
            }
            logger.warning(f"AI增强失败，使用默认数据: {person_name}")

        # 获取公司logo URL
        from_company_logo_url = self.get_company_logo_url(from_company) or ""
        to_company_logo_url = self.get_company_logo_url(to_company) or ""

        # 处理教育信息，添加学校logo URL
        import json
        education_data = enhanced_info.get('education', "[{\"school\": \"Top University\", \"major\": \"Computer Science\", \"time\": \"2015-2019\"}]")
        try:
            education_list = json.loads(education_data)
            for edu in education_list:
                if 'school' in edu:
                    school_logo_url = self.get_school_logo_url(edu['school'])
                    if school_logo_url:
                        edu['school_logo_url'] = school_logo_url
            education_data = json.dumps(education_list)
        except:
            pass  # 如果JSON解析失败，保持原样

        # 处理工作经验信息，添加公司logo URL
        work_experience_data = enhanced_info.get('work_experience', '{"from": "2020", "to": "2024", "company": "' + from_company + '", "position": "Senior Position"}')
        try:
            work_list = json.loads(work_experience_data)
            for work in work_list:
                if 'company' in work:
                    company_logo_url = self.get_company_logo_url(work['company'])
                    if company_logo_url:
                        work['company_logo_url'] = company_logo_url
            work_experience_data = json.dumps(work_list)
        except:
            pass  # 如果JSON解析失败，保持原样

        # 使用转换后的LinkedIn数据，优先级：LinkedIn转换数据 > AI数据
        import json

        # 确保linkedin_converted不为None
        if linkedin_converted is None:
            linkedin_converted = {}

        # 教育信息
        if linkedin_converted.get('education'):
            final_education = linkedin_converted['education']
            logger.info(f"使用LinkedIn教育数据: {person_name}")
        else:
            final_education = education_data
            logger.info(f"使用AI教育数据: {person_name}")

        # 工作经历
        if linkedin_converted.get('work_experience'):
            final_work_experience = linkedin_converted['work_experience']
            logger.info(f"使用LinkedIn工作经历数据: {person_name}")
        else:
            final_work_experience = work_experience_data
            logger.info(f"使用AI工作经历数据: {person_name}")

        # 头像
        if linkedin_converted.get('avatar_url'):
            final_avatar_url = linkedin_converted['avatar_url']
            logger.info(f"使用LinkedIn头像: {person_name}")
        else:
            final_avatar_url = avatar_url
            logger.info(f"使用默认头像: {person_name}")

        # 人才描述
        if linkedin_converted.get('talent_description'):
            final_talent_description = linkedin_converted['talent_description']
            logger.info(f"使用LinkedIn人才描述: {person_name}")
        else:
            final_talent_description = enhanced_info.get('talent_description', f"{person_name} moved from {from_company} to {to_company}. {tweet_text}")
            logger.info(f"使用AI人才描述: {person_name}")

        move_data = {
            "person_name": person_name,
            "from_company": from_company,
            "to_company": to_company,
            "salary": enhanced_info.get('salary', salary),
            "avatar_url": final_avatar_url,
            "post_image_url": post_image_url,
            "tweet_url": tweet_url,
            "created_at": created_at,
            "query": account,
            "talent_description": final_talent_description,
            "age": enhanced_info.get('age', 30),
            "work_experience": final_work_experience,
            "education": final_education,
            "major_achievement": enhanced_info.get('major_achievement', "[{\"title\": \"Career Move\", \"description\": \"" + person_name + " moved from " + from_company + " to " + to_company + "\"}]"),
            "like_count": like_count,
            "from_company_logo_url": from_company_logo_url,
            "to_company_logo_url": to_company_logo_url
        }
        try:
            self.repo.add_move(move_data)
            logger.info(f"成功保存人才流动信息: {person_name} 从 {from_company} 到 {to_company} - {tweet_url}")
            return True
        except Exception as e:
            logger.error(f"保存人才流动信息失败: {tweet_url}, 错误: {e}")
            return False

    def process_tweet_with_ai(self, tweet, account):
        """使用AI分析单条推文"""
        tweet_url = tweet.get('url', '')
        
        # 检查是否已经处理过
        if self.is_tweet_already_processed(tweet_url):
            print(f"推文已处理过: {tweet_url}")
            return False
        
        post_image_url = tweet.get('extendedEntities', {}).get('media', [{}])[0].get('media_url_https')
        ai_result = analyze_tweet_with_ai(tweet['text'], post_image_url)
        
        if ai_result and ai_result.get('is_talent_move'):
            # 获取基本信息
            person_names = ai_result.get('person_names') or ""
            person_name = ai_result.get('person_name') or ""
            from_company = ai_result.get('from_company') or ""
            to_company = ai_result.get('to_company') or ""
            salary = ai_result.get('salary') or ""
            tweet_text = tweet['text']
            created_at = datetime.strptime(tweet['createdAt'], "%a %b %d %H:%M:%S +0000 %Y")
            like_count = 0
            
            # 处理人才流动信息
            success_count = 0
            
            # 如果有 person_names，处理每个人
            if person_names and person_names.strip():
                logger.info(f"person_names :{person_names}")
                logger.info(f"tweet_url :{tweet_url}")
                logger.info(f"created_at :{created_at}")
                # 分割多个名字
                names_list = [name.strip() for name in person_names.split(',') if name.strip()]
                for name in names_list:
                    if self.process_person_move(name, from_company, to_company, salary, tweet_text, tweet_url, post_image_url, account, created_at, like_count):
                        success_count += 1
            # 如果没有 person_names 但有 person_name，处理单个
            elif person_name and person_name.strip():
                if self.process_person_move(person_name, from_company, to_company, salary, tweet_text, tweet_url, post_image_url, account, created_at, like_count):
                    success_count += 1
            
            # 标记推文为已处理
            self.mark_tweet_as_processed(tweet_url)
            
            return success_count > 0
        else:
            # 即使不是人才流动，也标记为已处理，避免重复分析
            self.mark_tweet_as_processed(tweet_url)
            
        return False
    
    def monitor_single_account(self, account=None, query=None, since_time=None, until_time=None):
        """监控单个Twitter账号"""
        logger.info(f"正在检查: {account if account else query}")
        
        # 获取新推文
        tweets = self.fetch_new_tweets(account, query, since_time, until_time)
        logger.info(f"获取到 {len(tweets)} 条推文")
        
        if not tweets:
            logger.info("没有发现新推文")
            return 0
        
        # 处理每条推文
        processed_count = 0
        for tweet in tweets:
            if self.process_tweet_with_ai(tweet, account if account else query):
                processed_count += 1
        
        logger.info(f"处理完成，发现 {processed_count} 条人才流动信息")
        return processed_count
    
    def monitor_all_accounts(self):
        """监控所有目标账号"""
        print("开始监控Twitter账号...")
        total_processed = 0
        
        # 获取时间范围
        since_time, until_time = self.get_last_run_time_range()
        
        print(f"监控时间范围: {since_time} 到 {until_time}")
        
        # 监控指定账号
        for account in self.target_accounts:
            processed_count = self.monitor_single_account(account, None, since_time, until_time)
            total_processed += processed_count
        
        # 监控指定查询
        for query in self.target_queries:
            processed_count = self.monitor_single_account(None, query, since_time, until_time)
            total_processed += processed_count
        
        # 保存已处理的推文
        self.save_processed_tweets()
        
        return total_processed
    
    def scan_last_month(self):
        """扫描最近一个月内的所有信息"""
        print("=== 开始扫描最近一个月的信息 ===")
        
        # 计算一个月前的时间
        now = datetime.now(timezone.utc)
        one_month_ago = now - timedelta(days=50)
        
        print(f"扫描时间范围: {one_month_ago} 到 {now}")
        
        total_processed = 0
        
        # 监控指定账号
        for account in self.target_accounts:
            processed_count = self.monitor_single_account(account, None, one_month_ago, now)
            total_processed += processed_count
        
        # 监控指定查询
        for query in self.target_queries:
            processed_count = self.monitor_single_account(None, query, one_month_ago, now)
            total_processed += processed_count
        
        # 保存已处理的推文
        self.save_processed_tweets()
        
        print(f"=== 一个月扫描完成，处理了 {total_processed} 条人才流动信息 ===")
        return total_processed
    
    def start_monitoring(self):
        """启动监控线程"""
        print("启动Twitter监控线程...")
        
        # 加载已处理的推文
        self.load_processed_tweets()
        
        def monitoring_loop():
            while True:
                try:
                    print(f"\n=== 开始新一轮监控 {datetime.now()} ===")
                    processed_count = self.monitor_all_accounts()
                    print(f"本轮监控完成，处理了 {processed_count} 条人才流动信息")
                    print(f"等待 {self.check_interval} 秒后继续...")
                except Exception as e:
                    print(f"Twitter monitor error: {e}")
                    import traceback
                    traceback.print_exc()
                time.sleep(self.check_interval)
        
        import threading
        t = threading.Thread(target=monitoring_loop, daemon=True)
        t.start()
        print("监控线程已启动")

def start_twitter_monitor():
    """启动Twitter监控的入口函数"""
    monitor = TwitterMonitor()
    monitor.start_monitoring()

def run_once():
    """运行一次监控（用于定时任务）"""
    print("=== 运行一次Twitter监控 ===")
    monitor = TwitterMonitor()
    monitor.load_processed_tweets()
    processed_count = monitor.monitor_all_accounts()
    monitor.save_processed_tweets()
    print(f"监控完成，处理了 {processed_count} 条人才流动信息")
    return processed_count

def scan_last_month_once():
    """扫描最近一个月的信息（独立函数）"""
    print("=== 运行一个月扫描 ===")
    monitor = TwitterMonitor()
    monitor.load_processed_tweets()
    processed_count = monitor.scan_last_month()
    monitor.save_processed_tweets()
    print(f"一个月扫描完成，处理了 {processed_count} 条人才流动信息")
    return processed_count

if __name__ == "__main__":
    print("=== Twitter AI人才监控启动 ===")
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--month":
        # 扫描一个月
        scan_last_month_once()
    else:
        # 持续监控
        start_twitter_monitor()
        
        # 保持主线程运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n监控已停止")
    
    # 手动执行一个月扫描的代码（注释掉，需要时解开注释）
    # print("=== 手动执行一个月扫描 ===")
    # scan_last_month_once()
