-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    email VARCHAR(100),
    profile_picture VARCHAR(255),
    is_activated BOOLEAN NOT NULL DEFAULT FALSE,
    activation_code VARCHAR(6),
    activated_at DATETIME,
    user_type VARCHAR(20) NOT NULL DEFAULT 'standard',
    preferences JSON,
    last_login DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    UNIQUE INDEX idx_user_id (user_id),
    INDEX idx_is_activated (is_activated),
    INDEX idx_activation_code (activation_code),
    INDEX idx_user_type (user_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 添加注释
ALTER TABLE users
    MODIFY COLUMN user_id VARCHAR(100) NOT NULL COMMENT '唯一用户标识符（来自认证系统）',
    MODIFY COLUMN display_name VARCHAR(100) COMMENT '用户显示名称',
    MODIFY COLUMN email VARCHAR(100) COMMENT '用户电子邮件地址',
    MODIFY COLUMN profile_picture VARCHAR(255) COMMENT '用户头像URL',
    MODIFY COLUMN is_activated BOOLEAN NOT NULL DEFAULT FALSE COMMENT '用户是否已使用激活码',
    MODIFY COLUMN activation_code VARCHAR(6) COMMENT '用户使用的激活码',
    MODIFY COLUMN activated_at DATETIME COMMENT '用户激活时间',
    MODIFY COLUMN user_type VARCHAR(20) NOT NULL DEFAULT 'standard' COMMENT '用户类型（standard, premium, admin等）',
    MODIFY COLUMN preferences JSON COMMENT '用户偏好设置（JSON格式）',
    MODIFY COLUMN last_login DATETIME COMMENT '最后登录时间',
    MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '用户创建时间',
    MODIFY COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '用户信息更新时间';
