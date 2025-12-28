from typing import Any, Optional, Dict, List
from collections import defaultdict
from datetime import datetime

def safe_parse_datetime(datetime_str: str) -> Optional[datetime]:
    """
    安全的日期时间解析函数

    Args:
        datetime_str: 日期时间字符串

    Returns:
        解析后的datetime对象，如果解析失败返回None
    """
    if not datetime_str:
        return None

    try:
        # 处理 'Z' 时区标识符 (UTC)
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str[:-1] + '+00:00'

        return datetime.fromisoformat(datetime_str)
    except ValueError:
        # 如果解析失败，尝试其他格式
        try:
            # 尝试标准ISO格式
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except ValueError:
            # 如果还是失败，返回None
            return None


class Query:
    """查询的基类"""

    def __init__(self):
        # GraphQL变量参数
        self.vars = {}
        # 判断查询是否完成,用于有分页的情况
        self._finished = False

    def json(self) -> Dict[str, Any]:
        """构造查询请求体"""
        return {"query": self.__class__.QUERY, "variables": self.vars}

    def process(self, data: Any) -> Any:
        """处理响应数据"""
        self._finished = True
        return data


class UserQuery(Query):
    """查询用户的基本信息和仓库的统计信息"""

    QUERY = """
        query($login: String!) {
            user(login: $login) {
                id
                name
                login
                createdAt
                bio
                avatarUrl
                url
                issues {
                    totalCount
                }
                pullRequests {
                    totalCount
                }
                repositories(isFork: false, ownerAffiliations: [OWNER]) {
                    totalCount
                }
            }
        }
    """

    def __init__(self, login: str):
        super().__init__()
        self.vars["login"] = login

    def process(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._finished = True
        return data["user"]


class GithubBundleQuery(Query):
    """
    Single-shot GitHub data bundle query (no pagination).

    Goal: minimize request fan-out by fetching all fields needed by unified cards in one GraphQL call.

    Notes:
    - We intentionally cap list sizes (top repos, PR candidates, PR repos) to keep payload small and stable.
    - Activity uses contributionCalendar only (no search(...) fan-out).
    """

    QUERY = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $login) {
                id
                name
                login
                createdAt
                bio
                avatarUrl
                url
                issues { totalCount }
                pullRequests { totalCount }
                repositories(isFork: false, ownerAffiliations: [OWNER]) { totalCount }

                topRepos: repositories(
                    isFork: false,
                    ownerAffiliations: [OWNER],
                    first: 50,
                    orderBy: { field: STARGAZERS, direction: DESC }
                ) {
                    nodes {
                        name
                        nameWithOwner
                        url
                        description
                        owner { avatarUrl }
                        stargazerCount
                        forkCount
                    }
                }

                pullRequestsTop: pullRequests(first: 50, orderBy: { field: COMMENTS, direction: DESC }) {
                    totalCount
                    nodes {
                        url
                        title
                        additions
                        deletions
                        repository {
                            nameWithOwner
                            url
                            stargazerCount
                            forkCount
                            languages(first: 3, orderBy: { field: SIZE, direction: DESC }) {
                                edges {
                                    size
                                    node { name }
                                }
                            }
                        }
                    }
                }

                contributionsCollection(from: $from, to: $to) {
                    contributionCalendar {
                        weeks {
                            contributionDays {
                                date
                                contributionCount
                            }
                        }
                    }
                    pullRequestContributionsByRepository(maxRepositories: 10) {
                        contributions(orderBy: { direction: DESC }) {
                            totalCount
                        }
                        repository {
                            url
                            name
                            description
                            owner { avatarUrl }
                            stargazerCount
                        }
                    }
                }
            }
        }
    """

    def __init__(self, login: str, start: datetime, end: datetime):
        super().__init__()
        self.vars["login"] = login
        self.vars["from"] = start.isoformat()
        self.vars["to"] = end.isoformat()

    def process(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._finished = True
        return data["user"]


class Search(Query):
    """搜索基类"""

    def strftime(self, date: datetime | str) -> str:
        if isinstance(date, str):
            parsed_date = safe_parse_datetime(date)
            if parsed_date is None:
                # 如果解析失败，尝试使用当前时间作为fallback
                date = datetime.now()
            else:
                date = parsed_date
        return date.strftime("%Y-%m-%d")

    def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = data["search"]
        # 搜索结果也可以不分页
        if "pageInfo" not in result:
            return result.get("nodes", [])
        # 如果分页,一定有edges节点
        self.vars["cursor"] = result["pageInfo"]["endCursor"]
        self._finished = not result["pageInfo"]["hasNextPage"]
        return [edge["node"] for edge in result["edges"]]


class CountDaysSearch(Search):
    """将搜索结果按日期聚合的基类"""

    def __init__(self, start: datetime, end: datetime):
        super().__init__()
        self.vars["query"] = f"created:{self.strftime(start)}..{self.strftime(end)}"
        self.vars["cursor"] = ""

    def process(self, data: Dict[str, Any]) -> List[Any]:
        result = defaultdict(int)
        for item in super().process(data):
            key = self.strftime(item["createdAt"])
            result[key] += 1
        return list(result.items())


class PullRequestDaysQuery(CountDaysSearch):
    """查询指定日期范围内用户提交的所有Pull Requests"""

    QUERY = """
        query($query: String!, $cursor: String) {
            search(query: $query, type: ISSUE, after: $cursor, first: 100) {
                edges {
                    node {
                        ... on PullRequest {
                            url
                            createdAt
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    """

    def __init__(self, query: str, start: datetime, end: datetime):
        super().__init__(start, end)
        self.vars["query"] = f"is:pr {query} {self.vars['query']}"


class IssueDaysQuery(CountDaysSearch):
    """查询指定日期范围内用户提交的所有Issues"""

    QUERY = """
        query($query: String!, $cursor: String) {
            search(query: $query, type: ISSUE, after: $cursor, first: 100) {
                edges {
                    node {
                        ... on Issue {
                            url
                            createdAt
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    """

    def __init__(self, query: str, start: datetime, end: datetime):
        super().__init__(start, end)
        self.vars["query"] = f"is:issue {query} {self.vars['query']}"


class ContributionDaysQuery(Query):
    """查询指定日期范围内用户每天的Contributions数量"""

    QUERY = """
        query($login: String!, $start: DateTime!, $end: DateTime!) {
            user(login: $login) {
                contributionsCollection(from: $start, to: $end) {
                    contributionCalendar {
                        weeks {
                            contributionDays {
                                date
                                contributionCount
                            }
                        }
                    }
                }
            }
        }
    """

    def __init__(self, login: str, start: datetime, end: datetime):
        super().__init__()
        self.vars["login"] = login
        self.vars["start"] = start.isoformat()
        self.vars["end"] = end.isoformat()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self._finished = True
        result = {}
        items = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for item in [day for week in items for day in week["contributionDays"]]:
            result[item["date"]] = item["contributionCount"]
        return result


class PullRequestsQuery(Query):
    """
    根据评论数查询前50个Pull Requests
    用于分析最有价值的Pull Request以及用来估算全部Pull Requests的代码改动行数
    不需要分页,有些人的Pull Requests太多,全部查询出来会消耗非常多的points
    """

    QUERY = """
        query($login: String!) {
            user(login: $login) {
                pullRequests(first: 50, orderBy: { field: COMMENTS, direction: DESC }) {
                    totalCount
                    nodes {
                        url
                        title
                        additions
                        deletions
                        repository {
                            languages(first: 3, orderBy: { field: SIZE, direction: DESC }) {
                                edges {
                                    size
                                    node {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    def __init__(self, login: str):
        super().__init__()
        self.vars["login"] = login

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self._finished = True
        total_count = data["user"]["pullRequests"]["totalCount"]
        pull_requests = data["user"]["pullRequests"]["nodes"]
        total_additions, total_deletions = 0, 0
        total_mutations = {"additions": 0, "deletions": 0}
        total_languages = defaultdict(int)
        for pull_request in pull_requests:
            additions = pull_request["additions"]
            deletions = pull_request["deletions"]
            total_additions += additions
            total_deletions += deletions
            total = additions + deletions
            languages_size = 0
            languages = pull_request["repository"]["languages"]["edges"]
            for language in languages:
                languages_size += language["size"]
            for language in languages:
                name = language["node"]["name"]
                percent = language["size"] / languages_size
                total_languages[name] += round(percent * total)
        count = len(pull_requests)
        if count > 0:
            total_additions = round(total_additions / count * total_count)
            total_deletions = round(total_deletions / count * total_count)
            total_mutations["additions"] = total_additions
            total_mutations["deletions"] = total_deletions
            for name in total_languages:
                mutations = round(total_languages[name] / count * total_count)
                total_languages[name] = mutations
        total_mutations["languages"] = dict(total_languages)
        return {"mutations": total_mutations, "nodes": pull_requests}


class MutationsQuery(Query):
    """查询最近10个仓库每个仓库100个Commits的数据用来估算全部仓库的代码改动"""

    QUERY = """
        query($login: String!, $user_id: ID!) {
            user(login: $login) {
                repositories(isFork: false, ownerAffiliations: [OWNER], first: 10, orderBy: { field: CREATED_AT, direction: DESC }) {
                    totalCount
                    nodes {
                        name
                        languages(first: 3, orderBy: { field: SIZE, direction: DESC }) {
                            edges {
                                size
                                node {
                                    name
                                }
                            }
                        }
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history(first: 100, author: { id: $user_id }) {
                                        totalCount
                                        nodes {
                                            additions
                                            deletions
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    def __init__(self, login: str, user_id: str):
        super().__init__()
        self.vars["login"] = login
        self.vars["user_id"] = user_id

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self._finished = True
        total_count = data["user"]["repositories"]["totalCount"]
        repositories = data["user"]["repositories"]["nodes"]
        total_additions, total_deletions = 0, 0
        total_mutations = {"additions": 0, "deletions": 0}
        total_languages = defaultdict(int)
        delta = 0.85
        for repository in repositories:
            if repository is None:
                continue
            additions, deletions = 0, 0
            if not repository["defaultBranchRef"]:
                continue
            branch = repository["defaultBranchRef"]["target"]
            branch_commit_count = branch["history"]["totalCount"]
            commits = branch["history"]["nodes"]
            for commit in commits:
                additions += commit["additions"]
                deletions += commit["deletions"]
            count = len(commits)
            if count == 0:
                continue
            additions = additions / count * branch_commit_count
            additions = round(additions * delta)
            deletions = deletions / count * branch_commit_count
            deletions = round(deletions * delta)
            total_additions += additions
            total_deletions += deletions
            total = additions + deletions
            languages_size = 0
            languages = repository["languages"]["edges"]
            for language in languages:
                languages_size += language["size"]
            for language in languages:
                name = language["node"]["name"]
                percent = language["size"] / languages_size
                total_languages[name] += round(percent * total)
        count = len(repositories)
        if count > 0:
            total_additions = round(total_additions / count * total_count)
            total_deletions = round(total_deletions / count * total_count)
            total_mutations["additions"] = total_additions
            total_mutations["deletions"] = total_deletions
            for name in total_languages:
                mutations = round(total_languages[name] / count * total_count)
                total_languages[name] = mutations
        total_mutations["languages"] = dict(total_languages)
        return total_mutations


class MostStarredRepositoriesQuery(Query):
    """查询用户Star数量最多的仓库,不包含Fork的仓库"""

    QUERY = """
        query($login: String!, $cursor: String) {
            user(login: $login) {
                repositories(isFork: false, ownerAffiliations: [OWNER], first: 100, after: $cursor, orderBy: { field: STARGAZERS, direction: DESC }) {
                    edges {
                        node {
                            name
                            nameWithOwner
                            url
                            description
                            owner {
                                avatarUrl
                            }
                            stargazerCount
                            forkCount
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }
    """

    def __init__(self, login: str):
        super().__init__()
        self.vars["login"] = login
        self.vars["cursor"] = ""

    def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        repositories = data["user"]["repositories"]
        self.vars["cursor"] = repositories["pageInfo"]["endCursor"]
        self._finished = not repositories["pageInfo"]["hasNextPage"]
        return [edge["node"] for edge in repositories["edges"]]


class MostPullRequestRepositoriesQuery(Query):
    """统计Pull Requests数量最多的3个仓库,按年查询"""

    QUERY = """
        query($login: String!, $start: DateTime) {
            user(login: $login) {
                contributionsCollection(from: $start) {
                    pullRequestContributionsByRepository(maxRepositories: 3) {
                        contributions(orderBy: { direction: DESC }) {
                            totalCount
                        }
                        repository {
                            url
                            name
                            description
                            owner {
                                avatarUrl
                            }
                            stargazerCount
                        }
                    }
                }
            }
        }
    """

    def __init__(self, login, start: datetime):
        super().__init__()
        self.vars["login"] = login
        self.vars["start"] = start.isoformat()

    def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        self._finished = True
        collection = data["user"]["contributionsCollection"]
        return collection["pullRequestContributionsByRepository"]
