import asyncio
from typing import Any, Optional, Dict, List
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import logging

import httpx

from .github_queries import (
    Query,
    UserQuery,
    GithubBundleQuery,
    PullRequestDaysQuery,
    IssueDaysQuery,
    ContributionDaysQuery,
    PullRequestsQuery,
    MutationsQuery,
    MostStarredRepositoriesQuery,
    MostPullRequestRepositoriesQuery,
)


class GithubClient:
    """GitHub GraphQL API 客户端"""

    ENDPOINT = "https://api.github.com/graphql"

    def __init__(self, options: Dict[str, Any]):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={
                "Authorization": f"Bearer {options['token']}",
                "Content-Type": "application/json",
            },
        )

    async def query(self, query: Query) -> Any:
        """执行 GraphQL 查询"""
        result = None
        while not query._finished:
            response = await self.client.post(self.ENDPOINT, json=query.json())
            if response.status_code == httpx.codes.OK:
                data = response.json()
                if "errors" in data:
                    logging.error(f"Github errors: {data['errors']}")
                    break
            else:
                logging.error(f"Github request failed: {response.text}")
                break
            if result:
                result.extend(query.process(data["data"]))
            else:
                result = query.process(data["data"])
        return result

    async def profile(self, login: str) -> Optional[Dict[str, Any]]:
        """获取用户基本信息"""
        logging.info("Querying profile ...")
        return await self.query(UserQuery(login))

    async def bundle(self, login: str, start: datetime, end: datetime) -> Optional[Dict[str, Any]]:
        """Fetch a single-shot GitHub data bundle (minimize request fan-out)."""
        logging.info("Querying bundle ...")
        return await self.query(GithubBundleQuery(login, start, end))

    async def mutations(self, login: str, user_id: str) -> Dict[str, Any]:
        """获取用户代码变更统计"""
        logging.info("Querying mutations ...")
        return await self.query(MutationsQuery(login, user_id))

    async def pull_requests(self, login: str) -> List[Dict[str, Any]]:
        """获取用户 Pull Requests"""
        logging.info("Querying pull requests ...")
        return await self.query(PullRequestsQuery(login))

    async def activity(self, login: str, last_n_days: int = 30, start_date: datetime = None) -> Dict[str, Any]:
        """获取用户活动统计
        
        Args:
            login: GitHub用户名
            last_n_days: 最近N天的活动统计（当start_date=None时使用）
            start_date: 开始日期，如果提供则从该日期查询到当前时间
        """
        if start_date:
            # 检查start_date是否距离现在超过一年，如果是则限制为一年前
            now = datetime.now(timezone.utc)
            one_year_ago = now - relativedelta(years=1)
            
            if start_date < one_year_ago:
                logging.info(f"Start date {start_date.strftime('%Y-%m-%d')} is more than 1 year ago, limiting to 1 year ago for {login} ...")
                start_date = one_year_ago
            
            logging.info(f"Querying activity from {start_date.strftime('%Y-%m-%d')} to now for {login} ...")
            end = datetime.now(timezone.utc)
            start = start_date
        else:
            logging.info(f"Querying activity from the past {last_n_days} days for {login} ...")
            end = datetime.now(timezone.utc)
            start = end - relativedelta(days=last_n_days)

        # 由于GitHub API的时间范围限制，我们需要分批查询
        # GitHub GraphQL API对时间范围查询有限制，我们按年分批查询
        result = {}
        
        if start_date:
            # 按年分批查询，避免API限制
            current_start = start
            while current_start < end:
                current_end = min(current_start + relativedelta(years=1), end)
                logging.info(f"Querying activity from {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
                
                batch_result = await self._query_activity_batch(login, current_start, current_end)
                result.update(batch_result)
                
                current_start = current_end
        else:
            # 对于短期查询，直接查询
            result = await self._query_activity_batch(login, start, end)
        
        return result
    
    async def _query_activity_batch(self, login: str, start: datetime, end: datetime) -> Dict[str, Any]:
        """查询指定时间范围内的活动批次"""
        result = {}
        
        tasks = [
            self.query(PullRequestDaysQuery(f"author:{login}", start, end)),
            self.query(IssueDaysQuery(f"author:{login}", start, end)),
            self.query(PullRequestDaysQuery(f"commenter:{login}", start, end)),
            self.query(IssueDaysQuery(f"commenter:{login}", start, end)),
            self.query(ContributionDaysQuery(login, start, end)),
        ]
        data = [dict(data) for data in await asyncio.gather(*tasks)]

        current_date = start
        while current_date <= end:
            date = current_date.strftime("%Y-%m-%d")
            if date not in result:
                result[date] = {
                    "pull_requests": 0,
                    "issues": 0,
                    "comments": 0,
                    "contributions": 0,
                }
            result[date]["pull_requests"] += data[0].get(date, 0)
            result[date]["issues"] += data[1].get(date, 0)
            result[date]["comments"] += data[2].get(date, 0) + data[3].get(date, 0)
            result[date]["contributions"] += data[4].get(date, 0)
            current_date += relativedelta(days=1)
        
        return result

    async def most_starred_repositories(self, login: str) -> List[Dict[str, Any]]:
        """获取用户最受欢迎的仓库"""
        logging.info("Querying repositories ...")
        return await self.query(MostStarredRepositoriesQuery(login))

    async def most_pull_request_repositories(
        self, login: str, last_n_years: int = 1
    ) -> List[Dict[str, Any]]:
        """获取用户贡献最多的仓库"""
        result = []
        now = datetime.now(timezone.utc)
        tasks = []

        for i in range(1, last_n_years + 1):
            start = now - relativedelta(years=i)
            logging.info(f"Querying pull requests contributions for {start.year} ...")
            tasks.append(self.query(MostPullRequestRepositoriesQuery(login, start)))

        results = await asyncio.gather(*tasks)
        for data in results:
            result.extend(data)

        maps = {}
        for item in result:
            url = item["repository"]["url"]
            if url not in maps:
                maps[url] = {"pull_requests": 0, "repository": item["repository"]}
            maps[url]["pull_requests"] += item["contributions"]["totalCount"]

        items = maps.items()
        sorted_items = sorted(items, key=lambda x: x[1]["pull_requests"], reverse=True)
        return [item[1] for item in sorted_items[:10]]

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
