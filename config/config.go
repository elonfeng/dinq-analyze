package config

import (
	"os"
)

// Config 应用配置
type Config struct {
	Port          string
	FirecrawlKey  string
	TavilyKey     string
	OpenRouterKey string
	DatabaseURL   string
	GithubToken   string
	ApifyKey      string
}

// Load 从环境变量加载配置
func Load() *Config {
	return &Config{
		Port:          getEnv("PORT", "8080"),
		FirecrawlKey:  getEnv("FIRECRAWL_API_KEY", ""),
		TavilyKey:     getEnv("TAVILY_API_KEY", ""),
		OpenRouterKey: getEnv("OPENROUTER_API_KEY", ""),
		DatabaseURL:   getEnv("DATABASE_URL", ""),
		GithubToken:   getEnv("GITHUB_TOKEN", ""),
		ApifyKey:      getEnv("APIFY_API_KEY", ""),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
