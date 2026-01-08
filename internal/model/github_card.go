package model

import "encoding/json"

// GitHubCardType GitHub卡片类型
type GitHubCardType string

const (
	GitHubCardProfile        GitHubCardType = "profile_card"
	GitHubCardActivity       GitHubCardType = "activity_card"
	GitHubCardFeatureProject GitHubCardType = "feature_project_card"
	GitHubCardTopProjects    GitHubCardType = "top_projects_card"
	GitHubCardMostValuablePR GitHubCardType = "most_valuable_pr_card"
	GitHubCardRoleModel      GitHubCardType = "role_model_card"
	GitHubCardRoast          GitHubCardType = "roast_card"
	GitHubCardValuation      GitHubCardType = "valuation_card"
)

// AllGitHubCards 所有GitHub卡片类型
var AllGitHubCards = []GitHubCardType{
	GitHubCardProfile, GitHubCardActivity, GitHubCardFeatureProject,
	GitHubCardTopProjects, GitHubCardMostValuablePR,
	GitHubCardRoleModel, GitHubCardRoast, GitHubCardValuation,
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
	Login        string   `json:"login"`
	Name         string   `json:"name"`
	AvatarURL    string   `json:"avatar_url"`
	URL          string   `json:"url"`
	Bio          string   `json:"bio,omitempty"`
	Company      string   `json:"company,omitempty"`
	Location     string   `json:"location,omitempty"`
	Email        string   `json:"email,omitempty"`
	Blog         string   `json:"blog,omitempty"`
	TwitterUser  string   `json:"twitter_username,omitempty"`
	Followers    int      `json:"followers"`
	Following    int      `json:"following"`
	PublicRepos  int      `json:"public_repos"`
	CreatedAt    string   `json:"created_at"`
	PersonalTags []string `json:"personal_tags,omitempty"`
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

// ========== Feature Project Card ==========

// GitHubRepoOwner 仓库所有者信息
type GitHubRepoOwner struct {
	AvatarURL string `json:"avatarUrl,omitempty"`
}

// GitHubFeatureProjectCard Feature Project卡片
type GitHubFeatureProjectCard struct {
	UsedBy          int              `json:"used_by"`
	Contributors    int              `json:"contributors"`
	MonthlyTrending int              `json:"monthly_trending"`
	Name            string           `json:"name"`
	NameWithOwner   string           `json:"nameWithOwner"`
	URL             string           `json:"url"`
	Description     string           `json:"description,omitempty"`
	Owner           *GitHubRepoOwner `json:"owner,omitempty"`
	StargazerCount  int              `json:"stargazerCount"`
	ForkCount       int              `json:"forkCount"`
	Tags            []string         `json:"tags,omitempty"`
}

// ========== Top Projects Card ==========

// GitHubTopProjectRepo Top Project中的仓库信息
type GitHubTopProjectRepo struct {
	URL            string           `json:"url"`
	Name           string           `json:"name"`
	Description    string           `json:"description,omitempty"`
	Owner          *GitHubRepoOwner `json:"owner,omitempty"`
	StargazerCount int              `json:"stargazerCount"`
}

// GitHubTopProject Top Project贡献信息
type GitHubTopProject struct {
	PullRequests int                   `json:"pull_requests"`
	Repository   *GitHubTopProjectRepo `json:"repository"`
}

// GitHubTopProjectsCard Top Projects卡片
type GitHubTopProjectsCard struct {
	Projects []GitHubTopProject `json:"projects"`
}

// ========== Most Valuable PR Card ==========

// GitHubMostValuablePRCard Most Valuable PR卡片
type GitHubMostValuablePRCard struct {
	Repository string `json:"repository"`
	URL        string `json:"url"`
	Title      string `json:"title"`
	Additions  int    `json:"additions"`
	Deletions  int    `json:"deletions"`
	Reason     string `json:"reason,omitempty"`
	Impact     string `json:"impact,omitempty"`
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
	Salary          int     `json:"salary"`           // e.g. 250000
	IndustryRanking float64 `json:"industry_ranking"` // e.g. 0.25 = top 25%
	GrowthPotential string  `json:"growth_potential"` // e.g. "High"
	Reasoning       string  `json:"reasoning"`
}

// GitHubSummaryCard GitHub摘要卡片
type GitHubSummaryCard struct {
	ValuationAndLevel GitHubValuationLevel `json:"valuation_and_level"`
	Description       string               `json:"description"`
}
