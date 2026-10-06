"""配置管理模块"""
import json
import os

def read_config(config_path: str = "environment.json") -> dict:
    """安全读取并清理配置文件"""
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = json.load(f)
        
        # 清理关键字段的空白字符（特别是URL和token）
        cleaned_config = {}
        for key, value in raw_config.items():
            if isinstance(value, str):
                # 对URL、token等关键字段进行清理
                if key in ["mcsm_url", "base_url", "base_token", "mcsm_apikey"]:
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
        
        # 确保group_id是字符串列表
        if not isinstance(cleaned_config["group_id"], list):
            cleaned_config["group_id"] = [str(cleaned_config["group_id"])]
        else:
            cleaned_config["group_id"] = [str(g) for g in cleaned_config["group_id"]]
        
        # 确保uuids是字典
        if not isinstance(cleaned_config["uuids"], dict):
            raise ValueError("uuids 配置必须是字典类型")
        
        return cleaned_config
    
    except json.JSONDecodeError as e:
        raise ValueError(f"配置文件格式错误 ({config_path}): {str(e)}")
    except Exception as e:
        raise RuntimeError(f"加载配置失败: {str(e)}")

# 全局配置加载
try:
    CONFIG = read_config()
except Exception as e:
    raise SystemExit(1)

# 从配置中提取关键参数
MAX_PLAYERS_FILE = CONFIG.get("MAX_PLAYERS_FILE", "max_players_history.json")
UPDATE_INTERVAL = CONFIG.get("UPDATE_INTERVAL", 10)
MAX_RETRIES = CONFIG.get("max_retries", 5)
BASE_DELAY = CONFIG.get("base_delay", 0.5)
MAX_DELAY = CONFIG.get("max_delay", 2.0)

# 服务器映射
UUIDS = CONFIG["uuids"]

# 群组白名单
AUTHORIZED_GROUPS = CONFIG["group_id"]

# MCSM 配置
MCSM_URL = CONFIG["mcsm_url"].rstrip('/')
MCSM_APIKEY = CONFIG["mcsm_apikey"]
DAEMON_ID = CONFIG["daemon_id"]

# 基础API配置
BASE_URL = CONFIG.get("base_url").rstrip('/')
BASE_TOKEN = CONFIG.get("base_token")

# 状态映射
STATUS_MAP = {
    '-1': "🟡 忙碌 ",
    '0': "🔴 停止 ",
    '1': "🟣 停止中",
    '2': "🟠 启动中 ",
    '3': "🟢 运行 "
}

# MCP知识库配置
MCP_KB_ENABLED = CONFIG.get("mcp_kb_enabled", True)
MCP_KB_MODE = CONFIG.get("mcp_kb_mode", "http")  # "http" 或 "stdio"
MCP_KB_URL = CONFIG.get("mcp_kb_url", "http://localhost:9000/query")
MCP_KB_API_KEY = CONFIG.get("mcp_kb_api_key", "")
MCP_KB_SERVER_PATH = CONFIG.get("mcp_kb_server_path", "./knowledge-base-mcp-server")