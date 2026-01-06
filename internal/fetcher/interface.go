package fetcher

import "context"

// HTMLFetcher 获取网页HTML (Crawlbase)
type HTMLFetcher interface {
	FetchScholarPage(ctx context.Context, scholarID string) (string, error)
}

// SearchFetcher 搜索获取器 (Tavily)
type SearchFetcher interface {
	SearchNews(ctx context.Context, query string, maxResults int) ([]NewsResult, error)
	SearchScholar(ctx context.Context, name string) ([]ScholarCandidate, error)
}

// LLMClient LLM客户端 (OpenRouter)
type LLMClient interface {
	GenerateEarnings(ctx context.Context, profile ProfileData, papers []PaperData) (*EarningsResult, error)
	GenerateResearchStyle(ctx context.Context, profile ProfileData, papers []PaperData) (*ResearchStyleResult, error)
	GenerateRoleModel(ctx context.Context, profile ProfileData) (*RoleModelResult, error)
	GenerateRoast(ctx context.Context, profile ProfileData) (string, error)
	SummarizeContent(ctx context.Context, text string) (string, error)
}

// NewsResult 新闻搜索结果
type NewsResult struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Source  string `json:"source"`
	Date    string `json:"date"`
	Snippet string `json:"snippet"`
}

// ScholarCandidate 学者候选人
type ScholarCandidate struct {
	ScholarID string `json:"scholar_id"`
	Name      string `json:"name"`
	Content   string `json:"content"`
	URL       string `json:"url"`
}

// ProfileData 用于LLM分析的profile数据
type ProfileData struct {
	Name            string         `json:"name"`
	Affiliation     string         `json:"affiliation"`
	Interests       string         `json:"interests"`
	HIndex          int            `json:"h_index"`
	HIndex5y        int            `json:"h_index_5y"`
	I10Index        int            `json:"i10_index"`
	TotalCites      int            `json:"total_cites"`
	Citations5y     int            `json:"citations_5y"`
	YearlyCitations map[string]int `json:"yearly_citations,omitempty"`
}

// PaperData 用于LLM分析的论文数据
type PaperData struct {
	Title     string   `json:"title"`
	Authors   []string `json:"authors"`
	Year      int      `json:"year"`
	Citations int      `json:"citations"`
	Venue     string   `json:"venue"`
}

// EarningsResult 薪资分析结果
type EarningsResult struct {
	LevelCN             string               `json:"level_cn"`
	LevelUS             string               `json:"level_us"`
	Earnings            int                  `json:"earnings"` // 单个数字
	Justification       string               `json:"justification"`
	CompensationFactors *CompensationFactors `json:"compensation_factors,omitempty"`
}

// CompensationFactors 薪资计算因子
type CompensationFactors struct {
	ResearchImpactScore     float64 `json:"research_impact_score"`
	FieldPremiumScore       float64 `json:"field_premium_score"`
	RoleSeniorityScore      float64 `json:"role_seniority_score"`
	IndustryLeadershipScore float64 `json:"industry_leadership_score"`
	MarketCompetitionScore  float64 `json:"market_competition_score"`
}

// ResearchStyleDimension 研究风格维度
type ResearchStyleDimension struct {
	Score       int    `json:"score"`
	Explanation string `json:"explanation"`
}

// ResearchStyleResult 研究风格分析结果
type ResearchStyleResult struct {
	DepthVsBreadth   ResearchStyleDimension `json:"depth_vs_breadth"`
	TheoryVsPractice ResearchStyleDimension `json:"theory_vs_practice"`
	IndividualVsTeam ResearchStyleDimension `json:"individual_vs_team"`
	Justification    string                 `json:"justification"`
}

// RoleModelResult 榜样结果
type RoleModelResult struct {
	Name        string `json:"name"`
	Institution string `json:"institution,omitempty"`
	Position    string `json:"position,omitempty"`
	PhotoURL    string `json:"photo_url,omitempty"`
	Achievement string `json:"achievement,omitempty"`
	Reason      string `json:"reason"`
	Similarity  string `json:"similarity"`
}
