package fetcher

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// OpenAlexFetcher OpenAlex API获取器（免费学术API）
type OpenAlexFetcher struct {
	httpClient *http.Client
}

// NewOpenAlexFetcher 创建OpenAlex获取器
func NewOpenAlexFetcher() *OpenAlexFetcher {
	return &OpenAlexFetcher{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

type openAlexResponse struct {
	Results []struct {
		Title       string `json:"title"`
		Authorships []struct {
			Author struct {
				DisplayName string `json:"display_name"`
			} `json:"author"`
		} `json:"authorships"`
	} `json:"results"`
}

// FindAuthorsByTitle 通过论文标题查找完整作者列表
func (o *OpenAlexFetcher) FindAuthorsByTitle(ctx context.Context, paperTitle string) ([]string, error) {
	if len(paperTitle) < 5 {
		return nil, nil
	}

	// 构建请求URL
	baseURL := "https://api.openalex.org/works"
	params := url.Values{}
	params.Set("filter", fmt.Sprintf("title.search:%s", paperTitle))
	params.Set("per-page", "1")

	reqURL := fmt.Sprintf("%s?%s", baseURL, params.Encode())

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// OpenAlex 建议设置 User-Agent 包含邮箱，可以获得更高的速率限制
	req.Header.Set("User-Agent", "DinqAnalyze/1.0 (mailto:support@dinq.io)")

	resp, err := o.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("openalex returned status %d: %s", resp.StatusCode, string(body))
	}

	var result openAlexResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if len(result.Results) == 0 {
		return nil, nil
	}

	// 提取作者名字
	authors := make([]string, 0)
	for _, authorship := range result.Results[0].Authorships {
		name := authorship.Author.DisplayName
		if name != "" {
			authors = append(authors, name)
		}
	}

	return authors, nil
}

// FindAuthorsForPapers 批量查找多篇论文的作者（并发）
func (o *OpenAlexFetcher) FindAuthorsForPapers(ctx context.Context, paperTitles []string) map[string][]string {
	result := make(map[string][]string)

	// 限制并发数
	semaphore := make(chan struct{}, 5)
	type paperResult struct {
		title   string
		authors []string
	}
	resultChan := make(chan paperResult, len(paperTitles))

	for _, title := range paperTitles {
		go func(t string) {
			semaphore <- struct{}{}
			defer func() { <-semaphore }()

			authors, _ := o.FindAuthorsByTitle(ctx, t)
			resultChan <- paperResult{title: t, authors: authors}
		}(title)
	}

	// 收集结果
	for i := 0; i < len(paperTitles); i++ {
		pr := <-resultChan
		if len(pr.authors) > 0 {
			result[pr.title] = pr.authors
		}
	}

	return result
}
