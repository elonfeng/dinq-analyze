package model

import (
	"encoding/json"
	"sync"
)

// CardType 定义card类型
type CardType string

const (
	CardProfile             CardType = "profile_card"
	CardPapers              CardType = "papers_card"
	CardCoauthors           CardType = "coauthors_card"
	CardLevel               CardType = "level_card"
	CardSummary             CardType = "summary_card"
	CardRoleModel           CardType = "role_model_card"
	CardNews                CardType = "news_card"
	CardRoast               CardType = "roast_card"
	CardInsight             CardType = "insight_card"
	CardClosestCollaborator CardType = "closest_collaborator_card"
	CardPaperOfYear         CardType = "paper_of_year_card"
	CardRepresentative      CardType = "representative_paper_card"
)

// AllCards 所有card类型
var AllCards = []CardType{
	CardProfile, CardPapers, CardCoauthors, CardLevel,
	CardSummary, CardRoleModel, CardNews, CardRoast,
	CardInsight, CardClosestCollaborator, CardPaperOfYear, CardRepresentative,
}

// CardStatus card状态
type CardStatus string

const (
	StatusPending CardStatus = "pending"
	StatusDone    CardStatus = "done"
	StatusError   CardStatus = "error"
)

// CardState 单个card的状态
type CardState struct {
	Status CardStatus  `json:"status"`          // pending/done/error
	Data   interface{} `json:"data,omitempty"`  // 数据
	Error  string      `json:"error,omitempty"` // 错误信息
}

// CardMap 并发安全的card状态map
type CardMap struct {
	m sync.Map
}

// NewCardMap 创建CardMap
func NewCardMap() *CardMap {
	return &CardMap{}
}

// Set 设置card状态
func (c *CardMap) Set(card CardType, state *CardState) {
	c.m.Store(card, state)
}

// Get 获取card状态
func (c *CardMap) Get(card CardType) *CardState {
	v, ok := c.m.Load(card)
	if !ok {
		return nil
	}
	return v.(*CardState)
}

// CountDone 统计已完成的card数量
func (c *CardMap) CountDone() int {
	count := 0
	c.m.Range(func(_, v interface{}) bool {
		if state := v.(*CardState); state.Status == StatusDone || state.Status == StatusError {
			count++
		}
		return true
	})
	return count
}

// MarshalJSON 实现json序列化
func (c *CardMap) MarshalJSON() ([]byte, error) {
	m := make(map[CardType]*CardState)
	c.m.Range(func(k, v interface{}) bool {
		m[k.(CardType)] = v.(*CardState)
		return true
	})
	return json.Marshal(m)
}

// ScholarCandidate 学者候选人
type ScholarCandidate struct {
	ScholarID string `json:"scholar_id"`
	Name      string `json:"name"`
	Content   string `json:"content"`
	URL       string `json:"url"`
}

// AnalysisState 完整分析状态 - SSE每次输出这个完整结构
type AnalysisState struct {
	Status        string             `json:"status"`               // "analyzing" | "need_selection" | "completed" | "error"
	Query         string             `json:"query,omitempty"`      // 用户查询
	Overall       int                `json:"overall"`              // 整体进度 0-100
	CurrentAction string             `json:"current_action"`       // 当前AI在做什么
	Candidates    []ScholarCandidate `json:"candidates,omitempty"` // 候选人列表（需要选择时）
	Cards         *CardMap           `json:"cards"`                // 所有card状态（并发安全）
	Error         string             `json:"error,omitempty"`      // 全局错误
}

// NewAnalysisState 创建初始状态
func NewAnalysisState() *AnalysisState {
	cards := NewCardMap()
	for _, card := range AllCards {
		cards.Set(card, &CardState{Status: StatusPending})
	}
	return &AnalysisState{
		Status:        "analyzing",
		Overall:       0,
		CurrentAction: "Initializing...",
		Cards:         cards,
	}
}

// ProfileCard profile卡片数据
type ProfileCard struct {
	Name            string         `json:"name"`
	Affiliation     string         `json:"affiliation"`
	Email           string         `json:"email,omitempty"`
	Avatar          string         `json:"avatar,omitempty"`
	Homepage        string         `json:"homepage,omitempty"`
	Interests       string         `json:"interests"`
	HIndex          int            `json:"h_index"`
	HIndex5y        int            `json:"h_index_5y,omitempty"`
	I10Index        int            `json:"i10_index"`
	TotalCites      int            `json:"total_cites"`
	Citations5y     int            `json:"citations_5y,omitempty"`
	YearlyCitations map[string]int `json:"yearly_citations,omitempty"`
	ScholarID       string         `json:"scholar_id"`
	ScholarURL      string         `json:"scholar_url"`
	Description     string         `json:"description,omitempty"`
}

// Paper 论文信息
type Paper struct {
	Title     string   `json:"title"`
	Authors   []string `json:"authors"`
	Venue     string   `json:"venue"`
	Year      int      `json:"year"`
	Citations int      `json:"citations"`
	URL       string   `json:"url,omitempty"`
}

// PapersCard 论文卡片数据
type PapersCard struct {
	TotalPapers    int         `json:"total_papers"`
	TotalCitations int         `json:"total_citations"`
	Papers         []Paper     `json:"papers"`
	YearlyStats    map[int]int `json:"yearly_stats"`
}

// Coauthor 合作者
type Coauthor struct {
	Name        string `json:"name"`
	ScholarID   string `json:"scholar_id,omitempty"`
	Affiliation string `json:"affiliation,omitempty"`
	PaperCount  int    `json:"paper_count,omitempty"`
}

// CoauthorsCard 合作者卡片
type CoauthorsCard struct {
	TotalCoauthors int        `json:"total_coauthors"`
	Coauthors      []Coauthor `json:"coauthors"`
}

// LevelCard 职级卡片
type LevelCard struct {
	LevelCN       string                 `json:"level_cn"`
	LevelUS       string                 `json:"level_us"`
	Earnings      string                 `json:"earnings"`
	Justification string                 `json:"justification"`
	ResearchStyle map[string]interface{} `json:"research_style,omitempty"`
}

// SummaryCard 摘要卡片
type SummaryCard struct {
	Summary       string   `json:"summary"`
	Keywords      []string `json:"keywords"`
	ResearchAreas []string `json:"research_areas"`
}

// RoleModelCard 榜样卡片
type RoleModelCard struct {
	Name        string `json:"name"`
	Institution string `json:"institution,omitempty"`
	Position    string `json:"position,omitempty"`
	PhotoURL    string `json:"photo_url,omitempty"`
	Achievement string `json:"achievement,omitempty"`
	Reason      string `json:"reason"`
	Similarity  string `json:"similarity"`
}

// NewsItem 新闻条目
type NewsItem struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Source  string `json:"source,omitempty"`
	Date    string `json:"date,omitempty"`
	Snippet string `json:"snippet"`
}

// NewsCard 新闻卡片
type NewsCard struct {
	Items []NewsItem `json:"items"`
}

// RoastCard 吐槽卡片
type RoastCard struct {
	Roast string `json:"roast"`
}

// InsightCard 论文洞察卡片
type InsightCard struct {
	TotalPapers            int            `json:"total_papers"`
	TopTierPapers          int            `json:"top_tier_papers"`
	FirstAuthorPapers      int            `json:"first_author_papers"`
	FirstAuthorCitations   int            `json:"first_author_citations"`
	LastAuthorPapers       int            `json:"last_author_papers"`
	TotalCoauthors         int            `json:"total_coauthors"`
	ConferenceDistribution map[string]int `json:"conference_distribution"`
}

// ClosestCollaboratorCard 最亲密合作者卡片
type ClosestCollaboratorCard struct {
	FullName            string         `json:"full_name"`
	Affiliation         string         `json:"affiliation,omitempty"`
	ScholarID           string         `json:"scholar_id,omitempty"`
	CoauthoredPapers    int            `json:"coauthored_papers"`
	Avatar              string         `json:"avatar,omitempty"`
	BestCoauthoredPaper *BestPaperInfo `json:"best_coauthored_paper,omitempty"`
}

// BestPaperInfo 最佳论文信息
type BestPaperInfo struct {
	Title     string `json:"title"`
	Year      int    `json:"year"`
	Venue     string `json:"venue"`
	Citations int    `json:"citations"`
}

// PaperOfYearCard 年度论文卡片
type PaperOfYearCard struct {
	Title          string `json:"title"`
	Year           int    `json:"year"`
	Venue          string `json:"venue"`
	Citations      int    `json:"citations"`
	AuthorPosition int    `json:"author_position"`
	Summary        string `json:"summary,omitempty"`
}

// RepresentativePaperCard 代表作卡片
type RepresentativePaperCard struct {
	Title          string     `json:"title"`
	Year           int        `json:"year"`
	Venue          string     `json:"venue"`
	FullVenue      string     `json:"full_venue,omitempty"`
	Citations      int        `json:"citations"`
	AuthorPosition int        `json:"author_position"`
	PaperNews      *PaperNews `json:"paper_news,omitempty"`
}

// PaperNews 论文相关新闻
type PaperNews struct {
	News        string `json:"news"`
	Date        string `json:"date"`
	Description string `json:"description"`
	URL         string `json:"url,omitempty"`
	IsFallback  bool   `json:"is_fallback"`
}
