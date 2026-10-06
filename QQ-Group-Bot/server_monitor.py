"""服务器监控模块 - 监控MCSM服务器状态和玩家数量"""
import asyncio
import json
import os
import logging
from datetime import date, datetime, timedelta
from api_client import get_server_status, get_server_players
from config import MAX_PLAYERS_FILE, UPDATE_INTERVAL, UUIDS

logger = logging.getLogger(__name__)

def init_max_players_file():
    """初始化历史记录文件"""
    if not os.path.exists(MAX_PLAYERS_FILE):
        init_data = {}
        for i in range(7):
            d = (date.today() - timedelta(days=i)).isoformat()
            init_data[d] = 0
        with open(MAX_PLAYERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(init_data, f, ensure_ascii=False, indent=2)
        logger.info("✅ 已创建历史记录文件模板")

async def get_total_players() -> int:
    """获取所有服务器当前玩家总数"""
    total = 0
    for uuid in UUIDS.keys():
        players = await get_server_players(uuid)
        total += players
    return total

async def get_server_info() -> str:
    """获取所有服务器的状态信息"""
    status_lines = []
    
    for uuid, server_name in UUIDS.items():
        result = await get_server_status(uuid)
        if result['success']:
            status_lines.append(f"🎮 {server_name}: {result['status']} 👥 {result['players']}人")
        else:
            status_lines.append(f"❌ {server_name}: {result['status']}")
    
    total_players = await get_total_players()
    status_lines.append(f"服务器总在线: {total_players}人")
    
    return "\n".join(status_lines)

async def background_update_max_players():
    """每UPDATE_INTERVAL秒更新当日最高在线人数记录"""
    logger.info(f"后台监控任务已启动 (间隔: {UPDATE_INTERVAL}秒)")
    while True:
        try:
            today = date.today().isoformat()
            
            # 读取历史数据
            try:
                if os.path.exists(MAX_PLAYERS_FILE):
                    with open(MAX_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                else:
                    history = {}
                    for i in range(7):
                        d = (date.today() - timedelta(days=i)).isoformat()
                        history[d] = 0
            except Exception as e:
                logger.error(f"❌ 读取历史文件失败: {e}")
                history = {today: 0}
            
            # 获取当前总玩家数
            current_total = await get_total_players()
            current_max = history.get(today, 0)
            
            # 更新当日最高记录
            if current_total > current_max:
                history[today] = current_total
                try:
                    temp_file = MAX_PLAYERS_FILE + ".tmp"
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(history, f, ensure_ascii=False, indent=2)
                    os.replace(temp_file, MAX_PLAYERS_FILE)
                    logger.info(f"📈 {today} 最高在线更新: {current_max} → {current_total}人")
                except Exception as e:
                    logger.error(f"❌ 写入历史文件失败: {e}")
            
        except asyncio.CancelledError:
            logger.info("🛑 后台监控任务已取消")
            break
        except Exception as e:
            logger.error(f"⚠️ 后台任务异常: {e}")
        
        await asyncio.sleep(UPDATE_INTERVAL)

def get_max_players_for_date(query_date: str) -> tuple:
    """查询指定日期的最高在线人数"""
    try:
        query_dt = datetime.strptime(query_date, "%Y-%m-%d").date()
    except ValueError:
        current_date = date.today()
        raise ValueError(f"日期格式错误！正确格式: YYYY-MM-DD（例如: {current_date})")

    if not os.path.exists(MAX_PLAYERS_FILE):
        raise FileNotFoundError("历史记录文件不存在，请等待首次数据采集（约10秒后）")

    with open(MAX_PLAYERS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    if query_dt > date.today():
        raise ValueError("无法查询未来日期的数据")

    if query_date not in history:
        earliest = min(history.keys()) if history else "未知"
        raise KeyError(f"未找到 {query_date} 的记录（最早记录: {earliest}）")

    count = history[query_date]
    if count == 0:
        desc = "（当日无玩家上线）"
    elif count < 3:
        desc = "（服务器较为空闲）"
    elif count < 6:
        desc = "（正常活跃）"
    else:
        desc = "（高峰日期）"
    
    return True, f"{query_date} 服务器最高同时在线: {count}人 {desc}"