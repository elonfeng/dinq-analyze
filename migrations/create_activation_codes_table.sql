-- 创建激活码表
CREATE TABLE IF NOT EXISTS activation_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(6) NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_by VARCHAR(100),
    used_by VARCHAR(100),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    used_at DATETIME,
    expires_at DATETIME,
    batch_id VARCHAR(50),
    notes TEXT,
    
    -- 索引
    UNIQUE INDEX idx_activation_code (code),
    INDEX idx_is_used (is_used),
    INDEX idx_created_by (created_by),
    INDEX idx_used_by (used_by),
    INDEX idx_batch_id (batch_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 添加注释
ALTER TABLE activation_codes
    MODIFY COLUMN code VARCHAR(6) NOT NULL COMMENT '唯一激活码（6个字符）',
    MODIFY COLUMN is_used BOOLEAN NOT NULL DEFAULT FALSE COMMENT '激活码是否已被使用',
    MODIFY COLUMN created_by VARCHAR(100) COMMENT '创建激活码的用户ID',
    MODIFY COLUMN used_by VARCHAR(100) COMMENT '使用激活码的用户ID',
    MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    MODIFY COLUMN used_at DATETIME COMMENT '使用时间',
    MODIFY COLUMN expires_at DATETIME COMMENT '过期时间（可选）',
    MODIFY COLUMN batch_id VARCHAR(50) COMMENT '批次ID（用于批量生成）',
    MODIFY COLUMN notes TEXT COMMENT '备注或用途';
