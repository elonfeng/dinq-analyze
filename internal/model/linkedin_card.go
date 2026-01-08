package model

import "encoding/json"

// LinkedInCardType LinkedIn卡片类型
type LinkedInCardType string

const (
	LinkedInCardProfile       LinkedInCardType = "profile_card"
	LinkedInCardMoney         LinkedInCardType = "money_card"
	LinkedInCardRoast         LinkedInCardType = "roast_card"
	LinkedInCardSkills        LinkedInCardType = "skills_card"
	LinkedInCardColleagues    LinkedInCardType = "colleagues_card"
	LinkedInCardCareer        LinkedInCardType = "career_card"
	LinkedInCardRoleModel     LinkedInCardType = "role_model_card"
	LinkedInCardLifeWellBeing LinkedInCardType = "life_well_being_card"
)

// AllLinkedInCards 所有LinkedIn卡片类型
var AllLinkedInCards = []LinkedInCardType{
	LinkedInCardProfile, LinkedInCardMoney, LinkedInCardRoast,
	LinkedInCardSkills, LinkedInCardColleagues, LinkedInCardCareer,
	LinkedInCardRoleModel, LinkedInCardLifeWellBeing,
}

// LinkedInCardMap 并发安全的LinkedIn card状态map
type LinkedInCardMap struct {
	CardMap
}

// NewLinkedInCardMap 创建LinkedInCardMap
func NewLinkedInCardMap() *LinkedInCardMap {
	return &LinkedInCardMap{}
}

// SetLinkedIn 设置LinkedIn card状态
func (c *LinkedInCardMap) SetLinkedIn(card LinkedInCardType, state *CardState) {
	c.m.Store(card, state)
}

// GetLinkedIn 获取LinkedIn card状态
func (c *LinkedInCardMap) GetLinkedIn(card LinkedInCardType) *CardState {
	v, ok := c.m.Load(card)
	if !ok {
		return nil
	}
	return v.(*CardState)
}

// MarshalJSON 实现json序列化
func (c *LinkedInCardMap) MarshalJSON() ([]byte, error) {
	m := make(map[LinkedInCardType]*CardState)
	c.m.Range(func(k, v interface{}) bool {
		m[k.(LinkedInCardType)] = v.(*CardState)
		return true
	})
	return json.Marshal(m)
}

// CountDone 计算已完成的card数量
func (c *LinkedInCardMap) CountDone() int {
	count := 0
	c.m.Range(func(k, v interface{}) bool {
		if state, ok := v.(*CardState); ok && state.Status == StatusDone {
			count++
		}
		return true
	})
	return count
}

// LinkedInCandidate LinkedIn候选人 (直接使用Tavily返回的结构)
type LinkedInCandidate struct {
	URL     string  `json:"url"`     // LinkedIn URL
	Title   string  `json:"title"`   // 标题，如 "Keith Rabois - Khosla Ventures"
	Content string  `json:"content"` // 内容摘要，用作about
	Score   float64 `json:"score"`   // 匹配分数
}

// LinkedInAnalysisState LinkedIn分析状态
type LinkedInAnalysisState struct {
	Status        string              `json:"status"`               // "analyzing" | "need_selection" | "completed" | "error"
	LinkedInID    string              `json:"linkedin_id"`          // LinkedIn用户名
	PersonName    string              `json:"person_name"`          // 姓名
	Overall       int                 `json:"overall"`              // 整体进度 0-100
	CurrentAction string              `json:"current_action"`       // 当前动作
	Candidates    []LinkedInCandidate `json:"candidates,omitempty"` // 候选人列表（需要选择时）
	Cards         *LinkedInCardMap    `json:"cards"`                // 所有card状态
	Error         string              `json:"error,omitempty"`
}

// NewLinkedInAnalysisState 创建初始状态
func NewLinkedInAnalysisState(linkedInID, personName string) *LinkedInAnalysisState {
	cards := NewLinkedInCardMap()
	for _, card := range AllLinkedInCards {
		cards.SetLinkedIn(card, &CardState{Status: StatusPending})
	}
	return &LinkedInAnalysisState{
		Status:        "analyzing",
		LinkedInID:    linkedInID,
		PersonName:    personName,
		Overall:       0,
		CurrentAction: "Initializing...",
		Cards:         cards,
	}
}

// ========== Profile Card ==========

// LinkedInProfileCard LinkedIn个人资料卡片
type LinkedInProfileCard struct {
	LinkedInID  string `json:"linkedin_id"`
	FullName    string `json:"full_name"`
	FirstName   string `json:"first_name,omitempty"`
	LastName    string `json:"last_name,omitempty"`
	Headline    string `json:"headline"`
	Location    string `json:"location,omitempty"`
	About       string `json:"about,omitempty"`
	ProfileURL  string `json:"profile_url"`
	PhotoURL    string `json:"photo_url,omitempty"`
	Connections int    `json:"connections"`
	Followers   int    `json:"followers"`
	CompanyName string `json:"company_name,omitempty"`
	CompanyLogo string `json:"company_logo,omitempty"`
}

// ========== Money Card (money_analysis in Python) ==========

// LinkedInYearsOfExperience 工作经验
type LinkedInYearsOfExperience struct {
	Years            int    `json:"years"`
	StartYear        int    `json:"start_year"`
	CalculationBasis string `json:"calculation_basis"`
}

// LinkedInMoneyCard LinkedIn薪资分析卡片 (matches Python money_analysis)
type LinkedInMoneyCard struct {
	YearsOfExperience LinkedInYearsOfExperience `json:"years_of_experience"`
	LevelUS           string                    `json:"level_us"`         // e.g. "L5"
	LevelCN           string                    `json:"level_cn"`         // e.g. "P7"
	EstimatedSalary   int                       `json:"estimated_salary"` // e.g. 250000
	Explanation       string                    `json:"explanation"`
}

// ========== Roast Card ==========

// LinkedInRoastCard LinkedIn吐槽卡片
type LinkedInRoastCard struct {
	Roast string `json:"roast"`
}

// ========== Skills Card (matches Python skills structure) ==========

// LinkedInSkillsCard LinkedIn技能卡片 (简单字符串数组，匹配Python版本)
type LinkedInSkillsCard struct {
	IndustryKnowledge   []string `json:"industry_knowledge"`
	ToolsTechnologies   []string `json:"tools_technologies"`
	InterpersonalSkills []string `json:"interpersonal_skills"`
	Language            []string `json:"language"` // Python版本用的是language不是languages
}

// ========== Colleagues Card (colleagues_view in Python) ==========

// LinkedInColleaguesCard LinkedIn同事评价卡片
type LinkedInColleaguesCard struct {
	Highlights          []string `json:"highlights"`
	AreasForImprovement []string `json:"areas_for_improvement"`
}

// ========== Career Card ==========

// LinkedInDevelopmentAdvice 发展建议
type LinkedInDevelopmentAdvice struct {
	PastEvaluation           string `json:"past_evaluation"`
	SimplifiedPastEvaluation string `json:"simplified_past_evaluation,omitempty"`
	FutureAdvice             string `json:"future_advice"`
}

// LinkedInCareerCard LinkedIn职业卡片
type LinkedInCareerCard struct {
	FutureDevelopmentPotential           string                    `json:"future_development_potential"`
	SimplifiedFutureDevelopmentPotential string                    `json:"simplified_future_development_potential,omitempty"`
	DevelopmentAdvice                    LinkedInDevelopmentAdvice `json:"development_advice"`
}

// ========== Role Model Card ==========

// LinkedInRoleModelCard LinkedIn榜样卡片
type LinkedInRoleModelCard struct {
	Name             string `json:"name"`
	Institution      string `json:"institution"`
	Position         string `json:"position"`
	PhotoURL         string `json:"photo_url"` // 不用omitempty，确保字段始终存在
	Achievement      string `json:"achievement"`
	SimilarityReason string `json:"similarity_reason"`
	IsCelebrity      bool   `json:"is_celebrity"`
	CelebrityReason  string `json:"celebrity_reasoning,omitempty"`
}

// ========== Life & Well-Being Card (matches Python structure) ==========

// LinkedInAction 行动项
type LinkedInAction struct {
	Emoji  string `json:"emoji"`
	Phrase string `json:"phrase"`
}

// LinkedInSuggestion 建议
type LinkedInSuggestion struct {
	Advice           string           `json:"advice"`
	SimplifiedAdvice string           `json:"simplified_advice"`
	Actions          []LinkedInAction `json:"actions"`
}

// LinkedInLifeWellBeingCard LinkedIn生活建议卡片
type LinkedInLifeWellBeingCard struct {
	LifeSuggestion LinkedInSuggestion `json:"life_suggestion"`
	Health         LinkedInSuggestion `json:"health"`
}

// ========== Work Experience & Education (from raw profile) ==========

// LinkedInExperience 工作经历 (matches Apify output)
type LinkedInExperience struct {
	CompanyID       string `json:"companyId,omitempty"`
	CompanyUrn      string `json:"companyUrn,omitempty"`
	CompanyLink1    string `json:"companyLink1,omitempty"`
	CompanyName     string `json:"companyName,omitempty"`
	CompanySize     string `json:"companySize,omitempty"`
	CompanyWebsite  string `json:"companyWebsite,omitempty"`
	CompanyIndustry string `json:"companyIndustry,omitempty"`
	Logo            string `json:"logo,omitempty"`
	Title           string `json:"title,omitempty"`
	JobDescription  string `json:"jobDescription,omitempty"`
	JobStartedOn    string `json:"jobStartedOn,omitempty"`
	JobEndedOn      string `json:"jobEndedOn,omitempty"`
	JobLocation     string `json:"jobLocation,omitempty"`
	JobStillWorking bool   `json:"jobStillWorking,omitempty"`
	EmploymentType  string `json:"employmentType,omitempty"`
}

// LinkedInEducation 教育经历 (matches Apify output)
type LinkedInEducation struct {
	CompanyID    string                 `json:"companyId,omitempty"`
	CompanyUrn   string                 `json:"companyUrn,omitempty"`
	CompanyLink1 string                 `json:"companyLink1,omitempty"`
	Logo         string                 `json:"logo,omitempty"`
	Title        string                 `json:"title,omitempty"`    // School name
	Subtitle     string                 `json:"subtitle,omitempty"` // Degree
	Description  string                 `json:"description,omitempty"`
	Grade        string                 `json:"grade,omitempty"`
	Period       map[string]interface{} `json:"period,omitempty"`
}

// ========== Complete Profile Data (matches Python profile_data) ==========

// LinkedInProfileData 完整的LinkedIn分析数据 (matches Python profile_data structure)
type LinkedInProfileData struct {
	RoleModel             *LinkedInRoleModelCard     `json:"role_model,omitempty"`
	MoneyAnalysis         *LinkedInMoneyCard         `json:"money_analysis,omitempty"`
	Roast                 string                     `json:"roast,omitempty"`
	Skills                *LinkedInSkillsCard        `json:"skills,omitempty"`
	ColleaguesView        *LinkedInColleaguesCard    `json:"colleagues_view,omitempty"`
	Career                *LinkedInCareerCard        `json:"career,omitempty"`
	LifeWellBeing         *LinkedInLifeWellBeingCard `json:"life_well_being,omitempty"`
	About                 string                     `json:"about,omitempty"`
	PersonalTags          []string                   `json:"personal_tags,omitempty"`
	WorkExperience        interface{}                `json:"work_experience,omitempty"` // 直接使用原始数据
	WorkExperienceSummary string                     `json:"work_experience_summary,omitempty"`
	Education             interface{}                `json:"education,omitempty"` // 直接使用原始数据
	EducationSummary      string                     `json:"education_summary,omitempty"`
	Avatar                interface{}                `json:"avatar"` // 可能为null
	Name                  string                     `json:"name,omitempty"`
}

// ========== Complete Result (matches Python final output) ==========

// LinkedInAnalysisResult 完整的LinkedIn分析结果 (matches Python output)
type LinkedInAnalysisResult struct {
	LinkedInID  string               `json:"linkedin_id"`
	PersonName  string               `json:"person_name"`
	LinkedInURL string               `json:"linkedin_url"`
	ProfileData *LinkedInProfileData `json:"profile_data"`
	LastUpdated string               `json:"last_updated"`
	CreatedAt   string               `json:"created_at"`
}

// LinkedInFinalResponse 最终SSE响应 (matches Python final SSE message)
type LinkedInFinalResponse struct {
	Type    string                  `json:"type"`
	Message string                  `json:"message"`
	Data    *LinkedInAnalysisResult `json:"data"`
}
