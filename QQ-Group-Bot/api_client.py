"""API客户端模块 - 处理与MCSM服务器的通信"""
import aiohttp
import ssl
import asyncio
import logging
from config import MCSM_URL, MCSM_APIKEY, DAEMON_ID, MAX_RETRIES, BASE_DELAY, MAX_DELAY, UUIDS, STATUS_MAP

logger = logging.getLogger(__name__)

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

SERVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Referer": f"{MCSM_URL}/",
    "Origin": MCSM_URL,
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "DNT": "1"
}

async def get_server_status(uuid: str) -> dict:
    """获取单个服务器的状态"""
    async with aiohttp.ClientSession() as session:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                url = (
                    f"{MCSM_URL}/api/instance?"
                    f"daemonId={DAEMON_ID}&page=1&page_size=50"
                    f"&apikey={MCSM_APIKEY}&uuid={uuid}"
                )
                
                async with session.get(
                    url, 
                    timeout=aiohttp.ClientTimeout(total=5), 
                    ssl=ssl_context, 
                    headers=SERVER_HEADERS
                ) as response:
                    if response.status == 200:
                        obj = await response.json()
                        status_code = str(obj.get('data', {}).get('status', ''))
                        info = obj.get('data', {}).get('info', {})
                        players = info.get('currentPlayers', 0)
                        return {
                            'success': True,
                            'status': STATUS_MAP.get(status_code, "❓ 未知"),
                            'players': players
                        }
                    else:
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"HTTP {response.status}"
                        )
                
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as e:
                if attempt == MAX_RETRIES:
                    logger.warning(
                        f"服务器 {uuid} 重试{MAX_RETRIES}次后仍失败: "
                        f"{type(e).__name__}: {str(e)[:100]}"
                    )
                    return {'success': False, 'status': '连接失败', 'players': 0}
                
                delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
                logger.debug(
                    f"服务器 {uuid} 第{attempt}次请求失败 ({type(e).__name__})，"
                    f"{delay:.1f}秒后重试..."
                )
                await asyncio.sleep(delay)
            
            except Exception as e:
                logger.error(
                    f"服务器 {uuid} 发生未预期异常: {type(e).__name__}: {e}", 
                    exc_info=True
                )
                return {'success': False, 'status': '异常', 'players': 0}
    
    return {'success': False, 'status': '连接失败', 'players': 0}

async def get_server_players(uuid: str) -> int:
    """获取单个服务器的玩家数"""
    async with aiohttp.ClientSession() as session:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                url = (
                    f"{MCSM_URL}/api/instance?"
                    f"daemonId={DAEMON_ID}&page=1&page_size=50"
                    f"&apikey={MCSM_APIKEY}&uuid={uuid}"
                )
                
                async with session.get(
                    url, 
                    timeout=aiohttp.ClientTimeout(total=5), 
                    ssl=ssl_context, 
                    headers=SERVER_HEADERS
                ) as response:
                    if response.status != 200:
                        raise aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"HTTP {response.status}"
                        )
                    
                    data = await response.json()
                    players = data.get('data', {}).get('info', {}).get('currentPlayers', 0)
                    if not isinstance(players, int):
                        raise ValueError(f"Invalid player count type: {type(players)}")
                    
                    return players
                
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as e:
                if attempt == MAX_RETRIES:
                    logger.warning(
                        f"服务器 {uuid} 重试{MAX_RETRIES}次后仍失败: {type(e).__name__}: {str(e)[:100]}"
                    )
                    return 0
                
                delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
                logger.debug(
                    f"服务器 {uuid} 第{attempt}次请求失败 ({type(e).__name__})，"
                    f"{delay:.1f}秒后重试..."
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"服务器 {uuid} 发生未预期异常（跳过）: {type(e).__name__}: {e}", exc_info=True)
                return 0

    return 0