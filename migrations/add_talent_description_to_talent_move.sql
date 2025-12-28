-- 为 talent_move 表添加 talent_description 字段
-- 执行时间: 2025-07-12

-- 添加 talent_description 字段
ALTER TABLE talent_move ADD COLUMN talent_description TEXT;

-- 添加注释
COMMENT ON COLUMN talent_move.talent_description IS 'Comprehensive description of the talent move including background, salary, and significance';

-- 验证字段是否添加成功
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'talent_move' AND column_name = 'talent_description'; 