package handler

import (
	"encoding/json"
	"log"
	"net/http"

	"dinq-analyze-go/internal/service"
	"dinq-analyze-go/internal/sse"
)

// LinkedInHandler LinkedIn分析HTTP处理器
type LinkedInHandler struct {
	service *service.LinkedInService
}

// NewLinkedInHandler 创建处理器
func NewLinkedInHandler(svc *service.LinkedInService) *LinkedInHandler {
	return &LinkedInHandler{service: svc}
}

// AnalyzeSSE 处理SSE分析请求
// POST /api/analyze/linkedin/sse
// Body: {"query": "xxx", "data": {...}}
// data: 用户选择的候选人信息 {linkedin_id, name, content, url}
func (h *LinkedInHandler) AnalyzeSSE(w http.ResponseWriter, r *http.Request) {
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
	writer, err := sse.NewLinkedInWriter(w)
	if err != nil {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	log.Printf("Starting LinkedIn SSE analysis for: %s (with data: %v)", req.Query, req.Data != nil)

	// 执行分析，传递候选人数据
	if err := h.service.AnalyzeWithSSE(r.Context(), req.Query, req.Data, writer); err != nil {
		log.Printf("LinkedIn analysis error for %s: %v", req.Query, err)
		writer.SendGlobalError(err.Error())
	}

	log.Printf("LinkedIn SSE analysis completed for: %s", req.Query)
}
