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
	CardEarnings            CardType = "earnings_card"
	CardResearchStyle       CardType = "research_style_card"
	CardRoleModel           CardType = "role_model_card"
	CardRoast               CardType = "roast_card"
	CardInsight             CardType = "insight_card"
	CardClosestCollaborator CardType = "closest_collaborator_card"
	CardPaperOfYear         CardType = "paper_of_year_card"
	CardRepresentative      CardType = "representative_paper_card"
)

// AllCards 所有card类型
var AllCards = []CardType{
	CardProfile, CardPapers, CardEarnings, CardResearchStyle,
	CardRoleModel, CardRoast,
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
	Name        string `json:"name"`
	Affiliation string `json:"affiliation"`
	Avatar      string `json:"avatar,omitempty"`
	Interests   string `json:"interests"`
	ScholarURL  string `json:"scholar_url"`
	Description string `json:"description,omitempty"`
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
	TotalPapers     int            `json:"total_papers"`
	TotalCitations  int            `json:"total_citations"`
	HIndex          int            `json:"h_index"`
	HIndex5y        int            `json:"h_index_5y,omitempty"`
	I10Index        int            `json:"i10_index"`
	Citations5y     int            `json:"citations_5y,omitempty"`
	YearlyCitations map[string]int `json:"yearly_citations,omitempty"`
	YearlyStats     map[int]int    `json:"yearly_stats"`
	Papers          []Paper        `json:"papers"`
}

// EarningsCard 薪资卡片
type EarningsCard struct {
	Earnings int    `json:"earnings"` // 年薪（单个数字，美元）
	LevelCN  string `json:"level_cn"` // 中国职级 (P6/P7/P8...)
	LevelUS  string `json:"level_us"` // 美国职级 (L4/L5/L6...)
	Reason   string `json:"reason"`   // 评估理由
}

// ResearchStyleDimension 研究风格维度
type ResearchStyleDimension struct {
	Score       int    `json:"score"`       // 1-10分
	Explanation string `json:"explanation"` // 解释说明
}

// ResearchStyleCard 研究风格卡片
type ResearchStyleCard struct {
	DepthVsBreadth   ResearchStyleDimension `json:"depth_vs_breadth"`   // 深度vs广度
	TheoryVsPractice ResearchStyleDimension `json:"theory_vs_practice"` // 理论vs实践
	IndividualVsTeam ResearchStyleDimension `json:"individual_vs_team"` // 个人vs团队
	Justification    string                 `json:"justification"`      // 总体分析理由
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
