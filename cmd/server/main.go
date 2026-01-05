package main

import (
	"log"
	"net/http"

	"github.com/joho/godotenv"

	"dinq-analyze-go/config"
	"dinq-analyze-go/internal/cache"
	"dinq-analyze-go/internal/handler"
	"dinq-analyze-go/internal/service"
)

func main() {
	// 加载 .env 文件（如果存在）
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using environment variables")
	}

	cfg := config.Load()

	// 验证必要的API keys
	if cfg.FirecrawlKey == "" || cfg.TavilyKey == "" || cfg.OpenRouterKey == "" {
		log.Println("Warning: Some API keys are not configured")
		log.Println("Required: FIRECRAWL_API_KEY, TAVILY_API_KEY, OPENROUTER_API_KEY")
	}
	if cfg.GithubToken == "" {
		log.Println("Warning: GITHUB_TOKEN not configured, GitHub analysis will not work")
	}
	if cfg.ApifyKey == "" {
		log.Println("Warning: APIFY_API_KEY not configured, LinkedIn analysis will not work")
	}

	// 创建缓存（优先使用PostgreSQL，否则使用内存缓存）
	var scholarCache, githubCache, linkedinCache cache.Cache
	if cfg.DatabaseURL != "" {
		pgScholarCache, err := cache.NewPostgresCache(cfg.DatabaseURL, "scholar")
		if err != nil {
			log.Printf("Warning: Failed to connect to PostgreSQL, using memory cache: %v", err)
			scholarCache = cache.NewMemoryCache()
			githubCache = cache.NewMemoryCache()
			linkedinCache = cache.NewMemoryCache()
		} else {
			log.Println("Using PostgreSQL cache")
			scholarCache = pgScholarCache
			// GitHub使用相同数据库但不同source
			pgGithubCache, _ := cache.NewPostgresCache(cfg.DatabaseURL, "github")
			githubCache = pgGithubCache
			// LinkedIn使用相同数据库但不同source
			pgLinkedinCache, _ := cache.NewPostgresCache(cfg.DatabaseURL, "linkedin")
			linkedinCache = pgLinkedinCache
		}
	} else {
		log.Println("DATABASE_URL not configured, using memory cache")
		scholarCache = cache.NewMemoryCache()
		githubCache = cache.NewMemoryCache()
		linkedinCache = cache.NewMemoryCache()
	}

	// 创建Scholar服务
	scholarService := service.NewScholarServiceWithCache(
		cfg.FirecrawlKey,
		cfg.TavilyKey,
		cfg.OpenRouterKey,
		scholarCache,
	)

	// 创建GitHub服务
	githubService := service.NewGitHubService(
		cfg.GithubToken,
		cfg.OpenRouterKey,
		githubCache,
	)

	// 创建LinkedIn服务
	linkedinService := service.NewLinkedInService(
		cfg.TavilyKey,
		cfg.ApifyKey,
		cfg.OpenRouterKey,
		linkedinCache,
	)

	// 创建处理器
	scholarHandler := handler.NewScholarHandler(scholarService)
	githubHandler := handler.NewGitHubHandler(githubService)
	linkedinHandler := handler.NewLinkedInHandler(linkedinService)

	// 设置路由
	mux := http.NewServeMux()
	mux.HandleFunc("/health", scholarHandler.Health)
	mux.HandleFunc("/api/analyze/scholar/sse", scholarHandler.AnalyzeSSE)
	mux.HandleFunc("/api/analyze/github/sse", githubHandler.AnalyzeSSE)
	mux.HandleFunc("/api/analyze/linkedin/sse", linkedinHandler.AnalyzeSSE)

	// CORS中间件
	corsHandler := corsMiddleware(mux)

	log.Printf("Server starting on port %s", cfg.Port)
	if err := http.ListenAndServe(":"+cfg.Port, corsHandler); err != nil {
		log.Fatal(err)
	}
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
