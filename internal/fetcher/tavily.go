package fetcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
	"unicode"
)

// TavilyFetcher Tavily搜索获取器
type TavilyFetcher struct {
	apiKey     string
	httpClient *http.Client
}

// NewTavilyFetcher 创建Tavily获取器
func NewTavilyFetcher(apiKey string) *TavilyFetcher {
	return &TavilyFetcher{
		apiKey: apiKey,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

type tavilyRequest struct {
	APIKey            string   `json:"api_key"`
	Query             string   `json:"query"`
	SearchDepth       string   `json:"search_depth"`
	MaxResults        int      `json:"max_results"`
	IncludeDomains    []string `json:"include_domains,omitempty"`
	IncludeAnswer     bool     `json:"include_answer"`
	IncludeRawContent bool     `json:"include_raw_content"`
}

type tavilyResponse struct {
	Results []struct {
		Title         string  `json:"title"`
		URL           string  `json:"url"`
		Content       string  `json:"content"`
		Score         float64 `json:"score"`
		PublishedDate string  `json:"published_date"`
	} `json:"results"`
}

// SearchNews 搜索新闻
func (t *TavilyFetcher) SearchNews(ctx context.Context, query string, maxResults int) ([]NewsResult, error) {
	reqBody := tavilyRequest{
		APIKey:            t.apiKey,
		Query:             query + " news",
		SearchDepth:       "basic",
		MaxResults:        maxResults,
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

	resp, err := t.httpClient.Do(req)
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

	results := make([]NewsResult, 0, len(tavilyResp.Results))
	for _, r := range tavilyResp.Results {
		results = append(results, NewsResult{
			Title:   r.Title,
			URL:     r.URL,
			Snippet: r.Content,
			Date:    r.PublishedDate,
		})
	}

	return results, nil
}

// SearchScholar 搜索学者候选人
func (t *TavilyFetcher) SearchScholar(ctx context.Context, query string) ([]ScholarCandidate, error) {
	reqBody := tavilyRequest{
		APIKey:            t.apiKey,
		Query:             fmt.Sprintf("%s site:scholar.google.com/citations", query),
		SearchDepth:       "basic",
		MaxResults:        10,
		IncludeDomains:    []string{"scholar.google.com"},
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

	resp, err := t.httpClient.Do(req)
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

	// 从搜索结果中提取学者候选人
	candidates := make([]ScholarCandidate, 0)
	seen := make(map[string]bool) // 去重

	for _, r := range tavilyResp.Results {
		// 解析scholar URL获取ID
		scholarID := extractScholarID(r.URL)
		if scholarID == "" || seen[scholarID] {
			continue
		}
		seen[scholarID] = true

		name := extractNameFromTitle(r.Title)
		candidate := ScholarCandidate{
			ScholarID: scholarID,
			Name:      name,
			Content:   r.Content,
			URL:       r.URL,
		}
		candidates = append(candidates, candidate)
	}

	// 相似度过滤
	candidates = filterBySimilarity(candidates, query)

	return candidates, nil
}

// extractScholarID 从Google Scholar URL中提取user ID
func extractScholarID(url string) string {
	// URL格式: https://scholar.google.com/citations?user=XXXXXX&hl=en
	if !strings.Contains(url, "scholar.google.com/citations") {
		return ""
	}

	// 查找 user= 参数
	idx := strings.Index(url, "user=")
	if idx == -1 {
		return ""
	}

	start := idx + 5
	end := start
	for end < len(url) && url[end] != '&' {
		end++
	}

	return url[start:end]
}

// extractNameFromTitle 从搜索结果title中提取名字
func extractNameFromTitle(title string) string {
	// 去掉特殊Unicode字符
	title = strings.ReplaceAll(title, "‪", "")
	title = strings.ReplaceAll(title, "‬", "")

	// 检查各种横杠格式: " - ", " – ", " — "
	// Title格式: "Xusen Sun - Google 学术搜索", "Name - Affiliation", "Name – University"
	separators := []string{" - ", " – ", " — "}
	for _, sep := range separators {
		if idx := strings.Index(title, sep); idx != -1 {
			title = title[:idx]
			break
		}
	}

	return strings.TrimSpace(title)
}

// filterBySimilarity 根据相似度过滤候选人
func filterBySimilarity(candidates []ScholarCandidate, query string) []ScholarCandidate {
	if len(candidates) == 0 {
		return candidates
	}

	query = strings.ToLower(strings.TrimSpace(query))

	type scored struct {
		candidate ScholarCandidate
		score     float64
	}

	var scoredCandidates []scored
	for _, c := range candidates {
		name := strings.ToLower(c.Name)
		content := strings.ToLower(c.Content)

		score := calculateSimilarity(query, name, content)
		scoredCandidates = append(scoredCandidates, scored{c, score})
	}

	// 按分数排序（高到低）
	for i := 0; i < len(scoredCandidates)-1; i++ {
		for j := i + 1; j < len(scoredCandidates); j++ {
			if scoredCandidates[j].score > scoredCandidates[i].score {
				scoredCandidates[i], scoredCandidates[j] = scoredCandidates[j], scoredCandidates[i]
			}
		}
	}

	// 过滤相似度太低的（阈值0.3），但至少保留3个
	const minThreshold = 0.3
	const minKeep = 3

	var filtered []ScholarCandidate
	for i, sc := range scoredCandidates {
		if sc.score >= minThreshold || i < minKeep {
			filtered = append(filtered, sc.candidate)
		}
	}

	return filtered
}

// calculateSimilarity 计算查询与候选人的相似度
func calculateSimilarity(query, name, content string) float64 {
	var score float64

	// 1. 名字完全匹配
	if name == query {
		score += 1.0
	} else if strings.Contains(name, query) || strings.Contains(query, name) {
		// 名字部分包含
		score += 0.7
	} else {
		// 计算编辑距离相似度
		score += stringSimilarity(query, name) * 0.5
	}

	// 2. content包含查询
	if strings.Contains(content, query) {
		score += 0.3
	}

	return score
}

// stringSimilarity 使用Jaro-Winkler相似度的简化版本
func stringSimilarity(s1, s2 string) float64 {
	if s1 == s2 {
		return 1.0
	}
	if len(s1) == 0 || len(s2) == 0 {
		return 0.0
	}

	// 计算共同前缀长度
	prefixLen := 0
	maxPrefix := 4
	if len(s1) < maxPrefix {
		maxPrefix = len(s1)
	}
	if len(s2) < maxPrefix {
		maxPrefix = len(s2)
	}
	for i := 0; i < maxPrefix; i++ {
		if s1[i] == s2[i] {
			prefixLen++
		} else {
			break
		}
	}

	// 计算共同字符
	r1 := []rune(s1)
	r2 := []rune(s2)
	matchWindow := max(len(r1), len(r2))/2 - 1
	if matchWindow < 0 {
		matchWindow = 0
	}

	matched1 := make([]bool, len(r1))
	matched2 := make([]bool, len(r2))
	matches := 0

	for i := range r1 {
		start := max(0, i-matchWindow)
		end := min(len(r2), i+matchWindow+1)
		for j := start; j < end; j++ {
			if matched2[j] || r1[i] != r2[j] {
				continue
			}
			matched1[i] = true
			matched2[j] = true
			matches++
			break
		}
	}

	if matches == 0 {
		return 0.0
	}

	// Jaro相似度
	t := 0
	j := 0
	for i := range r1 {
		if !matched1[i] {
			continue
		}
		for !matched2[j] {
			j++
		}
		if r1[i] != r2[j] {
			t++
		}
		j++
	}
	t /= 2

	jaro := (float64(matches)/float64(len(r1)) +
		float64(matches)/float64(len(r2)) +
		float64(matches-t)/float64(matches)) / 3.0

	// Jaro-Winkler
	return jaro + float64(prefixLen)*0.1*(1-jaro)
}

// containsChinese 检测字符串是否包含中文
func containsChinese(s string) bool {
	for _, r := range s {
		if unicode.Is(unicode.Han, r) {
			return true
		}
	}
	return false
}
