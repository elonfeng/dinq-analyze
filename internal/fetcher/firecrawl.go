package fetcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

// FirecrawlFetcher Firecrawl HTML获取器
type FirecrawlFetcher struct {
	apiKey     string
	httpClient *http.Client
}

// NewFirecrawlFetcher 创建Firecrawl获取器
func NewFirecrawlFetcher(apiKey string) *FirecrawlFetcher {
	return &FirecrawlFetcher{
		apiKey: apiKey,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

type firecrawlRequest struct {
	URL     string   `json:"url"`
	Formats []string `json:"formats"`
	WaitFor int      `json:"waitFor,omitempty"` // 等待毫秒数，让JS渲染完成
}

type firecrawlResponse struct {
	Success bool `json:"success"`
	Data    struct {
		HTML     string `json:"html"`
		Markdown string `json:"markdown"`
	} `json:"data"`
	Error string `json:"error,omitempty"`
}

// FetchScholarPage 获取Google Scholar页面HTML（单页，用于向后兼容）
func (f *FirecrawlFetcher) FetchScholarPage(ctx context.Context, scholarID string) (string, error) {
	return f.fetchSinglePage(ctx, scholarID, 0)
}

// fetchSinglePage 获取单页
func (f *FirecrawlFetcher) fetchSinglePage(ctx context.Context, scholarID string, cstart int) (string, error) {
	scholarURL := fmt.Sprintf("https://scholar.google.com/citations?user=%s&hl=en&cstart=%d&pagesize=100", scholarID, cstart)

	reqBody := firecrawlRequest{
		URL:     scholarURL,
		Formats: []string{"html"},
		WaitFor: 3000, // 等待3秒让页面JS渲染完成
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.firecrawl.dev/v1/scrape", bytes.NewBuffer(jsonBody))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+f.apiKey)

	resp, err := f.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to fetch page: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("firecrawl returned status %d: %s", resp.StatusCode, string(body))
	}

	var fcResp firecrawlResponse
	if err := json.Unmarshal(body, &fcResp); err != nil {
		return "", fmt.Errorf("failed to parse response: %w", err)
	}

	if !fcResp.Success {
		return "", fmt.Errorf("firecrawl error: %s", fcResp.Error)
	}

	if fcResp.Data.HTML == "" {
		return "", fmt.Errorf("empty HTML response")
	}

	return fcResp.Data.HTML, nil
}

// FetchScholarPageMulti 获取多页论文并返回所有HTML
// 优化：先获取第一页，只有当论文数>=100时才并发获取后续页
func (f *FirecrawlFetcher) FetchScholarPageMulti(ctx context.Context, scholarID string, maxPages int) ([]string, error) {
	if maxPages <= 0 {
		maxPages = 3
	}
	if maxPages > 5 {
		maxPages = 5
	}

	// 先获取第一页
	firstPage, err := f.fetchSinglePage(ctx, scholarID, 0)
	if err != nil {
		return nil, err
	}

	// 检查第一页是否有足够多的论文（通过检查是否有 cstart=100 的链接或论文数量）
	// 简单方法：统计 gsc_a_tr 的数量，如果接近100则可能有更多
	paperCount := strings.Count(firstPage, "gsc_a_tr")
	if paperCount < 95 || maxPages <= 1 {
		// 论文不足95篇，不需要获取更多页
		return []string{firstPage}, nil
	}

	// 并发获取后续页面
	results := []string{firstPage}
	additionalPages := maxPages - 1
	htmlResults := make([]string, additionalPages)
	errors := make([]error, additionalPages)

	var wg sync.WaitGroup
	for i := 0; i < additionalPages; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			cstart := (idx + 1) * 100
			html, err := f.fetchSinglePage(ctx, scholarID, cstart)
			htmlResults[idx] = html
			errors[idx] = err
		}(i)
	}
	wg.Wait()

	// 收集成功的页面
	for i := 0; i < additionalPages; i++ {
		if errors[i] == nil && htmlResults[i] != "" {
			results = append(results, htmlResults[i])
		}
	}

	return results, nil
}
