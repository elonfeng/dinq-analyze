package fetcher

import (
	"encoding/csv"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// LinkedInCelebrity LinkedIn名人数据
type LinkedInCelebrity struct {
	Name        string `json:"name"`
	LinkedInURL string `json:"linkedin_url"`
	PhotoURL    string `json:"photo_url"`
	CompanyLogo string `json:"company_logo"`
	Company     string `json:"company"`
	Title       string `json:"title"`
	Salary      string `json:"salary"`
	Remark      string `json:"remark"`
}

// linkedInCelebrities 缓存的名人列表
var linkedInCelebrities []LinkedInCelebrity
var celebritiesLoaded bool

// LoadLinkedInCelebrities 加载LinkedIn名人CSV
func LoadLinkedInCelebrities() ([]LinkedInCelebrity, error) {
	if celebritiesLoaded {
		return linkedInCelebrities, nil
	}

	// 获取CSV文件路径
	csvPath := getLinkedInCelebritiesCSVPath()
	log.Printf("[LinkedIn Celebrities] Loading from: %s", csvPath)

	file, err := os.Open(csvPath)
	if err != nil {
		log.Printf("[LinkedIn Celebrities] Failed to open CSV: %v", err)
		return nil, err
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}

	// 跳过header
	for i := 1; i < len(records); i++ {
		row := records[i]
		// 跳过空行
		if len(row) < 6 || strings.TrimSpace(row[0]) == "" {
			continue
		}

		celebrity := LinkedInCelebrity{
			Name:        strings.TrimSpace(row[0]),
			LinkedInURL: strings.TrimSpace(row[1]),
			PhotoURL:    strings.TrimSpace(row[2]),
			CompanyLogo: strings.TrimSpace(row[3]),
			Company:     strings.TrimSpace(row[4]),
			Title:       strings.TrimSpace(row[5]),
		}
		if len(row) > 6 {
			celebrity.Salary = strings.TrimSpace(row[6])
		}
		if len(row) > 7 {
			celebrity.Remark = strings.TrimSpace(row[7])
		}

		linkedInCelebrities = append(linkedInCelebrities, celebrity)
	}

	celebritiesLoaded = true
	log.Printf("[LinkedIn Celebrities] Loaded %d celebrities", len(linkedInCelebrities))
	return linkedInCelebrities, nil
}

// getLinkedInCelebritiesCSVPath 获取CSV文件路径
func getLinkedInCelebritiesCSVPath() string {
	// 尝试多种路径
	paths := []string{
		"data/linkedin_celebrities.csv",
		"./data/linkedin_celebrities.csv",
		"../data/linkedin_celebrities.csv",
	}

	// 获取可执行文件所在目录
	_, filename, _, ok := runtime.Caller(0)
	if ok {
		dir := filepath.Dir(filepath.Dir(filepath.Dir(filename)))
		paths = append(paths, filepath.Join(dir, "data", "linkedin_celebrities.csv"))
	}

	// 尝试每个路径
	for _, p := range paths {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}

	// 默认返回
	return "data/linkedin_celebrities.csv"
}

// GetLinkedInCelebrities 获取LinkedIn名人列表
func GetLinkedInCelebrities() []LinkedInCelebrity {
	celebrities, err := LoadLinkedInCelebrities()
	if err != nil {
		log.Printf("[LinkedIn Celebrities] Error loading celebrities: %v", err)
		return nil
	}
	return celebrities
}

// FindCelebrityByName 通过名字查找名人
func FindCelebrityByName(name string) *LinkedInCelebrity {
	celebrities := GetLinkedInCelebrities()
	nameLower := strings.ToLower(name)

	for i := range celebrities {
		if strings.ToLower(celebrities[i].Name) == nameLower {
			return &celebrities[i]
		}
	}
	return nil
}

// FindCelebrityByLinkedIn 通过LinkedIn URL查找名人
func FindCelebrityByLinkedIn(linkedinURL string) *LinkedInCelebrity {
	celebrities := GetLinkedInCelebrities()
	urlLower := strings.ToLower(linkedinURL)

	for i := range celebrities {
		celebrityURL := strings.ToLower(celebrities[i].LinkedInURL)
		if celebrityURL != "" && strings.Contains(urlLower, ExtractLinkedInID(celebrityURL)) {
			return &celebrities[i]
		}
	}
	return nil
}

// IsCelebrityByLinkedIn 检查是否是CSV中的名人
func IsCelebrityByLinkedIn(linkedinURL string) bool {
	return FindCelebrityByLinkedIn(linkedinURL) != nil
}

// FormatCelebritiesForPrompt 格式化名人列表用于AI prompt
func FormatCelebritiesForPrompt() string {
	celebrities := GetLinkedInCelebrities()
	if len(celebrities) == 0 {
		return ""
	}

	var sb strings.Builder
	for i, c := range celebrities {
		if i >= 20 { // 限制数量
			break
		}
		sb.WriteString(c.Name)
		sb.WriteString(" - ")
		sb.WriteString(c.Title)
		sb.WriteString(" at ")
		sb.WriteString(c.Company)
		sb.WriteString("\n")
	}
	return sb.String()
}
