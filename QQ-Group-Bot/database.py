"""数据库管理模块"""
import sqlite3
import logging

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