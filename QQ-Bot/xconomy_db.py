"""XConomy数据库模块 - 查询玩家交易记录和余额

此文件支持通过环境变量覆盖表名：
- `XCONOMY_TABLE` 默认为 `xconomy`
- `XCONOMY_RECORD_TABLE` 默认为 `xconomyrecord`
"""
import logging
import os
import pymysql
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# MySQL配置（可根据需要从环境或配置文件加载）
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "172.17.0.1"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "xconomy"),
    "password": os.getenv("MYSQL_PASSWORD", "Xconomy@Sparkpixel.1128"),
    "database": os.getenv("MYSQL_DATABASE", "global_xconomy"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# 表名支持通过环境变量覆盖，便于不同环境/前缀的兼容
XCONOMY_TABLE = os.getenv("XCONOMY_TABLE", "xconomy")
XCONOMY_RECORD_TABLE = os.getenv("XCONOMY_RECORD_TABLE", "xconomyrecord")


@contextmanager
def get_connection():
    """获取数据库连接（上下文管理器）"""
    conn = None
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        yield conn
    except pymysql.Error as e:
        logger.error(f"数据库连接错误: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_player_balance(player_name: str) -> Optional[Dict[str, Any]]:
    """
    查询玩家余额
    Returns:
        dict or None
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                sql = f"SELECT player, balance FROM `{XCONOMY_TABLE}` WHERE player = %s"
                cursor.execute(sql, (player_name,))
                result = cursor.fetchone()

                if not result:
                    return None

                # 结果使用 DictCursor，优先用 dict 获取
                if isinstance(result, dict):
                    player = result.get("player")
                    balance = float(result.get("balance") or 0.0)
                else:
                    player = result[0]
                    balance = float(result[1] or 0.0)

                # XConomy 默认没有 bank_balance 字段，保持兼容性返回 0.0
                return {"player": player, "balance": balance, "bank_balance": 0.0}
    except Exception as e:
        logger.exception("查询玩家余额失败")
        return None


def get_player_transaction_count(player_name: str) -> int:
    """查询玩家交易记录总数"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                sql = f"SELECT COUNT(*) AS cnt FROM `{XCONOMY_RECORD_TABLE}` WHERE player = %s"
                cursor.execute(sql, (player_name,))
                result = cursor.fetchone()
                if isinstance(result, dict):
                    return int(result.get("cnt") or 0)
                return int(result[0] or 0)
    except Exception as e:
        logger.exception("查询交易记录总数失败")
        return 0


def get_player_transactions(player_name: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """
    查询玩家交易记录，返回最近的记录（按 id DESC）
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT id, type, uid, player, balance, amount, operation, command, comment, datetime
                    FROM `{XCONOMY_RECORD_TABLE}`
                    WHERE player = %s
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (player_name, limit, offset))
                rows = cursor.fetchall()

                transactions: List[Dict[str, Any]] = []
                for r in rows:
                    if isinstance(r, dict):
                        ttype = r.get("type")
                        amount = float(r.get("amount") or 0)
                        balance = float(r.get("balance") or 0)
                        target = r.get("player") or ""
                        dt = str(r.get("datetime") or "")
                        comment = r.get("comment") or ""
                        operation = r.get("operation") or ""
                        command = r.get("command") or ""
                    else:
                        # tuple ordering: id, type, uid, player, balance, amount, operation, command, comment, datetime
                        ttype = r[1]
                        balance = float(r[4] or 0)
                        amount = float(r[5] or 0)
                        target = r[3] or ""
                        operation = r[6] or ""
                        command = r[7] or ""
                        comment = r[8] or ""
                        dt = str(r[9] or "")

                    # comment 字段存储交易对方玩家名，N/A 表示无对方
                    if comment and comment != "N/A":
                        target = comment
                    else:
                        target = ""

                    transactions.append({
                        "type": ttype,
                        "amount": amount,
                        "balance": balance,
                        "target": target,
                        "operation": operation,
                        "command": command,
                        "comment": comment,
                        "datetime": dt,
                    })

                return transactions
    except Exception as e:
        logger.exception("查询交易记录失败")
        return []


def get_player_transactions_page(player_name: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    分页查询玩家交易记录，返回数据+分页信息
    """
    total = get_player_transaction_count(player_name)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    transactions = get_player_transactions(player_name, limit=page_size, offset=offset)
    return {
        "player": player_name,
        "transactions": transactions,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


def get_transaction_summary(player_name: str) -> Optional[Dict[str, Any]]:
    """
    按类型汇总交易统计
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                sql = f"""
                    SELECT operation, COUNT(*) AS count, SUM(amount) AS total_amount
                    FROM `{XCONOMY_RECORD_TABLE}`
                    WHERE player = %s
                    GROUP BY operation
                """
                cursor.execute(sql, (player_name,))
                rows = cursor.fetchall()

                summary = {
                    "player": player_name,
                }
                for r in rows:
                    if isinstance(r, dict):
                        op = r.get("operation")
                        cnt = int(r.get("count") or 0)
                        total = float(r.get("total_amount") or 0)
                    else:
                        op = r[0]
                        cnt = int(r[1] or 0)
                        total = float(r[2] or 0)
                    summary[op] = {"count": cnt, "total": total}

                return summary
    except Exception as e:
        logger.exception("查询交易统计失败")
        return None


def format_balance_message(player_name: str) -> str:
    balance = get_player_balance(player_name)
    if not balance:
        return f"❌ 未找到玩家 {player_name} 的账户信息"
    cash = balance.get("balance", 0.0)
    bank = balance.get("bank_balance", 0.0)
    msg = f"💰 {player_name} 的账户信息\n"
    msg += f"├ 现金: {cash:,.2f}\n"
    msg += f"└ 银行: {bank:,.2f}\n"
    msg += f"总计: {cash + bank:,.2f}"
    return msg


def format_transactions_message(player_name: str, page: int = 1, page_size: int = 20) -> str:
    offset = (page - 1) * page_size
    transactions = get_player_transactions(player_name, limit=page_size, offset=offset)
    total = get_player_transaction_count(player_name)
    total_pages = max(1, (total + page_size - 1) // page_size)
    if not transactions:
        return f"📋 {player_name} 暂无交易记录"
    msg = f"📋 {player_name} 交易记录 (第{page}/{total_pages}页 共{total}条)\n"
    msg += "─" * 30 + "\n"
    op_icons = {"DEPOSIT": "📥", "WITHDRAW": "📤"}
    for t in transactions:
        op = (t.get("operation") or "").upper()
        icon = op_icons.get(op, "💱")
        amount = t.get('amount', 0)
        if op == "WITHDRAW":
            amount = -amount
        target = f" → {t.get('target')}" if t.get('target') else ""
        balance = f" 余额:{t.get('balance'):,.2f}" if t.get('balance') else ""
        dt = t.get('datetime', '')
        if dt and len(dt) > 5:
            dt_short = dt[5:16]  # MM-DD HH:MM
        else:
            dt_short = dt
        msg += f"{icon} {amount:+,.2f}{target}{balance} {dt_short}\n"
    return msg.strip()


def test_connection() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
    except Exception:
        return False
