-- Create YouTube analysis results table
-- This table stores cached YouTube channel analysis results

CREATE TABLE IF NOT EXISTS youtube_analysis_results (
    channel_id VARCHAR(50) PRIMARY KEY,
    channel_name VARCHAR(200),
    result JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_youtube_analysis_created_at ON youtube_analysis_results(created_at);
CREATE INDEX IF NOT EXISTS idx_youtube_analysis_channel_name ON youtube_analysis_results(channel_name);

-- Add comments for documentation
COMMENT ON TABLE youtube_analysis_results IS 'Stores cached YouTube channel analysis results';
COMMENT ON COLUMN youtube_analysis_results.channel_id IS 'YouTube channel ID (primary key)';
COMMENT ON COLUMN youtube_analysis_results.channel_name IS 'YouTube channel name for easier identification';
COMMENT ON COLUMN youtube_analysis_results.result IS 'JSON analysis result data';
COMMENT ON COLUMN youtube_analysis_results.created_at IS 'When the record was first created';
COMMENT ON COLUMN youtube_analysis_results.updated_at IS 'When the record was last updated';
