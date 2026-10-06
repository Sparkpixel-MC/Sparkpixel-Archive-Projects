"""服务器监控模块 - 监控 MCSM 服务器状态和玩家数量（仅 status 协议，含玩家列表显示）"""
import asyncio
import json
import os
import logging
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional

from mcstatus import JavaServer

from api_client import get_server_status, get_server_players
from config import (
    UUIDS,
    SERVER_PORTS,
    HOST_IP,
    UPDATE_INTERVAL,
    MAX_PLAYERS_FILE,
    PLAYERS_FILE
)

logger = logging.getLogger(__name__)


class ServerMonitor:
    """服务器监控管理器 - 统一缓存和管理所有服务器数据"""

    def __init__(
        self,
        uuids: Dict[str, str],
        port_map: Dict[str, int],
        host_ip: str = "172.17.0.1",
        cache_ttl: float = 10.0
    ) -> None:
        self._uuids: Dict[str, str] = uuids
        self._port_map: Dict[str, int] = port_map
        self._host_ip: str = host_ip
        self._cache_ttl: float = cache_ttl
        
        self._cache_timestamp: float = 0.0
        self._server_data: Dict[str, Dict[str, Any]] = {}
        self._total_players: int = 0
        self._status_lines: List[str] = []
        self._is_cache_valid: bool = False
        
        self._last_error: Optional[str] = None
        self._fetch_in_progress: bool = False

    def _is_cache_expired(self) -> bool:
        if not self._is_cache_valid:
            return True
        return (time.time() - self._cache_timestamp) > self._cache_ttl

    async def _fetch_player_list(self, port: int, timeout: float = 5.0) -> tuple:
        """
        使用 mcstatus status 协议获取玩家列表（原生异步 API）

        Returns:
            tuple: (玩家名称列表，是否完整)
        """
        try:
            server = JavaServer.lookup(f"{self._host_ip}:{port}")

            status_result = await asyncio.wait_for(
                server.async_status(),
                timeout=timeout
            )

            # 安全访问 players 属性
            players_info = getattr(status_result, 'players', None)

            if players_info is None:
                return [], True

            # 获取在线人数
            online_count = getattr(players_info, 'online', 0) or 0

            # 获取玩家样本列表
            sample = getattr(players_info, 'sample', None)

            if sample and len(sample) > 0:
                player_names = sorted([player.name for player in sample if hasattr(player, 'name')])
                sample_count = len(player_names)
                # 样本数 >= 在在线数 或 样本数 < 20 时认为完整
                is_complete = (sample_count >= online_count) or (sample_count < 20)
                logger.debug(f"📋 {self._host_ip}:{port} 获取到 {sample_count}/{online_count} 玩家")
                return player_names, is_complete
            elif online_count > 0:
                logger.debug(f"🔍 {self._host_ip}:{port} 有 {online_count} 名玩家，但列表被隐藏")
                return [], False
            else:
                return [], True

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ 获取 {self._host_ip}:{port} 玩家列表超时")
        except ConnectionError as e:
            logger.warning(f"🔌 {self._host_ip}:{port} 连接失败: {e}")
        except Exception as e:
            logger.debug(f"🔍 获取 {self._host_ip}:{port} 玩家列表异常：{type(e).__name__}: {e}")

        return [], False

    async def _fetch_all_data(self) -> bool:
        """执行单次循环获取所有服务器数据"""
        if self._fetch_in_progress:
            logger.debug("⏳ 数据获取任务已在进行中，跳过重复请求")
            return False
        
        self._fetch_in_progress = True
        try:
            temp_total = 0
            temp_lines: List[str] = []
            temp_server_data: Dict[str, Dict[str, Any]] = {}
            
            for uuid, server_name in self._uuids.items():
                try:
                    status_task = get_server_status(uuid)
                    players_task = get_server_players(uuid)
                    
                    status_result, player_count = await asyncio.gather(
                        status_task, players_task, return_exceptions=True
                    )
                    
                    if isinstance(status_result, Exception):
                        logger.warning(f"⚠️ {server_name} 状态获取异常：{status_result}")
                        status_result = {'success': False, 'status': '连接异常'}
                    if isinstance(players_task, Exception):
                        logger.warning(f"⚠️ {server_name} 玩家数获取异常：{players_task}")
                        player_count = 0
                    
                    # 获取玩家列表（仅当有玩家在线时）
                    player_list: List[str] = []
                    is_list_complete = True
                    if player_count > 0:
                        port = self._port_map.get(uuid, 25565)
                        player_list, is_list_complete = await self._fetch_player_list(port)
                    
                    temp_server_data[uuid] = {
                        'name': server_name,
                        'status_result': status_result,
                        'player_count': player_count,
                        'player_list': player_list,
                        'player_list_complete': is_list_complete,
                        'success': status_result.get('success', False)
                    }
                    
                    temp_total += player_count
                    
                    # 构建状态显示行
                    if status_result.get('success'):
                        display_players = status_result.get('players', player_count)
                        line = f"🎮 {server_name}: {status_result['status']} 👥 {display_players}人"
                        
                        if player_list:
                            players_str = ", ".join(player_list[:10])
                            line += f"\n   👤 玩家：{players_str}"
                            if len(player_list) > 10:
                                line += f" ...(+{len(player_list) - 10})"
                            if not is_list_complete:
                                line += " ⚠️(列表可能不完整)"
                        elif player_count > 0 and not is_list_complete:
                            line += "\n   ⚠️ 玩家列表被服务器隐藏或未返回样本"
                            
                        temp_lines.append(line)
                    else:
                        temp_lines.append(f"❌ {server_name}: {status_result['status']}")
                        
                except Exception as e:
                    logger.error(f"❌ 处理服务器 {server_name}({uuid}) 时发生错误：{e}")
                    temp_lines.append(f"❌ {server_name}: 数据获取失败")
                    continue
            
            # 批量更新缓存
            self._server_data = temp_server_data
            self._total_players = temp_total
            self._status_lines = temp_lines
            self._cache_timestamp = time.time()
            self._is_cache_valid = True
            self._last_error = None
            
            logger.debug(f"✅ 缓存已更新 | 服务器：{len(self._uuids)} | 总玩家：{temp_total}")
            return True
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"❌ 缓存更新失败：{e}")
            return False
        finally:
            self._fetch_in_progress = False

    async def _ensure_cache_valid(self) -> bool:
        if self._is_cache_expired():
            return await self._fetch_all_data()
        return True

    async def get_total_players(self) -> int:
        await self._ensure_cache_valid()
        return self._total_players

    async def get_server_info(self) -> str:
        await self._ensure_cache_valid()
        output_lines = self._status_lines.copy()
        output_lines.append(f"\n📊 服务器总在线：{self._total_players}人")
        if self._last_error:
            output_lines.append(f"⚠️ 注意：{self._last_error}")
        return "\n".join(output_lines)

    async def get_detailed_server_info(self) -> str:
        await self._ensure_cache_valid()
        lines = []
        for uuid, data in self._server_data.items():
            if not data['success']:
                continue
            name = data['name']
            count = data['player_count']
            players = data.get('player_list', [])
            is_complete = data.get('player_list_complete', True)
            
            if count > 0:
                lines.append(f"🎮 {name} ({count}人):")
                if players:
                    for i in range(0, len(players), 4):
                        chunk = players[i:i+4]
                        lines.append("   👤 " + ", ".join(chunk))
                    if not is_complete:
                        lines.append("   ⚠️ 提示：玩家列表可能不完整（status 协议限制）")
                else:
                    lines.append("   ⚠️ 玩家列表被服务器隐藏或未返回样本")
            else:
                lines.append(f"🎮 {name}: 🟢 空闲")
        lines.append(f"\n📊 服务器总在线：{self._total_players}人")
        return "\n".join(lines)

    async def get_current_total_for_monitoring(self) -> int:
        await self._fetch_all_data()
        return self._total_players

    def get_raw_server_data(self) -> Dict[str, Dict[str, Any]]:
        return self._server_data.copy()

    def invalidate_cache(self) -> None:
        self._is_cache_valid = False
        logger.debug("🔄 缓存已手动失效")


# ===== 全局单例 =====
_monitor_instance: Optional[ServerMonitor] = None

def get_monitor() -> ServerMonitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ServerMonitor(
            uuids=UUIDS,
            port_map=SERVER_PORTS,
            host_ip=HOST_IP,
            cache_ttl=float(UPDATE_INTERVAL)
        )
        logger.info(f"🔧 ServerMonitor 已初始化 | TTL: {UPDATE_INTERVAL}s | IP: {HOST_IP}")
    return _monitor_instance

async def get_total_players() -> int:
    return await get_monitor().get_total_players()

async def get_server_info() -> str:
    return await get_monitor().get_server_info()

async def get_detailed_server_info() -> str:
    return await get_monitor().get_detailed_server_info()


# ===== 历史记录功能 =====

def init_max_players_file():
    files_to_init = [
        (MAX_PLAYERS_FILE, "历史记录文件"),
        (PLAYERS_FILE, "玩家数据文件")
    ]
    for file_path, file_desc in files_to_init:
        if not os.path.exists(file_path):
            init_data = {}
            for i in range(7):
                d = (date.today() - timedelta(days=i)).isoformat()
                init_data[d] = 0
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(init_data, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ 已创建{file_desc}: {file_path}")
            except Exception as e:
                logger.error(f"❌ 创建{file_desc}失败 {file_path}: {e}")

async def background_update_max_players():
    logger.info(f"🚀 后台监控任务已启动 (间隔：{UPDATE_INTERVAL}秒)")
    monitor = get_monitor()
    while True:
        try:
            today = date.today().isoformat()
            current_total = await monitor.get_current_total_for_monitoring()
            
            # ===== 新增：每次轮询都记录到数据库 =====
            try:
                from database import save_player_history
                server_data = monitor.get_raw_server_data()
                # 简化服务器数据用于存储
                simplified_data = {}
                for uuid, data in server_data.items():
                    simplified_data[uuid] = {
                        'name': data.get('name', ''),
                        'player_count': data.get('player_count', 0),
                        'success': data.get('success', False)
                    }
                save_player_history(current_total, simplified_data)
            except Exception as e:
                logger.error(f"❌ 保存玩家历史记录失败：{e}")
            # ===== 结束新增 =====
            
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
                logger.error(f"❌ 读取历史文件失败：{e}")
                history = {today: 0}
            
            current_max = history.get(today, 0)
            if current_total > current_max:
                history[today] = current_total
                try:
                    temp_file = MAX_PLAYERS_FILE + ".tmp"
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(history, f, ensure_ascii=False, indent=2)
                    os.replace(temp_file, MAX_PLAYERS_FILE)
                    logger.info(f"📈 {today} 最高在线：{current_max} → {current_total}人")
                except Exception as e:
                    logger.error(f"❌ 写入历史文件失败：{e}")
            else:
                logger.debug(f"📊 {today} 当前：{current_total} | 历史最高：{current_max} (无需更新)")
                
        except asyncio.CancelledError:
            logger.info("🛑 后台监控任务已取消")
            break
        except Exception as e:
            logger.error(f"⚠️ 后台任务异常：{type(e).__name__}: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)

def get_max_players_for_date(query_date: str) -> tuple:
    try:
        query_dt = datetime.strptime(query_date, "%Y-%m-%d").date()
    except ValueError:
        current_date = date.today()
        raise ValueError(f"日期格式错误！正确格式：YYYY-MM-DD（例如：{current_date}）")
    if not os.path.exists(MAX_PLAYERS_FILE):
        raise FileNotFoundError("历史记录文件不存在，请等待首次数据采集（约 10 秒后）")
    with open(MAX_PLAYERS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)
    if query_dt > date.today():
        raise ValueError("无法查询未来日期的数据")
    if query_date not in history:
        earliest = min(history.keys()) if history else "未知"
        raise KeyError(f"未找到 {query_date} 的记录（最早记录：{earliest}）")
    count = history[query_date]
    if count == 0:
        desc = "（当日无玩家上线）"
    elif count < 5:
        desc = "（服务器较为空闲）"
    elif count < 15:
        desc = "（正常活跃）"
    else:
        desc = "（高峰日期）"
    return True, f"{query_date} 服务器最高同时在线：{count}人 {desc}"