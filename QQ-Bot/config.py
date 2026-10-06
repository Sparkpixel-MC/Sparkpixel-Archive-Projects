"""配置管理模块 - 统一加载和管理全局配置"""
import json
import os
from typing import Dict, List, Any

def read_config(config_path: str = "environment.json") -> Dict[str, Any]:
    """
    安全读取并清理配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Dict[str, Any]: 清理后的配置字典
        
    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置文件格式错误或缺少必需字段
        RuntimeError: 其他加载错误
    """
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = json.load(f)
        
        # 清理关键字段的空白字符（URL、token等）
        cleaned_config = {}
        for key, value in raw_config.items():
            if isinstance(value, str):
                if key in ["mcsm_url", "base_url", "base_token", "mcsm_apikey", 
                          "ai_api_url", "ai_api_url2", "ai_api_url3", 
                          "ai_api_key", "ai_api_key2", "ai_api_key3",
                          "MCP_SERVER_URL", "HOST_IP"]:
                    cleaned_config[key] = value.strip()
                else:
                    cleaned_config[key] = value
            else:
                cleaned_config[key] = value
        
        # 验证必需字段
        required_fields = ["mcsm_url", "mcsm_apikey", "uuids", "group_id"]
        missing = [f for f in required_fields if f not in cleaned_config]
        if missing:
            raise ValueError(f"配置文件缺少必需字段: {', '.join(missing)}")
        
        # 确保 group_id 是字符串列表
        if not isinstance(cleaned_config["group_id"], list):
            cleaned_config["group_id"] = [str(cleaned_config["group_id"])]
        else:
            cleaned_config["group_id"] = [str(g) for g in cleaned_config["group_id"]]
        
        # 确保 uuids 是字典
        if not isinstance(cleaned_config["uuids"], dict):
            raise ValueError("uuids 配置必须是字典类型")
        
        # 确保 SERVER_PORTS 是字典（若存在）
        if "SERVER_PORTS" in cleaned_config:
            if not isinstance(cleaned_config["SERVER_PORTS"], dict):
                raise ValueError("SERVER_PORTS 配置必须是字典类型")
            # 确保端口值为整数
            cleaned_config["SERVER_PORTS"] = {
                k: int(v) if isinstance(v, (str, int)) else 25565 
                for k, v in cleaned_config["SERVER_PORTS"].items()
            }
        
        return cleaned_config
    
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误 ({config_path}): {str(e)}")
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"加载配置失败: {str(e)}")


# ===== 全局配置加载 =====
try:
    CONFIG = read_config()
except Exception as e:
    # 记录错误并退出，避免后续模块使用无效配置
    import logging
    logging.getLogger(__name__).critical(f"配置加载失败，程序终止: {e}")
    raise SystemExit(1)


# ===== 基础配置导出 =====
ENVIRONMENT: str = CONFIG.get("environment", "development")
DAEMON_ID: str = CONFIG.get("daemon_id", "")
AUTHORIZED_GROUPS: List[str] = CONFIG.get("group_id", [])
ADMIN_GROUP_ID: str = CONFIG.get("admin_group_id", AUTHORIZED_GROUPS[0] if AUTHORIZED_GROUPS else "")
FINANCE_BLOCKED_USERS: List[str] = [str(u) for u in CONFIG.get("finance_blocked_users", [])]
HEALTH_URL: str = CONFIG.get("health_url", "https://health.sparkpixel.top/")

# MCSM 面板配置
MCSM_URL: str = CONFIG["mcsm_url"].rstrip('/')
MCSM_APIKEY: str = CONFIG["mcsm_apikey"]

# 基础 API 配置
BASE_URL: str = CONFIG.get("base_url", "").rstrip('/')
BASE_TOKEN: str = CONFIG.get("base_token", "")

# 服务器映射配置
UUIDS: Dict[str, str] = CONFIG["uuids"]
SERVER_PORTS: Dict[str, int] = CONFIG.get("SERVER_PORTS", {})
HOST_IP: str = CONFIG.get("HOST_IP", "172.17.0.1")

# 监控任务配置
UPDATE_INTERVAL: int = CONFIG.get("UPDATE_INTERVAL", 10)
MAX_RETRIES: int = CONFIG.get("max_retries", 5)
BASE_DELAY: float = CONFIG.get("base_delay", 0.5)
MAX_DELAY: float = CONFIG.get("max_delay", 2.0)

# 数据文件路径
PLAYERS_FILE: str = CONFIG.get("players_file", "players_file.json")
MAX_PLAYERS_FILE: str = CONFIG.get("MAX_PLAYERS_FILE", "max_players_history.json")

# 状态显示映射（用于格式化服务器状态）
STATUS_MAP: Dict[str, str] = {
    '-1': "🟡 忙碌",
    '0':  "🔴 停止",
    '1':  "🟣 停止中",
    '2':  "🟠 启动中",
    '3':  "🟢 运行"
}

# AI API 配置（多端点 fallback）
AI_ENDPOINTS: List[Dict[str, str]] = []
for i in range(1, 4):
    url_key = f"ai_api_url{i}"
    key_key = f"ai_api_key{i}"
    if url_key in CONFIG and key_key in CONFIG:
        AI_ENDPOINTS.append({
            "url": CONFIG[url_key].rstrip('/'),
            "key": CONFIG[key_key]
        })

# 插件列表（用于兼容性检查或功能开关）
PLUGINS_LIST: List[str] = [
    p.strip() for p in CONFIG.get("pluginslist", "").split(",") if p.strip()
]


# ===== 配置验证辅助函数 =====

def validate_server_config() -> bool:
    """
    验证服务器监控相关配置完整性
    
    Returns:
        bool: 配置是否有效
    """
    if not UUIDS:
        logging.getLogger(__name__).error("UUIDS 配置为空，无法监控任何服务器")
        return False
    
    # 检查每个 UUID 是否有对应端口（非强制，但建议）
    missing_ports = [uuid for uuid in UUIDS if uuid not in SERVER_PORTS]
    if missing_ports:
        logging.getLogger(__name__).warning(
            f"以下服务器未配置端口，将使用默认 25565: {missing_ports}"
        )
    
    return True


def get_server_port(uuid: str, default: int = 25565) -> int:
    """
    安全获取服务器端口
    
    Args:
        uuid: 服务器 UUID
        default: 默认端口（若未配置）
        
    Returns:
        int: 服务器端口号
    """
    return SERVER_PORTS.get(uuid, default)


def get_server_name(uuid: str) -> str:
    """
    获取服务器显示名称
    
    Args:
        uuid: 服务器 UUID
        
    Returns:
        str: 服务器名称，若未知则返回 UUID 前 8 位
    """
    return UUIDS.get(uuid, f"未知服务器({uuid[:8]}...)")