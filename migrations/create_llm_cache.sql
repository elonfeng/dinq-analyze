CREATE TABLE IF NOT EXISTS llm_cache (
  id SERIAL PRIMARY KEY,
  cache_key VARCHAR(128) UNIQUE NOT NULL,
  response_text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_cache_key ON llm_cache(cache_key);
