package utils

import (
	"fmt"
	"testing"
)

func TestFuzzyMatchName(t *testing.T) {
	testCases := []struct {
		full     string
		abbrev   string
		minScore float64
	}{
		{"Daiheng Gao", "D Gao", 0.5},
		{"Shilin Lu", "S Lu", 0.5},
		{"Haoxiang Wen", "H Wen", 0.5},
		{"Yang Hong", "Y Hong", 0.5},
		{"He Zhou", "H Zhou", 0.5},
	}

	for _, tc := range testCases {
		score := FuzzyMatchName(tc.full, tc.abbrev)
		fmt.Printf("FuzzyMatchName(%q, %q) = %.2f\n", tc.full, tc.abbrev, score)
		if score < tc.minScore {
			t.Errorf("FuzzyMatchName(%q, %q) = %.2f, want >= %.2f", tc.full, tc.abbrev, score, tc.minScore)
		}
	}
}

func TestExpandAuthorNames(t *testing.T) {
	authors := []string{"D Gao", "S Lu", "H Wen", "H Zhou", "X Xin", "Y Zhou"}
	coauthors := []string{"Daiheng Gao", "Shilin Lu", "Haoxiang Wen", "He Zhou", "Xu Xin", "Yuntao Zhou", "Yang Hong", "Lin Gao"}

	expanded := ExpandAuthorNames(authors, coauthors)

	fmt.Printf("Authors:   %v\n", authors)
	fmt.Printf("Coauthors: %v\n", coauthors)
	fmt.Printf("Expanded:  %v\n", expanded)

	// Check that at least some names were expanded
	expandedCount := 0
	for i, e := range expanded {
		if e != authors[i] {
			expandedCount++
		}
	}

	if expandedCount == 0 {
		t.Error("No names were expanded")
	}

	fmt.Printf("Expanded %d/%d names\n", expandedCount, len(authors))
}
