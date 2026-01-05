package model

import "encoding/json"

// GitHubCardType GitHub卡片类型
type GitHubCardType string

const (
	GitHubCardProfile   GitHubCardType = "profile_card"
	GitHubCardActivity  GitHubCardType = "activity_card"
	GitHubCardRepos     GitHubCardType = "repos_card"
	GitHubCardRoleModel GitHubCardType = "role_model_card"
	GitHubCardRoast     GitHubCardType = "roast_card"
	GitHubCardSummary   GitHubCardType = "summary_card"
)

// AllGitHubCards 所有GitHub卡片类型
var AllGitHubCards = []GitHubCardType{
	GitHubCardProfile, GitHubCardActivity, GitHubCardRepos,
	GitHubCardRoleModel, GitHubCardRoast, GitHubCardSummary,
}

// GitHubCardMap 并发安全的GitHub card状态map
type GitHubCardMap struct {
	CardMap
}

// NewGitHubCardMap 创建GitHubCardMap
func NewGitHubCardMap() *GitHubCardMap {
	return &GitHubCardMap{}
}

// SetGitHub 设置GitHub card状态
func (c *GitHubCardMap) SetGitHub(card GitHubCardType, state *CardState) {
	c.m.Store(card, state)
}

// GetGitHub 获取GitHub card状态
func (c *GitHubCardMap) GetGitHub(card GitHubCardType) *CardState {
	v, ok := c.m.Load(card)
	if !ok {
		return nil
	}
	return v.(*CardState)
}

// MarshalJSON 实现json序列化 (覆盖嵌入的CardMap方法)
func (c *GitHubCardMap) MarshalJSON() ([]byte, error) {
	m := make(map[GitHubCardType]*CardState)
	c.m.Range(func(k, v interface{}) bool {
		m[k.(GitHubCardType)] = v.(*CardState)
		return true
	})
	return json.Marshal(m)
}

// GitHubAnalysisState GitHub分析状态
type GitHubAnalysisState struct {
	Status        string         `json:"status"`         // "analyzing" | "completed" | "error"
	Login         string         `json:"login"`          // GitHub用户名
	Overall       int            `json:"overall"`        // 整体进度 0-100
	CurrentAction string         `json:"current_action"` // 当前动作
	Cards         *GitHubCardMap `json:"cards"`          // 所有card状态
	Error         string         `json:"error,omitempty"`
}

// NewGitHubAnalysisState 创建初始状态
func NewGitHubAnalysisState(login string) *GitHubAnalysisState {
	cards := NewGitHubCardMap()
	for _, card := range AllGitHubCards {
		cards.SetGitHub(card, &CardState{Status: StatusPending})
	}
	return &GitHubAnalysisState{
		Status:        "analyzing",
		Login:         login,
		Overall:       0,
		CurrentAction: "Initializing...",
		Cards:         cards,
	}
}

// ========== Profile Card ==========

// GitHubProfileCard GitHub个人资料卡片
type GitHubProfileCard struct {
	Login       string `json:"login"`
	Name        string `json:"name"`
	AvatarURL   string `json:"avatar_url"`
	URL         string `json:"url"`
	Bio         string `json:"bio,omitempty"`
	Company     string `json:"company,omitempty"`
	Location    string `json:"location,omitempty"`
	Email       string `json:"email,omitempty"`
	Blog        string `json:"blog,omitempty"`
	TwitterUser string `json:"twitter_username,omitempty"`
	Followers   int    `json:"followers"`
	Following   int    `json:"following"`
	PublicRepos int    `json:"public_repos"`
	CreatedAt   string `json:"created_at"`
}

// ========== Activity Card ==========

// GitHubActivityOverview GitHub活动概览
type GitHubActivityOverview struct {
	WorkExperience int `json:"work_experience"` // years
	Stars          int `json:"stars"`
	Issues         int `json:"issues"`
	PullRequests   int `json:"pull_requests"`
	Repositories   int `json:"repositories"`
	Additions      int `json:"additions"`
	Deletions      int `json:"deletions"`
	ActiveDays     int `json:"active_days"`
}

// GitHubDailyActivity 每日活动统计
type GitHubDailyActivity struct {
	Date          string `json:"date"`
	PullRequests  int    `json:"pull_requests"`
	Issues        int    `json:"issues"`
	Comments      int    `json:"comments"`
	Contributions int    `json:"contributions"`
}

// GitHubCodeContribution 代码贡献统计
type GitHubCodeContribution struct {
	Total          int            `json:"total"`
	TotalAdditions int            `json:"total_additions"`
	TotalDeletions int            `json:"total_deletions"`
	TotalCommits   int            `json:"total_commits"`
	Languages      map[string]int `json:"languages,omitempty"`
}

// GitHubActivityCard GitHub活动卡片
type GitHubActivityCard struct {
	Overview         GitHubActivityOverview `json:"overview"`
	Activity         []GitHubDailyActivity  `json:"activity"`
	CodeContribution GitHubCodeContribution `json:"code_contribution"`
}

// ========== Repos Card ==========

// GitHubRepository GitHub仓库信息
type GitHubRepository struct {
	Name            string   `json:"name"`
	FullName        string   `json:"full_name,omitempty"`
	Description     string   `json:"description,omitempty"`
	URL             string   `json:"url"`
	Stars           int      `json:"stars"`
	Forks           int      `json:"forks"`
	Language        string   `json:"language,omitempty"`
	Topics          []string `json:"topics,omitempty"`
	IsOwner         bool     `json:"is_owner"`
	PullRequests    int      `json:"pull_requests,omitempty"`    // 用户的PR数
	ContributionPct float64  `json:"contribution_pct,omitempty"` // 贡献占比
}

// GitHubPullRequest GitHub PR信息
type GitHubPullRequest struct {
	Title      string `json:"title"`
	URL        string `json:"url"`
	Repository string `json:"repository"`
	Additions  int    `json:"additions"`
	Deletions  int    `json:"deletions"`
	Comments   int    `json:"comments"`
	MergedAt   string `json:"merged_at,omitempty"`
	State      string `json:"state"`
}

// GitHubReposCard GitHub仓库卡片
type GitHubReposCard struct {
	FeatureProject          *GitHubRepository  `json:"feature_project,omitempty"`
	TopProjects             []GitHubRepository `json:"top_projects"`
	MostValuablePullRequest *GitHubPullRequest `json:"most_valuable_pull_request,omitempty"`
}

// ========== Role Model Card ==========

// GitHubRoleModelCard GitHub榜样卡片
type GitHubRoleModelCard struct {
	Name            string  `json:"name"`
	GitHub          string  `json:"github"`
	AvatarURL       string  `json:"avatar_url,omitempty"`
	SimilarityScore float64 `json:"similarity_score"`
	Reason          string  `json:"reason"`
	Achievement     string  `json:"achievement,omitempty"`
}

// ========== Roast Card ==========

// GitHubRoastCard GitHub吐槽卡片
type GitHubRoastCard struct {
	Roast string `json:"roast"`
}

// ========== Summary Card ==========

// GitHubValuationLevel GitHub估值等级
type GitHubValuationLevel struct {
	Level           string  `json:"level"`            // e.g. "L5"
	SalaryRange     []int   `json:"salary_range"`     // e.g. [210000, 250000]
	IndustryRanking float64 `json:"industry_ranking"` // e.g. 0.25 = top 25%
	GrowthPotential string  `json:"growth_potential"` // e.g. "High"
	Reasoning       string  `json:"reasoning"`
}

// GitHubSummaryCard GitHub摘要卡片
type GitHubSummaryCard struct {
	ValuationAndLevel GitHubValuationLevel `json:"valuation_and_level"`
	Description       string               `json:"description"`
}
