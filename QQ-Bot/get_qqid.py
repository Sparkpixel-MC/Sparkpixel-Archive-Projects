"""数据库管理模块"""
import json
import sqlite3
import logging
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


def get_eid(qq_id: str) -> str:
    """获取指定qq号的eid"""
    conn = None
    try:
        conn = sqlite3.connect('EasyBot.db')
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM SocialAccount WHERE Uuid = ?', (qq_id,))

        result = cursor.fetchone()

        return result[0] if result else None
    except Exception as e:
        logger.error(f"查询eid失败: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_gamenick(qq_id: str) -> str:
    """获取指定qq号的游戏昵称"""
    conn = None
    try:
        eid = get_eid(qq_id)
        if not eid:
            return None
        conn = sqlite3.connect('EasyBot.db')
        cursor = conn.cursor()

        cursor.execute('SELECT Name FROM Player WHERE SocialAccountId = ?', (eid,))

        result = cursor.fetchone()

        return result[0] if result else None
    except Exception as e:
        logger.error(f"查询游戏昵称失败: {e}")
        return None
    finally:
        if conn:
            conn.close()