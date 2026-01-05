package handler

// AnalyzeRequest 统一的分析请求参数
type AnalyzeRequest struct {
	Query string                 `json:"query"`          // 查询内容：人名、ID、URL等
	Data  map[string]interface{} `json:"data,omitempty"` // 用户选择的候选人数据 {url, title, content}
}
