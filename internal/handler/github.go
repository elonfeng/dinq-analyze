package handler

import (
	"encoding/json"
	"log"
	"net/http"

	"dinq-analyze-go/internal/service"
	"dinq-analyze-go/internal/sse"
)

// GitHubHandler GitHub分析HTTP处理器
type GitHubHandler struct {
	service *service.GitHubService
}

// NewGitHubHandler 创建处理器
func NewGitHubHandler(svc *service.GitHubService) *GitHubHandler {
	return &GitHubHandler{service: svc}
}

// AnalyzeSSE 处理SSE分析请求
// POST /api/analyze/github/sse
// Body: {"query": "xxx", "data": {...}}
func (h *GitHubHandler) AnalyzeSSE(w http.ResponseWriter, r *http.Request) {
	var req AnalyzeRequest

	// 解析JSON请求体
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	if req.Query == "" {
		http.Error(w, "query is required", http.StatusBadRequest)
		return
	}

	// 创建SSE writer
	writer, err := sse.NewGitHubWriter(w)
	if err != nil {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	log.Printf("Starting GitHub SSE analysis for: %s", req.Query)

	// 执行分析 (data暂不使用，保留接口兼容)
	if err := h.service.Analyze(r.Context(), req.Query, writer); err != nil {
		log.Printf("GitHub analysis error for %s: %v", req.Query, err)
	}

	log.Printf("GitHub SSE analysis completed for: %s", req.Query)
}
