package service

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"sort"
	"strings"
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

	// 发送profile card（第一个，同步，包含AI生成的标签）
	w.SetAction(20, "Processing profile...")
	profileCard := s.buildProfileCard(ctx, userData)
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

	// Feature Project card
	wg.Add(1)
	go func() {
		defer wg.Done()
		featureCard := s.buildFeatureProjectCard(ctx, userData)
		w.SendCardDone(model.GitHubCardFeatureProject, featureCard)
		resultsMu.Lock()
		results[model.GitHubCardFeatureProject] = featureCard
		resultsMu.Unlock()
	}()

	// Top Projects card
	wg.Add(1)
	go func() {
		defer wg.Done()
		topProjectsCard := s.buildTopProjectsCard(userData)
		w.SendCardDone(model.GitHubCardTopProjects, topProjectsCard)
		resultsMu.Lock()
		results[model.GitHubCardTopProjects] = topProjectsCard
		resultsMu.Unlock()
	}()

	// Most Valuable PR card
	wg.Add(1)
	go func() {
		defer wg.Done()
		prCard := s.buildMostValuablePRCard(ctx, userData)
		if prCard != nil {
			w.SendCardDone(model.GitHubCardMostValuablePR, prCard)
			resultsMu.Lock()
			results[model.GitHubCardMostValuablePR] = prCard
			resultsMu.Unlock()
		}
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
		w.SendCardDone(model.GitHubCardValuation, summaryCard)
		resultsMu.Lock()
		results[model.GitHubCardValuation] = summaryCard
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
		model.GitHubCardFeatureProject,
		model.GitHubCardTopProjects,
		model.GitHubCardMostValuablePR,
		model.GitHubCardRoleModel,
		model.GitHubCardRoast,
		model.GitHubCardValuation,
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
func (s *GitHubService) buildProfileCard(ctx context.Context, user *fetcher.GitHubUserData) *model.GitHubProfileCard {
	// 生成个人标签
	tags := s.generatePersonalTags(ctx, user)

	return &model.GitHubProfileCard{
		Login:        user.Login,
		Name:         user.Name,
		AvatarURL:    user.AvatarURL,
		Bio:          user.Bio,
		URL:          user.URL,
		Followers:    user.Followers.TotalCount,
		Following:    user.Following.TotalCount,
		PublicRepos:  user.Repositories.TotalCount,
		CreatedAt:    user.CreatedAt,
		PersonalTags: tags,
	}
}

// generatePersonalTags 生成个人标签
func (s *GitHubService) generatePersonalTags(ctx context.Context, user *fetcher.GitHubUserData) []string {
	// 收集顶级仓库语言
	languages := make([]string, 0)
	for _, repo := range user.TopRepos.Nodes {
		if repo.PrimaryLanguage.Name != "" {
			languages = append(languages, repo.PrimaryLanguage.Name)
		}
	}

	prompt := fmt.Sprintf(`Based on this GitHub profile, provide exactly 3 short professional tags (single words or 2-word phrases):

Name: %s
Bio: %s
Top Languages: %s
Top Repo: %s
Followers: %d

Return only a comma-separated list of 3 tags, no JSON. Example: Open Source, Python, Machine Learning`,
		user.Name,
		user.Bio,
		strings.Join(languages, ", "),
		func() string {
			if len(user.TopRepos.Nodes) > 0 {
				return user.TopRepos.Nodes[0].Name
			}
			return ""
		}(),
		user.Followers.TotalCount)

	response, err := s.llmClient.Chat(ctx, "You generate professional tags for GitHub developers.", prompt)
	if err != nil {
		// 默认标签：基于语言
		if len(languages) > 0 {
			return languages[:min(3, len(languages))]
		}
		return []string{"Developer", "Open Source"}
	}

	// 解析逗号分隔的标签
	tags := strings.Split(response, ",")
	result := make([]string, 0, 3)
	for _, tag := range tags {
		tag = strings.TrimSpace(tag)
		if tag != "" && len(result) < 3 {
			result = append(result, tag)
		}
	}
	if len(result) == 0 {
		return []string{"Developer"}
	}
	return result
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

// buildFeatureProjectCard 构建feature project card
func (s *GitHubService) buildFeatureProjectCard(ctx context.Context, user *fetcher.GitHubUserData) *model.GitHubFeatureProjectCard {
	if len(user.TopRepos.Nodes) == 0 {
		return nil
	}

	topRepo := user.TopRepos.Nodes[0]

	// 提取 owner avatar
	var owner *model.GitHubRepoOwner
	if parts := strings.Split(topRepo.NameWithOwner, "/"); len(parts) >= 1 {
		ownerLogin := parts[0]
		avatarURL := topRepo.Owner.AvatarURL
		if avatarURL == "" {
			avatarURL = fmt.Sprintf("https://avatars.githubusercontent.com/%s", ownerLogin)
		}
		owner = &model.GitHubRepoOwner{
			AvatarURL: avatarURL,
		}
	}

	// 生成 tags (基于 topics 或 AI)
	tags := make([]string, 0)
	for _, t := range topRepo.RepositoryTopics.Nodes {
		if len(tags) < 3 {
			tags = append(tags, t.Topic.Name)
		}
	}
	// 如果没有topics，生成一些基于语言的标签
	if len(tags) == 0 && topRepo.PrimaryLanguage.Name != "" {
		tags = append(tags, topRepo.PrimaryLanguage.Name)
	}

	return &model.GitHubFeatureProjectCard{
		UsedBy:          0, // GitHub API不提供，默认0
		Contributors:    0, // GitHub API不提供，默认0
		MonthlyTrending: 0, // GitHub API不提供，默认0
		Name:            topRepo.Name,
		NameWithOwner:   topRepo.NameWithOwner,
		URL:             topRepo.URL,
		Description:     topRepo.Description,
		Owner:           owner,
		StargazerCount:  topRepo.StargazerCount,
		ForkCount:       topRepo.ForkCount,
		Tags:            tags,
	}
}

// buildTopProjectsCard 构建top projects card
func (s *GitHubService) buildTopProjectsCard(user *fetcher.GitHubUserData) *model.GitHubTopProjectsCard {
	card := &model.GitHubTopProjectsCard{
		Projects: make([]model.GitHubTopProject, 0),
	}

	// 从PR贡献构建
	prRepoMap := make(map[string]*model.GitHubTopProject)
	for _, contrib := range user.ContributionsCollection.PRContributions {
		repo := contrib.Repository
		// 从 nameWithOwner 提取 owner 并构建头像 URL
		var owner *model.GitHubRepoOwner
		if parts := strings.Split(repo.NameWithOwner, "/"); len(parts) >= 1 {
			ownerLogin := parts[0]
			owner = &model.GitHubRepoOwner{
				AvatarURL: fmt.Sprintf("https://avatars.githubusercontent.com/%s", ownerLogin),
			}
		}
		prRepoMap[repo.URL] = &model.GitHubTopProject{
			PullRequests: contrib.Contributions.TotalCount,
			Repository: &model.GitHubTopProjectRepo{
				URL:            repo.URL,
				Name:           repo.Name,
				Description:    repo.Description,
				Owner:          owner,
				StargazerCount: repo.StargazerCount,
			},
		}
	}

	// 按PR数排序
	projects := make([]*model.GitHubTopProject, 0, len(prRepoMap))
	for _, p := range prRepoMap {
		projects = append(projects, p)
	}
	sort.Slice(projects, func(i, j int) bool {
		return projects[i].PullRequests > projects[j].PullRequests
	})

	for _, p := range projects {
		if len(card.Projects) >= 10 {
			break
		}
		card.Projects = append(card.Projects, *p)
	}

	// 如果没有PR贡献项目，用自己的仓库填充
	if len(card.Projects) == 0 {
		for _, repo := range user.TopRepos.Nodes {
			if len(card.Projects) >= 10 {
				break
			}
			// 提取 owner
			var owner *model.GitHubRepoOwner
			if parts := strings.Split(repo.NameWithOwner, "/"); len(parts) >= 1 {
				ownerLogin := parts[0]
				avatarURL := repo.Owner.AvatarURL
				if avatarURL == "" {
					avatarURL = fmt.Sprintf("https://avatars.githubusercontent.com/%s", ownerLogin)
				}
				owner = &model.GitHubRepoOwner{
					AvatarURL: avatarURL,
				}
			}
			card.Projects = append(card.Projects, model.GitHubTopProject{
				PullRequests: 0, // 自己的仓库没有PR贡献数
				Repository: &model.GitHubTopProjectRepo{
					URL:            repo.URL,
					Name:           repo.Name,
					Description:    repo.Description,
					Owner:          owner,
					StargazerCount: repo.StargazerCount,
				},
			})
		}
	}

	return card
}

// buildMostValuablePRCard 构建most valuable PR card
func (s *GitHubService) buildMostValuablePRCard(ctx context.Context, user *fetcher.GitHubUserData) *model.GitHubMostValuablePRCard {
	if len(user.PullRequestsTop.Nodes) == 0 {
		return nil
	}

	// 选最大改动的PR
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

	if bestPR == nil {
		return nil
	}

	// 生成 PR reason 和 impact
	reason, impact := s.generatePRReasonAndImpact(ctx, bestPR)

	return &model.GitHubMostValuablePRCard{
		Repository: bestPR.Repository.NameWithOwner,
		URL:        bestPR.URL,
		Title:      bestPR.Title,
		Additions:  bestPR.Additions,
		Deletions:  bestPR.Deletions,
		Reason:     reason,
		Impact:     impact,
	}
}

// generatePRReasonAndImpact 生成PR价值原因和影响
func (s *GitHubService) generatePRReasonAndImpact(ctx context.Context, pr *fetcher.GitHubPRNode) (reason, impact string) {
	prompt := fmt.Sprintf(`Analyze this Pull Request and provide:
1. reason: A concise explanation (1-2 sentences) of why this PR is valuable
2. impact: A brief description (max 20 words) of what this PR contributes or changes

PR Title: %s
Repository: %s (Stars: %d)
Changes: +%d/-%d lines

Return ONLY valid JSON with this exact structure:
{"reason": "...", "impact": "..."}`,
		pr.Title,
		pr.Repository.NameWithOwner,
		pr.Repository.StargazerCount,
		pr.Additions,
		pr.Deletions)

	response, err := s.llmClient.Chat(ctx, "You analyze GitHub pull requests. Return only valid JSON.", prompt)
	if err != nil {
		return "Significant code contribution to a popular repository.",
			"Enhances functionality with substantial code changes."
	}

	// 解析 JSON 响应
	type prAnalysis struct {
		Reason string `json:"reason"`
		Impact string `json:"impact"`
	}

	var result prAnalysis
	// 清理可能的 markdown 代码块
	response = strings.TrimSpace(response)
	response = strings.TrimPrefix(response, "```json")
	response = strings.TrimPrefix(response, "```")
	response = strings.TrimSuffix(response, "```")
	response = strings.TrimSpace(response)

	if err := json.Unmarshal([]byte(response), &result); err != nil {
		// JSON 解析失败，返回默认值
		return "Significant code contribution to a popular repository.",
			"Enhances functionality with substantial code changes."
	}

	// 限制长度
	if len(result.Reason) > 200 {
		result.Reason = result.Reason[:197] + "..."
	}
	if len(result.Impact) > 100 {
		result.Impact = result.Impact[:97] + "..."
	}

	return result.Reason, result.Impact
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
