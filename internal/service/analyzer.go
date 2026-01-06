package service

import (
	"context"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"

	"dinq-analyze-go/internal/fetcher"
	"dinq-analyze-go/internal/model"
)

// TopTierVenues 顶会列表
var TopTierVenues = map[string]bool{
	"CVPR": true, "ICCV": true, "ECCV": true,
	"NeurIPS": true, "NIPS": true, "ICLR": true, "ICML": true,
	"AAAI": true, "IJCAI": true,
	"ACM MM": true, "SIGGRAPH": true,
	"ICASSP": true, "ICIP": true,
	"KDD": true, "WWW": true,
	"ACL": true, "EMNLP": true, "NAACL": true,
	"IJCV": true, "TPAMI": true, "TIP": true,
	"3DV": true,
}

// VenueAliases 会议别名映射
var VenueAliases = map[string]string{
	"NIPS":                           "NeurIPS",
	"Advances in Neural Information": "NeurIPS",
	"Computer Vision and Pattern":    "CVPR",
	"International Conference on Computer Vision":          "ICCV",
	"European Conference on Computer Vision":               "ECCV",
	"International Conference on Machine Learning":         "ICML",
	"International Conference on Learning Representations": "ICLR",
	"AAAI Conference on Artificial Intelligence":           "AAAI",
	"ACM International Conference on Multimedia":           "ACM MM",
	"International Conference on 3D Vision":                "3DV",
}

// AnalyzePapers 分析论文数据，生成洞察
func AnalyzePapers(papers []fetcher.PaperData, authorName string) *model.InsightCard {
	insight := &model.InsightCard{
		TotalPapers:            len(papers),
		ConferenceDistribution: make(map[string]int),
	}

	coauthorSet := make(map[string]bool)

	for _, p := range papers {
		// 统计顶会论文
		venue := simplifyVenue(p.Venue)
		if isTopTier(venue) {
			insight.TopTierPapers++
		}

		// 统计会议分布（排除arXiv和Others，只保留顶会）
		if venue != "" && venue != "Others" && venue != "arXiv" && isTopTier(venue) {
			insight.ConferenceDistribution[venue]++
		}

		// 判断作者位置
		pos := getAuthorPosition(p.Authors, authorName)
		if pos == 1 {
			insight.FirstAuthorPapers++
			insight.FirstAuthorCitations += p.Citations
		}
		if pos == len(p.Authors) && len(p.Authors) > 1 {
			insight.LastAuthorPapers++
		}

		// 统计合作者
		for _, author := range p.Authors {
			if !isSameAuthor(author, authorName) {
				coauthorSet[author] = true
			}
		}
	}

	insight.TotalCoauthors = len(coauthorSet)

	// 如果没有识别到顶会，但有论文，只保留有意义的会议
	if len(insight.ConferenceDistribution) == 0 {
		insight.ConferenceDistribution = nil
	}

	return insight
}

// FindClosestCollaboratorFromPapers 找出最亲密的合作者
func FindClosestCollaboratorFromPapers(ctx context.Context, papers []model.Paper, coauthors []fetcher.CoauthorData, authorName string, openAlexClient *fetcher.OpenAlexFetcher) *model.ClosestCollaboratorCard {
	if len(papers) == 0 {
		return nil
	}

	// 统计每个合作者出现次数和最佳论文
	type coauthorStats struct {
		name      string
		count     int
		bestPaper *model.Paper
	}
	stats := make(map[string]*coauthorStats)

	for i := range papers {
		p := &papers[i]
		for _, author := range p.Authors {
			if isSameAuthor(author, authorName) {
				continue
			}
			normalized := normalizeAuthorName(author)
			if normalized == "" {
				continue
			}
			if stats[normalized] == nil {
				stats[normalized] = &coauthorStats{name: author}
			}
			stats[normalized].count++
			if stats[normalized].bestPaper == nil || p.Citations > stats[normalized].bestPaper.Citations {
				stats[normalized].bestPaper = p
			}
		}
	}

	// 找出合作最多的
	var best *coauthorStats
	for _, s := range stats {
		if best == nil || s.count > best.count {
			best = s
		}
	}

	if best == nil {
		return nil
	}

	// 尝试从coauthors列表找更多信息
	card := &model.ClosestCollaboratorCard{
		FullName:         best.name,
		CoauthoredPapers: best.count,
		Avatar:           "https://api.dinq.io/images/icon/advisor.png",
	}

	// 匹配coauthors列表获取更多信息
	foundInCoauthors := false
	for _, c := range coauthors {
		if isSameAuthor(c.Name, best.name) {
			card.FullName = c.Name
			card.Affiliation = c.Affiliation
			card.ScholarID = c.ScholarID
			// 如果有scholar_id，使用Google Scholar头像
			if c.ScholarID != "" {
				card.Avatar = "https://scholar.googleusercontent.com/citations?view_op=view_photo&user=" + c.ScholarID + "&citpid=2"
			}
			foundInCoauthors = true
			break
		}
	}

	// 如果coauthors列表没找到，用OpenAlex查bestPaper获取全名
	if !foundInCoauthors && best.bestPaper != nil && openAlexClient != nil {
		fullAuthors, err := openAlexClient.FindAuthorsByTitle(ctx, best.bestPaper.Title)
		if err == nil && len(fullAuthors) > 0 {
			for _, fullName := range fullAuthors {
				if isSameAuthor(fullName, best.name) {
					card.FullName = fullName
					break
				}
			}
		}
	}

	if best.bestPaper != nil {
		card.BestCoauthoredPaper = &model.BestPaperInfo{
			Title:     best.bestPaper.Title,
			Year:      best.bestPaper.Year,
			Venue:     simplifyVenue(best.bestPaper.Venue),
			Citations: best.bestPaper.Citations,
		}
	}

	return card
}

// FindPaperOfYear 找出最近年份的最佳论文（使用原始数据）
func FindPaperOfYear(papers []fetcher.PaperData, authorName string) *model.PaperOfYearCard {
	modelPapers := make([]model.Paper, len(papers))
	for i, p := range papers {
		modelPapers[i] = model.Paper{
			Title:     p.Title,
			Authors:   p.Authors,
			Venue:     p.Venue,
			Year:      p.Year,
			Citations: p.Citations,
		}
	}
	return FindPaperOfYearFromPapers(modelPapers, authorName)
}

// FindPaperOfYearFromPapers 找出最近年份的最佳论文（使用扩展后的数据）
func FindPaperOfYearFromPapers(papers []model.Paper, authorName string) *model.PaperOfYearCard {
	if len(papers) == 0 {
		return nil
	}

	currentYear := time.Now().Year()

	// 找最近年份有论文的年份
	var latestYear int
	for _, p := range papers {
		if p.Year > 0 && p.Year <= currentYear && p.Year > latestYear {
			latestYear = p.Year
		}
	}

	if latestYear == 0 {
		return nil
	}

	// 找该年份引用最高的论文
	var best *model.Paper
	for i := range papers {
		p := &papers[i]
		if p.Year == latestYear {
			if best == nil || p.Citations > best.Citations {
				best = p
			}
		}
	}

	if best == nil {
		return nil
	}

	return &model.PaperOfYearCard{
		Title:          best.Title,
		Year:           best.Year,
		Venue:          simplifyVenue(best.Venue),
		Citations:      best.Citations,
		AuthorPosition: getAuthorPosition(best.Authors, authorName),
	}
}

// FindRepresentativePaper 找出代表作（引用最高的论文）- 使用原始数据
func FindRepresentativePaper(papers []fetcher.PaperData, authorName string) *model.RepresentativePaperCard {
	modelPapers := make([]model.Paper, len(papers))
	for i, p := range papers {
		modelPapers[i] = model.Paper{
			Title:     p.Title,
			Authors:   p.Authors,
			Venue:     p.Venue,
			Year:      p.Year,
			Citations: p.Citations,
		}
	}
	return FindRepresentativePaperFromPapers(modelPapers, authorName)
}

// FindRepresentativePaperFromPapers 找出代表作（引用最高的论文）- 使用扩展后的数据
func FindRepresentativePaperFromPapers(papers []model.Paper, authorName string) *model.RepresentativePaperCard {
	if len(papers) == 0 {
		return nil
	}

	// 找引用最高的论文
	var best *model.Paper
	for i := range papers {
		p := &papers[i]
		if best == nil || p.Citations > best.Citations {
			best = p
		}
	}

	if best == nil || best.Citations == 0 {
		return nil
	}

	return &model.RepresentativePaperCard{
		Title:          best.Title,
		Year:           best.Year,
		Venue:          simplifyVenue(best.Venue),
		FullVenue:      best.Venue,
		Citations:      best.Citations,
		AuthorPosition: getAuthorPosition(best.Authors, authorName),
	}
}

// formatVenueWithYear 格式化会议名称带年份
func formatVenueWithYear(venue string, year int) string {
	if venue == "" || venue == "Others" || venue == "arXiv" {
		return venue
	}
	if year > 0 {
		return fmt.Sprintf("%s %d", venue, year)
	}
	return venue
}

// simplifyVenue 简化会议名称
func simplifyVenue(venue string) string {
	if venue == "" {
		return ""
	}

	venueUpper := strings.ToUpper(venue)

	// 检查是否是arXiv
	if strings.Contains(venueUpper, "ARXIV") {
		return "arXiv"
	}

	// 检查直接匹配顶会
	for name := range TopTierVenues {
		if strings.Contains(venueUpper, strings.ToUpper(name)) {
			return name
		}
	}

	// 检查别名
	for alias, name := range VenueAliases {
		if strings.Contains(venue, alias) {
			return name
		}
	}

	// 尝试提取会议缩写 (大写字母组成的词)
	re := regexp.MustCompile(`\b([A-Z]{2,})\b`)
	matches := re.FindStringSubmatch(venue)
	if len(matches) > 1 {
		abbr := matches[1]
		if TopTierVenues[abbr] {
			return abbr
		}
	}

	// 不认识的返回原始值
	return venue
}

// isTopTier 判断是否是顶会
func isTopTier(venue string) bool {
	if venue == "" || venue == "Others" || venue == "arXiv" {
		return false
	}
	return TopTierVenues[venue]
}

// getAuthorPosition 获取作者在论文中的位置
func getAuthorPosition(authors []string, authorName string) int {
	for i, author := range authors {
		if isSameAuthor(author, authorName) {
			return i + 1
		}
	}
	return 0
}

// isSameAuthor 判断是否是同一作者（模糊匹配）
func isSameAuthor(a, b string) bool {
	if a == "" || b == "" {
		return false
	}

	// 标准化
	a = normalizeAuthorName(a)
	b = normalizeAuthorName(b)

	if a == b {
		return true
	}

	// 检查是否一个是另一个的缩写
	aParts := strings.Fields(a)
	bParts := strings.Fields(b)

	if len(aParts) == 0 || len(bParts) == 0 {
		return false
	}

	// 姓氏匹配
	aLast := aParts[len(aParts)-1]
	bLast := bParts[len(bParts)-1]
	if aLast != bLast {
		return false
	}

	// 名字首字母匹配
	if len(aParts) > 1 && len(bParts) > 1 {
		aFirst := strings.ToUpper(string(aParts[0][0]))
		bFirst := strings.ToUpper(string(bParts[0][0]))
		return aFirst == bFirst
	}

	return true
}

// normalizeAuthorName 标准化作者名
func normalizeAuthorName(name string) string {
	name = strings.TrimSpace(name)
	name = strings.ToLower(name)
	// 移除标点
	re := regexp.MustCompile(`[^\w\s]`)
	name = re.ReplaceAllString(name, "")
	return strings.TrimSpace(name)
}

// SortConferenceDistribution 按数量排序会议分布
func SortConferenceDistribution(dist map[string]int) []struct {
	Name  string
	Count int
} {
	result := make([]struct {
		Name  string
		Count int
	}, 0, len(dist))

	for name, count := range dist {
		result = append(result, struct {
			Name  string
			Count int
		}{name, count})
	}

	sort.Slice(result, func(i, j int) bool {
		return result[i].Count > result[j].Count
	})

	return result
}
