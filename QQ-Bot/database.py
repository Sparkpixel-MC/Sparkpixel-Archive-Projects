"""数据库管理模块"""
import json
import sqlite3
import logging
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

def init_database():
    """初始化数据库表"""
    conn = sqlite3.connect('Data.db')
    c = conn.cursor()
    
    # 撤回记录表
    c.execute('''CREATE TABLE IF NOT EXISTS recall
                 (ID TEXT PRIMARY KEY, op TEXT, qq TEXT, reason TEXT, date INTEGER)''')
    
    # 禁言记录表
    c.execute('''CREATE TABLE IF NOT EXISTS group_ban
                 (ID TEXT PRIMARY KEY, op TEXT, qq TEXT, times INTEGER, date INTEGER, reason TEXT)''')
    
    # 群消息记录表
    c.execute('''CREATE TABLE IF NOT EXISTS group_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  group_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  message_id INTEGER,
                  raw_message TEXT,
                  message_type TEXT,
                  timestamp INTEGER,
                  date TEXT)''')
    
    # 玩家历史记录表
    c.execute('''CREATE TABLE IF NOT EXISTS player_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp INTEGER NOT NULL,
                  date TEXT NOT NULL,
                  hour INTEGER NOT NULL,
                  total_players INTEGER DEFAULT 0,
                  server_data TEXT)''')
    
    # 创建索引
    c.execute('''CREATE INDEX IF NOT EXISTS idx_player_history_timestamp
                 ON player_history(timestamp)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_player_history_date
                 ON player_history(date)''')

    # 免责声明同意记录表
    c.execute('''CREATE TABLE IF NOT EXISTS disclaimer_agreement
                 (user_id TEXT PRIMARY KEY,
                  agreed_at INTEGER NOT NULL,
                  agreed_date TEXT NOT NULL)''')

    conn.commit()
    conn.close()
    logger.info("✅ 数据库初始化完成")

def save_message(group_id: str, user_id: str, message_id: int, raw_message: str, message_type: str, timestamp: int, date: str):
    """保存群消息到数据库"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO group_messages (group_id, user_id, message_id, raw_message, message_type, timestamp, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (group_id, user_id, message_id, raw_message, message_type, timestamp, date))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"消息记录保存失败: {e}")

def save_recall_record(msg_id: str, operator: str, target: str, time: int):
    """保存撤回记录"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO recall (ID, op, qq, reason, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (msg_id, operator, target, '', time))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"撤回记录写入失败: {e}")

def save_ban_record(ban_id: str, operator: str, target: str, duration: int, time: int):
    """保存禁言记录"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO group_ban (ID, op, qq, times, date, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ban_id, operator, target, duration, time, ''))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"禁言记录写入失败: {e}")

def update_recall_reason(msg_id: str, reason: str) -> bool:
    """更新撤回理由"""
    try:
        conn = sqlite3.connect('Data.db')
        c = conn.cursor()
        c.execute('SELECT op FROM recall WHERE ID = ?', (msg_id,))
        op_value = c.fetchone()
        conn.close()
        return op_value is not None
    except Exception as e:
        logger.error(f"查询撤回记录失败: {e}")
        return False

def execute_update_recall(msg_id: str, reason: str):
    """执行撤回理由更新"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE recall SET reason = ? WHERE ID = ?', (reason, msg_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"更新撤回记录失败: {e}")

def get_recall_operator(msg_id: str) -> str:
    """获取撤回记录的操作人"""
    try:
        conn = sqlite3.connect('Data.db')
        c = conn.cursor()
        c.execute('SELECT op FROM recall WHERE ID = ?', (msg_id,))
        op_value = c.fetchone()
        conn.close()
        return str(op_value[0]) if op_value else ""
    except Exception as e:
        logger.error(f"查询撤回记录失败: {e}")
        return ""

def update_ban_reason(ban_id: str, reason: str):
    """更新禁言理由"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE group_ban SET reason = ? WHERE ID = ?', (reason, ban_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"更新禁言记录失败: {e}")

def get_ban_operator(ban_id: str) -> str:
    """获取禁言记录的操作人"""
    try:
        conn = sqlite3.connect('Data.db')
        c = conn.cursor()
        c.execute('SELECT op FROM group_ban WHERE ID = ?', (ban_id,))
        op_value = c.fetchone()
        conn.close()
        return str(op_value[0]) if op_value else ""
    except Exception as e:
        logger.error(f"查询禁言记录失败: {e}")
        return ""


# ===== 免责声明同意功能 =====

def has_agreed_disclaimer(user_id: str) -> bool:
    """检查用户是否已同意免责声明"""
    try:
        conn = sqlite3.connect('Data.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM disclaimer_agreement WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"查询免责声明状态失败: {e}")
        return False


def save_disclaimer_agreement(user_id: str) -> bool:
    """保存用户免责声明同意记录"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT OR REPLACE INTO disclaimer_agreement (user_id, agreed_at, agreed_date)
            VALUES (?, ?, ?)
        ''', (user_id, current_time, current_date))
        conn.commit()
        conn.close()
        logger.info(f"✅ 用户 {user_id} 已同意免责声明")
        return True
    except Exception as e:
        logger.error(f"保存免责声明同意记录失败: {e}")
        return False


# ===== 玩家历史记录功能 =====

def init_player_history_table():
    """初始化玩家历史记录表"""
    conn = sqlite3.connect('Data.db')
    c = conn.cursor()
    
    # 玩家历史记录表 - 记录每次轮询的数据
    c.execute('''CREATE TABLE IF NOT EXISTS player_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp INTEGER NOT NULL,
                  date TEXT NOT NULL,
                  hour INTEGER NOT NULL,
                  total_players INTEGER DEFAULT 0,
                  server_data TEXT)''')
    
    # 创建索引加速查询
    c.execute('''CREATE INDEX IF NOT EXISTS idx_player_history_timestamp 
                 ON player_history(timestamp)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_player_history_date 
                 ON player_history(date)''')
    
    conn.commit()
    conn.close()
    logger.info("✅ 玩家历史记录表初始化完成")


def save_player_history(total_players: int, server_data: dict = None):
    """保存玩家历史记录（每次轮询都记录）"""
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d')
        current_hour = datetime.fromtimestamp(current_time).hour
        
        server_data_json = json.dumps(server_data, ensure_ascii=False) if server_data else '{}'
        
        cursor.execute('''
            INSERT INTO player_history (timestamp, date, hour, total_players, server_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (current_time, current_date, current_hour, total_players, server_data_json))
        
        conn.commit()
        conn.close()
        logger.debug(f"📊 玩家历史记录已保存: {current_date} {current_hour}时 - {total_players}人")
    except Exception as e:
        logger.error(f"玩家历史记录保存失败: {e}")


def get_player_history(hours: int = 24) -> list:
    """
    获取指定小时内的玩家历史记录
    
    Args:
        hours: 查询的小时数，默认24小时
        
    Returns:
        list: 历史记录列表，每项包含 timestamp, total_players, date
    """
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        
        start_time = int(time.time()) - (hours * 3600)
        
        cursor.execute('''
            SELECT timestamp, total_players, date, server_data
            FROM player_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        ''', (start_time,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'timestamp': row[0],
                'player_count': row[1],
                'date': row[2],
                'server_data': json.loads(row[3]) if row[3] else {}
            })
        
        conn.close()
        return results
    except Exception as e:
        logger.error(f"获取玩家历史记录失败: {e}")
        return []


def get_player_history_by_date(start_date: str, end_date: str = None) -> list:
    """
    获取指定日期范围内的玩家历史记录
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)，默认为今天
        
    Returns:
        list: 历史记录列表
    """
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT timestamp, total_players, date, server_data
            FROM player_history
            WHERE date >= ? AND date <= ?
            ORDER BY timestamp ASC
        ''', (start_date, end_date))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'timestamp': row[0],
                'player_count': row[1],
                'date': row[2],
                'server_data': json.loads(row[3]) if row[3] else {}
            })
        
        conn.close()
        return results
    except Exception as e:
        logger.error(f"获取玩家历史记录失败: {e}")
        return []


def get_daily_max_players(days: int = 30) -> list:
    """
    获取最近N天每日最高在线人数
    
    Args:
        days: 查询天数
        
    Returns:
        list: 每日最高人数列表
    """
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT date, MAX(total_players) as max_players
            FROM player_history
            WHERE date >= ?
            GROUP BY date
            ORDER BY date ASC
        ''', (start_date,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'date': row[0],
                'max_players': row[1]
            })
        
        conn.close()
        return results
    except Exception as e:
        logger.error(f"获取每日最高人数失败: {e}")
        return []


def get_server_reliability_30d() -> dict:
    """
    获取最近30天每个服务器每天的可靠率（每小时采样一次）

    Returns:
        dict: {
            "server_name": {
                "dates": ["2026-05-01", ...],  # 30天日期列表
                "reliability": [95.0, 100.0, ...],  # 每天可靠率百分比
            }
        }
    """
    try:
        conn = sqlite3.connect('Data.db')
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        # 每小时采样一条记录（每小时第一条）
        cursor.execute('''
            SELECT date, hour, server_data
            FROM player_history
            WHERE date >= ?
            GROUP BY date, hour
            ORDER BY date ASC, hour ASC
        ''', (start_date,))

        rows = cursor.fetchall()
        conn.close()

        # 按服务器和日期聚合
        # {server_name: {date: [success_bool, ...]}}
        server_daily: dict = {}

        for date_str, hour, server_data_json in rows:
            if not server_data_json:
                continue
            try:
                server_data = json.loads(server_data_json)
            except Exception:
                continue

            for uuid, sdata in server_data.items():
                name = sdata.get('name', uuid)
                success = sdata.get('success', False)

                if name not in server_daily:
                    server_daily[name] = {}
                if date_str not in server_daily[name]:
                    server_daily[name][date_str] = []
                server_daily[name][date_str].append(success)

        # 生成最近30天的日期列表
        today = datetime.now().date()
        all_dates = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

        # 计算每天可靠率
        result = {}
        for name, daily_data in server_daily.items():
            reliabilities = []
            for d in all_dates:
                checks = daily_data.get(d, [])
                if checks:
                    rel = sum(1 for c in checks if c) / len(checks) * 100
                    reliabilities.append(round(rel, 1))
                else:
                    reliabilities.append(None)  # 无数据
            result[name] = {
                "dates": all_dates,
                "reliability": reliabilities,
            }

        return result

    except Exception as e:
        logger.error(f"获取服务器可靠率失败: {e}")
        return {}


