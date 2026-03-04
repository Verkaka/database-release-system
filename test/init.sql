-- 初始化测试数据库
-- 创建初始表结构用于对比测试

CREATE TABLE IF NOT EXISTS existing_table (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO existing_table (name) VALUES 
    ('test_item_1'),
    ('test_item_2');

-- 创建迁移日志表
CREATE TABLE IF NOT EXISTS schema_migrations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL,
    sql TEXT NOT NULL,
    rollback_sql TEXT,
    executed_at DATETIME NOT NULL,
    executed_by VARCHAR(128),
    status ENUM('success', 'failed', 'rolled_back') NOT NULL,
    error TEXT,
    affected_rows INT DEFAULT 0,
    rolled_back_at DATETIME,
    INDEX idx_request_id (request_id),
    INDEX idx_status (status),
    INDEX idx_executed_at (executed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
