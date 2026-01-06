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
	log.Printf("[Scholar Search] Query: %q, candidates count: %d", query, len(candidates))

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
		log.Printf("[Scholar Search] Candidate: %q, score: %.2f", c.Name, score)
	}

	// 按分数排序（高到低）
	for i := 0; i < len(scoredCandidates)-1; i++ {
		for j := i + 1; j < len(scoredCandidates); j++ {
			if scoredCandidates[j].score > scoredCandidates[i].score {
				scoredCandidates[i], scoredCandidates[j] = scoredCandidates[j], scoredCandidates[i]
			}
		}
	}

	// 过滤相似度太低的（阈值0.7）
	const minThreshold = 0.7

	var filtered []ScholarCandidate
	for _, sc := range scoredCandidates {
		if sc.score >= minThreshold {
			filtered = append(filtered, sc.candidate)
		} else {
			log.Printf("[Scholar Search] Filtered out: %q (score: %.2f < %.2f)", sc.candidate.Name, sc.score, minThreshold)
		}
	}

	log.Printf("[Scholar Search] After filter: %d candidates remain", len(filtered))
	return filtered
}

// calculateSimilarity 计算查询与候选人的相似度
func calculateSimilarity(query, name, content string) float64 {
	queryNoSpace := strings.ReplaceAll(query, " ", "")
	nameNoSpace := strings.ReplaceAll(name, " ", "")

	var bestScore float64

	// 方法1: 直接比较（去空格后）
	bestScore = directSimilarity(queryNoSpace, nameNoSpace)

	// 方法2: 按空格拆分比较（处理名字顺序颠倒、额外关键词）
	splitScore := splitBasedSimilarity(query, name)
	if splitScore > bestScore {
		bestScore = splitScore
	}

	// 方法3: 名字部分排列组合匹配（处理 "wangqiang" vs "qiang wang"）
	nameParts := strings.Fields(name)
	if len(nameParts) >= 2 {
		// 生成名字的各种组合形式
		combinations := generateNameCombinations(nameParts)
		for _, combo := range combinations {
			// 检查query是否包含这个组合
			if strings.Contains(queryNoSpace, combo) {
				bestScore = 1.0
				break
			}
			// Levenshtein相似度
			sim := levenshteinSimilarity(queryNoSpace, combo)
			if sim > bestScore {
				bestScore = sim
			}
			// 滑动窗口（query更长时）
			if len(queryNoSpace) > len(combo) {
				windowSize := len(combo)
				for i := 0; i <= len(queryNoSpace)-windowSize; i++ {
					window := queryNoSpace[i : i+windowSize]
					windowSim := levenshteinSimilarity(combo, window)
					if windowSim > bestScore {
						bestScore = windowSim
					}
				}
			}
		}
	}

	// content 包含 name 加分
	if strings.Contains(content, name) || strings.Contains(content, nameNoSpace) {
		bestScore += 0.2
	}

	if bestScore > 1.0 {
		bestScore = 1.0
	}
	return bestScore
}

// directSimilarity 直接比较两个字符串的相似度
func directSimilarity(a, b string) float64 {
	if strings.Contains(a, b) {
		return 1.0
	}
	if strings.Contains(b, a) {
		return 0.9
	}
	return levenshteinSimilarity(a, b)
}

// splitBasedSimilarity 基于空格拆分的相似度计算
func splitBasedSimilarity(query, name string) float64 {
	queryParts := strings.Fields(query)
	nameParts := strings.Fields(name)

	if len(queryParts) == 0 || len(nameParts) == 0 {
		return 0
	}

	// 计算name的每个部分在query中的最佳匹配得分
	var totalScore float64
	for _, np := range nameParts {
		np = strings.ToLower(np)
		bestPartScore := 0.0
		for _, qp := range queryParts {
			qp = strings.ToLower(qp)
			// 完全匹配
			if qp == np {
				bestPartScore = 1.0
				break
			}
			// 包含关系
			if strings.Contains(qp, np) || strings.Contains(np, qp) {
				if 0.9 > bestPartScore {
					bestPartScore = 0.9
				}
			}
			// Levenshtein
			sim := levenshteinSimilarity(qp, np)
			if sim > bestPartScore {
				bestPartScore = sim
			}
		}
		totalScore += bestPartScore
	}

	return totalScore / float64(len(nameParts))
}

// generateNameCombinations 生成名字部分的各种组合
func generateNameCombinations(parts []string) []string {
	if len(parts) == 0 {
		return nil
	}
	if len(parts) == 1 {
		return []string{strings.ToLower(parts[0])}
	}

	// 对于两个部分，生成正序和倒序
	if len(parts) == 2 {
		p0 := strings.ToLower(parts[0])
		p1 := strings.ToLower(parts[1])
		return []string{
			p0 + p1, // firstname+lastname
			p1 + p0, // lastname+firstname
		}
	}

	// 对于更多部分，只生成正序和完全倒序
	var forward, backward string
	for i := 0; i < len(parts); i++ {
		forward += strings.ToLower(parts[i])
		backward += strings.ToLower(parts[len(parts)-1-i])
	}
	return []string{forward, backward}
}

// levenshteinSimilarity 计算 Levenshtein 相似度 (0-1)
func levenshteinSimilarity(a, b string) float64 {
	if a == b {
		return 1.0
	}
	if len(a) == 0 || len(b) == 0 {
		return 0.0
	}

	dist := levenshteinDistance(a, b)
	maxLen := len(a)
	if len(b) > maxLen {
		maxLen = len(b)
	}
	return 1.0 - float64(dist)/float64(maxLen)
}

// levenshteinDistance 计算编辑距离
func levenshteinDistance(a, b string) int {
	if len(a) == 0 {
		return len(b)
	}
	if len(b) == 0 {
		return len(a)
	}

	// 创建距离矩阵
	d := make([][]int, len(a)+1)
	for i := range d {
		d[i] = make([]int, len(b)+1)
		d[i][0] = i
	}
	for j := range d[0] {
		d[0][j] = j
	}

	for i := 1; i <= len(a); i++ {
		for j := 1; j <= len(b); j++ {
			cost := 1
			if a[i-1] == b[j-1] {
				cost = 0
			}
			d[i][j] = min(d[i-1][j]+1, min(d[i][j-1]+1, d[i-1][j-1]+cost))
		}
	}
	return d[len(a)][len(b)]
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
