const express = require('express');
const mysql = require('mysql2/promise');
const crypto = require('crypto');
const axios = require('axios');
const app = express();
const cors = require('cors');
const rateLimit = require('express-rate-limit');



// 启用 JSON 解析中间件
app.use(express.json());
app.use(cors());
// 启用静态文件服务
app.use(express.static('public'));

// 数据库连接配置
const dbConfig = {
    host: '1Panel-mysql-5HGq',
    user: 'sponsor_db',
    password: '123456',
    database: 'sponsor_db',
    port:  3306,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
};

// 创建数据库连接池
const pool = mysql.createPool(dbConfig);
// 定时任务：合并赞助数据和清理旧数据
async function scheduledTasks() {
    try {
        // 合并已完成的赞助数据到汇总表
        await pool.query(`
            INSERT INTO sponsor_summary (username, recipient, total_amount)
            SELECT 
                username,
                recipient,
                SUM(amount) as total_amount
            FROM sponsors
            WHERE status = 'completed'
            GROUP BY username, recipient
            ON DUPLICATE KEY UPDATE
                total_amount = total_amount + VALUES(total_amount)
        `);

        // 清空已合并的已完成订单
        await pool.query(`
            DELETE FROM sponsors 
            WHERE status = 'completed'
        `);

        // 检查未支付订单总数
        const [countResult] = await pool.query(
            'SELECT COUNT(*) as total FROM sponsors WHERE status = "pending"'
        );
        const totalPendingOrders = countResult[0].total;

        // 如果未支付订单数超过5000，删除两小时前的未支付订单
        if (totalPendingOrders > 5000) {
            const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
            await pool.query(
                'DELETE FROM sponsors WHERE status = "pending" AND created_at < ?', 
                [twoHoursAgo]
            );
            console.log('已删除两小时前的未支付订单数据');
        }

        console.log('定时任务执行完成，未支付订单数:', totalPendingOrders);
    } catch (error) {
        console.error('定时任务执行失败:', error);
    }
}

// 每20秒执行一次定时任务
setInterval(scheduledTasks, 20000);
// 生成订单号
function generateOrderId() {
    return 'ORDER' + Date.now() + Math.random().toString(36).substr(2, 5);
}

// 获取赞助排名的API
app.get('/api/sponsors/ranking', async (req, res) => {
    try {
        // 获取所有赞助记录，按金额排序
        const [rows] = await pool.query(`
            SELECT 
                username,
                recipient,
                total_amount as amount
            FROM sponsor_summary 
            ORDER BY total_amount DESC
        `);
        
        const rankings = rows.map((row, index) => ({
            rank: index + 1,
            username: row.username,
            amount: row.amount,
            recipient: row.recipient
        }));

        res.json({
            success: true,
            data: rankings
        });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({
            success: false,
            message: '服务器内部错误'
        });
    }
});
// 提交赞助请求的API
app.get('/submit_donation', async (req, res) => {
    const { recipient, amount } = req.query;  // 从 query 参数获取
    
    if (!recipient || !amount) {
        return res.status(400).json({
            success: false,
            message: '缺少必要参数'
        });
    }

    try {
        // 生成订单号
        const orderId = generateOrderId();
        
        // 创建待处理的赞助记录
        await pool.query(
            'INSERT INTO sponsors (order_id, username, recipient, amount) VALUES (?, ?, ?, ?)',
            [orderId, '', recipient, amount]
        );

        // 构建 OAuth 授权 URL
        const oauthUrl = `https://mcskin.bu7.top/oauth/authorize?client_id=2&redirect_uri=${encodeURIComponent(`https://api-donate-sparkpixel.bu7.top/oauth2`)}&response_type=code&scope=&state=${orderId}`;
        
        // 直接重定向到 OAuth 授权页面
        res.redirect(oauthUrl);
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({
            success: false,
            message: '服务器内部错误'
        });
    }
});

// OAuth回调处理
app.get('/oauth2', async (req, res) => {
    const { code, state: order_id } = req.query;

    try {
        // 使用 code 获取 access_token
        const tokenResponse = await axios.post('https://mcskin.bu7.top/oauth/token', 
            new URLSearchParams({
                grant_type: 'authorization_code',
                client_id: '2',
                client_secret: 'QFMwLJcWroEsJre62juI2mxgXn3DL4HOX8X3GLw7',
                redirect_uri: 'https://api-donate-sparkpixel.bu7.top/oauth2',
                code: code
            }).toString(),
            {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                }
            }
        );

        const accessToken = tokenResponse.data.access_token;

        // 使用 access_token 获取用户信息
        const userResponse = await axios.get('https://mcskin.bu7.top/api/user', {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Accept': 'application/json'
            }
        });

        const { email, nickname } = userResponse.data;

        // 确保 username 不为 NULL
        const safeUsername = nickname || '匿名用户';

        // 获取订单信息
        const [rows] = await pool.query(
            'SELECT recipient, amount FROM sponsors WHERE order_id = ?',
            [order_id]
        );

        if (rows.length === 0) {
            throw new Error('订单不存在');
        }

        const { recipient, amount } = rows[0];

        // 更新订单信息
        await pool.query(
            'UPDATE sponsors SET username = ? WHERE order_id = ?',
            [safeUsername, order_id]
        );

        // BSC赞助使用特定的爱发电链接
        if (recipient.toLowerCase() === 'bsc') {
            const afdianUrl = `https://afdian.com/order/create?user_id=4c407a94d64511ecb69652540025c377&remark=&month=1&custom_price=${amount}&custom_order_id=${order_id}`;
            return res.redirect(afdianUrl);
        }
        if (recipient.toLowerCase() === 'bus') {
            const afdianUrl = `https://afdian.com/order/create?user_id=4c407a94d64511ecb69652540025c37&remark=&month=1&custom_price=${amount}&custom_order_id=${order_id}`;
            return res.redirect(afdianUrl);
        }
        if (recipient.toLowerCase() === 'cdpyx') {
            const afdianUrl = `https://afdian.com/order/create?user_id=a200c604600311ecb10e52540025c377&remark=&month=1&custom_price=${amount}&custom_order_id=${order_id}`;
            return res.redirect(afdianUrl);
        }

        // 其他赞助对象
        res.json({
            success: true,
            message: '登录成功'
        });
    } catch (error) {
        console.error('OAuth Error:', error.response?.data || error.message);
        res.status(500).json({
            success: false,
            message: '处理OAuth回调时出错',
            error: error.response?.data || error.message
        });
    }
});

// 爱发电 webhook 处理
app.post('/afdian/webhook', async (req, res) => {
    try {
        console.log('收到爱发电回调:', req.body);
        const { ec, data } = req.body;
        
        // 验证请求是否成功
        if (ec !== 200) {
            console.error('爱发电回调错误:', ec);
            return res.json({ ec: 200, em: 'ok' });
        }

        // 处理订单信息
        const order = data.order;
        if (!order) {
            console.error('订单信息为空');
            return res.json({ ec: 200, em: 'ok' });
        }

        // 获取自定义订单号
        const customOrderId = order.custom_order_id;
        console.log('处理订单:', customOrderId);
        
        // 检查订单状态
        if (order.status === 2) { // 2 表示支付成功
            try {
                // 先检查订单是否存在
                const [checkResult] = await pool.query(
                    'SELECT id, status FROM sponsors WHERE order_id = ?',
                    [customOrderId]
                );

                if (checkResult.length === 0) {
                    console.error('订单不存在:', customOrderId);
                    return res.json({ ec: 200, em: 'ok' });
                }

                // 更新订单状态
                const [result] = await pool.query(
                    'UPDATE sponsors SET status = ? WHERE order_id = ?',
                    ['completed', customOrderId]
                );

                if (result.affectedRows > 0) {
                    console.log('赞助订单处理成功:', {
                        order_id: customOrderId,
                        amount: order.total_amount
                    });
                } else {
                    console.log('订单状态未更新:', customOrderId);
                }
            } catch (dbError) {
                console.error('数据库更新失败:', dbError);
                if (dbError.sqlMessage) {
                    console.error('SQL错误:', dbError.sqlMessage);
                }
            }
        } else {
            console.log('订单状态不是支付成功:', order.status);
        }

        // 返回成功响应
        res.json({ ec: 200, em: 'ok' });
    } catch (error) {
        console.error('Webhook Error:', error);
        res.json({ ec: 200, em: 'ok' }); // 即使处理失败也返回成功，避免爱发电重试
    }
});

// 启动服务器
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`服务器运行在 http://localhost:${PORT}`);
}); 