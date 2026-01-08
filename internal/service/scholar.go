package service

import (
	"context"
	"log"
	"regexp"
	"strings"
	"sync"
	"time"

	"dinq-analyze-go/internal/cache"
	"dinq-analyze-go/internal/fetcher"
	"dinq-analyze-go/internal/model"
	"dinq-analyze-go/internal/sse"
	"dinq-analyze-go/internal/utils"
)

// CacheTTL 缓存过期时间
const CacheTTL = 24 * time.Hour

type ScholarService struct {
	htmlFetcher    *fetcher.FirecrawlFetcher
	searchFetcher  *fetcher.TavilyFetcher
	llmClient      *fetcher.OpenRouterClient
	parser         *fetcher.ScholarParser
	openAlexClient *fetcher.OpenAlexFetcher
	cache          cache.Cache
}

func NewScholarService(firecrawlKey, tavilyKey, openrouterKey string) *ScholarService {
	// 创建内存缓存（生产环境可换成FileCache或Redis）
	memCache := cache.NewMemoryCache()

	return &ScholarService{
		htmlFetcher:    fetcher.NewFirecrawlFetcher(firecrawlKey),
		searchFetcher:  fetcher.NewTavilyFetcher(tavilyKey),
		llmClient:      fetcher.NewOpenRouterClient(openrouterKey),
		parser:         fetcher.NewScholarParser(),
		openAlexClient: fetcher.NewOpenAlexFetcher(),
		cache:          memCache,
	}
}

// NewScholarServiceWithCache 使用指定缓存创建服务
func NewScholarServiceWithCache(firecrawlKey, tavilyKey, openrouterKey string, c cache.Cache) *ScholarService {
	return &ScholarService{
		htmlFetcher:    fetcher.NewFirecrawlFetcher(firecrawlKey),
		searchFetcher:  fetcher.NewTavilyFetcher(tavilyKey),
		llmClient:      fetcher.NewOpenRouterClient(openrouterKey),
		parser:         fetcher.NewScholarParser(),
		openAlexClient: fetcher.NewOpenAlexFetcher(),
		cache:          c,
	}
}

// isScholarID 判断输入是否像scholar_id（字母数字组合，通常12位左右）
func isScholarID(query string) bool {
	// Google Scholar ID 通常是12位字母数字组合，如 "JicYPdAAAAAJ"
	matched, _ := regexp.MatchString(`^[a-zA-Z0-9_-]{10,14}$`, query)
	return matched
}

// extractScholarIDFromURL 从 Google Scholar URL 中提取 scholar_id
// 支持格式: https://scholar.google.com/citations?user=dOad5HoAAAAJ 或 https://scholar.google.com/citations?user=dOad5HoAAAAJ&hl=en
func extractScholarIDFromURL(url string) string {
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

// Analyze 分析学者
// query: 可以是scholar_id、Google Scholar URL或者人名
// cacheOnly: 如果为true，只走缓存，没缓存返回登录错误（用于未登录用户）
func (s *ScholarService) Analyze(ctx context.Context, query string, w *sse.Writer, cacheOnly bool) error {
	log.Printf("[Scholar Service] Analyze started, query: %s, cacheOnly: %v", query, cacheOnly)

	// 设置query
	w.SetQuery(query)

	var scholarID string

	// 1. 先检查是否是 Google Scholar URL
	if urlID := extractScholarIDFromURL(query); urlID != "" {
		scholarID = urlID
		log.Printf("[Scholar Service] Extracted scholar ID from URL: %s", scholarID)
		w.SetAction(5, "Scholar URL detected, starting analysis...")
	} else if isScholarID(query) {
		// 2. 直接是scholar_id
		scholarID = query
		log.Printf("[Scholar Service] Query is a scholar ID: %s", scholarID)
		w.SetAction(5, "Scholar ID detected, starting analysis...")
	} else {
		// 是人名，需要搜索
		// 未登录用户不允许搜索（因为搜索没有缓存）
		if cacheOnly {
			w.SendLoginRequired("Please login to search scholars by name")
			return nil
		}

		w.SetAction(5, "Searching for scholar candidates...")

		candidates, err := s.searchFetcher.SearchScholar(ctx, query)
		if err != nil {
			w.SendGlobalError("Failed to search: " + err.Error())
			return err
		}

		if len(candidates) == 0 {
			w.SendGlobalError("No scholars found for: " + query)
			return nil
		}

		if len(candidates) > 1 {
			// 多个候选人，并发总结content
			candidates = s.summarizeCandidatesContent(ctx, candidates)

			// 让前端选择
			modelCandidates := make([]model.ScholarCandidate, len(candidates))
			for i, c := range candidates {
				modelCandidates[i] = model.ScholarCandidate{
					ScholarID: c.ScholarID,
					Name:      c.Name,
					Content:   c.Content,
					URL:       c.URL,
				}
			}
			w.SendCandidates(modelCandidates)
			return nil
		}

		// 只有一个候选人，直接用
		scholarID = candidates[0].ScholarID
		w.SetAction(10, "Found scholar: "+candidates[0].Name)
	}

	// 开始分析
	return s.analyzeScholar(ctx, scholarID, w, cacheOnly)
}

// summarizeCandidatesContent 并发总结候选人的content为简短英文
func (s *ScholarService) summarizeCandidatesContent(ctx context.Context, candidates []fetcher.ScholarCandidate) []fetcher.ScholarCandidate {
	var wg sync.WaitGroup

	for i := range candidates {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()

			summarized, err := s.llmClient.SummarizeContent(ctx, candidates[idx].Content)
			if err != nil {
				return // 失败保持原文
			}

			candidates[idx].Content = summarized
		}(i)
	}

	wg.Wait()
	return candidates
}

// analyzeScholar 执行实际的分析
// cacheOnly: 如果为true，只走缓存，没缓存返回登录错误
func (s *ScholarService) analyzeScholar(ctx context.Context, scholarID string, w *sse.Writer, cacheOnly bool) error {
	log.Printf("[Scholar Service] analyzeScholar started for ID: %s, cacheOnly: %v", scholarID, cacheOnly)

	// ========== 发送 start 消息 ==========
	w.SetAction(0, "Starting analysis...")

	// ========== 立即发送初始 profile_card（只有 avatar 和 scholar_url）==========
	initialProfile := model.ProfileCard{
		ScholarID:  scholarID,
		ScholarURL: "https://scholar.google.com/citations?user=" + scholarID,
		Avatar:     "https://scholar.googleusercontent.com/citations?view_op=view_photo&user=" + scholarID + "&citpid=2",
	}
	w.SetCard(model.CardProfile, initialProfile, "Loading profile...")

	// ========== 检查缓存 ==========
	if s.cache != nil {
		cached, err := s.cache.Get(ctx, scholarID)
		if err == nil && cached != nil {
			log.Printf("[Scholar Service] Cache HIT for ID: %s", scholarID)
			w.SetAction(5, "Loading from cache...")
			return s.sendCachedResults(ctx, w, cached.Data)
		}
		log.Printf("[Scholar Service] Cache MISS for ID: %s", scholarID)
	}

	// 如果是 cacheOnly 模式（未登录）且没有缓存，返回需要登录的错误
	if cacheOnly {
		log.Printf("[Scholar Service] Cache MISS and cacheOnly=true, requiring login for ID: %s", scholarID)
		w.SendLoginRequired("Please login to analyze this scholar")
		return nil
	}

	var wg sync.WaitGroup
	var mu sync.Mutex
	var parsedData *fetcher.ParsedProfile
	var fetchErr error

	// 存储phase 1计算结果，供phase 2复用（避免重复计算）
	// 注意：由于 wg.Wait() 在 phase 1 和 phase 2 之间提供了同步，不需要锁
	var paperOfYear *model.PaperOfYearCard
	var repPaper *model.RepresentativePaperCard

	// ========== 阶段1: 获取HTML ==========
	wg.Add(1)

	// 任务1: HTML → profile + papers + coauthors (并发获取多页)
	go func() {
		defer wg.Done()

		log.Printf("[Scholar Service] Starting to fetch HTML pages for ID: %s", scholarID)
		w.SetAction(15, "Fetching Google Scholar pages...")

		// 并发获取多页论文（最多3页，300篇论文）
		htmlPages, err := s.htmlFetcher.FetchScholarPageMulti(ctx, scholarID, 3)
		if err != nil {
			log.Printf("[Scholar Service] ERROR: Failed to fetch HTML: %v", err)
			mu.Lock()
			fetchErr = err
			mu.Unlock()
			w.SetError(model.CardProfile, err.Error(), "Failed to fetch")
			w.SetError(model.CardPapers, err.Error(), "Failed to fetch")
			return
		}

		log.Printf("[Scholar Service] Fetched %d HTML pages, starting to parse", len(htmlPages))
		w.SetAction(25, "Parsing scholar data...")

		// 解析多页HTML并合并论文
		parsed, err := s.parser.ParseMultiPage(htmlPages)
		if err != nil {
			log.Printf("[Scholar Service] ERROR: Failed to parse HTML: %v", err)
			mu.Lock()
			fetchErr = err
			mu.Unlock()
			w.SetError(model.CardProfile, err.Error(), "Failed to parse")
			w.SetError(model.CardPapers, err.Error(), "Failed to parse")
			return
		}

		// 检查解析结果
		if parsed == nil {
			log.Printf("[Scholar Service] ERROR: Parsed result is nil")
			mu.Lock()
			fetchErr = err
			mu.Unlock()
			w.SetError(model.CardProfile, "No data parsed", "Failed to parse")
			return
		}

		log.Printf("[Scholar Service] Parse complete: name=%q, papers=%d, coauthors=%d, h-index=%d",
			parsed.Profile.Name, len(parsed.Papers), len(parsed.Coauthors), parsed.Profile.HIndex)

		mu.Lock()
		parsedData = parsed
		mu.Unlock()

		// 填充3个card
		profileCard := model.ProfileCard{
			ScholarID:   scholarID,
			Name:        parsed.Profile.Name,
			Affiliation: parsed.Profile.Affiliation,
			Interests:   parsed.Profile.Interests,
			ScholarURL:  "https://scholar.google.com/citations?user=" + scholarID,
			Avatar:      "https://scholar.googleusercontent.com/citations?view_op=view_photo&user=" + scholarID + "&citpid=2",
		}

		// 提取合作者全名列表用于匹配
		coauthorNames := make([]string, 0, len(parsed.Coauthors))
		for _, c := range parsed.Coauthors {
			if c.Name != "" {
				coauthorNames = append(coauthorNames, c.Name)
			}
		}
		// 加上作者本人
		if parsed.Profile.Name != "" {
			coauthorNames = append(coauthorNames, parsed.Profile.Name)
		}

		papers := make([]model.Paper, 0, len(parsed.Papers))
		totalCitations := 0
		yearlyStats := make(map[int]int)

		// 扩展作者名：用coauthors列表匹配扩展
		for _, p := range parsed.Papers {
			expandedAuthors := p.Authors
			if len(coauthorNames) > 0 {
				expandedAuthors = utils.ExpandAuthorNames(p.Authors, coauthorNames)
			}

			papers = append(papers, model.Paper{
				Title:     p.Title,
				Authors:   expandedAuthors,
				Venue:     p.Venue,
				Year:      p.Year,
				Citations: p.Citations,
			})
			totalCitations += p.Citations
			yearlyStats[p.Year]++
		}
		papersCard := model.PapersCard{
			TotalPapers:     len(papers),
			TotalCitations:  totalCitations,
			HIndex:          parsed.Profile.HIndex,
			HIndex5y:        parsed.Profile.HIndex5y,
			I10Index:        parsed.Profile.I10Index,
			Citations5y:     parsed.Profile.Citations5y,
			YearlyCitations: parsed.Profile.YearlyCitations,
			YearlyStats:     yearlyStats,
		}

		w.SetCard(model.CardProfile, profileCard, "Profile loaded")
		w.SetCard(model.CardPapers, papersCard, "Papers loaded")

		// ========== 计算洞察数据（使用扩展后的作者名） ==========
		w.SetAction(35, "Analyzing publication insights...")

		// 论文洞察
		insightCard := AnalyzePapers(parsed.Papers, parsed.Profile.Name)
		w.SetCard(model.CardInsight, insightCard, "Insight loaded")

		// 最亲密合作者 - 使用扩展后的papers
		closestCollab := FindClosestCollaboratorFromPapers(ctx, papers, parsed.Coauthors, parsed.Profile.Name, s.openAlexClient)
		if closestCollab != nil {
			w.SetCard(model.CardClosestCollaborator, closestCollab, "Collaborator found")
		}

		// 年度最佳论文 - 使用扩展后的papers（存储供phase 2复用）
		poy := FindPaperOfYearFromPapers(papers, parsed.Profile.Name)
		if poy != nil {
			paperOfYear = poy
			w.SetCard(model.CardPaperOfYear, poy, "Paper of year found")
		}

		// 代表作 - 使用扩展后的papers（存储供phase 2复用）
		rp := FindRepresentativePaperFromPapers(papers, parsed.Profile.Name)
		if rp != nil {
			repPaper = rp
			w.SetCard(model.CardRepresentative, rp, "Representative paper found")
		}
	}()

	wg.Wait()

	if fetchErr != nil {
		return fetchErr
	}

	// ========== 阶段2: 并发LLM任务 ==========
	wg.Add(7) // paper summary + earnings + research_style + rolemodel + roast + description + paper_news

	// 用于更新profile card的description
	var profileDescription string
	var profileDescMu sync.Mutex

	// 任务: 生成年度论文摘要（复用phase 1的结果）
	go func() {
		defer wg.Done()

		// 使用phase 1存储的结果（wg.Wait已保证同步）
		if paperOfYear == nil {
			return
		}
		poy := paperOfYear

		w.SetAction(50, "AI summarizing paper of year...")

		summary, err := s.llmClient.SummarizePaper(ctx, poy.Title, poy.Year, poy.Venue, poy.Citations)
		if err != nil {
			// 失败不阻塞，保持原有card
			return
		}

		// 更新card添加summary
		poy.Summary = summary
		w.SetCard(model.CardPaperOfYear, poy, "Paper summary complete")
	}()

	// 任务: 生成profile description
	go func() {
		defer wg.Done()

		w.SetAction(52, "AI generating profile description...")

		desc, err := s.llmClient.GenerateDescription(ctx, parsedData.Profile)
		if err != nil {
			return
		}

		profileDescMu.Lock()
		profileDescription = desc
		profileDescMu.Unlock()
	}()

	// 任务: 搜索代表作相关新闻（复用phase 1的结果）
	go func() {
		defer wg.Done()

		// 使用phase 1存储的结果（wg.Wait已保证同步）
		if repPaper == nil {
			return
		}
		rp := repPaper

		w.SetAction(53, "Searching paper news...")

		paperNews := s.searchPaperNews(ctx, rp.Title)
		rp.PaperNews = paperNews
		w.SetCard(model.CardRepresentative, rp, "Paper news loaded")
	}()

	// 任务: 生成薪资评估
	go func() {
		defer wg.Done()
		w.SetAction(55, "AI analyzing earnings...")

		topPapers := parsedData.Papers
		if len(topPapers) > 10 {
			topPapers = topPapers[:10]
		}

		result, err := s.llmClient.GenerateEarnings(ctx, parsedData.Profile, topPapers)
		if err != nil {
			w.SetError(model.CardEarnings, err.Error(), "Earnings analysis failed")
			return
		}

		w.SetCard(model.CardEarnings, model.EarningsCard{
			Earnings: result.Earnings,
			LevelCN:  result.LevelCN,
			LevelUS:  result.LevelUS,
			Reason:   result.Justification,
		}, "Earnings complete")
	}()

	// 任务: 生成研究风格
	go func() {
		defer wg.Done()
		w.SetAction(58, "AI analyzing research style...")

		topPapers := parsedData.Papers
		if len(topPapers) > 10 {
			topPapers = topPapers[:10]
		}

		result, err := s.llmClient.GenerateResearchStyle(ctx, parsedData.Profile, topPapers)
		if err != nil {
			w.SetError(model.CardResearchStyle, err.Error(), "Research style analysis failed")
			return
		}

		w.SetCard(model.CardResearchStyle, model.ResearchStyleCard{
			DepthVsBreadth: model.ResearchStyleDimension{
				Score:       result.DepthVsBreadth.Score,
				Explanation: result.DepthVsBreadth.Explanation,
			},
			TheoryVsPractice: model.ResearchStyleDimension{
				Score:       result.TheoryVsPractice.Score,
				Explanation: result.TheoryVsPractice.Explanation,
			},
			IndividualVsTeam: model.ResearchStyleDimension{
				Score:       result.IndividualVsTeam.Score,
				Explanation: result.IndividualVsTeam.Explanation,
			},
			Justification: result.Justification,
		}, "Research style complete")
	}()

	go func() {
		defer wg.Done()
		w.SetAction(60, "AI finding role model...")

		result, err := s.llmClient.GenerateRoleModel(ctx, parsedData.Profile)
		if err != nil {
			w.SetError(model.CardRoleModel, err.Error(), "Role model failed")
			return
		}

		w.SetCard(model.CardRoleModel, model.RoleModelCard{
			Name:        result.Name,
			Institution: result.Institution,
			Position:    result.Position,
			PhotoURL:    result.PhotoURL,
			Achievement: result.Achievement,
			Reason:      result.Reason,
			Similarity:  result.Similarity,
		}, "Role model found")
	}()

	go func() {
		defer wg.Done()
		w.SetAction(70, "AI generating roast...")

		roast, err := s.llmClient.GenerateRoast(ctx, parsedData.Profile)
		if err != nil {
			w.SetError(model.CardRoast, err.Error(), "Roast failed")
			return
		}

		w.SetCard(model.CardRoast, model.RoastCard{Roast: roast}, "Roast complete")
	}()

	wg.Wait()

	// 如果有description，更新profile card
	profileDescMu.Lock()
	if profileDescription != "" {
		// 重新构建完整的profile card并更新
		profileCard := model.ProfileCard{
			ScholarID:   scholarID,
			Name:        parsedData.Profile.Name,
			Affiliation: parsedData.Profile.Affiliation,
			Interests:   parsedData.Profile.Interests,
			ScholarURL:  "https://scholar.google.com/citations?user=" + scholarID,
			Avatar:      "https://scholar.googleusercontent.com/citations?view_op=view_photo&user=" + scholarID + "&citpid=2",
			Description: profileDescription,
		}
		w.SetCard(model.CardProfile, profileCard, "Profile complete")
	}
	profileDescMu.Unlock()

	// ========== 保存到缓存 ==========
	if s.cache != nil {
		cacheData := w.GetAllCardsData()
		if cacheData != nil {
			go s.cache.Set(context.Background(), scholarID, cacheData, CacheTTL)
		}
	}

	w.Done()
	return nil
}

// sendCachedResults 从缓存发送所有card数据
func (s *ScholarService) sendCachedResults(ctx context.Context, w *sse.Writer, data map[string]interface{}) error {
	// 快速发送所有缓存的card数据
	progress := 10
	for cardType, cardData := range data {
		ct := model.CardType(cardType)
		w.SetCard(ct, cardData, "Loaded from cache")
		progress += 7
		if progress > 95 {
			progress = 95
		}
		w.SetAction(progress, "Loading cached data...")
	}

	w.Done()
	return nil
}

// searchPaperNews 使用 Perplexity AI 搜索论文相关新闻（和 Python 版本逻辑一致）
func (s *ScholarService) searchPaperNews(ctx context.Context, paperTitle string) *model.PaperNews {
	if paperTitle == "" {
		return nil
	}

	// 使用 LLM 的 Perplexity 搜索方法
	result, err := s.llmClient.SearchPaperNews(ctx, paperTitle)
	if err != nil || result == nil {
		// 返回 fallback
		return &model.PaperNews{
			News:        "No recent news found for: " + paperTitle,
			Date:        time.Now().Format("2006-01-02"),
			Description: "Our systems could not locate verified news about this paper. This could be because the paper is very recent, highly specialized, or not widely covered in accessible sources.",
			IsFallback:  true,
		}
	}

	return &model.PaperNews{
		News:        result.News,
		Date:        result.Date,
		Description: result.Description,
		URL:         result.URL,
		IsFallback:  result.IsFallback,
	}
}
