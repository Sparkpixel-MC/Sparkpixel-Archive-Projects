-- 创建数据库
CREATE DATABASE IF NOT EXISTS sponsor_db;
USE sponsor_db;

-- 创建赞助表
CREATE TABLE IF NOT EXISTS sponsors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入一些测试数据
INSERT INTO sponsors (username, amount) VALUES
    ('张三', 1000.00),
    ('李四', 2000.00),
    ('王五', 1500.00),
    ('赵六', 3000.00); 