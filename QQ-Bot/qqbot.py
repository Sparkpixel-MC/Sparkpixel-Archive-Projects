"""QQ机器人主程序 - FastAPI应用入口"""
import asyncio
import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from config import CONFIG, AUTHORIZED_GROUPS
from database import init_database, save_recall_record, save_ban_record
from message_handler import handle_private_message, handle_group_message, handle_group_notice
from message_sender import send_group_msg, send_private_msg
from server_monitor import background_update_max_players, init_max_players_file

# ====== 日志配置 ======
# 创建 log 文件夹
os.makedirs("log", exist_ok=True)

# 生成日期+次数的日志文件名
def get_log_file_path():
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = "log"
    counter = 1
    while True:
        log_file = os.path.join(log_dir, f"{today}_{counter}.log")
        if not os.path.exists(log_file):
            return log_file
        counter += 1

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(get_log_file_path(), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ====== 全局变量 ======
background_task = None

# ====== FastAPI 应用生命周期 ======
@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
    
    # 初始化数据库
    init_database()
    
    # 初始化历史记录文件
    init_max_players_file()
    
    # 启动后台监控任务
    background_task = asyncio.create_task(background_update_max_players())
    logger.info("🚀 应用启动完成")
    
    yield
    
    # 关闭时清理
    if background_task and not background_task.done():
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass
    logger.info("🛑 应用已安全关闭")

app = FastAPI(lifespan=lifespan)

# ====== 主路由处理 ======
@app.post("/")
async def root(request: Request):
    try:
        data = await request.json()
        obj = data
        logger.debug(f"收到事件: {obj.get('post_type', 'unknown')}")

        # 私聊消息处理
        if "group_id" not in obj:
            await handle_private_message(obj, send_private_msg)
            return {}

        # 群消息处理
        if obj.get("post_type") == "message":
            await handle_group_message(obj, send_group_msg)
        
        # 群事件处理
        elif obj.get("post_type") == "notice":
            handle_group_notice(obj, send_private_msg, save_recall_record, save_ban_record)

    except Exception as e:
        logger.exception("❌ 处理事件时发生未预期错误")
        if "group_id" in obj:
            send_group_msg(f"❌ 系统错误: {str(e)[:60]}", str(obj["group_id"]))
    
    return {"status": "ok"}

if __name__ == "__main__":
    import sys
    import uvicorn
    logger.info(f"🔧 服务器启动中... 监听端口: 8080 | 群组: {AUTHORIZED_GROUPS}|环境：{CONFIG['environment']}")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")