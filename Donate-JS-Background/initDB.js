const mysql = require('mysql2/promise');

async function initDatabase() {
    // 首先创建连接（不指定数据库）
    const connection = await mysql.createConnection({
        host: '1Panel-mysql-5HGq',
        user: 'sponsor_db',
        password: '123456',
        port: 3306
    });

    try {
        // 创建数据库
        await connection.query('CREATE DATABASE IF NOT EXISTS sponsor_db');
        console.log('数据库创建成功');

        // 使用 sponsor_db 数据库
        await connection.query('USE sponsor_db');

        // 删除旧表（如果存在）
        await connection.query('DROP TABLE IF EXISTS sponsors');
        await connection.query('DROP TABLE IF EXISTS sponsor_summary');
        console.log('旧表删除成功');

        // 创建订单表
        await connection.query(`
            CREATE TABLE IF NOT EXISTS sponsors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id VARCHAR(50) UNIQUE NOT NULL,
                username VARCHAR(100) NOT NULL,
                recipient VARCHAR(100) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                status ENUM('pending', 'completed', 'failed') DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        `);
        console.log('订单表创建成功');

        // 创建汇总表
        await connection.query(`
            CREATE TABLE IF NOT EXISTS sponsor_summary (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                recipient VARCHAR(100) NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_recipient (username, recipient)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        `);
        console.log('汇总表创建成功');

        console.log('数据库初始化完成！');
    } catch (error) {
        console.error('初始化过程中出错：', error);
        // 打印更详细的错误信息
        if (error.code) {
            console.error('错误代码:', error.code);
        }
        if (error.sqlMessage) {
            console.error('SQL错误:', error.sqlMessage);
        }
    } finally {
        await connection.end();
    }
}

// 运行初始化函数
initDatabase(); 