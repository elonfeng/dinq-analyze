package fetcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
)

const apifyLinkedInActorID = "2SyF0bVxmgGr8IVCZ"

// LinkedInClient LinkedIn数据获取客户端
type LinkedInClient struct {
	tavilyAPIKey string
	apifyAPIKey  string
	httpClient   *http.Client
}

// NewLinkedInClient 创建LinkedIn客户端
func NewLinkedInClient(tavilyAPIKey, apifyAPIKey string) *LinkedInClient {
	return &LinkedInClient{
		tavilyAPIKey: tavilyAPIKey,
		apifyAPIKey:  apifyAPIKey,
		httpClient: &http.Client{
			Timeout: 120 * time.Second, // Apify可能需要较长时间
		},
	}
}

// LinkedInSearchResult LinkedIn搜索结果
type LinkedInSearchResult struct {
	URL        string  `json:"url"`
	Title      string  `json:"title"`
	Content    string  `json:"content"`
	Score      float64 `json:"score"`
	PersonName string  `json:"person_name"`
}

// LinkedInProfileData LinkedIn档案原始数据
type LinkedInProfileData struct {
	LinkedInID            string                   `json:"linkedInId"`
	FirstName             string                   `json:"firstName"`
	LastName              string                   `json:"lastName"`
	FullName              string                   `json:"fullName"`
	Headline              string                   `json:"headline"`
	Location              string                   `json:"location"`
	AddressWithCountry    string                   `json:"addressWithCountry"`
	About                 string                   `json:"about"`
	ProfileURL            string                   `json:"url"`
	ProfilePic            string                   `json:"profilePic"`
	ProfilePicHighQuality string                   `json:"profilePicHighQuality"`
	Connections           int                      `json:"connections"`
	Followers             int                      `json:"followers"`
	CompanyName           string                   `json:"companyName"`
	CompanyIndustry       string                   `json:"companyIndustry"`
	CompanySize           string                   `json:"companySize"`
	CompanyLogo           string                   `json:"companyLogo"`
	JobTitle              string                   `json:"jobTitle"`
	Experiences           []LinkedInExperienceRaw  `json:"experiences"`
	Educations            []LinkedInEducationRaw   `json:"educations"`
	Skills                []LinkedInSkillRaw       `json:"skills"`
	Languages             []LinkedInLanguageRaw    `json:"languages"`
	Certifications        []map[string]interface{} `json:"certifications"`
	Recommendations       []map[string]interface{} `json:"recommendations"`
	// RawData 保存完整的原始Apify响应，包含所有字段
	RawData map[string]interface{} `json:"-"`
}

// LinkedInExperienceRaw 原始工作经历
type LinkedInExperienceRaw struct {
	Title         string                   `json:"title"`
	Subtitle      string                   `json:"subtitle"`
	Caption       string                   `json:"caption"`
	CompanyLink1  string                   `json:"companyLink1"`
	Logo          string                   `json:"logo"`
	SubComponents []map[string]interface{} `json:"subComponents"`
}

// LinkedInEducationRaw 原始教育经历
type LinkedInEducationRaw struct {
	Title         string                   `json:"title"`
	Subtitle      string                   `json:"subtitle"`
	Caption       string                   `json:"caption"`
	CompanyLink1  string                   `json:"companyLink1"`
	Logo          string                   `json:"logo"`
	SubComponents []map[string]interface{} `json:"subComponents"`
}

// LinkedInSkillRaw 原始技能
type LinkedInSkillRaw struct {
	Title string `json:"title"`
}

// LinkedInLanguageRaw 原始语言
type LinkedInLanguageRaw struct {
	Title string `json:"title"`
}

// SearchLinkedInURL 搜索LinkedIn URL (使用site:linkedin.com格式)
func (c *LinkedInClient) SearchLinkedInURL(ctx context.Context, personName string) ([]LinkedInSearchResult, error) {
	// 使用 site:linkedin.com (name) 格式搜索
	query := fmt.Sprintf("site:linkedin.com/in/ (%s)", personName)

	reqBody := tavilyRequest{
		APIKey:            c.tavilyAPIKey,
		Query:             query,
		SearchDepth:       "basic",
		MaxResults:        10,
		IncludeAnswer:     false,
		IncludeRawContent: false,
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.tavily.com/search", bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to search: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("tavily returned status %d: %s", resp.StatusCode, string(body))
	}

	var tavilyResp tavilyResponse
	if err := json.NewDecoder(resp.Body).Decode(&tavilyResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	log.Printf("[LinkedIn Search] Query: %s, Results: %d", query, len(tavilyResp.Results))

	// 过滤LinkedIn个人主页结果
	var results []LinkedInSearchResult
	for _, r := range tavilyResp.Results {
		if strings.Contains(r.URL, "linkedin.com/in/") {
			results = append(results, LinkedInSearchResult{
				URL:        r.URL,
				Title:      r.Title,
				Content:    r.Content,
				Score:      r.Score,
				PersonName: ExtractLinkedInNameFromTitle(r.Title), // 从title提取名字
			})
		}
	}

	return results, nil
}

// ExtractLinkedInNameFromTitle 从LinkedIn标题中提取名字
// 标题格式通常是 "Name - Title | LinkedIn" 或 "Name | LinkedIn"
func ExtractLinkedInNameFromTitle(title string) string {
	// 移除 " | LinkedIn" 后缀
	title = strings.TrimSuffix(title, " | LinkedIn")
	title = strings.TrimSuffix(title, " - LinkedIn")

	// 尝试按 " - " 分割，取第一部分作为名字
	if idx := strings.Index(title, " - "); idx > 0 {
		return strings.TrimSpace(title[:idx])
	}

	// 如果没有分隔符，整个标题可能就是名字
	return strings.TrimSpace(title)
}

// isLikelyMatch 判断是否匹配目标人物
func (c *LinkedInClient) isLikelyMatch(url, title, content, personName string) bool {
	// 提取LinkedIn用户名
	if !strings.Contains(url, "linkedin.com/in/") {
		return false
	}

	parts := strings.Split(url, "linkedin.com/in/")
	if len(parts) < 2 {
		return false
	}
	linkedinUsername := strings.Split(strings.Split(parts[1], "?")[0], "/")[0]

	// 将人名转换为可能的LinkedIn用户名格式
	nameParts := strings.Fields(strings.ToLower(personName))

	// 检查用户名是否包含人名的一部分
	for _, part := range nameParts {
		if len(part) > 2 && strings.Contains(strings.ToLower(linkedinUsername), part) {
			return true
		}
	}

	// 检查标题和内容是否包含人名
	searchText := strings.ToLower(title + " " + content)
	for _, part := range nameParts {
		if len(part) > 2 && strings.Contains(searchText, part) {
			return true
		}
	}

	return false
}

// ExtractLinkedInID 从URL中提取LinkedIn ID
func ExtractLinkedInID(linkedinURL string) string {
	if !strings.Contains(linkedinURL, "linkedin.com/in/") {
		return ""
	}
	parts := strings.Split(linkedinURL, "linkedin.com/in/")
	if len(parts) < 2 {
		return ""
	}
	return strings.Split(strings.Split(parts[1], "?")[0], "/")[0]
}

// FetchProfile 获取LinkedIn档案数据 (使用Apify同步API)
func (c *LinkedInClient) FetchProfile(ctx context.Context, linkedinURL string) (*LinkedInProfileData, error) {
	// 使用 run-sync-get-dataset-items 同步API，无需轮询
	apiURL := fmt.Sprintf("https://api.apify.com/v2/acts/%s/run-sync-get-dataset-items?token=%s",
		apifyLinkedInActorID, c.apifyAPIKey)

	reqBody := map[string]interface{}{
		"profileUrls": []string{linkedinURL},
	}
	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, apiURL, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("apify request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("apify returned status %d: %s", resp.StatusCode, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// 打印Apify返回的原始内容
	log.Printf("[Apify LinkedIn] Raw response (first 2000 chars): %s", truncateString(string(body), 2000))

	// 解析返回的数组
	var profiles []map[string]interface{}
	if err := json.Unmarshal(body, &profiles); err != nil {
		return nil, fmt.Errorf("failed to parse apify response: %w", err)
	}

	if len(profiles) == 0 {
		return nil, fmt.Errorf("no profile data returned from apify")
	}

	// 转换为结构体
	profileBytes, err := json.Marshal(profiles[0])
	if err != nil {
		return nil, fmt.Errorf("failed to marshal profile: %w", err)
	}

	var profile LinkedInProfileData
	if err := json.Unmarshal(profileBytes, &profile); err != nil {
		return nil, fmt.Errorf("failed to unmarshal profile: %w", err)
	}

	// 保存完整的原始数据
	profile.RawData = profiles[0]

	// 设置LinkedIn ID
	if profile.LinkedInID == "" {
		profile.LinkedInID = ExtractLinkedInID(linkedinURL)
	}
	if profile.ProfileURL == "" {
		profile.ProfileURL = linkedinURL
	}

	return &profile, nil
}

// GetFullName 获取完整姓名
func (p *LinkedInProfileData) GetFullName() string {
	if p.FullName != "" {
		return p.FullName
	}
	if p.FirstName != "" || p.LastName != "" {
		return strings.TrimSpace(p.FirstName + " " + p.LastName)
	}
	return ""
}

// GetLocation 获取位置
func (p *LinkedInProfileData) GetLocation() string {
	if p.AddressWithCountry != "" {
		return p.AddressWithCountry
	}
	return p.Location
}

// GetPhotoURL 获取头像URL
func (p *LinkedInProfileData) GetPhotoURL() string {
	if p.ProfilePicHighQuality != "" {
		return p.ProfilePicHighQuality
	}
	return p.ProfilePic
}

// GetHeadline 获取职位头衔
func (p *LinkedInProfileData) GetHeadline() string {
	if p.Headline != "" {
		return p.Headline
	}
	return p.JobTitle
}

// truncateString 截断字符串到指定长度
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
