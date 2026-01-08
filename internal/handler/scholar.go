package handler

import (
	"encoding/json"
	"log"
	"net/http"

	"dinq-analyze-go/internal/service"
	"dinq-analyze-go/internal/sse"
)

// ScholarHandler 学者分析HTTP处理器
type ScholarHandler struct {
	service *service.ScholarService
}

// NewScholarHandler 创建处理器
func NewScholarHandler(svc *service.ScholarService) *ScholarHandler {
	return &ScholarHandler{service: svc}
}

// AnalyzeSSE 处理SSE分析请求
// POST /api/analyze/scholar/sse
// Body: {"query": "xxx", "data": {...}}
// Header: X-User-ID (可选，来自gateway鉴权)
func (h *ScholarHandler) AnalyzeSSE(w http.ResponseWriter, r *http.Request) {
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

	// 从 header 获取用户ID（gateway 鉴权后会设置 X-User-ID）
	userID := r.Header.Get("X-User-ID")
	isLoggedIn := userID != ""

	// 创建SSE writer
	writer, err := sse.NewWriter(w)
	if err != nil {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}
	defer writer.StopHeartbeat()

	log.Printf("Starting SSE analysis for: %s (logged_in: %v)", req.Query, isLoggedIn)

	// 执行分析
	// cacheOnly: 未登录时只走缓存，没缓存返回需要登录的错误
	if err := h.service.Analyze(r.Context(), req.Query, writer, !isLoggedIn); err != nil {
		log.Printf("Analysis error for %s: %v", req.Query, err)
	}

	log.Printf("SSE analysis completed for: %s", req.Query)
}

// Health 健康检查
func (h *ScholarHandler) Health(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}
