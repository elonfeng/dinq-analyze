package fetcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const githubGraphQLEndpoint = "https://api.github.com/graphql"

// GitHubClient GitHub GraphQL API客户端
type GitHubClient struct {
	token      string
	httpClient *http.Client
}

// NewGitHubClient 创建GitHub客户端
func NewGitHubClient(token string) *GitHubClient {
	return &GitHubClient{
		token: token,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// GraphQLRequest GraphQL请求结构
type GraphQLRequest struct {
	Query     string                 `json:"query"`
	Variables map[string]interface{} `json:"variables,omitempty"`
}

// GraphQLResponse GraphQL响应结构
type GraphQLResponse struct {
	Data   json.RawMessage `json:"data"`
	Errors []struct {
		Message string `json:"message"`
	} `json:"errors,omitempty"`
}

// query 执行GraphQL查询
func (c *GitHubClient) query(ctx context.Context, query string, variables map[string]interface{}) (json.RawMessage, error) {
	reqBody := GraphQLRequest{
		Query:     query,
		Variables: variables,
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", githubGraphQLEndpoint, bytes.NewReader(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error: %s - %s", resp.Status, string(body))
	}

	var gqlResp GraphQLResponse
	if err := json.Unmarshal(body, &gqlResp); err != nil {
		return nil, fmt.Errorf("failed to unmarshal response: %w", err)
	}

	if len(gqlResp.Errors) > 0 {
		return nil, fmt.Errorf("GraphQL error: %s", gqlResp.Errors[0].Message)
	}

	return gqlResp.Data, nil
}

// GitHubUserData GitHub用户数据（从bundle查询返回）
type GitHubUserData struct {
	ID           string                   `json:"id"`
	Name         string                   `json:"name"`
	Login        string                   `json:"login"`
	CreatedAt    string                   `json:"createdAt"`
	Bio          string                   `json:"bio"`
	AvatarURL    string                   `json:"avatarUrl"`
	URL          string                   `json:"url"`
	Followers    struct{ TotalCount int } `json:"followers"`
	Following    struct{ TotalCount int } `json:"following"`
	Issues       struct{ TotalCount int } `json:"issues"`
	PullRequests struct{ TotalCount int } `json:"pullRequests"`
	Repositories struct{ TotalCount int } `json:"repositories"`
	TopRepos     struct {
		Nodes []GitHubRepo `json:"nodes"`
	} `json:"topRepos"`
	PullRequestsTop struct {
		TotalCount int            `json:"totalCount"`
		Nodes      []GitHubPRNode `json:"nodes"`
	} `json:"pullRequestsTop"`
	ContributionsCollection struct {
		ContributionCalendar struct {
			Weeks []struct {
				ContributionDays []struct {
					Date              string `json:"date"`
					ContributionCount int    `json:"contributionCount"`
				} `json:"contributionDays"`
			} `json:"weeks"`
		} `json:"contributionCalendar"`
		PRContributions []struct {
			Contributions struct{ TotalCount int } `json:"contributions"`
			Repository    GitHubRepo               `json:"repository"`
		} `json:"pullRequestContributionsByRepository"`
	} `json:"contributionsCollection"`
}

// GitHubRepo GitHub仓库信息
type GitHubRepo struct {
	Name            string `json:"name"`
	NameWithOwner   string `json:"nameWithOwner"`
	URL             string `json:"url"`
	Description     string `json:"description"`
	StargazerCount  int    `json:"stargazerCount"`
	ForkCount       int    `json:"forkCount"`
	PrimaryLanguage struct {
		Name string `json:"name"`
	} `json:"primaryLanguage"`
	RepositoryTopics struct {
		Nodes []struct {
			Topic struct {
				Name string `json:"name"`
			} `json:"topic"`
		} `json:"nodes"`
	} `json:"repositoryTopics"`
	Owner struct {
		AvatarURL string `json:"avatarUrl"`
	} `json:"owner"`
}

// GitHubPRNode GitHub PR节点
type GitHubPRNode struct {
	URL        string `json:"url"`
	Title      string `json:"title"`
	Additions  int    `json:"additions"`
	Deletions  int    `json:"deletions"`
	Repository struct {
		NameWithOwner  string `json:"nameWithOwner"`
		URL            string `json:"url"`
		StargazerCount int    `json:"stargazerCount"`
		ForkCount      int    `json:"forkCount"`
		Languages      struct {
			Edges []struct {
				Size int `json:"size"`
				Node struct {
					Name string `json:"name"`
				} `json:"node"`
			} `json:"edges"`
		} `json:"languages"`
	} `json:"repository"`
}

const bundleQuery = `
query($login: String!, $from: DateTime!, $to: DateTime!) {
    user(login: $login) {
        id
        name
        login
        createdAt
        bio
        avatarUrl
        url
        followers { totalCount }
        following { totalCount }
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
                primaryLanguage { name }
                repositoryTopics(first: 5) {
                    nodes { topic { name } }
                }
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
`

// FetchBundle 获取GitHub用户数据bundle（单次请求获取大部分数据）
func (c *GitHubClient) FetchBundle(ctx context.Context, login string) (*GitHubUserData, error) {
	now := time.Now().UTC()
	oneYearAgo := now.AddDate(-1, 0, 0)

	variables := map[string]interface{}{
		"login": login,
		"from":  oneYearAgo.Format(time.RFC3339),
		"to":    now.Format(time.RFC3339),
	}

	data, err := c.query(ctx, bundleQuery, variables)
	if err != nil {
		return nil, err
	}

	var result struct {
		User *GitHubUserData `json:"user"`
	}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal user data: %w", err)
	}

	if result.User == nil {
		return nil, fmt.Errorf("user not found: %s", login)
	}

	return result.User, nil
}

const pullRequestsQuery = `
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
    }
}
`

// PRStats Pull Request统计
type PRStats struct {
	TotalCount int
	Nodes      []GitHubPRNode
	Mutations  struct {
		Additions int
		Deletions int
		Languages map[string]int
	}
}

// FetchPullRequests 获取用户PR统计
func (c *GitHubClient) FetchPullRequests(ctx context.Context, login string) (*PRStats, error) {
	variables := map[string]interface{}{
		"login": login,
	}

	data, err := c.query(ctx, pullRequestsQuery, variables)
	if err != nil {
		return nil, err
	}

	var result struct {
		User struct {
			PullRequests struct {
				TotalCount int            `json:"totalCount"`
				Nodes      []GitHubPRNode `json:"nodes"`
			} `json:"pullRequests"`
		} `json:"user"`
	}
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal PR data: %w", err)
	}

	stats := &PRStats{
		TotalCount: result.User.PullRequests.TotalCount,
		Nodes:      result.User.PullRequests.Nodes,
	}

	// 计算代码变更统计
	var totalAdditions, totalDeletions int
	languages := make(map[string]int)

	for _, pr := range stats.Nodes {
		totalAdditions += pr.Additions
		totalDeletions += pr.Deletions

		total := pr.Additions + pr.Deletions
		var langSize int
		for _, lang := range pr.Repository.Languages.Edges {
			langSize += lang.Size
		}
		if langSize > 0 {
			for _, lang := range pr.Repository.Languages.Edges {
				pct := float64(lang.Size) / float64(langSize)
				languages[lang.Node.Name] += int(pct * float64(total))
			}
		}
	}

	count := len(stats.Nodes)
	if count > 0 {
		stats.Mutations.Additions = totalAdditions / count * stats.TotalCount
		stats.Mutations.Deletions = totalDeletions / count * stats.TotalCount
		for name := range languages {
			languages[name] = languages[name] / count * stats.TotalCount
		}
	}
	stats.Mutations.Languages = languages

	return stats, nil
}

// prContributionsQuery PR贡献查询（按年）
const prContributionsQuery = `
query($login: String!, $from: DateTime!, $to: DateTime!) {
    user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
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
`

// PRContribution PR贡献信息
type PRContribution struct {
	PullRequests int
	Repository   GitHubRepo
}

// FetchMultiYearPRContributions 获取多年PR贡献（类似Python的most_pull_request_repositories）
func (c *GitHubClient) FetchMultiYearPRContributions(ctx context.Context, login string, workExp int) ([]PRContribution, error) {
	if workExp < 1 {
		workExp = 1
	}
	if workExp > 10 {
		workExp = 10 // 最多查10年
	}

	now := time.Now().UTC()
	repoMap := make(map[string]*PRContribution)

	// 并发查询每年的PR贡献
	type yearResult struct {
		contributions []struct {
			Contributions struct{ TotalCount int } `json:"contributions"`
			Repository    GitHubRepo               `json:"repository"`
		}
		err error
	}

	results := make(chan yearResult, workExp)

	for i := 0; i < workExp; i++ {
		go func(yearOffset int) {
			to := now.AddDate(-yearOffset, 0, 0)
			from := now.AddDate(-yearOffset-1, 0, 0)

			variables := map[string]interface{}{
				"login": login,
				"from":  from.Format(time.RFC3339),
				"to":    to.Format(time.RFC3339),
			}

			data, err := c.query(ctx, prContributionsQuery, variables)
			if err != nil {
				results <- yearResult{err: err}
				return
			}

			var result struct {
				User struct {
					ContributionsCollection struct {
						PRContributions []struct {
							Contributions struct{ TotalCount int } `json:"contributions"`
							Repository    GitHubRepo               `json:"repository"`
						} `json:"pullRequestContributionsByRepository"`
					} `json:"contributionsCollection"`
				} `json:"user"`
			}
			if err := json.Unmarshal(data, &result); err != nil {
				results <- yearResult{err: err}
				return
			}

			results <- yearResult{contributions: result.User.ContributionsCollection.PRContributions}
		}(i)
	}

	// 收集结果
	for i := 0; i < workExp; i++ {
		yr := <-results
		if yr.err != nil {
			continue // 忽略单年失败
		}
		for _, contrib := range yr.contributions {
			url := contrib.Repository.URL
			if existing, ok := repoMap[url]; ok {
				existing.PullRequests += contrib.Contributions.TotalCount
			} else {
				repoMap[url] = &PRContribution{
					PullRequests: contrib.Contributions.TotalCount,
					Repository:   contrib.Repository,
				}
			}
		}
	}

	// 转换为slice并排序
	contributions := make([]PRContribution, 0, len(repoMap))
	for _, c := range repoMap {
		contributions = append(contributions, *c)
	}

	// 按PR数量降序排序
	for i := 0; i < len(contributions)-1; i++ {
		for j := i + 1; j < len(contributions); j++ {
			if contributions[j].PullRequests > contributions[i].PullRequests {
				contributions[i], contributions[j] = contributions[j], contributions[i]
			}
		}
	}

	// 只返回前10个
	if len(contributions) > 10 {
		contributions = contributions[:10]
	}

	return contributions, nil
}

// mutationsQuery 查询用户仓库的commit数据来估算代码改动
const mutationsQuery = `
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
`

// CommitMutations 提交代码改动统计
type CommitMutations struct {
	Additions int
	Deletions int
	Languages map[string]int
}

// FetchCommitMutations 获取用户仓库的commit代码改动统计
func (c *GitHubClient) FetchCommitMutations(ctx context.Context, login string, userID string) (*CommitMutations, error) {
	variables := map[string]interface{}{
		"login":   login,
		"user_id": userID,
	}

	data, err := c.query(ctx, mutationsQuery, variables)
	if err != nil {
		return nil, err
	}

	var result struct {
		User struct {
			Repositories struct {
				TotalCount int `json:"totalCount"`
				Nodes      []struct {
					Name      string `json:"name"`
					Languages struct {
						Edges []struct {
							Size int `json:"size"`
							Node struct {
								Name string `json:"name"`
							} `json:"node"`
						} `json:"edges"`
					} `json:"languages"`
					DefaultBranchRef *struct {
						Target struct {
							History struct {
								TotalCount int `json:"totalCount"`
								Nodes      []struct {
									Additions int `json:"additions"`
									Deletions int `json:"deletions"`
								} `json:"nodes"`
							} `json:"history"`
						} `json:"target"`
					} `json:"defaultBranchRef"`
				} `json:"nodes"`
			} `json:"repositories"`
		} `json:"user"`
	}

	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal mutations data: %w", err)
	}

	totalRepoCount := result.User.Repositories.TotalCount
	repos := result.User.Repositories.Nodes

	var totalAdditions, totalDeletions int
	totalLanguages := make(map[string]int)
	delta := 0.85 // 与Python一致的系数

	for _, repo := range repos {
		if repo.DefaultBranchRef == nil {
			continue
		}

		history := repo.DefaultBranchRef.Target.History
		if len(history.Nodes) == 0 {
			continue
		}

		var repoAdditions, repoDeletions int
		for _, commit := range history.Nodes {
			repoAdditions += commit.Additions
			repoDeletions += commit.Deletions
		}

		// 按采样比例放大
		commitCount := len(history.Nodes)
		branchTotalCommits := history.TotalCount
		if commitCount > 0 && branchTotalCommits > 0 {
			scale := float64(branchTotalCommits) / float64(commitCount)
			repoAdditions = int(float64(repoAdditions) * scale * delta)
			repoDeletions = int(float64(repoDeletions) * scale * delta)
		}

		totalAdditions += repoAdditions
		totalDeletions += repoDeletions

		// 按语言分配
		repoTotal := repoAdditions + repoDeletions
		var langSizeSum int
		for _, lang := range repo.Languages.Edges {
			langSizeSum += lang.Size
		}
		if langSizeSum > 0 {
			for _, lang := range repo.Languages.Edges {
				ratio := float64(lang.Size) / float64(langSizeSum)
				totalLanguages[lang.Node.Name] += int(float64(repoTotal) * ratio)
			}
		}
	}

	// 按仓库数量放大
	sampleCount := len(repos)
	if sampleCount > 0 && totalRepoCount > 0 {
		scale := float64(totalRepoCount) / float64(sampleCount)
		totalAdditions = int(float64(totalAdditions) * scale)
		totalDeletions = int(float64(totalDeletions) * scale)
		for name := range totalLanguages {
			totalLanguages[name] = int(float64(totalLanguages[name]) * scale)
		}
	}

	return &CommitMutations{
		Additions: totalAdditions,
		Deletions: totalDeletions,
		Languages: totalLanguages,
	}, nil
}
