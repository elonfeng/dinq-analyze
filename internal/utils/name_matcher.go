package utils

import (
	"regexp"
	"strings"
	"unicode"
)

// NameFeatures 名字特征
type NameFeatures struct {
	Original    string
	Parts       []string // 所有部分（小写）
	Initials    []string // 首字母（大写）
	FullWords   []string // 完整词（小写，长度>1）
	SingleChars []string // 单字符（大写）
	PartCount   int
}

// ParseNameFeatures 提取名字特征
func ParseNameFeatures(name string) *NameFeatures {
	cleaned := cleanName(name)
	if cleaned == "" {
		return nil
	}

	rawParts := strings.Fields(cleaned)
	var parts []string

	for _, p := range rawParts {
		if strings.Contains(p, ".") && len(p) <= 3 {
			// 中间名缩写，如 "Q."
			char := strings.ReplaceAll(p, ".", "")
			if char != "" {
				parts = append(parts, char)
			}
		} else if strings.Contains(p, "-") {
			// 连字符名字
			parts = append(parts, strings.Split(p, "-")...)
		} else {
			parts = append(parts, p)
		}
	}

	if len(parts) == 0 {
		return nil
	}

	features := &NameFeatures{
		Original:  name,
		PartCount: len(parts),
	}

	for _, p := range parts {
		if p == "" {
			continue
		}
		features.Parts = append(features.Parts, strings.ToLower(p))
		features.Initials = append(features.Initials, strings.ToUpper(string(p[0])))
		if len(p) > 1 {
			features.FullWords = append(features.FullWords, strings.ToLower(p))
		} else {
			features.SingleChars = append(features.SingleChars, strings.ToUpper(p))
		}
	}

	return features
}

// cleanName 清理和标准化姓名
func cleanName(name string) string {
	if name == "" {
		return ""
	}
	// 移除引用标记和特殊字符
	re := regexp.MustCompile(`\[\d+\]`)
	name = re.ReplaceAllString(name, "")
	// 只保留字母、数字、空格、点、连字符
	var result strings.Builder
	for _, r := range name {
		if unicode.IsLetter(r) || unicode.IsDigit(r) || r == ' ' || r == '.' || r == '-' {
			result.WriteRune(r)
		}
	}
	// 标准化空格
	return strings.Join(strings.Fields(result.String()), " ")
}

// isAbbreviationMatch 检查是否为缩写匹配
func isAbbreviationMatch(full, abbrev *NameFeatures) bool {
	if full == nil || abbrev == nil {
		return false
	}

	// 获取完整姓名的首字母
	fullInitials := strings.Join(full.Initials, "")
	abbrevChars := strings.Join(abbrev.SingleChars, "")

	// 检查缩写是否是完整姓名首字母的子串
	if abbrevChars != "" && strings.Contains(fullInitials, abbrevChars) {
		// 检查是否有共同的完整单词（通常是姓氏）
		for _, fw := range full.FullWords {
			for _, aw := range abbrev.FullWords {
				if fw == aw {
					return true
				}
			}
		}
	}

	return false
}

// CalculateMatchScore 计算匹配分数 (0-1)
func CalculateMatchScore(f1, f2 *NameFeatures) float64 {
	if f1 == nil || f2 == nil {
		return 0.0
	}

	// 1. 完全匹配检查
	if setsEqual(f1.Parts, f2.Parts) {
		return 1.0
	}

	// 2. 缩写匹配检查
	if isAbbreviationMatch(f1, f2) || isAbbreviationMatch(f2, f1) {
		return 0.85
	}

	// 3. 常规匹配逻辑
	var score float64

	// 完整单词匹配
	if len(f1.FullWords) > 0 && len(f2.FullWords) > 0 {
		overlap := setIntersectionCount(f1.FullWords, f2.FullWords)
		total := setUnionCount(f1.FullWords, f2.FullWords)
		if total > 0 {
			score += 40 * float64(overlap) / float64(total)
		}
	}

	// 首字母匹配
	if len(f1.Initials) > 0 && len(f2.Initials) > 0 {
		overlap := setIntersectionCount(f1.Initials, f2.Initials)
		total := max(len(f1.Initials), len(f2.Initials))
		score += 30 * float64(overlap) / float64(total)
	}

	// 结构一致性
	if f1.PartCount == f2.PartCount {
		score += 10
	} else if abs(f1.PartCount-f2.PartCount) == 1 {
		score += 5
	}

	return score / 100
}

// FuzzyMatchName 模糊匹配名字
// scholarName: 全名（如 "Shilin Lu"）
// paperAuthor: 论文作者（可能是缩写，如 "S Lu"）
// 返回匹配分数
func FuzzyMatchName(fullName, abbrevName string) float64 {
	f1 := ParseNameFeatures(fullName)
	f2 := ParseNameFeatures(abbrevName)
	return CalculateMatchScore(f1, f2)
}

// ExpandAuthorNames 扩展论文作者名字
// authors: 论文作者列表（可能是缩写）
// coauthors: 合作者全名列表
// 返回扩展后的作者列表
func ExpandAuthorNames(authors []string, coauthors []string) []string {
	if len(coauthors) == 0 {
		return authors
	}

	result := make([]string, len(authors))
	for i, author := range authors {
		bestMatch := ""
		bestScore := 0.5 // 最低阈值

		for _, coauthor := range coauthors {
			score := FuzzyMatchName(coauthor, author)
			if score > bestScore {
				bestScore = score
				bestMatch = coauthor
			}
		}

		if bestMatch != "" {
			result[i] = bestMatch
		} else {
			result[i] = author // 保持原样
		}
	}

	return result
}

// Helper functions
func setsEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	set := make(map[string]bool)
	for _, s := range a {
		set[s] = true
	}
	for _, s := range b {
		if !set[s] {
			return false
		}
	}
	return true
}

func setIntersectionCount(a, b []string) int {
	set := make(map[string]bool)
	for _, s := range a {
		set[s] = true
	}
	count := 0
	for _, s := range b {
		if set[s] {
			count++
		}
	}
	return count
}

func setUnionCount(a, b []string) int {
	set := make(map[string]bool)
	for _, s := range a {
		set[s] = true
	}
	for _, s := range b {
		set[s] = true
	}
	return len(set)
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
