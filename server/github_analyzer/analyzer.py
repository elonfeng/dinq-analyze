import os
import json
import asyncio
import math
import logging
from datetime import datetime, timezone
import random
import re
from typing import Any, Optional, Dict, List
from server.api.reports_handler import serve_report_file
# 尝试使用DINQ项目的trace日志系统
try:
    from server.utils.trace_context import get_trace_logger
    logger = get_trace_logger(__name__)
except ImportError:
    # 如果无法导入，使用标准日志
    logger = logging.getLogger(__name__)

# Import json-repair with fallback
try:
    from json_repair import repair_json
except ImportError:
    # Define a simple fallback function if json-repair is not installed
    def repair_json(json_str, **kwargs):
        logging.warning("json-repair library not available, using fallback")
        return json_str

def parse_github_datetime(datetime_str: str) -> Optional[datetime]:
    """
    健壮的GitHub日期时间解析函数

    Args:
        datetime_str: GitHub API返回的日期时间字符串

    Returns:
        解析后的datetime对象，如果解析失败返回None
    """
    if not datetime_str:
        return None

    try:
        # 记录原始输入
        logger.debug(f"Parsing GitHub datetime: {datetime_str}")

        # 处理常见的GitHub日期格式
        cleaned_str = datetime_str.strip()

        # 方法1: 处理 'Z' 时区标识符 (UTC)
        if cleaned_str.endswith('Z'):
            # 替换 'Z' 为 '+00:00'
            cleaned_str = cleaned_str[:-1] + '+00:00'

        # 方法2: 尝试使用fromisoformat解析
        try:
            result = datetime.fromisoformat(cleaned_str)
            logger.debug(f"Successfully parsed datetime: {result}")
            return result
        except ValueError as e:
            logger.debug(f"fromisoformat failed: {e}")

        # 方法3: 尝试处理微秒精度问题
        # GitHub有时返回带微秒的格式: 2011-01-25T18:44:36.000Z
        if '.' in cleaned_str and cleaned_str.endswith('+00:00'):
            # 移除微秒部分
            base_part = cleaned_str.split('.')[0]
            timezone_part = '+00:00'
            simplified_str = base_part + timezone_part
            try:
                result = datetime.fromisoformat(simplified_str)
                logger.debug(f"Successfully parsed datetime after removing microseconds: {result}")
                return result
            except ValueError as e:
                logger.debug(f"Simplified format failed: {e}")

        # 方法4: 使用正则表达式解析常见格式
        # 支持格式: YYYY-MM-DDTHH:MM:SSZ 或 YYYY-MM-DDTHH:MM:SS.sssZ
        pattern = r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?Z?'
        match = re.match(pattern, datetime_str)
        if match:
            year, month, day, hour, minute, second = map(int, match.groups()[:6])
            microsecond = 0
            if match.group(7):  # 如果有微秒部分
                # 将微秒部分标准化为6位
                microsecond_str = match.group(7)[:6].ljust(6, '0')
                microsecond = int(microsecond_str)

            result = datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)
            logger.debug(f"Successfully parsed datetime using regex: {result}")
            return result

        # 方法5: 尝试其他常见格式
        common_formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
        ]

        for fmt in common_formats:
            try:
                result = datetime.strptime(datetime_str, fmt)
                # 如果没有时区信息，假设为UTC
                if result.tzinfo is None:
                    result = result.replace(tzinfo=timezone.utc)
                logger.debug(f"Successfully parsed datetime using format {fmt}: {result}")
                return result
            except ValueError:
                continue

        logger.warning(f"Could not parse datetime '{datetime_str}' using any known format")
        return None

    except Exception as e:
        logger.error(f"Unexpected error parsing datetime '{datetime_str}': {e}")
        return None

from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI
import pandas as pd

try:
    from .ai_client import ChatClient
    from .github_client import GithubClient
    from .models import AnalysisResult, create_database_session
except ImportError:  # pragma: no cover
    # Fallback for environments where relative import resolution is not available.
    # Use absolute package imports instead of bare-module imports.
    from server.github_analyzer.ai_client import ChatClient
    from server.github_analyzer.github_client import GithubClient
    from server.github_analyzer.models import AnalysisResult, create_database_session

DESC_PRESETS = [
    "is a digital artisan, weaving logic into existence, line by recursive line, understanding that every commit is a step towards a more elegant truth.",
    "is a persistent explorer in the boundless universe of code, knowing that true innovation often lies just beyond the last failed build.",
    "is a patient gardener of ideas, cultivating open-source projects with the foresight that the most valuable contributions often blossom from shared efforts. ",
    "is a resilient problem-solver, embracing errors not as defeats, but as enigmatic puzzles guiding them closer to profound understanding.",
    "is a visionary architect, shaping the future of technology with each carefully crafted algorithm, believing that clarity in code fosters clarity in thought.",
    "is a meticulous storyteller, transforming raw information into insightful narratives, understanding that the greatest impact comes from making complexity comprehensible.",
    "is a dedicated learner, seeing every pull request as an opportunity for growth and refinement, knowing that mastery is a journey, not a destination.",
    "is a collaborative spirit, recognizing that the strength of the developer community lies in the willingness to share, critique, and collectively build.",
    "is a reflective creator, pausing amidst the lines of code to ponder the deeper implications of their work, striving for both functionality and meaningful impact.",
    "is an enduring optimist, believing that within every coding challenge lies an opportunity to push the boundaries of what's possible and to inspire others to do the same.",
]

class GitHubAnalyzer:
    """GitHub 用户分析器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ai = ChatClient(config["openrouter"])
        self.crawling = CrawlingAPI(config["crawlbase"])
        self.session = create_database_session()

        # 加载开发者先驱数据
        csv_file = os.path.join(os.path.dirname(__file__), "dev_pioneers.csv")
        self.dev_pioneers_df = pd.read_csv(csv_file, encoding="iso-8859-1", encoding_errors="ignore")
        self.dev_pioneers_data = self.dev_pioneers_df.to_dict(orient="records")

    def load_json(self, result: Any, default_value: Any) -> Any:
        """Best-effort JSON parse with optional repair.

        Notes:
        - OpenRouter models sometimes wrap JSON in markdown fences or include small syntax issues.
        - SQL/python-ish dict outputs may still be repairable via json-repair.
        """

        if result is None:
            return default_value
        if isinstance(result, (dict, list)):
            return result

        text = str(result).strip()
        if not text:
            return default_value

        # Extract fenced JSON blocks if present.
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                text = match.group(1).strip()

        try:
            parsed = json.loads(text)
        except Exception:
            try:
                parsed = json.loads(repair_json(text))
            except Exception:
                return default_value

        if isinstance(default_value, dict) and not isinstance(parsed, dict):
            return default_value
        if isinstance(default_value, list) and not isinstance(parsed, list):
            return default_value
        return parsed

    def _fallback_most_valuable_pr(self, pull_requests: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not pull_requests:
            return None

        def _score(pr: Dict[str, Any]) -> int:
            try:
                additions = int(pr.get("additions") or 0)
            except Exception:
                additions = 0
            try:
                deletions = int(pr.get("deletions") or 0)
            except Exception:
                deletions = 0
            return additions + deletions

        best = max(pull_requests, key=_score)
        url = str(best.get("url") or "").strip()
        title = str(best.get("title") or "").strip()
        try:
            additions = int(best.get("additions") or 0)
        except Exception:
            additions = 0
        try:
            deletions = int(best.get("deletions") or 0)
        except Exception:
            deletions = 0

        repository = ""
        # https://github.com/<owner>/<repo>/pull/<id>
        if url.startswith("https://github.com/"):
            parts = url.split("/")
            if len(parts) >= 6:
                repository = f"{parts[3]}/{parts[4]}"

        return {
            "repository": repository,
            "url": url,
            "title": title,
            "additions": additions,
            "deletions": deletions,
            "reason": "Fallback selection based on largest code change among top-commented PRs.",
            "impact": "Largest code-change PR (fallback).",
        }

    def _fallback_valuation_and_level(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        overview = input_data.get("overview") if isinstance(input_data, dict) else None
        if not isinstance(overview, dict):
            overview = {}

        try:
            stars = int(overview.get("stars") or 0)
        except Exception:
            stars = 0
        try:
            work_exp = int(overview.get("work_experience") or 0)
        except Exception:
            work_exp = 0
        try:
            pull_requests = int(overview.get("pull_requests") or 0)
        except Exception:
            pull_requests = 0

        level = "L4"
        if stars >= 10000 or pull_requests >= 2000 or work_exp >= 10:
            level = "L6"
        elif stars >= 1000 or pull_requests >= 500 or work_exp >= 7:
            level = "L5"
        elif stars >= 100 or pull_requests >= 100 or work_exp >= 3:
            level = "L4"
        else:
            level = "L3"

        base_comp = {
            "L3": 194_000,
            "L4": 287_000,
            "L5": 377_000,
            "L6": 562_000,
            "L7": 779_000,
            "L8": 1_111_000,
        }.get(level, 287_000)
        low = int(base_comp * 0.9)
        high = int(base_comp * 1.1)

        industry_ranking = 0.25 if level in ("L6", "L7", "L8") else (0.35 if level == "L5" else 0.5)
        growth = "High" if stars >= 1000 else "Medium"

        return {
            "level": level,
            "salary_range": [low, high],
            "industry_ranking": industry_ranking,
            "growth_potential": growth,
            "reasoning": "Fallback estimate based on GitHub stars, PR volume, and account age.",
        }

    def fetch_page(self, url: str) -> str:
        """获取网页内容"""
        try:
            response = self.crawling.get(url)
            if "headers" in response and response["headers"]:
                if response["headers"]["original_status"] == "200":
                    return response["body"]
        except Exception as e:
            logger.error(f"Failed to fetch page {url}: {e}")
        return ""

    async def ai_user_tags(self, login: str) -> List[str]:
        """生成用户标签"""
        logger.info("Generating user tags ...")
        result = await self.ai.just_chat(f"""
            You are an expert GitHub analyst.
            Analyze the GitHub account at: https://github.com/{login}
            Based on the user's repositories, contributions, and overall activity, infer their primary areas of expertise or research interests.
            Return exactly three concise and meaningful tags that best describe their focus areas (e.g., "computer vision", "deep learning", "distributed systems").
            Output format must be a JSON array of strings. No explanations or extra text.
        """)
        return self.load_json(result, [])

    async def ai_repository_tags(self, repository: Optional[Dict[str, Any]]) -> List[str]:
        """生成仓库标签"""
        logger.info("Generating repository tags ...")
        if not repository:
            return []
        result = await self.ai.just_chat(f"""
            You are an expert GitHub analyst.
            Analyze the GitHub repository at: {repository["url"]}
            Based on its code functionality, architecture, and application domain, identify and return exactly three tags that best describe the repository's purpose and primary use cases (e.g., "image classification", "API backend", "NLP toolkit").
            Output must be a JSON array of strings. Do not include any explanations, markdown, or extra text.
        """)
        return self.load_json(result, [])

    async def ai_most_valuable_pull_request(self, pull_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析最有价值的 Pull Request"""
        logger.info("Generating most valuable pull request ...")
        if not pull_requests:
            return {}
        result = await self.ai.chat([
            {
                "role": "system",
                "content": """
                    You are an expert GitHub analyst.
                    You are given an array of pull requests (PRs), each containing metadata such as:
                        - PR title, URL, addtions, deletions, languages
                    Your task is to:
                        1. Analyze all PRs in the array.
                        2. Determine which PR is the most valuable, based on a combination of:
                            - Repository popularity (e.g., stars, forks, issues, activity)
                            - PR impact (e.g., merged status, code changes, discussion/comments)
                            - Importance of the target repository
                        3. Provide a short explanation (1 - 2 sentences) of why it is the most valuable.
                        4. A brief `impact` description summarizing what this PR contributes or changes, no more than 20 words.

                    Output ONLY a valid Python dictionary with the following structure, No explanations or extra text:
                    ```json
                    {
                        "repository": "owner/repo",
                        "url": "https://github.com/owner/repo/pull/123",
                        "title": "PR title",
                        "additions": 99,
                        "deletions": 99,
                        "reason": "Concise explanation of why this PR is the most valuable."
                        "impact": "Brief description of what this PR contributes or improves."
                    }
                    ```
             """,
            },
            {
                "role": "user",
                "content": str(pull_requests),
            },
        ])
        parsed = self.load_json(repair_json(result), {})
        if isinstance(parsed, dict) and parsed.get("url") and parsed.get("title"):
            return parsed
        fallback = self._fallback_most_valuable_pr(pull_requests)
        return fallback or {}

    async def ai_role_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成角色模型分析"""
        logger.info("Generating role model ...")
        result = await self.ai.chat([
            {
                "role": "system",
                "content": f"""
                    You are a GitHub user profiler.
                    You have been provided with a JSON array of GitHub user profile objects. Each item in the array represents one GitHub user and contains fields such as username, name, bio, location, followers, following, repositories, programming languages, company, and activity data.
                    The JSON array is: {self.dev_pioneers_data}
                    Your task is to find the most similar user profile from the provided array based on the input user's GitHub data.
                    Compare factors like programming languages, repository types, contribution patterns, work experience, and technical focus areas.
                    Return ONLY a valid JSON object with the following structure:
                    {{
                        "name": "Most similar developer name",
                        "github": "GitHub URL",
                        "similarity_score": 0.85,
                        "reason": "Brief explanation of why this developer is most similar (1-2 sentences)"
                        "achievement": "A brief summary of the developer's main achievements"
                    }}
                """,
            },
            {
                "role": "user",
                "content": f"Analyze this GitHub user: {input_data}",
            },
        ])
        parsed = self.load_json(repair_json(result), {})
        if isinstance(parsed, dict) and parsed.get("name") and parsed.get("github"):
            return parsed

        # Fallback: return a minimal, non-empty object to avoid caching empty role_model.
        user = input_data.get("user") if isinstance(input_data, dict) else None
        if not isinstance(user, dict):
            user = {}
        github_url = str(user.get("url") or "").strip()
        name = str(user.get("name") or user.get("login") or "Unknown").strip()
        if not github_url and user.get("login"):
            github_url = f"https://github.com/{user.get('login')}"

        return {
            "name": name or "Unknown",
            "github": github_url,
            "similarity_score": 0,
            "reason": "Role model unavailable (fallback).",
            "achievement": "",
        }

    async def ai_valuation_and_level(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成估值和级别分析"""
        

        result = await self.ai.chat([
                {
                    "role": "system",
                    "content": """You will evaluate a software engineer's market value using industry-standard salary benchmarks based on their GitHub profile data. Analyze their technical contributions, open source impact, code quality, and professional experience to determine appropriate compensation levels. Be AGGRESSIVE and COMPETITIVE in recognizing top-tier talent, especially in AI/ML domains where exceptional developers command premium compensation.

            CRITICAL INSTRUCTION: You must NEVER return "No data" for any field. Even with limited information, generate reasonable estimates based on available GitHub metrics and industry patterns.

            EVALUATION APPROACH: Be GENEROUS in recognizing exceptional open source contributors and AI/ML talent. The current tech talent market rewards high-impact developers significantly above traditional software engineering baselines.

            Analysis Framework:

            1. Experience Assessment
            - Account Age: Calculate years since GitHub account creation as baseline experience
            - Contribution Pattern: Analyze commit history, contribution consistency, and career progression
            - Code Volume: Factor in total additions/deletions as indicator of hands-on experience
            - Repository Quality: Assess repository count, star ratings, and project complexity

            2. Technical Impact Scoring
            Apply these GitHub-specific upgrade criteria:
            - High-Impact Repositories (>1000 stars): +1 level boost
            - Major Open Source Contributions (PyTorch/TensorFlow PRs): +2 level boost
            - AI/ML Specialization (computer vision, deep learning): +50% compensation premium
            - Research Publications (10+ NeurIPS/CVPR papers): +100% compensation premium
            - Community Leadership (>50 issues resolved, >50 PRs): +1 level boost

            3. Level Determination (Google Standards)
            Use GitHub metrics to determine equivalent Google levels:
            - L3 (Entry): <2 years, basic contributions, <10 stars total
            - L4 (Mid): 2-4 years, solid contributions, 10-100 stars, some notable PRs
            - L5 (Senior): 4-7 years, significant contributions, 100-1000 stars, major project ownership
            - L6 (Staff): 7-10 years, high-impact contributions, 1000+ stars, industry recognition
            - L7 (Senior Staff): 10+ years, exceptional contributions, major open source projects
            - L8 (Principal): 10+ years, transformative contributions, research publications, industry leadership

            4. Compensation Calculation
            Base Software Engineer Compensation (2025 Market):
            - L3: ~$194,000 total comp
            - L4: ~$287,000 total comp
            - L5: ~$377,000 total comp
            - L6: ~$562,000 total comp
            - L7: ~$779,000 total comp
            - L8: ~$1,111,000 total comp

            GitHub-Specific Premium Multipliers (stack generously):
            - Open Source Impact Premium: +25% minimum for active contributors
            - AI/ML Specialization Premium: +50% for computer vision/deep learning focus
            - Research Publication Premium: +100% for academic contributions (10+ papers)
            - Major Project Leadership: +75% for owning high-star repositories
            - Cross-Platform Contributions: +25% for contributing to multiple major projects
            - Community Recognition: +50% for exceptional GitHub metrics

            Return ONLY a valid JSON object with this exact structure:
            {
                "level": "L4",
                "salary_range": [210000, 250000],
                "industry_ranking": 0.25,
                "growth_potential": "[Low/Medium/High]",
                "reasoning": "[50-70 word justification emphasizing competitive advantages, GitHub impact, technical expertise, and market scarcity that drives premium compensation]"
            }

            Field Specifications:
            - level: Google engineering level (L3-L8+)
            - salary_range: Total annual compensation range as array of two numbers (e.g., [400000, 500000])
            - industry_ranking: Decimal representing percentile (0.05 = top 5%, 0.25 = top 25%)
            - growth_potential: Qualitative assessment based on trajectory and specialization
            - reasoning: Concise English explanation highlighting why this developer commands premium compensation in current market

            FINAL REMINDER: Be AGGRESSIVE in valuation. Exceptional open source contributors, especially in AI/ML, are among the most sought-after talent in tech. Reflect market realities where top GitHub contributors receive competing offers well above traditional compensation bands.""",
                },
                {
                    "role": "user",
                    "content": f"Analyze this GitHub user profile data and provide compensation evaluation: {input_data}",
                },
            ])
        parsed = self.load_json(repair_json(result), {})
        if isinstance(parsed, dict):
            level = str(parsed.get("level") or "").strip()
            salary_range = parsed.get("salary_range")
            if level and isinstance(salary_range, list) and len(salary_range) == 2:
                return parsed
        return self._fallback_valuation_and_level(input_data)

    async def ai_roast(self, data: Dict[str, Any]) -> str:
        """生成幽默评价"""
        logger.info("Generating roast ...")
        result = await self.ai.just_chat(f"""
            You are a witty and humorous commentator.
            Given a JSON dictionary with the following structure: {data}
            Generate a short, playful roast about the user.
            The roast should be clever and light-hearted, poking fun at their GitHub activity or profile traits without being mean or offensive.
            Output only a single short paragraph of plain text. Do not include any explanations or extra formatting.

            Example output:
                "With just 3 repos and zero stars, code_master is clearly on a mission to keep GitHub lightweight."
        """)
        return result

    def fetch_repository_extra(self, repository_name_with_owner: str) -> Dict[str, Any]:
        """获取仓库额外信息"""
        result = {"used_by": 0, "contributors": 0, "monthly_trending": 0}
        html = self.fetch_page(f"https://github.com/{repository_name_with_owner}")
        soup = BeautifulSoup(html, features="html.parser")

        # 解析仓库的 Used By 和 Contributors 数据
        for link in soup.select(".Layout-sidebar h2 > a"):
            content = link.contents[0].strip().lower().replace(" ", "_")
            if content == "used_by" or content == "contributors":
                span = link.find("span")
                if span and "title" in span.attrs:
                    formatted_value = span.attrs["title"]
                    result[content] = int(formatted_value.replace(",", ""))

        # 解析仓库是否在 Monthly Trending 榜单上
        html = self.fetch_page("https://github.com/trending?since=monthly")
        soup = BeautifulSoup(html, features="html.parser")
        for link in soup.select("article h2 > a"):
            if link.attrs["href"].lstrip("/") == repository_name_with_owner:
                result["monthly_trending"] = 1

        return result

    async def safe_ai_call(self, coro, name, default_value):
        """安全的AI调用包装器"""
        try:
            result = await coro
            logger.debug(f"Successfully completed AI call: {name}")
            return result
        except Exception as e:
            logger.warning(f"AI call failed for {name}: {e}")
            return default_value

    async def analyze(self, login: str) -> Optional[Dict[str, Any]]:
        github = GithubClient(self.config["github"])
        """分析 GitHub 用户"""
        try:
            user = await github.profile(login)
            if not user:
                logger.error(f"Github user `{login}` doesn't exists.")
                return None

            output = {}
            output["user"] = user
            output["description"] = random.choices(DESC_PRESETS)[0]
            now = datetime.now(timezone.utc)

            # 解析GitHub用户创建时间
            created_at_str = user.get("createdAt", "")
            sign_up_at = parse_github_datetime(created_at_str)

            if sign_up_at is None:
                # 如果无法解析，使用当前时间减去一年作为默认值
                logger.warning(f"Could not parse datetime '{created_at_str}', using fallback (current time - 1 year)")
                sign_up_at = now.replace(year=now.year-1)
            else:
                logger.info(f"Successfully parsed user creation time: {sign_up_at}")

            work_exp = math.ceil((now - sign_up_at).days / 365)

            # 并行获取各种数据，使用错误处理
            logger.info(f"Starting parallel data collection for user {login}")

            async def safe_github_call(coro, name, default_value):
                """安全的GitHub API调用包装器"""
                try:
                    result = await coro
                    logger.debug(f"Successfully completed {name} for {login}")
                    return result
                except Exception as e:
                    logger.warning(f"Failed to get {name} for {login}: {e}")
                    return default_value

            # 使用安全包装器进行并行调用
            results = await asyncio.gather(
                safe_github_call(github.pull_requests(login), "pull_requests", {"mutations": {"additions": 0, "deletions": 0, "languages": {}}, "nodes": []}),
                safe_github_call(github.mutations(login, user["id"]), "mutations", {"additions": 0, "deletions": 0, "languages": {}}),
                safe_github_call(github.activity(login=login), "activity", {}),  # 最近30天的活动数据
                safe_github_call(github.activity(login=login, start_date=sign_up_at), "all_time_activity", {}),  # 有史以来的活动数据
                safe_github_call(github.most_starred_repositories(login), "most_starred_repositories", []),
                safe_github_call(github.most_pull_request_repositories(login, min(10, work_exp)), "most_pull_request_repositories", []),
                return_exceptions=True
            )

            pull_requests_data = results[0] if results[0] and not isinstance(results[0], Exception) else {"mutations": {"additions": 0, "deletions": 0, "languages": {}}, "nodes": []}
            mutations = results[1] if results[1] and not isinstance(results[1], Exception) else {"additions": 0, "deletions": 0, "languages": {}}
            activity = results[2] if results[2] and not isinstance(results[2], Exception) else {}  # 最近30天的活动
            all_time_activity = results[3] if results[3] and not isinstance(results[3], Exception) else {}  # 有史以来的活动
            most_starred_repositories = results[4] if results[4] and not isinstance(results[4], Exception) else []
            most_pull_request_repositories = results[5] if results[5] and not isinstance(results[5], Exception) else []

            logger.info(f"Completed data collection for user {login}")

            # 计算统计数据
            additions = mutations["additions"] + pull_requests_data["mutations"]["additions"]
            deletions = mutations["deletions"] + pull_requests_data["mutations"]["deletions"]
            languages = mutations["languages"]
            
            for name, value in pull_requests_data["mutations"]["languages"].items():
                if name not in languages:
                    languages[name] = 0
                languages[name] += value

            stars_count = 0
            for repository in most_starred_repositories:
                stars_count += repository["stargazerCount"]

            # 计算活跃天数统计（使用有史以来的活动数据）
            active_days = 0
            if all_time_activity:
                for date, day_data in all_time_activity.items():
                    # 如果当天有任何活动（PR、Issues、评论或贡献），就认为是活跃天
                    if (day_data.get("pull_requests", 0) > 0 or 
                        day_data.get("issues", 0) > 0 or 
                        day_data.get("comments", 0) > 0 or 
                        day_data.get("contributions", 0) > 0):
                        active_days += 1

            # Overview
            output["overview"] = {
                "work_experience": work_exp,
                "stars": stars_count,
                "issues": user["issues"]["totalCount"],
                "pull_requests": user["pullRequests"]["totalCount"],
                "repositories": user["repositories"]["totalCount"],
                "additions": additions,
                "deletions": deletions,
                "active_days": active_days,  # 添加活跃天数
            }

            
            # Monthly Activity
            output["activity"] = activity

            # Feature Project
            if most_starred_repositories:
                most_starred_repository = most_starred_repositories[0]
                try:
                    feature_project = self.fetch_repository_extra(
                        most_starred_repository["nameWithOwner"]
                    )
                    feature_project.update(most_starred_repository)
                except Exception as e:
                    logger.warning(f"Failed to fetch repository extra info for {most_starred_repository['nameWithOwner']}: {e}")
                    feature_project = most_starred_repository
            else:
                feature_project = None
            output["feature_project"] = feature_project

            # Code Contribution Analysis
            output["code_contribution"] = {
                "total": additions + deletions,
                "languages": languages,
            }

            # Top Projects Contributed To
            output["top_projects"] = most_pull_request_repositories

            # AI 分析 - 使用错误处理
            logger.info(f"Starting AI analysis for user {login}")
            pull_requests = pull_requests_data["nodes"]

            try:
                ai_results = await asyncio.gather(
                    self.safe_ai_call(self.ai_user_tags(login), "user_tags", []),
                    self.safe_ai_call(self.ai_repository_tags(feature_project), "repository_tags", []),
                    self.safe_ai_call(self.ai_most_valuable_pull_request(pull_requests), "most_valuable_pr", None),
                    return_exceptions=True
                )

                output["user"]["tags"] = ai_results[0] if ai_results[0] and not isinstance(ai_results[0], Exception) else []
                if output["feature_project"]:
                    output["feature_project"]["tags"] = ai_results[1] if ai_results[1] and not isinstance(ai_results[1], Exception) else []
                output["most_valuable_pull_request"] = ai_results[2] if ai_results[2] and not isinstance(ai_results[2], Exception) else None

                # 根据先前的结果继续分析
                final_results = await asyncio.gather(
                    self.safe_ai_call(self.ai_valuation_and_level(output), "valuation_and_level", {"level": "Unknown", "salary_range": "Unknown"}),
                    self.safe_ai_call(self.ai_role_model(output), "role_model", {"name": "Unknown", "similarity_score": 0}),
                    self.safe_ai_call(self.ai_roast(output), "roast", "No roast available"),
                    return_exceptions=True
                )

                output["valuation_and_level"] = final_results[0] if final_results[0] and not isinstance(final_results[0], Exception) else {"level": "Unknown", "salary_range": "Unknown"}
                output["role_model"] = final_results[1] if final_results[1] and not isinstance(final_results[1], Exception) else {"name": "Unknown", "similarity_score": 0}
                output["roast"] = final_results[2] if final_results[2] and not isinstance(final_results[2], Exception) else "No roast available"

            except Exception as e:
                logger.error(f"AI analysis failed for user {login}: {e}")
                # 提供默认值
                output["user"]["tags"] = []
                if output["feature_project"]:
                    output["feature_project"]["tags"] = []
                output["most_valuable_pull_request"] = None
                output["valuation_and_level"] = {"level": "Unknown", "salary_range": "Unknown"}
                output["role_model"] = {"name": "Unknown", "similarity_score": 0}
                output["roast"] = "Analysis temporarily unavailable"

            logger.info(f"Successfully completed analysis for user {login}")
            return output

        except Exception as e:
            logger.error(f"Critical error during analysis of user {login}: {e}")
            return None
        finally:
            await github.close()

    async def analyze_with_progress(self, login: str, progress_callback=None, cancel_event=None) -> Optional[Dict[str, Any]]:
        """带进度回调的分析 GitHub 用户"""
        from server.utils.trace_context import TraceContext, propagate_trace_to_thread

        # 获取当前trace ID
        current_trace_id = TraceContext.get_trace_id()
        github = GithubClient(self.config["github"])

        def safe_progress_callback(step, message, data=None):
            """安全的进度回调，确保trace ID传播"""
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return
            if progress_callback:
                try:
                    # 确保在回调中也有trace ID
                    if current_trace_id:
                        TraceContext.set_trace_id(current_trace_id)
                    progress_callback(step, message, data)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        try:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None
            safe_progress_callback('profile_fetch', f'Fetching profile for user {login}...')

            user = await github.profile(login)
            if not user:
                logger.error(f"Github user `{login}` doesn't exists.")
                safe_progress_callback('user_not_found', f'GitHub user {login} not found')
                return None

            safe_progress_callback('profile_success', f'Successfully fetched profile for {login}', {'user': user.get('name', login)})

            output = {}
            output["user"] = user
            output["description"] = random.choices(DESC_PRESETS)[0]
            now = datetime.now(timezone.utc)

            # 解析GitHub用户创建时间
            safe_progress_callback('parse_datetime', 'Parsing user creation time...')
            created_at_str = user.get("createdAt", "")
            sign_up_at = parse_github_datetime(created_at_str)

            if sign_up_at is None:
                logger.warning(f"Could not parse datetime '{created_at_str}', using fallback (current time - 1 year)")
                sign_up_at = now.replace(year=now.year-1)
                safe_progress_callback('datetime_fallback', 'Using default time to calculate work experience')
            else:
                logger.info(f"Successfully parsed user creation time: {sign_up_at}")
                safe_progress_callback('datetime_success', f'User registered on: {sign_up_at.strftime("%Y-%m-%d")}')

            work_exp = math.ceil((now - sign_up_at).days / 365)
            safe_progress_callback('work_exp_calculated', f'Calculated work experience: {work_exp} years')

            # 并行获取各种数据，使用错误处理
            safe_progress_callback('data_collection_start', 'Starting GitHub data collection...')

            async def safe_github_call_with_progress(coro, name, default_value, step_name):
                """安全的GitHub API调用包装器，带进度回调"""
                try:
                    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                        return default_value
                    safe_progress_callback(f'{step_name}_start', f'Fetching {name}...')
                    result = await coro
                    safe_progress_callback(f'{step_name}_success', f'Successfully fetched {name}')
                    logger.debug(f"Successfully completed {name} for {login}")
                    return result
                except Exception as e:
                    safe_progress_callback(f'{step_name}_failed', f'Failed to fetch {name}: {str(e)}')
                    logger.warning(f"Failed to get {name} for {login}: {e}")
                    return default_value

            # 使用安全包装器进行并行调用
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None
            results = await asyncio.gather(
                safe_github_call_with_progress(
                    github.pull_requests(login),
                    "pull requests data",
                    {"mutations": {"additions": 0, "deletions": 0, "languages": {}}, "nodes": []},
                    "pull_requests"
                ),
                safe_github_call_with_progress(
                    github.mutations(login, user["id"]),
                    "code mutations",
                    {"additions": 0, "deletions": 0, "languages": {}},
                    "mutations"
                ),
                safe_github_call_with_progress(
                    github.activity(login),
                    "activity data",
                    {},
                    "activity"
                ),
                safe_github_call_with_progress(
                    github.activity(login, start_date=sign_up_at),
                    "all-time activity data",
                    {},
                    "all_time_activity"
                ),
                safe_github_call_with_progress(
                    github.most_starred_repositories(login),
                    "starred repositories",
                    [],
                    "starred_repos"
                ),
                safe_github_call_with_progress(
                    github.most_pull_request_repositories(login, work_exp),
                    "contributed repositories",
                    [],
                    "contributed_repos"
                ),
                return_exceptions=True
            )

            pull_requests_data = results[0] if results[0] and not isinstance(results[0], Exception) else {"mutations": {"additions": 0, "deletions": 0, "languages": {}}, "nodes": []}
            mutations = results[1] if results[1] and not isinstance(results[1], Exception) else {"additions": 0, "deletions": 0, "languages": {}}
            activity = results[2] if results[2] and not isinstance(results[2], Exception) else {}  # 最近30天的活动
            all_time_activity = results[3] if results[3] and not isinstance(results[3], Exception) else {}  # 有史以来的活动
            most_starred_repositories = results[4] if results[4] and not isinstance(results[4], Exception) else []
            most_pull_request_repositories = results[5] if results[5] and not isinstance(results[5], Exception) else []

            safe_progress_callback('data_collection_complete', 'Data collection complete, starting analysis...')

            # 计算统计数据
            safe_progress_callback('calculating_stats', 'Calculating statistics...')
            additions = mutations["additions"] + pull_requests_data["mutations"]["additions"]
            deletions = mutations["deletions"] + pull_requests_data["mutations"]["deletions"]
            languages = mutations["languages"]
            
            for name, value in pull_requests_data["mutations"]["languages"].items():
                if name not in languages:
                    languages[name] = 0
                languages[name] += value

            stars_count = 0
            for repository in most_starred_repositories:
                stars_count += repository["stargazerCount"]

            # 计算活跃天数统计（使用有史以来的活动数据）
            active_days = 0
            if all_time_activity:
                for date, day_data in all_time_activity.items():
                    # 如果当天有任何活动（PR、Issues、评论或贡献），就认为是活跃天
                    if (day_data.get("pull_requests", 0) > 0 or 
                        day_data.get("issues", 0) > 0 or 
                        day_data.get("comments", 0) > 0 or 
                        day_data.get("contributions", 0) > 0):
                        active_days += 1

            safe_progress_callback('active_days_calculated', f'Calculated active days: {active_days} days')

            # Overview
            output["overview"] = {
                "work_experience": work_exp,
                "stars": stars_count,
                "issues": user["issues"]["totalCount"],
                "pull_requests": user["pullRequests"]["totalCount"],
                "repositories": user["repositories"]["totalCount"],
                "additions": additions,
                "deletions": deletions,
                "active_days": active_days,  # 添加活跃天数
            }

            safe_progress_callback('overview_complete', f'Overview complete - Stars: {stars_count}, PRs: {user["pullRequests"]["totalCount"]}, Active days: {active_days}')

            # Monthly Activity
            output["activity"] = activity

            # Feature Project
            safe_progress_callback('feature_project_start', 'Analyzing featured project...')
            if most_starred_repositories:
                most_starred_repository = most_starred_repositories[0]
                try:
                    feature_project = self.fetch_repository_extra(
                        most_starred_repository["nameWithOwner"]
                    )
                    feature_project.update(most_starred_repository)
                    safe_progress_callback('feature_project_success', f'Featured project: {feature_project.get("name", "Unknown")}')
                except Exception as e:
                    logger.warning(f"Failed to fetch repository extra info for {most_starred_repository['nameWithOwner']}: {e}")
                    feature_project = most_starred_repository
                    safe_progress_callback('feature_project_partial', f'Featured project: {feature_project.get("name", "Unknown")} (partial info)')
            else:
                feature_project = None
                safe_progress_callback('feature_project_none', 'No featured project found')
            output["feature_project"] = feature_project

            # Code Contribution Analysis
            output["code_contribution"] = {
                "total": additions + deletions,
                "languages": languages,
            }

            # Top Projects Contributed To
            output["top_projects"] = most_pull_request_repositories

            # AI 分析 - 使用错误处理
            safe_progress_callback('ai_analysis_start', 'Starting AI analysis...')
            pull_requests = pull_requests_data["nodes"]

            try:
                safe_progress_callback('ai_user_tags_start', 'Generating user skill tags...')
                ai_results = await asyncio.gather(
                    self.safe_ai_call(self.ai_user_tags(login), "user_tags", []),
                    self.safe_ai_call(self.ai_repository_tags(feature_project), "repository_tags", []),
                    self.safe_ai_call(self.ai_most_valuable_pull_request(pull_requests), "most_valuable_pr", None),
                    return_exceptions=True
                )

                output["user"]["tags"] = ai_results[0] if ai_results[0] and not isinstance(ai_results[0], Exception) else []
                if output["feature_project"]:
                    output["feature_project"]["tags"] = ai_results[1] if ai_results[1] and not isinstance(ai_results[1], Exception) else []
                output["most_valuable_pull_request"] = ai_results[2] if ai_results[2] and not isinstance(ai_results[2], Exception) else None

                safe_progress_callback('ai_basic_complete', 'AI basic analysis complete')

                # 根据先前的结果继续分析
                safe_progress_callback('ai_advanced_start', 'Performing advanced AI analysis...')
                final_results = await asyncio.gather(
                    self.safe_ai_call(self.ai_valuation_and_level(output), "valuation_and_level", {"level": "Unknown", "salary_range": "Unknown"}),
                    self.safe_ai_call(self.ai_role_model(output), "role_model", {"name": "Unknown", "similarity_score": 0}),
                    self.safe_ai_call(self.ai_roast(output), "roast", "No roast available"),
                    return_exceptions=True
                )

                output["valuation_and_level"] = final_results[0] if final_results[0] and not isinstance(final_results[0], Exception) else {"level": "Unknown", "salary_range": "Unknown"}
                output["role_model"] = final_results[1] if final_results[1] and not isinstance(final_results[1], Exception) else {"name": "Unknown", "similarity_score": 0}
                output["roast"] = final_results[2] if final_results[2] and not isinstance(final_results[2], Exception) else "No roast available"

                safe_progress_callback('ai_analysis_complete', 'AI analysis complete')

            except Exception as e:
                logger.error(f"AI analysis failed for user {login}: {e}")
                safe_progress_callback('ai_analysis_failed', f'AI analysis failed: {str(e)}')
                # 提供默认值
                output["user"]["tags"] = []
                if output["feature_project"]:
                    output["feature_project"]["tags"] = []
                output["most_valuable_pull_request"] = None
                output["valuation_and_level"] = {"level": "Unknown", "salary_range": "Unknown"}
                output["role_model"] = {"name": "Unknown", "similarity_score": 0}
                output["roast"] = "Analysis temporarily unavailable"

            safe_progress_callback('analysis_complete', f'Analysis complete for user {login}')
            logger.info(f"Successfully completed analysis with progress for user {login}")
            return output

        except Exception as e:
            logger.error(f"Critical error during analysis with progress of user {login}: {e}")
            safe_progress_callback('critical_error', f'Critical error during analysis: {str(e)}')
            return None
        finally:
            await github.close()

    def get_result(self, login: str) -> Optional[Dict[str, Any]]:
        """获取分析结果（带缓存）"""
        try:
            # 检查缓存
            analysis_result = self.session.get(AnalysisResult, login)
            if analysis_result:
                try:
                    result = json.loads(analysis_result.result)
                    logger.info(f"Retrieved cached analysis result for user {login}")
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse cached result for {login}: {e}")
                    # 删除损坏的缓存
                    self.session.delete(analysis_result)
                    self.session.commit()

            # 执行分析
            logger.info(f"Starting fresh analysis for user {login}")
            result = asyncio.run(self.analyze(login))

            if result:
                try:
                    # 保存到缓存
                    analysis_result = AnalysisResult(id=login, result=json.dumps(result))
                    self.session.add(analysis_result)
                    self.session.commit()
                    logger.info(f"Saved analysis result to cache for user {login}")
                except Exception as e:
                    self.session.rollback()
                    logger.warning(f"Failed to save analysis result to cache for {login}: {e}")
                    # 即使缓存失败，也返回结果
            else:
                logger.error(f"Analysis returned no result for user {login}")
            return result

        except Exception as e:
            self.session.rollback()
            logger.error(f"Critical error in get_result for user {login}: {e}")
            return None
        
    async def get_compare_result(self, user1: str, user2: str) -> Optional[Dict[str, Any]]:
        """获取分析结果（带缓存）"""
        try:
            # 检查缓存
            analysis_result = self.get_cached_compare_result(user1,user2)
            if analysis_result:
                return analysis_result
      

            # 执行分析
            logger.info(f"Starting fresh analysis compare for user1:{user1}, user2:{user2}")
            task1 = asyncio.create_task(self.analyze(user1))
            task2 = asyncio.create_task(self.analyze(user2))
            result1 = await task1
            result2 = await task2
            result = self.transform_pk_result(user1,user2,result1,result2)
            if result1 and result2:
                    # 保存到缓存
                self.save_pk_report(result)
                logger.info(f"Saved analysis result to cache for user {user1} and {user2}")
            else:
                logger.error(f"Analysis returned no result for user {user1} and {user2}")
            return result

        except Exception as e:
            logger.error(f"Critical error in get_result for user {user1} and {user2}: {e}")
            return None    
    
    def transform_pk_result(self, user1: str, user2: str, result1: Dict[str, Any], result2: Dict[str, Any]) -> Dict[str, Any]:
        """转换PK结果"""
        def extract_user_data(user: str, result: Dict[str, Any]) -> Dict[str, Any]:
            """从原始结果中摘取用户关键数据"""
            return {
                # 特色项目
                "name": user,
                "feature_project": result.get("feature_project", {}),

                # 顶级项目
                "top_projects": result.get("top_projects", []),

                # 代码贡献
                "code_contribution": result.get("code_contribution", {}),

                # 概览统计
                "overview": result.get("overview", {}),
                "roast": result.get("roast", ""),
                "user": result.get("user", {})
            }

        # 生成PK roast
        pk_roast = self._generate_pk_roast(result1, result2)

        return {
            "user1": extract_user_data(user1,result1),
            "user2": extract_user_data(user2,result2),
            "roast": pk_roast  # 添加PK roast字段
        }

    def _generate_pk_roast(self, user1_info: Dict[str, Any], user2_info: Dict[str, Any]) -> str:
        """Generate a one-sentence roast comparing two GitHub developers"""
        try:
            import json

            from server.prompts.github_prompts import get_github_pk_roast_prompt
            from server.llm.gateway import openrouter_chat
            from server.config.llm_models import get_model

            # Format user information
            user1_str = json.dumps(user1_info, ensure_ascii=False)
            user2_str = json.dumps(user2_info, ensure_ascii=False)

            # 获取提示词
            messages = get_github_pk_roast_prompt(user1_str, user2_str)

            model = get_model("fast", task="github_pk.roast")
            response = openrouter_chat(
                task="github_pk.roast",
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=300,
                expect_json=True,
            )
            if isinstance(response, dict) and response.get("roast"):
                return str(response.get("roast") or "").strip()
            if isinstance(response, str) and response.strip():
                return response.strip()
            return "Failed to generate roast"

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in GitHub roast generation: {e}")
            return "Failed to generate roast due to JSON parsing error"
        except Exception as e:
            logger.error(f"Error generating GitHub roast: {e}")
            return f"Failed to generate roast: {str(e)}"

    def get_cached_compare_result(self, login1: str,login2: str) -> Optional[Dict[str, Any]]:
        """获取缓存分析结果"""
        try:
            # 检查缓存
            pk_filename = f"github_pk_{login1}_vs_{login2}.json"
            
            # 直接读取JSON文件内容
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
            pk_filepath = os.path.join(reports_dir, pk_filename)
            
            if os.path.exists(pk_filepath):
                try:
                    with open(pk_filepath, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                    logger.info(f"Retrieved cached compare result for {login1} vs {login2}")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from file for {login1} vs {login2}: {e}")
                    return None
            else:
                logger.info(f"No cached compare result found for {login1} vs {login2}")
                return None
           
        except Exception as e:
            logger.error(f"Critical error in get_cached_compare_result for user {login1} and {login2}: {e}")
            return None
    
    def save_pk_report(self, pk_result: Dict) -> Dict[str, str]:
        """保存github PK报告为JSON

        Args:
            pk_result: PK结果数据，包含两位github用户的信息
      

        Returns:
            包含两位github用户的JSON URL的字典
        """
        # 创建reports目录（如果不存在）
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
        os.makedirs(reports_dir, exist_ok=True)

        # 获取两位github用户的姓名
        github1_name = pk_result.get("user1", {}).get("name", "unknown")
        github2_name = pk_result.get("user2", {}).get("name", "unknown")
        

        # 生成PK文件名 (两位研究者姓名+谷歌学术ID)
        pk_filename = f"github_pk_{github1_name}_vs_{github2_name}.json"
        pk_filepath = os.path.join(reports_dir, pk_filename)

        # 保存PK JSON文件
        try:
            with open(pk_filepath, "w", encoding="utf-8") as f:
                json.dump(pk_result, f, ensure_ascii=False, indent=2)
            logger.info(f"PK github report data saved to {pk_filepath}")
        except Exception as e:
            logger.error(f"Error saving PK report data: {str(e)}")

        # 打印所有环境变量，便于调试
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith("DINQ_"):
                logger.info(f"  {key}: {value}")

        # 特别检查 DINQ_API_DOMAIN 环境变量
        dinq_api_domain = os.environ.get("DINQ_API_DOMAIN")
        logger.info(f"DINQ_API_DOMAIN from os.environ.get(): {dinq_api_domain}")

        # 从环境变量中获取域名配置，或使用默认值
        domain = os.environ.get("DINQ_API_DOMAIN", "http://127.0.0.1:5001")
        logger.info(f"Domain after first get: {domain}")

        # 根据环境变量选择不同的域名
        env = os.environ.get("DINQ_ENV", "development")
        logger.info(f"Environment: {env}")

        if env == "production":
            domain = os.environ.get("DINQ_API_DOMAIN", "https://api.dinq.ai")
            logger.info(f"Production domain: {domain}")
        elif env == "test":
            domain = os.environ.get("DINQ_API_DOMAIN", "https://test-api.dinq.ai")
            logger.info(f"Test domain: {domain}")

        logger.info(f"Using domain: {domain} for environment: {env}")

        # 获取JSON文件的相对路径，用于前端直接获取数据
        json_relative_path = os.path.relpath(pk_filepath, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        pk_json_url = f"{domain}/{json_relative_path}"

        # 返回包含两位研究者数据URL的字典
        return {
            "pk_json_url": pk_json_url,
            "user1_name": github1_name,
            "user2_name": github2_name
        }    
        
    def get_cached_result(self, login: str) -> Optional[Dict[str, Any]]:
        """获取缓存分析结果"""
        try:
            # 检查缓存
            analysis_result = self.session.get(AnalysisResult, login)
            return json.loads(analysis_result.result)
           
        except Exception as e:
            self.session.rollback()
            logger.error(f"Critical error in get_result for user {login}: {e}")
            return None
        
    def get_result_with_progress(self, login: str, progress_callback=None, cancel_event=None) -> Optional[Dict[str, Any]]:
        """获取分析结果（带缓存和进度回调）"""
        try:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return None

            def safe_progress(step: str, message: str, data=None) -> None:
                if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                    return
                if progress_callback:
                    progress_callback(step, message, data)

            # 检查缓存
            analysis_result = self.session.get(AnalysisResult, login)
            if analysis_result:
                try:
                    result = json.loads(analysis_result.result)
                    logger.info(f"Retrieved cached analysis result for user {login}")
                    safe_progress('cache_hit', f'Retrieved cached result for user {login}')
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse cached result for {login}: {e}")
                    # 删除损坏的缓存
                    self.session.delete(analysis_result)
                    self.session.commit()
                    safe_progress('cache_invalid', 'Cache data corrupted, re-analyzing')

            # 执行带进度的分析
            logger.info(f"Starting fresh analysis with progress for user {login}")
            safe_progress('analysis_start', f'Starting analysis for user {login}')

            result = asyncio.run(self.analyze_with_progress(login, progress_callback, cancel_event=cancel_event))

            if result:
                try:
                    # 保存到缓存
                    safe_progress('saving_cache', 'Saving analysis result to cache')

                    analysis_result = AnalysisResult(id=login, result=json.dumps(result))
                    self.session.add(analysis_result)
                    self.session.commit()
                    logger.info(f"Saved analysis result to cache for user {login}")

                    safe_progress('cache_saved', 'Analysis result saved to cache')
                except Exception as e:
                    logger.warning(f"Failed to save analysis result to cache for {login}: {e}")
                    safe_progress('cache_save_failed', f'Failed to save cache: {str(e)}')
                    # 即使缓存失败，也返回结果
            else:
                logger.error(f"Analysis returned no result for user {login}")
                safe_progress('analysis_failed', f'Analysis failed for user {login}')

            return result

        except Exception as e:
            logger.error(f"Critical error in get_result_with_progress for user {login}: {e}")
            if progress_callback and not (cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)()):
                progress_callback('critical_error', f'Critical error during analysis: {str(e)}')
            return None

    async def close(self):
        """关闭资源"""
        self.session.close()
