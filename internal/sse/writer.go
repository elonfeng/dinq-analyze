package sse

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"dinq-analyze-go/internal/model"
)

// Writer SSE写入器
type Writer struct {
	w         http.ResponseWriter
	flusher   http.Flusher
	mu        sync.Mutex
	state     *model.AnalysisState
	stopHeart chan struct{}
}

func NewWriter(w http.ResponseWriter) (*Writer, error) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		return nil, fmt.Errorf("streaming not supported")
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	writer := &Writer{
		w:         w,
		flusher:   flusher,
		state:     model.NewAnalysisState(),
		stopHeart: make(chan struct{}),
	}

	// 启动心跳
	go writer.heartbeat()

	return writer, nil
}

// heartbeat 定期发送心跳保持连接
func (s *Writer) heartbeat() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			s.mu.Lock()
			// 发送心跳消息，保持当前状态但标记为heartbeat
			heartbeat := map[string]interface{}{
				"status":         "heartbeat",
				"overall":        s.state.Overall,
				"current_action": s.state.CurrentAction,
			}
			data, _ := json.Marshal(heartbeat)
			fmt.Fprintf(s.w, "data: %s\n\n", data)
			s.flusher.Flush()
			s.mu.Unlock()
		case <-s.stopHeart:
			return
		}
	}
}

// StopHeartbeat 停止心跳
func (s *Writer) StopHeartbeat() {
	close(s.stopHeart)
}

func (s *Writer) send() error {
	data, err := json.Marshal(s.state)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(s.w, "data: %s\n\n", data)
	if err != nil {
		return err
	}
	s.flusher.Flush()
	return nil
}

// SetQuery 设置查询
func (s *Writer) SetQuery(query string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.state.Query = query
}

// SetAction 更新当前动作和进度并发送（让前端看到在干嘛）
// 进度只增不减
func (s *Writer) SetAction(progress int, action string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	// 进度只增不减
	if progress > s.state.Overall {
		s.state.Overall = progress
	}
	s.state.CurrentAction = action
	return s.send()
}

// SetCard 设置card数据并发送（有数据才发送）
func (s *Writer) SetCard(card model.CardType, data interface{}, action string) error {
	// CardMap 是并发安全的，不需要锁
	s.state.Cards.Set(card, &model.CardState{
		Status: model.StatusDone,
		Data:   data,
	})
	s.state.CurrentAction = action
	s.recalcOverall()

	// HTTP 写入需要锁防止交错
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.send()
}

// SetError 设置card错误并发送
func (s *Writer) SetError(card model.CardType, errMsg string, action string) error {
	s.state.Cards.Set(card, &model.CardState{
		Status: model.StatusError,
		Error:  errMsg,
	})
	s.state.CurrentAction = action
	s.recalcOverall()

	s.mu.Lock()
	defer s.mu.Unlock()
	return s.send()
}

// SendCandidates 发送候选人列表（需要用户选择）
func (s *Writer) SendCandidates(candidates []model.ScholarCandidate) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.state.Status = "need_selection"
	s.state.CurrentAction = "Multiple candidates found, please select one"
	s.state.Candidates = candidates
	return s.send()
}

// SendGlobalError 发送全局错误
func (s *Writer) SendGlobalError(errMsg string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.state.Status = "error"
	s.state.CurrentAction = "Analysis failed"
	s.state.Error = errMsg
	return s.send()
}

// SendLoginRequired 发送需要登录的错误（未登录用户且无缓存时）
func (s *Writer) SendLoginRequired(message string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.state.Status = "login_required"
	s.state.CurrentAction = "Login required"
	s.state.Error = message
	return s.send()
}

// Done 全部完成
func (s *Writer) Done() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.state.Status = "completed"
	s.state.Overall = 100
	s.state.CurrentAction = "Analysis completed"
	return s.send()
}

// recalcOverall 根据完成的card数量计算进度（只增不减）
func (s *Writer) recalcOverall() {
	done := s.state.Cards.CountDone()
	newOverall := done * 100 / len(model.AllCards)
	// 进度只增不减
	if newOverall > s.state.Overall {
		s.state.Overall = newOverall
	}
}

// GetAllCardsData 获取所有card数据用于缓存
func (s *Writer) GetAllCardsData() map[string]interface{} {
	result := make(map[string]interface{})
	for _, cardType := range model.AllCards {
		state := s.state.Cards.Get(cardType)
		if state != nil && state.Status == model.StatusDone && state.Data != nil {
			result[string(cardType)] = state.Data
		}
	}
	if len(result) == 0 {
		return nil
	}
	return result
}

// ========== GitHub SSE Writer ==========

// GitHubWriter GitHub SSE写入器
type GitHubWriter struct {
	w         http.ResponseWriter
	flusher   http.Flusher
	mu        sync.Mutex
	state     *model.GitHubAnalysisState
	stopHeart chan struct{}
}

// NewGitHubWriter 创建GitHub SSE写入器
func NewGitHubWriter(w http.ResponseWriter) (*GitHubWriter, error) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		return nil, fmt.Errorf("streaming not supported")
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	writer := &GitHubWriter{
		w:         w,
		flusher:   flusher,
		state:     &model.GitHubAnalysisState{},
		stopHeart: make(chan struct{}),
	}

	go writer.heartbeat()

	return writer, nil
}

// heartbeat 定期发送心跳保持连接
func (g *GitHubWriter) heartbeat() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			g.mu.Lock()
			heartbeat := map[string]interface{}{
				"status":         "heartbeat",
				"overall":        g.state.Overall,
				"current_action": g.state.CurrentAction,
			}
			data, _ := json.Marshal(heartbeat)
			fmt.Fprintf(g.w, "data: %s\n\n", data)
			g.flusher.Flush()
			g.mu.Unlock()
		case <-g.stopHeart:
			return
		}
	}
}

// StopHeartbeat 停止心跳
func (g *GitHubWriter) StopHeartbeat() {
	close(g.stopHeart)
}

func (g *GitHubWriter) send() error {
	data, err := json.Marshal(g.state)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(g.w, "data: %s\n\n", data)
	if err != nil {
		return err
	}
	g.flusher.Flush()
	return nil
}

// SetLogin 设置GitHub用户名并立即发送SSE消息
func (g *GitHubWriter) SetLogin(login string) error {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.state.Login = login
	g.state.Status = "analyzing"
	g.state.CurrentAction = "Initializing..."
	g.state.Cards = model.NewGitHubCardMap()
	for _, card := range model.AllGitHubCards {
		g.state.Cards.SetGitHub(card, &model.CardState{Status: model.StatusPending})
	}
	return g.send() // 立即发送
}

// SetAction 更新当前动作和进度
func (g *GitHubWriter) SetAction(progress int, action string) error {
	g.mu.Lock()
	defer g.mu.Unlock()
	if progress > g.state.Overall {
		g.state.Overall = progress
	}
	g.state.CurrentAction = action
	return g.send()
}

// SendCardDone 发送card完成
func (g *GitHubWriter) SendCardDone(card model.GitHubCardType, data interface{}) error {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.state.Cards.SetGitHub(card, &model.CardState{
		Status: model.StatusDone,
		Data:   data,
	})
	g.recalcOverall()
	return g.send()
}

// SendCardError 发送card错误
func (g *GitHubWriter) SendCardError(card model.GitHubCardType, errMsg string) error {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.state.Cards.SetGitHub(card, &model.CardState{
		Status: model.StatusError,
		Error:  errMsg,
	})
	g.recalcOverall()
	return g.send()
}

// SendGlobalError 发送全局错误
func (g *GitHubWriter) SendGlobalError(errMsg string) error {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.state.Status = "error"
	g.state.CurrentAction = "Analysis failed"
	g.state.Error = errMsg
	return g.send()
}

// SendLoginRequired 发送需要登录的错误（未登录用户且无缓存时）
func (g *GitHubWriter) SendLoginRequired(message string) error {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.state.Status = "login_required"
	g.state.CurrentAction = "Login required"
	g.state.Error = message
	return g.send()
}

// SendCompleted 发送完成
func (g *GitHubWriter) SendCompleted() error {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.state.Status = "completed"
	g.state.Overall = 100
	g.state.CurrentAction = "Analysis completed"
	return g.send()
}

// recalcOverall 根据完成的card数量计算进度
func (g *GitHubWriter) recalcOverall() {
	done := g.state.Cards.CountDone()
	newOverall := done * 100 / len(model.AllGitHubCards)
	if newOverall > g.state.Overall {
		g.state.Overall = newOverall
	}
}

// ========== LinkedIn SSE Writer ==========

// LinkedInWriter LinkedIn SSE写入器
type LinkedInWriter struct {
	w         http.ResponseWriter
	flusher   http.Flusher
	mu        sync.Mutex
	state     *model.LinkedInAnalysisState
	stopHeart chan struct{}
}

// NewLinkedInWriter 创建LinkedIn SSE写入器
func NewLinkedInWriter(w http.ResponseWriter) (*LinkedInWriter, error) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		return nil, fmt.Errorf("streaming not supported")
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	writer := &LinkedInWriter{
		w:         w,
		flusher:   flusher,
		state:     &model.LinkedInAnalysisState{},
		stopHeart: make(chan struct{}),
	}

	go writer.heartbeat()

	return writer, nil
}

// heartbeat 定期发送心跳保持连接
func (l *LinkedInWriter) heartbeat() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			l.mu.Lock()
			heartbeat := map[string]interface{}{
				"status":         "heartbeat",
				"overall":        l.state.Overall,
				"current_action": l.state.CurrentAction,
			}
			data, _ := json.Marshal(heartbeat)
			fmt.Fprintf(l.w, "data: %s\n\n", data)
			l.flusher.Flush()
			l.mu.Unlock()
		case <-l.stopHeart:
			return
		}
	}
}

// StopHeartbeat 停止心跳
func (l *LinkedInWriter) StopHeartbeat() {
	close(l.stopHeart)
}

func (l *LinkedInWriter) send() error {
	data, err := json.Marshal(l.state)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(l.w, "data: %s\n\n", data)
	if err != nil {
		return err
	}
	l.flusher.Flush()
	return nil
}

// SetLinkedIn 设置LinkedIn用户信息并立即发送SSE消息
func (l *LinkedInWriter) SetLinkedIn(linkedInID, personName string) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.state.LinkedInID = linkedInID
	l.state.PersonName = personName
	l.state.Status = "analyzing"
	l.state.CurrentAction = "Initializing..."
	l.state.Cards = model.NewLinkedInCardMap()
	for _, card := range model.AllLinkedInCards {
		l.state.Cards.SetLinkedIn(card, &model.CardState{Status: model.StatusPending})
	}
	return l.send() // 立即发送，让前端秒显示
}

// SetAction 更新当前动作和进度
func (l *LinkedInWriter) SetAction(progress int, action string) error {
	l.mu.Lock()
	defer l.mu.Unlock()
	if progress > l.state.Overall {
		l.state.Overall = progress
	}
	l.state.CurrentAction = action
	return l.send()
}

// SendCardDone 发送card完成
func (l *LinkedInWriter) SendCardDone(card model.LinkedInCardType, data interface{}) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.state.Cards.SetLinkedIn(card, &model.CardState{
		Status: model.StatusDone,
		Data:   data,
	})
	l.recalcOverall()
	return l.send()
}

// SendCardError 发送card错误
func (l *LinkedInWriter) SendCardError(card model.LinkedInCardType, errMsg string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.state.Cards.SetLinkedIn(card, &model.CardState{
		Status: model.StatusError,
		Error:  errMsg,
	})
	l.recalcOverall()
	return l.send()
}

// SendCandidates 发送候选人列表（需要用户选择）
func (l *LinkedInWriter) SendCandidates(candidates []model.LinkedInCandidate) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.state.Status = "need_selection"
	l.state.CurrentAction = "Multiple candidates found, please select one"
	l.state.Candidates = candidates
	return l.send()
}

// SendGlobalError 发送全局错误
func (l *LinkedInWriter) SendGlobalError(errMsg string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.state.Status = "error"
	l.state.CurrentAction = "Analysis failed"
	l.state.Error = errMsg
	return l.send()
}

// SendLoginRequired 发送需要登录的错误（未登录用户且无缓存时）
func (l *LinkedInWriter) SendLoginRequired(message string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.state.Status = "login_required"
	l.state.CurrentAction = "Login required"
	l.state.Error = message
	return l.send()
}

// SendCompleted 发送完成
func (l *LinkedInWriter) SendCompleted() error {
	l.mu.Lock()
	defer l.mu.Unlock()

	l.state.Status = "completed"
	l.state.Overall = 100
	l.state.CurrentAction = "Analysis completed"
	return l.send()
}

// SendFinalResult 发送最终结果 (matches Python final output format)
func (l *LinkedInWriter) SendFinalResult(result *model.LinkedInFinalResponse) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	data, err := json.Marshal(result)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(l.w, "data: %s\n\n", data)
	if err != nil {
		return err
	}
	l.flusher.Flush()
	return nil
}

// recalcOverall 根据完成的card数量计算进度
func (l *LinkedInWriter) recalcOverall() {
	done := l.state.Cards.CountDone()
	newOverall := done * 100 / len(model.AllLinkedInCards)
	if newOverall > l.state.Overall {
		l.state.Overall = newOverall
	}
}
