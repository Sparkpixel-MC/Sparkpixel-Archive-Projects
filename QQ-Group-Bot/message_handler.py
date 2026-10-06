"""消息处理模块 - 处理QQ机器人的消息命令"""
import time
from datetime import date, datetime
import logging
from config import AUTHORIZED_GROUPS
from database import save_message, get_recall_operator, execute_update_recall, get_ban_operator, update_ban_reason
from server_monitor import get_max_players_for_date, get_server_info
from ai_client import detect_game_help_request, game_help_reply

logger = logging.getLogger(__name__)

def handle_private_message(obj: dict, send_private_func):
    """处理私聊消息"""
    text = obj.get("raw_message", "")
    user_id = str(obj.get("user_id", ""))
    
    # 撤回登记处理
    if text.startswith("/recall"):
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            msg_id, reason = parts[1], parts[2]
            try:
                operator = get_recall_operator(msg_id)
                if operator and operator == user_id:
                    execute_update_recall(msg_id, reason)
                    send_private_func("✅ 撤回理由登记成功", user_id)
                else:
                    send_private_func("❌ 登记失败：操作人不匹配/消息ID不存在", user_id)
            except Exception as e:
                logger.error(f"撤回登记数据库错误: {e}")
                send_private_func("❌ 系统错误，请重试", user_id)
        else:
            send_private_func("❌ 格式错误: /recall [消息ID] [理由]", user_id)
    
    # 禁言登记处理
    elif text.startswith("/mute"):
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            ban_id, reason = parts[1], parts[2]
            try:
                operator = get_ban_operator(ban_id)
                if operator and operator == user_id:
                    update_ban_reason(ban_id, reason)
                    send_private_func("✅ 禁言理由登记成功", user_id)
                else:
                    send_private_func("❌ 登记失败：操作人不匹配/业务ID不存在", user_id)
            except Exception as e:
                logger.error(f"禁言登记数据库错误: {e}")
                send_private_func("❌ 系统错误，请重试", user_id)
        else:
            send_private_func("❌ 格式错误: /mute [业务ID] [理由]", user_id)

async def handle_group_message(obj: dict, send_msg_func):
    """处理群消息"""
    group_id = str(obj.get("group_id", ""))
    if group_id not in AUTHORIZED_GROUPS:
        return {}
    
    raw_msg = obj.get("raw_message", "").strip()
    
    # 保存消息到数据库
    try:
        current_time = int(time.time())
        current_date = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d')
        save_message(
            group_id,
            str(obj.get("user_id", "")),
            obj.get("message_id", 0),
            raw_msg,
            obj.get("message_type", ""),
            current_time,
            current_date
        )
    except Exception as e:
        logger.error(f"消息记录保存失败: {e}")
    
    # AI 检测是否为游戏求助
    is_game_help = False
    try:
        is_game_help = await detect_game_help_request(raw_msg)
        if is_game_help:
            logger.info(f"检测到游戏求助: [{group_id}] {raw_msg[:50]}...")
            # 调用AI生成回复，AI会自己决定是否查询知识库
            help_reply = await game_help_reply(raw_msg)
            if help_reply:
                send_msg_func(help_reply, group_id)
    except Exception as e:
        logger.error(f"AI检测或回复失败: {e}")
    
    # 服务器状态查询
    if raw_msg in ["/status", "/服务器状态", "/s"]:
        try:
            status_info = await get_server_info()
            send_msg_func(f"服务器状态\n{status_info}", group_id)
        except Exception as e:
            send_msg_func(f"⚠️ 状态查询失败: {str(e)[:50]}", group_id)
    
    # 历史最高人数查询
    elif raw_msg.startswith("/maxplayers") or raw_msg.startswith("/maxp"):
        parts = raw_msg.split(maxsplit=1)
        if len(parts) == 2:
            try:
                success, result = get_max_players_for_date(parts[1])
                send_msg_func(result, group_id)
            except Exception as e:
                send_msg_func(f"❌ {str(e)}", group_id)
        else:
            try:
                today = date.today().isoformat()
                success, result = get_max_players_for_date(today)
                send_msg_func(result, group_id)
            except Exception as e:
                send_msg_func(f"❌ {str(e)}", group_id)
    
    # 帮助命令
    elif raw_msg in ["/h", "/help"]:
        send_msg_func("❓ 可用命令:\n/status (/s) - 服务器状态\n/maxplayers (/maxp) [日期] - 历史最高人数（默认今天）", group_id)

def handle_group_notice(obj: dict, send_private_func, save_recall_func, save_ban_func):
    """处理群通知事件"""
    if obj.get("notice_type") == "group_recall" and obj.get("user_id") != obj.get("operator_id"):
        msg_id = obj.get("message_id")
        operator = obj.get("operator_id")
        target = obj.get("user_id")
        hint = f"📨 你撤回了 {target} 的消息\n🆔 消息ID: {msg_id}\n✏️ 请私聊回复: /recall {msg_id} [理由]"
        send_private_func(hint, operator)
        save_recall_func(msg_id, operator, target, obj.get('time', 0))
    
    elif obj.get("notice_type") == "group_ban":
        ban_id = f"{obj.get('user_id', 'unknown')}_{int(time.time())}"
        operator = obj.get("operator_id")
        target = obj.get("user_id")
        duration = obj.get("duration", 0)
        
        hint = f"🔇 你操作了 {target} 的禁言\n🆔 业务ID: {ban_id}\n✏️ 请私聊回复: /mute {ban_id} [理由]"
        send_private_func(hint, operator)
        save_ban_func(ban_id, operator, target, duration, obj.get('time', 0))