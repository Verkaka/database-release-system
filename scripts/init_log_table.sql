-- 初始化迁移日志表
-- 在所有目标数据库执行此脚本

USE test_db;  -- 修改为实际数据库名

CREATE TABLE IF NOT EXISTS schema_migrations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID',
    request_id VARCHAR(64) NOT NULL COMMENT '审批请求 ID',
    `sql` TEXT NOT NULL COMMENT '执行的 SQL',
    rollback_sql TEXT COMMENT '回滚 SQL',
    executed_at DATETIME NOT NULL COMMENT '执行时间',
    executed_by VARCHAR(128) COMMENT '执行人',
    status ENUM('success', 'failed', 'rolled_back') NOT NULL COMMENT '执行状态',
    error TEXT COMMENT '错误信息',
    affected_rows INT DEFAULT 0 COMMENT '影响行数',
    rolled_back_at DATETIME COMMENT '回滚时间',
    INDEX idx_request_id (request_id) COMMENT '请求 ID 索引',
    INDEX idx_status (status) COMMENT '状态索引',
    INDEX idx_executed_at (executed_at) COMMENT '执行时间索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库迁移日志表';

-- 测试插入
INSERT INTO schema_migrations 
(request_id, `sql`, executed_at, executed_by, status, affected_rows)
VALUES 
('INIT-001', 'CREATE TABLE init_test (id BIGINT);', NOW(), 'system', 'success', 0);

-- 验证
SELECT * FROM schema_migrations LIMIT 1;
