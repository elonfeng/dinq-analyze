package fetcher

import (
	"regexp"
	"strconv"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// ScholarParser Google Scholar HTML解析器
type ScholarParser struct{}

// NewScholarParser 创建解析器
func NewScholarParser() *ScholarParser {
	return &ScholarParser{}
}

// ParsedProfile 解析后的完整数据
type ParsedProfile struct {
	Profile   ProfileData
	Papers    []PaperData
	Coauthors []CoauthorData
}

// CoauthorData 合作者数据
type CoauthorData struct {
	Name        string
	ScholarID   string
	Affiliation string
}

// Parse 解析Google Scholar HTML
func (p *ScholarParser) Parse(html string) (*ParsedProfile, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
	if err != nil {
		return nil, err
	}

	result := &ParsedProfile{}

	// 解析Profile
	result.Profile = p.parseProfile(doc)

	// 解析Papers
	result.Papers = p.parsePapers(doc)

	// 解析Coauthors
	result.Coauthors = p.parseCoauthors(doc)

	return result, nil
}

func (p *ScholarParser) parseProfile(doc *goquery.Document) ProfileData {
	profile := ProfileData{}

	// 名字
	profile.Name = strings.TrimSpace(doc.Find("#gsc_prf_in").Text())

	// 机构
	profile.Affiliation = strings.TrimSpace(doc.Find(".gsc_prf_il").First().Text())

	// 研究兴趣
	interests := []string{}
	doc.Find("#gsc_prf_int a").Each(func(i int, s *goquery.Selection) {
		interests = append(interests, strings.TrimSpace(s.Text()))
	})
	profile.Interests = strings.Join(interests, ", ")

	// 引用指标 - 从表格解析 (All time 和 Since 5y 两列)
	doc.Find("#gsc_rsb_st tr").Each(func(i int, s *goquery.Selection) {
		label := strings.ToLower(strings.TrimSpace(s.Find("td").First().Text()))
		allTimeValue := strings.TrimSpace(s.Find("td.gsc_rsb_std").Eq(0).Text())
		since5yValue := strings.TrimSpace(s.Find("td.gsc_rsb_std").Eq(1).Text())

		switch {
		case strings.Contains(label, "citations"):
			profile.TotalCites, _ = strconv.Atoi(strings.ReplaceAll(allTimeValue, ",", ""))
			profile.Citations5y, _ = strconv.Atoi(strings.ReplaceAll(since5yValue, ",", ""))
		case strings.Contains(label, "h-index"):
			profile.HIndex, _ = strconv.Atoi(allTimeValue)
			profile.HIndex5y, _ = strconv.Atoi(since5yValue)
		case strings.Contains(label, "i10-index"):
			profile.I10Index, _ = strconv.Atoi(allTimeValue)
		}
	})

	// 年度引用 - 从图表解析 (gsc_g_t = 年份标签, gsc_g_a = 引用数)
	profile.YearlyCitations = make(map[string]int)
	years := []string{}
	doc.Find(".gsc_g_t").Each(func(i int, s *goquery.Selection) {
		years = append(years, strings.TrimSpace(s.Text()))
	})
	doc.Find(".gsc_g_a").Each(func(i int, s *goquery.Selection) {
		if i < len(years) {
			citations, _ := strconv.Atoi(strings.TrimSpace(s.Text()))
			profile.YearlyCitations[years[i]] = citations
		}
	})

	return profile
}

func (p *ScholarParser) parsePapers(doc *goquery.Document) []PaperData {
	papers := []PaperData{}

	doc.Find(".gsc_a_tr").Each(func(i int, s *goquery.Selection) {
		paper := PaperData{}

		// 标题
		paper.Title = strings.TrimSpace(s.Find(".gsc_a_at").Text())

		// 作者和venue
		grayText := s.Find(".gs_gray")
		if grayText.Length() >= 1 {
			authorsText := strings.TrimSpace(grayText.Eq(0).Text())
			paper.Authors = parseAuthors(authorsText)
		}
		if grayText.Length() >= 2 {
			paper.Venue = strings.TrimSpace(grayText.Eq(1).Text())
		}

		// 引用数
		citesText := strings.TrimSpace(s.Find(".gsc_a_ac").Text())
		paper.Citations, _ = strconv.Atoi(citesText)

		// 年份
		yearText := strings.TrimSpace(s.Find(".gsc_a_y span").Text())
		paper.Year, _ = strconv.Atoi(yearText)

		if paper.Title != "" {
			papers = append(papers, paper)
		}
	})

	return papers
}

func (p *ScholarParser) parseCoauthors(doc *goquery.Document) []CoauthorData {
	coauthors := []CoauthorData{}

	doc.Find(".gsc_rsb_a_desc").Each(func(i int, s *goquery.Selection) {
		coauthor := CoauthorData{}

		// 名字和链接
		link := s.Find("a")
		coauthor.Name = strings.TrimSpace(link.Text())
		if href, exists := link.Attr("href"); exists {
			// 从href提取scholar_id
			// 格式: /citations?user=XXXXXX&hl=en
			re := regexp.MustCompile(`user=([^&]+)`)
			if matches := re.FindStringSubmatch(href); len(matches) > 1 {
				coauthor.ScholarID = matches[1]
			}
		}

		// 机构 - 清理掉 "Verified email at..." 后缀
		affiliation := strings.TrimSpace(s.Find(".gsc_rsb_a_ext").Text())
		// 移除 "Verified email at xxx" 部分
		if idx := strings.Index(affiliation, "Verified email"); idx > 0 {
			affiliation = strings.TrimSpace(affiliation[:idx])
		}
		coauthor.Affiliation = affiliation

		if coauthor.Name != "" {
			coauthors = append(coauthors, coauthor)
		}
	})

	return coauthors
}

func parseAuthors(text string) []string {
	// 分割作者，可能用逗号或 "and" 分隔
	text = strings.ReplaceAll(text, " and ", ", ")
	parts := strings.Split(text, ",")
	authors := make([]string, 0, len(parts))
	for _, part := range parts {
		author := strings.TrimSpace(part)
		// 清理特殊字符（如 "*" 表示共同一作）
		author = strings.TrimSuffix(author, "*")
		author = strings.TrimSpace(author)
		if author != "" && author != "..." {
			authors = append(authors, author)
		}
	}
	return authors
}

// ParsePapersOnly 只解析论文（用于合并多页结果）
func (p *ScholarParser) ParsePapersOnly(html string) ([]PaperData, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
	if err != nil {
		return nil, err
	}
	return p.parsePapers(doc), nil
}

// ParseMultiPage 解析多页HTML，合并论文
func (p *ScholarParser) ParseMultiPage(htmlPages []string) (*ParsedProfile, error) {
	if len(htmlPages) == 0 {
		return nil, nil
	}

	// 第一页包含完整profile信息
	result, err := p.Parse(htmlPages[0])
	if err != nil {
		return nil, err
	}

	// 后续页只提取论文并合并
	for i := 1; i < len(htmlPages); i++ {
		papers, err := p.ParsePapersOnly(htmlPages[i])
		if err != nil {
			continue // 忽略解析失败的页面
		}
		result.Papers = append(result.Papers, papers...)
	}

	return result, nil
}
