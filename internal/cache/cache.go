package cache

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	_ "github.com/lib/pq"
)

// CachedResult 缓存的分析结果
type CachedResult struct {
	SubjectID string                 `json:"subject_id"` // scholar_id 或 github_login
	Source    string                 `json:"source"`     // "scholar" 或 "github"
	Data      map[string]interface{} `json:"data"`
	CreatedAt time.Time              `json:"created_at"`
	ExpiresAt time.Time              `json:"expires_at"`
}

// Cache 缓存接口
type Cache interface {
	Get(ctx context.Context, subjectID string) (*CachedResult, error)
	Set(ctx context.Context, subjectID string, data map[string]interface{}, ttl time.Duration) error
	Delete(ctx context.Context, subjectID string) error
}

// SourceCache 支持多数据源的缓存接口
type SourceCache interface {
	GetBySource(ctx context.Context, source, subjectID string) (*CachedResult, error)
	SetBySource(ctx context.Context, source, subjectID string, data map[string]interface{}, ttl time.Duration) error
	DeleteBySource(ctx context.Context, source, subjectID string) error
}

// FileCache 基于文件的缓存实现
type FileCache struct {
	dir string
	mu  sync.RWMutex
}

// NewFileCache 创建文件缓存
func NewFileCache(dir string) (*FileCache, error) {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create cache directory: %w", err)
	}
	return &FileCache{dir: dir}, nil
}

func (c *FileCache) cacheFile(scholarID string) string {
	return filepath.Join(c.dir, scholarID+".json")
}

// Get 获取缓存
func (c *FileCache) Get(ctx context.Context, scholarID string) (*CachedResult, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	data, err := os.ReadFile(c.cacheFile(scholarID))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil // 缓存不存在
		}
		return nil, err
	}

	var result CachedResult
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, err
	}

	// 检查是否过期
	if time.Now().After(result.ExpiresAt) {
		// 过期了，删除缓存
		go c.Delete(context.Background(), scholarID)
		return nil, nil
	}

	return &result, nil
}

// Set 设置缓存
func (c *FileCache) Set(ctx context.Context, scholarID string, data map[string]interface{}, ttl time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	result := CachedResult{
		SubjectID: scholarID,
		Source:    "scholar",
		Data:      data,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(ttl),
	}

	jsonData, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(c.cacheFile(scholarID), jsonData, 0644)
}

// Delete 删除缓存
func (c *FileCache) Delete(ctx context.Context, scholarID string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	err := os.Remove(c.cacheFile(scholarID))
	if os.IsNotExist(err) {
		return nil
	}
	return err
}

// MemoryCache 内存缓存实现（用于测试或单机部署）
type MemoryCache struct {
	data map[string]*CachedResult
	mu   sync.RWMutex
}

// NewMemoryCache 创建内存缓存
func NewMemoryCache() *MemoryCache {
	return &MemoryCache{
		data: make(map[string]*CachedResult),
	}
}

// Get 获取缓存
func (c *MemoryCache) Get(ctx context.Context, scholarID string) (*CachedResult, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result, ok := c.data[scholarID]
	if !ok {
		return nil, nil
	}

	// 检查是否过期
	if time.Now().After(result.ExpiresAt) {
		go c.Delete(context.Background(), scholarID)
		return nil, nil
	}

	return result, nil
}

// Set 设置缓存
func (c *MemoryCache) Set(ctx context.Context, scholarID string, data map[string]interface{}, ttl time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.data[scholarID] = &CachedResult{
		SubjectID: scholarID,
		Source:    "scholar",
		Data:      data,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(ttl),
	}
	return nil
}

// Delete 删除缓存
func (c *MemoryCache) Delete(ctx context.Context, scholarID string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	delete(c.data, scholarID)
	return nil
}

// PostgresCache PostgreSQL缓存实现
type PostgresCache struct {
	db     *sql.DB
	source string // 数据源标识: "scholar" 或 "github"
}

// NewPostgresCache 创建PostgreSQL缓存
func NewPostgresCache(databaseURL, source string) (*PostgresCache, error) {
	db, err := sql.Open("postgres", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// 测试连接
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	cache := &PostgresCache{db: db, source: source}
	return cache, nil
}

// Get 获取缓存
func (c *PostgresCache) Get(ctx context.Context, subjectID string) (*CachedResult, error) {
	return c.GetBySource(ctx, c.source, subjectID)
}

// GetBySource 按数据源获取缓存
func (c *PostgresCache) GetBySource(ctx context.Context, source, subjectID string) (*CachedResult, error) {
	query := `
	SELECT subject_id, source, data, created_at, expires_at
	FROM analysis_cache
	WHERE source = $1 AND subject_id = $2 AND expires_at > NOW()
	`

	var result CachedResult
	var dataJSON []byte

	err := c.db.QueryRowContext(ctx, query, source, subjectID).Scan(
		&result.SubjectID,
		&result.Source,
		&dataJSON,
		&result.CreatedAt,
		&result.ExpiresAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil // 缓存不存在或已过期
	}
	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal(dataJSON, &result.Data); err != nil {
		return nil, err
	}

	return &result, nil
}

// Set 设置缓存
func (c *PostgresCache) Set(ctx context.Context, subjectID string, data map[string]interface{}, ttl time.Duration) error {
	return c.SetBySource(ctx, c.source, subjectID, data, ttl)
}

// SetBySource 按数据源设置缓存
func (c *PostgresCache) SetBySource(ctx context.Context, source, subjectID string, data map[string]interface{}, ttl time.Duration) error {
	dataJSON, err := json.Marshal(data)
	if err != nil {
		return err
	}

	expiresAt := time.Now().Add(ttl)

	query := `
	INSERT INTO analysis_cache (source, subject_id, data, created_at, expires_at)
	VALUES ($1, $2, $3, NOW(), $4)
	ON CONFLICT (source, subject_id)
	DO UPDATE SET data = $3, created_at = NOW(), expires_at = $4
	`

	_, err = c.db.ExecContext(ctx, query, source, subjectID, dataJSON, expiresAt)
	return err
}

// Delete 删除缓存
func (c *PostgresCache) Delete(ctx context.Context, subjectID string) error {
	return c.DeleteBySource(ctx, c.source, subjectID)
}

// DeleteBySource 按数据源删除缓存
func (c *PostgresCache) DeleteBySource(ctx context.Context, source, subjectID string) error {
	query := `DELETE FROM analysis_cache WHERE source = $1 AND subject_id = $2`
	_, err := c.db.ExecContext(ctx, query, source, subjectID)
	return err
}

// Close 关闭数据库连接
func (c *PostgresCache) Close() error {
	return c.db.Close()
}

// CleanExpired 清理过期缓存
func (c *PostgresCache) CleanExpired(ctx context.Context) (int64, error) {
	query := `DELETE FROM analysis_cache WHERE expires_at < NOW()`
	result, err := c.db.ExecContext(ctx, query)
	if err != nil {
		return 0, err
	}
	return result.RowsAffected()
}
