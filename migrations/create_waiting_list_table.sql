-- 创建等待列表表
CREATE TABLE IF NOT EXISTS waiting_list (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    organization VARCHAR(100),
    job_title VARCHAR(100),
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    extra_data JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    approved_at DATETIME,
    approved_by VARCHAR(100),

    -- 索引
    UNIQUE INDEX idx_user_id (user_id),
    INDEX idx_email (email),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 添加注释
ALTER TABLE waiting_list
    MODIFY COLUMN user_id VARCHAR(100) NOT NULL COMMENT '用户ID（来自认证系统）',
    MODIFY COLUMN email VARCHAR(100) NOT NULL COMMENT '用户电子邮件地址',
    MODIFY COLUMN name VARCHAR(100) NOT NULL COMMENT '用户全名',
    MODIFY COLUMN organization VARCHAR(100) COMMENT '用户组织或公司',
    MODIFY COLUMN job_title VARCHAR(100) COMMENT '用户职位',
    MODIFY COLUMN reason TEXT COMMENT '加入等待列表的原因',
    MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态（pending, approved, rejected）',
    MODIFY COLUMN extra_data JSON COMMENT '额外元数据（JSON格式）',
    MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    MODIFY COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    MODIFY COLUMN approved_at DATETIME COMMENT '批准时间',
    MODIFY COLUMN approved_by VARCHAR(100) COMMENT '批准人的用户ID';
