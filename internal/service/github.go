package service

import (
	"context"
	"fmt"
	"log"
	"math"
	"sort"
	"sync"
	"time"

	"dinq-analyze-go/internal/cache"
	"dinq-analyze-go/internal/fetcher"
	"dinq-analyze-go/internal/model"
	"dinq-analyze-go/internal/sse"
)

// GitHubCacheTTL GitHub缓存过期时间
const GitHubCacheTTL = 24 * time.Hour

type GitHubService struct {
	githubClient *fetcher.GitHubClient
	llmClient    *fetcher.OpenRouterClient
	cache        cache.Cache
}

// NewGitHubService 创建GitHub服务
func NewGitHubService(githubToken, openrouterKey string, c cache.Cache) *GitHubService {
	return &GitHubService{
		githubClient: fetcher.NewGitHubClient(githubToken),
		llmClient:    fetcher.NewOpenRouterClient(openrouterKey),
		cache:        c,
	}
}

// Analyze 分析GitHub用户
func (s *GitHubService) Analyze(ctx context.Context, login string, w *sse.GitHubWriter) error {
	if err := w.SetLogin(login); err != nil {
		log.Printf("[GitHub] Failed to send initial SSE: %v", err)
	}
	w.SetAction(5, "Starting GitHub analysis...")

	// 检查缓存
	if s.cache != nil {
		cached, err := s.cache.Get(ctx, login)
		if err == nil && cached != nil {
			w.SetAction(100, "Loaded from cache")
			return s.sendCachedResult(w, cached.Data)
		}
	}

	// 获取GitHub数据
	w.SetAction(10, "Fetching GitHub profile...")
	userData, err := s.githubClient.FetchBundle(ctx, login)
	if err != nil {
		w.SendGlobalError("Failed to fetch GitHub data: " + err.Error())
		return err
	}

	// 构建基础数据
	baseData := s.buildBaseData(userData)

	// 发送profile card（第一个，同步）
	w.SetAction(20, "Processing profile...")
	profileCard := s.buildProfileCard(userData)
	w.SendCardDone(model.GitHubCardProfile, profileCard)

	// 全部card并发处理，谁先完成谁先发送
	var wg sync.WaitGroup
	results := make(map[model.GitHubCardType]interface{})
	var resultsMu sync.Mutex

	w.SetAction(30, "Running analysis...")

	// Activity card
	wg.Add(1)
	go func() {
		defer wg.Done()
		activityCard := s.buildActivityCard(userData)
		w.SendCardDone(model.GitHubCardActivity, activityCard)
		resultsMu.Lock()
		results[model.GitHubCardActivity] = activityCard
		resultsMu.Unlock()
	}()

	// Repos card
	wg.Add(1)
	go func() {
		defer wg.Done()
		reposCard := s.buildReposCard(userData)
		w.SendCardDone(model.GitHubCardRepos, reposCard)
		resultsMu.Lock()
		results[model.GitHubCardRepos] = reposCard
		resultsMu.Unlock()
	}()

	// Role Model card (LLM)
	wg.Add(1)
	go func() {
		defer wg.Done()
		roleModelCard, err := s.generateRoleModel(ctx, baseData)
		if err != nil || roleModelCard == nil {
			roleModelCard = s.defaultRoleModel(userData)
		}
		w.SendCardDone(model.GitHubCardRoleModel, roleModelCard)
		resultsMu.Lock()
		results[model.GitHubCardRoleModel] = roleModelCard
		resultsMu.Unlock()
	}()

	// Roast card (LLM)
	wg.Add(1)
	go func() {
		defer wg.Done()
		roastCard, err := s.generateRoast(ctx, baseData)
		if err != nil || roastCard == nil {
			roastCard = &model.GitHubRoastCard{
				Roast: "Your GitHub looks like a quiet powerhouse—shipping value without making too much noise.",
			}
		}
		w.SendCardDone(model.GitHubCardRoast, roastCard)
		resultsMu.Lock()
		results[model.GitHubCardRoast] = roastCard
		resultsMu.Unlock()
	}()

	// Summary card (LLM valuation)
	wg.Add(1)
	go func() {
		defer wg.Done()
		summaryCard, err := s.generateSummary(ctx, baseData, userData)
		if err != nil || summaryCard == nil {
			summaryCard = s.defaultSummary(baseData, userData)
		}
		w.SendCardDone(model.GitHubCardSummary, summaryCard)
		resultsMu.Lock()
		results[model.GitHubCardSummary] = summaryCard
		resultsMu.Unlock()
	}()

	// 等待所有card完成
	wg.Wait()

	// 缓存结果
	if s.cache != nil {
		cacheData := make(map[string]interface{})
		cacheData[string(model.GitHubCardProfile)] = profileCard
		for cardType, cardData := range results {
			cacheData[string(cardType)] = cardData
		}
		_ = s.cache.Set(ctx, login, cacheData, GitHubCacheTTL)
	}

	w.SetAction(100, "Analysis complete!")
	w.SendCompleted()

	return nil
}

// sendCachedResult 发送缓存的结果
func (s *GitHubService) sendCachedResult(w *sse.GitHubWriter, data map[string]interface{}) error {
	cardOrder := []model.GitHubCardType{
		model.GitHubCardProfile,
		model.GitHubCardActivity,
		model.GitHubCardRepos,
		model.GitHubCardRoleModel,
		model.GitHubCardRoast,
		model.GitHubCardSummary,
	}

	for _, cardType := range cardOrder {
		if cardData, ok := data[string(cardType)]; ok {
			w.SendCardDone(cardType, cardData)
		}
	}

	w.SendCompleted()
	return nil
}

// buildBaseData 构建基础数据供LLM使用
func (s *GitHubService) buildBaseData(user *fetcher.GitHubUserData) map[string]interface{} {
	// 计算工作年限
	var workExp int
	if user.CreatedAt != "" {
		createdAt, err := time.Parse(time.RFC3339, user.CreatedAt)
		if err == nil {
			workExp = int(math.Ceil(float64(time.Since(createdAt).Hours()) / (24 * 365)))
		}
	}

	// 计算总star数
	var totalStars int
	for _, repo := range user.TopRepos.Nodes {
		totalStars += repo.StargazerCount
	}

	// 计算活跃天数
	var activeDays int
	for _, week := range user.ContributionsCollection.ContributionCalendar.Weeks {
		for _, day := range week.ContributionDays {
			if day.ContributionCount > 0 {
				activeDays++
			}
		}
	}

	// 估算代码贡献
	var totalAdditions, totalDeletions int
	for _, pr := range user.PullRequestsTop.Nodes {
		totalAdditions += pr.Additions
		totalDeletions += pr.Deletions
	}
	// 简单估算
	if len(user.PullRequestsTop.Nodes) > 0 && user.PullRequestsTop.TotalCount > 0 {
		avgAdd := totalAdditions / len(user.PullRequestsTop.Nodes)
		avgDel := totalDeletions / len(user.PullRequestsTop.Nodes)
		totalAdditions = avgAdd * user.PullRequestsTop.TotalCount
		totalDeletions = avgDel * user.PullRequestsTop.TotalCount
	}

	return map[string]interface{}{
		"user": map[string]interface{}{
			"login":     user.Login,
			"name":      user.Name,
			"bio":       user.Bio,
			"createdAt": user.CreatedAt,
		},
		"overview": map[string]interface{}{
			"work_experience": workExp,
			"stars":           totalStars,
			"issues":          user.Issues.TotalCount,
			"pull_requests":   user.PullRequests.TotalCount,
			"repositories":    user.Repositories.TotalCount,
			"additions":       totalAdditions,
			"deletions":       totalDeletions,
			"active_days":     activeDays,
		},
	}
}

// buildProfileCard 构建profile card
func (s *GitHubService) buildProfileCard(user *fetcher.GitHubUserData) *model.GitHubProfileCard {
	return &model.GitHubProfileCard{
		Login:       user.Login,
		Name:        user.Name,
		AvatarURL:   user.AvatarURL,
		Bio:         user.Bio,
		URL:         user.URL,
		Followers:   user.Followers.TotalCount,
		Following:   user.Following.TotalCount,
		PublicRepos: user.Repositories.TotalCount,
		CreatedAt:   user.CreatedAt,
	}
}

// buildActivityCard 构建activity card
func (s *GitHubService) buildActivityCard(user *fetcher.GitHubUserData) *model.GitHubActivityCard {
	// 计算工作年限
	var workExp int
	if user.CreatedAt != "" {
		createdAt, err := time.Parse(time.RFC3339, user.CreatedAt)
		if err == nil {
			workExp = int(math.Ceil(float64(time.Since(createdAt).Hours()) / (24 * 365)))
		}
	}

	// 计算总star数
	var totalStars int
	for _, repo := range user.TopRepos.Nodes {
		totalStars += repo.StargazerCount
	}

	// 统计活动
	var activeDays int
	activity := make([]model.GitHubDailyActivity, 0)
	for _, week := range user.ContributionsCollection.ContributionCalendar.Weeks {
		for _, day := range week.ContributionDays {
			if day.ContributionCount > 0 {
				activeDays++
			}
			activity = append(activity, model.GitHubDailyActivity{
				Date:          day.Date,
				Contributions: day.ContributionCount,
			})
		}
	}

	// 估算代码贡献和语言统计
	var totalAdditions, totalDeletions int
	languages := make(map[string]int)

	for _, pr := range user.PullRequestsTop.Nodes {
		totalAdditions += pr.Additions
		totalDeletions += pr.Deletions

		// 按语言统计（按PR代码量比例分配）
		prTotal := pr.Additions + pr.Deletions
		var langSizeSum int
		for _, lang := range pr.Repository.Languages.Edges {
			langSizeSum += lang.Size
		}
		if langSizeSum > 0 {
			for _, lang := range pr.Repository.Languages.Edges {
				ratio := float64(lang.Size) / float64(langSizeSum)
				languages[lang.Node.Name] += int(float64(prTotal) * ratio)
			}
		}
	}

	return &model.GitHubActivityCard{
		Overview: model.GitHubActivityOverview{
			WorkExperience: workExp,
			Stars:          totalStars,
			Issues:         user.Issues.TotalCount,
			PullRequests:   user.PullRequests.TotalCount,
			Repositories:   user.Repositories.TotalCount,
			Additions:      totalAdditions,
			Deletions:      totalDeletions,
			ActiveDays:     activeDays,
		},
		Activity: activity,
		CodeContribution: model.GitHubCodeContribution{
			Total:          totalAdditions + totalDeletions,
			TotalAdditions: totalAdditions,
			TotalDeletions: totalDeletions,
			Languages:      languages,
		},
	}
}

// buildReposCard 构建repos card
func (s *GitHubService) buildReposCard(user *fetcher.GitHubUserData) *model.GitHubReposCard {
	card := &model.GitHubReposCard{
		TopProjects: make([]model.GitHubRepository, 0),
	}

	// Feature project (最多star的)
	if len(user.TopRepos.Nodes) > 0 {
		topRepo := user.TopRepos.Nodes[0]
		topics := make([]string, 0)
		for _, t := range topRepo.RepositoryTopics.Nodes {
			topics = append(topics, t.Topic.Name)
		}
		card.FeatureProject = &model.GitHubRepository{
			Name:        topRepo.Name,
			FullName:    topRepo.NameWithOwner,
			Description: topRepo.Description,
			URL:         topRepo.URL,
			Stars:       topRepo.StargazerCount,
			Forks:       topRepo.ForkCount,
			Language:    topRepo.PrimaryLanguage.Name,
			Topics:      topics,
			IsOwner:     true,
		}
	}

	// Top projects (从PR贡献)
	prRepoMap := make(map[string]*model.GitHubRepository)
	for _, contrib := range user.ContributionsCollection.PRContributions {
		repo := contrib.Repository
		prRepoMap[repo.URL] = &model.GitHubRepository{
			Name:         repo.Name,
			URL:          repo.URL,
			Description:  repo.Description,
			Stars:        repo.StargazerCount,
			PullRequests: contrib.Contributions.TotalCount,
		}
	}

	// 按PR数排序
	repos := make([]*model.GitHubRepository, 0, len(prRepoMap))
	for _, r := range prRepoMap {
		repos = append(repos, r)
	}
	sort.Slice(repos, func(i, j int) bool {
		return repos[i].PullRequests > repos[j].PullRequests
	})

	for _, r := range repos {
		if len(card.TopProjects) >= 10 {
			break
		}
		card.TopProjects = append(card.TopProjects, *r)
	}

	// 如果没有PR贡献项目，用自己的仓库填充
	if len(card.TopProjects) == 0 {
		for _, repo := range user.TopRepos.Nodes {
			if len(card.TopProjects) >= 10 {
				break
			}
			topics := make([]string, 0)
			for _, t := range repo.RepositoryTopics.Nodes {
				topics = append(topics, t.Topic.Name)
			}
			card.TopProjects = append(card.TopProjects, model.GitHubRepository{
				Name:        repo.Name,
				FullName:    repo.NameWithOwner,
				Description: repo.Description,
				URL:         repo.URL,
				Stars:       repo.StargazerCount,
				Forks:       repo.ForkCount,
				Language:    repo.PrimaryLanguage.Name,
				Topics:      topics,
				IsOwner:     true,
			})
		}
	}

	// Most valuable PR
	if len(user.PullRequestsTop.Nodes) > 0 {
		// 简单选最大改动的
		var bestPR *fetcher.GitHubPRNode
		var bestImpact int
		for i := range user.PullRequestsTop.Nodes {
			pr := &user.PullRequestsTop.Nodes[i]
			impact := pr.Additions + pr.Deletions
			if impact > bestImpact {
				bestImpact = impact
				bestPR = pr
			}
		}
		if bestPR != nil {
			card.MostValuablePullRequest = &model.GitHubPullRequest{
				Title:      bestPR.Title,
				URL:        bestPR.URL,
				Repository: bestPR.Repository.NameWithOwner,
				Additions:  bestPR.Additions,
				Deletions:  bestPR.Deletions,
			}
		}
	}

	return card
}

// generateRoleModel 生成role model card
func (s *GitHubService) generateRoleModel(ctx context.Context, baseData map[string]interface{}) (*model.GitHubRoleModelCard, error) {
	result, err := s.llmClient.GenerateGitHubRoleModel(ctx, baseData)
	if err != nil {
		return nil, err
	}

	return &model.GitHubRoleModelCard{
		Name:            result.Name,
		GitHub:          result.GitHub,
		SimilarityScore: result.SimilarityScore,
		Reason:          result.Reason,
		Achievement:     result.Achievement,
	}, nil
}

// generateRoast 生成roast card
func (s *GitHubService) generateRoast(ctx context.Context, baseData map[string]interface{}) (*model.GitHubRoastCard, error) {
	roast, err := s.llmClient.GenerateGitHubRoast(ctx, baseData)
	if err != nil {
		return nil, err
	}

	return &model.GitHubRoastCard{Roast: roast}, nil
}

// generateSummary 生成summary card (valuation)
func (s *GitHubService) generateSummary(ctx context.Context, baseData map[string]interface{}, user *fetcher.GitHubUserData) (*model.GitHubSummaryCard, error) {
	result, err := s.llmClient.GenerateGitHubValuation(ctx, baseData)
	if err != nil {
		return nil, err
	}

	return &model.GitHubSummaryCard{
		ValuationAndLevel: model.GitHubValuationLevel{
			Level:           result.Level,
			SalaryRange:     result.SalaryRange,
			IndustryRanking: result.IndustryRanking,
			GrowthPotential: result.GrowthPotential,
			Reasoning:       result.Reasoning,
		},
		Description: fmt.Sprintf("GitHub profile analysis for %s", user.Login),
	}, nil
}

// defaultRoleModel 默认role model
func (s *GitHubService) defaultRoleModel(user *fetcher.GitHubUserData) *model.GitHubRoleModelCard {
	return &model.GitHubRoleModelCard{
		Name:            user.Name,
		GitHub:          fmt.Sprintf("https://github.com/%s", user.Login),
		SimilarityScore: 1.0,
		Reason:          "No suitable external role model found; using self as baseline.",
	}
}

// defaultSummary 默认summary
func (s *GitHubService) defaultSummary(baseData map[string]interface{}, user *fetcher.GitHubUserData) *model.GitHubSummaryCard {
	overview, _ := baseData["overview"].(map[string]interface{})
	workExp, _ := overview["work_experience"].(int)
	stars, _ := overview["stars"].(int)
	prs, _ := overview["pull_requests"].(int)

	// 简单估算level
	var level string
	switch {
	case workExp >= 10 && stars >= 1000:
		level = "L7"
	case workExp >= 7 && stars >= 500:
		level = "L6"
	case workExp >= 4 && (stars >= 100 || prs >= 50):
		level = "L5"
	case workExp >= 2:
		level = "L4"
	default:
		level = "L3"
	}

	// Default salary ranges based on level
	salaryRanges := map[string][]int{
		"L3": {80000, 120000},
		"L4": {120000, 160000},
		"L5": {160000, 210000},
		"L6": {210000, 280000},
		"L7": {280000, 400000},
	}
	salaryRange := salaryRanges[level]
	if salaryRange == nil {
		salaryRange = []int{100000, 150000}
	}

	return &model.GitHubSummaryCard{
		ValuationAndLevel: model.GitHubValuationLevel{
			Level:           level,
			SalaryRange:     salaryRange,
			IndustryRanking: 0.5, // Top 50%
			GrowthPotential: "Medium",
			Reasoning:       fmt.Sprintf("Based on %d years of GitHub activity, %d stars, and %d pull requests.", workExp, stars, prs),
		},
		Description: fmt.Sprintf("GitHub profile summary for %s.", user.Login),
	}
}
