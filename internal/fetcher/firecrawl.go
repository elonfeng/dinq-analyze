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
	log.Printf("[Scholar Firecrawl] Fetching URL: %s", scholarURL)

	reqBody := firecrawlRequest{
		URL:     scholarURL,
		Formats: []string{"html"},
		WaitFor: 3000, // 等待3秒让页面JS渲染完成
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		log.Printf("[Scholar Firecrawl] ERROR: Failed to marshal request: %v", err)
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.firecrawl.dev/v1/scrape", bytes.NewBuffer(jsonBody))
	if err != nil {
		log.Printf("[Scholar Firecrawl] ERROR: Failed to create request: %v", err)
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+f.apiKey)

	resp, err := f.httpClient.Do(req)
	if err != nil {
		log.Printf("[Scholar Firecrawl] ERROR: Failed to fetch page: %v", err)
		return "", fmt.Errorf("failed to fetch page: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[Scholar Firecrawl] ERROR: Failed to read response: %v", err)
		return "", fmt.Errorf("failed to read response: %w", err)
	}

	log.Printf("[Scholar Firecrawl] Response status: %d, body size: %d bytes", resp.StatusCode, len(body))

	if resp.StatusCode != http.StatusOK {
		log.Printf("[Scholar Firecrawl] ERROR: Bad status %d, body: %s", resp.StatusCode, string(body))
		return "", fmt.Errorf("firecrawl returned status %d: %s", resp.StatusCode, string(body))
	}

	var fcResp firecrawlResponse
	if err := json.Unmarshal(body, &fcResp); err != nil {
		log.Printf("[Scholar Firecrawl] ERROR: Failed to parse JSON response: %v", err)
		return "", fmt.Errorf("failed to parse response: %w", err)
	}

	if !fcResp.Success {
		log.Printf("[Scholar Firecrawl] ERROR: Firecrawl returned error: %s", fcResp.Error)
		return "", fmt.Errorf("firecrawl error: %s", fcResp.Error)
	}

	htmlLen := len(fcResp.Data.HTML)
	log.Printf("[Scholar Firecrawl] SUCCESS: HTML length: %d chars", htmlLen)

	if fcResp.Data.HTML == "" {
		log.Printf("[Scholar Firecrawl] ERROR: Empty HTML response")
		return "", fmt.Errorf("empty HTML response")
	}

	// 检查是否是正常的Scholar页面（应该包含 gsc_prf_in 或 gsc_a_tr）
	html := fcResp.Data.HTML
	hasProfile := strings.Contains(html, "gsc_prf_in")
	hasPapers := strings.Contains(html, "gsc_a_tr")
	log.Printf("[Scholar Firecrawl] HTML check: hasProfile=%v, hasPapers=%v", hasProfile, hasPapers)

	// 如果都没有，记录HTML前500字符帮助诊断
	if !hasProfile && !hasPapers {
		preview := html
		if len(preview) > 500 {
			preview = preview[:500]
		}
		log.Printf("[Scholar Firecrawl] WARNING: Unexpected HTML content (first 500 chars): %s", preview)
	}

	return fcResp.Data.HTML, nil
}

// FetchScholarPageMulti 获取多页论文并返回所有HTML
// 优化：先获取第一页，只有当论文数>=100时才并发获取后续页
func (f *FirecrawlFetcher) FetchScholarPageMulti(ctx context.Context, scholarID string, maxPages int) ([]string, error) {
	log.Printf("[Scholar Firecrawl] FetchScholarPageMulti started for ID: %s, maxPages: %d", scholarID, maxPages)

	if maxPages <= 0 {
		maxPages = 3
	}
	if maxPages > 5 {
		maxPages = 5
	}

	// 先获取第一页
	firstPage, err := f.fetchSinglePage(ctx, scholarID, 0)
	if err != nil {
		log.Printf("[Scholar Firecrawl] ERROR: Failed to fetch first page: %v", err)
		return nil, err
	}

	// 检查第一页是否有足够多的论文（通过检查是否有 cstart=100 的链接或论文数量）
	// 简单方法：统计 gsc_a_tr 的数量，如果接近100则可能有更多
	paperCount := strings.Count(firstPage, "gsc_a_tr")
	log.Printf("[Scholar Firecrawl] First page paper count (gsc_a_tr): %d", paperCount)

	if paperCount < 95 || maxPages <= 1 {
		// 论文不足95篇，不需要获取更多页
		log.Printf("[Scholar Firecrawl] Only 1 page needed (paperCount=%d < 95)", paperCount)
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
