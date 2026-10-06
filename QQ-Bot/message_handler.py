"""消息处理模块 - 处理QQ机器人的消息命令（图片模式）"""
import time
import requests
from datetime import date, datetime, timedelta
import logging
from config import AUTHORIZED_GROUPS, ADMIN_GROUP_ID, FINANCE_BLOCKED_USERS, BASE_URL, BASE_TOKEN, HEALTH_URL
from database import save_message, get_recall_operator, execute_update_recall, get_ban_operator, update_ban_reason
from database import get_player_history, get_player_history_by_date, get_daily_max_players, get_server_reliability_30d
from database import has_agreed_disclaimer, save_disclaimer_agreement
from server_monitor import get_max_players_for_date, get_server_info
from server_monitor import get_monitor
from message_sender import send_group_msg, send_group_image, send_private_msg, send_private_image
from image_generator import (
    generate_status_card_async,
    generate_chart_image,
    generate_max_players_card,
    generate_help_card,
    generate_balance_card,
    generate_transactions_card
)
from xconomy_db import format_balance_message, format_transactions_message, get_player_transactions_page

logger = logging.getLogger(__name__)

# 转账免责声明
TRANSFER_DISCLAIMER = """⚠️ 转账免责声明 ⚠️

在使用转账功能前，请您仔细阅读并同意以下条款：

1️⃣ 【交易风险自担】
   所有转账行为均为用户自愿操作，转账完成后无法撤回。

2️⃣ 【核实收款方】
   请在转账前仔细核实收款人信息，转错账由转账人自行承担。

3️⃣ 【金额确认】
   请确认转账金额无误，系统不支持部分撤回或退款。

4️⃣ 【免责条款】
   因用户操作失误造成的损失，不予退还。

━━━━━━━━━━━━━━━━━━━━━━
📩 请回复「同意以上声明」以开通转账功能"""


def is_admin_group_member(user_id: str) -> bool:
    """检查用户是否在管理群中"""
    if not ADMIN_GROUP_ID:
        return False
    try:
        url = f"{BASE_URL}/get_group_member_info"
        payload = {"group_id": ADMIN_GROUP_ID, "user_id": user_id}
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {BASE_TOKEN}'}
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        data = resp.json()
        return data.get("retcode") == 0
    except Exception as e:
        logger.error(f"检查管理群成员失败: {e}")
        return False


async def fetch_health_data() -> dict:
    """从健康监控 API 获取服务状态"""
    try:
        import aiohttp
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{HEALTH_URL.rstrip('/')}/api/data",
                timeout=aiohttp.ClientTimeout(total=5),
                ssl=ssl_ctx
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f"健康监控 API 请求失败: {e}")
    return {}


def format_health_text(health_data: dict) -> str:
    """格式化健康监控数据为文本"""
    if not health_data or "monitors" not in health_data:
        return ""

    monitors = health_data["monitors"]
    up_count = health_data.get("up", 0)
    down_count = health_data.get("down", 0)

    lines = [f"🌐 服务状态: {up_count}✅ {down_count}❌"]
    for name, info in monitors.items():
        status = "✅" if info.get("up") else "❌"
        latency = info.get("latency", "?")
        lines.append(f"  {status} {name}: {latency}ms")

    return "\n".join(lines)


async def handle_private_message(obj: dict, send_private_func):
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

    # ===== 免责声明同意处理 =====

    elif text == "同意以上声明":
        if has_agreed_disclaimer(user_id):
            send_private_func("✅ 您已同意过免责声明，转账功能已开通", user_id)
        else:
            if save_disclaimer_agreement(user_id):
                send_private_func("✅ 免责声明同意成功！转账功能已开通\n\n您现在可以使用 /pay 命令进行转账", user_id)
            else:
                send_private_func("❌ 系统错误，请稍后重试", user_id)

    # ===== 金融相关指令（私信处理） =====

    # 转账功能
    elif text.startswith("/pay ") or text == "/pay":
        if user_id in FINANCE_BLOCKED_USERS:
            return

        # 检查是否已同意免责声明
        if not has_agreed_disclaimer(user_id):
            send_private_func(TRANSFER_DISCLAIMER, user_id)
            return

        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            send_private_func(
                "❌ 参数错误\n"
                "格式: /pay @玩家 金额 或 /pay 玩家名 金额\n"
                "示例: /pay @张三 100 或 /pay Steve 100",
                user_id
            )
            return

        payname = parts[1]
        amount_str = parts[2]

        try:
            amount = int(amount_str)
            if amount <= 0:
                send_private_func("❌ 金额必须大于0", user_id)
                return
            if amount > 1000000:
                send_private_func("❌ 单次转账不能超过100万", user_id)
                return
        except ValueError:
            send_private_func("❌ 金额格式错误，请输入数字", user_id)
            return

        try:
            from pay import parse_at_or_name, transfer_money
            from get_qqid import get_gamenick

            sender_name = get_gamenick(user_id)
            if not sender_name:
                send_private_func("❌ 未找到您的游戏昵称，请先绑定QQ", user_id)
                return

            qq_id, player_name = parse_at_or_name(payname)

            if not qq_id and not player_name:
                send_private_func("❌ 无法识别收款人，请使用@玩家或输入玩家名", user_id)
                return

            if qq_id:
                receiver_name = get_gamenick(qq_id)
                if not receiver_name:
                    send_private_func(f"❌ 未找到玩家 (QQ: {qq_id})，请确认对方已绑定", user_id)
                    return
            else:
                receiver_name = player_name
                

            if sender_name.lower() == receiver_name.lower():
                send_private_func("❌ 不能给自己转账", user_id)
                return

            result = transfer_money(sender_name, receiver_name, amount)

            if result["success"]:
                send_private_func(
                    f"✅ 转账成功\n"
                    f"📤 转账人: {sender_name}\n"
                    f"📥 收款人: {receiver_name}\n"
                    f"💰 金额: {amount}",
                    user_id
                )
                logger.info(f"💰 转账成功 | {sender_name} -> {receiver_name} | 金额: {amount}")
            else:
                send_private_func(f"❌ 转账失败: {result['message']}", user_id)
                logger.warning(f"💰 转账失败 | {result['message']}")

        except Exception as e:
            logger.error(f"转账系统错误: {e}")
            send_private_func(f"❌ 系统错误请联系管理员，时间: {datetime.now()}", user_id)

    # 余额查询
    elif text.startswith("/balance") or text.startswith("/余额"):
        if user_id in FINANCE_BLOCKED_USERS:
            return

        parts = text.split(maxsplit=1)

        try:
            from get_qqid import get_gamenick

            if len(parts) >= 2:
                if not is_admin_group_member(user_id):
                    player_name = get_gamenick(user_id)
                    if not player_name:
                        send_private_func("❌ 未找到您的游戏昵称，请先绑定QQ或指定玩家名", user_id)
                        return
                else:
                    player_name = parts[1].strip()
            else:
                player_name = get_gamenick(user_id)
                if not player_name:
                    send_private_func("❌ 未找到您的游戏昵称，请先绑定QQ或指定玩家名", user_id)
                    return

            from xconomy_db import get_player_balance
            balance_data = get_player_balance(player_name)
            if not balance_data:
                send_private_func(f"❌ 未找到玩家 {player_name} 的账户信息", user_id)
                return

            image_data = generate_balance_card(
                player_name,
                balance_data.get("balance", 0),
                balance_data.get("bank_balance", 0)
            )
            if image_data:
                send_private_image(image_data, user_id)
            else:
                send_private_func(format_balance_message(player_name), user_id)
            logger.info(f"💰 余额查询 | 玩家: {player_name}")

        except Exception as e:
            logger.error(f"余额查询失败: {e}")
            send_private_func(f"❌ 查询失败: {str(e)[:50]}", user_id)

    # 交易记录查询
    elif text.startswith("/transactions") or text.startswith("/交易记录"):
        if user_id in FINANCE_BLOCKED_USERS:
            return

        parts = text.split(maxsplit=2)

        try:
            from get_qqid import get_gamenick

            player_name = None
            page = 1

            if len(parts) >= 2:
                if parts[1].isdigit():
                    page = int(parts[1])
                else:
                    if is_admin_group_member(user_id):
                        player_name = parts[1].strip()
                    else:
                        send_private_func("❌ 只能查询自己的交易记录", user_id)
                        return
                    if len(parts) >= 3 and parts[2].isdigit():
                        page = int(parts[2])

            if not player_name:
                player_name = get_gamenick(user_id)
                if not player_name:
                    send_private_func("❌ 未找到您的游戏昵称，请先绑定QQ或指定玩家名", user_id)
                    return

            page = max(1, page)
            data = get_player_transactions_page(player_name, page=page, page_size=20)

            if not data["transactions"]:
                send_private_func(f"📋 {player_name} 暂无交易记录", user_id)
                return

            image_data = generate_transactions_card(
                player_name,
                data["transactions"],
                page=data["page"],
                total_pages=data["total_pages"],
                total=data["total"]
            )
            if image_data:
                send_private_image(image_data, user_id)
            else:
                result = format_transactions_message(player_name, page=page)
                send_private_func(result, user_id)
            logger.info(f"📋 交易记录查询 | 玩家: {player_name} | 页: {page}/{data['total_pages']}")

        except Exception as e:
            logger.error(f"交易记录查询失败: {e}")
            send_private_func(f"❌ 查询失败: {str(e)[:50]}", user_id)

    # ===== 以下为群聊命令的私信版本 =====

    # 服务器状态查询（私信）
    elif text in ["/status", "/服务器状态", "/s"]:
        try:
            monitor = get_monitor()
            total_players = await monitor.get_total_players()
            server_data = monitor.get_raw_server_data()
            health_data = await fetch_health_data()
            reliability_data = get_server_reliability_30d()

            image_data = await generate_status_card_async(server_data, total_players, "服务器状态", health_data, reliability_data)

            if image_data:
                send_private_image(image_data, user_id)
                logger.info(f"📊 私信状态图片 | 总玩家: {total_players}")
            else:
                status_info = await get_server_info()
                send_private_func(f"服务器状态\n{status_info}", user_id)
        except Exception as e:
            logger.error(f"私信状态查询失败: {e}")
            send_private_func(f"⚠️ 状态查询失败: {str(e)[:50]}", user_id)

    # 历史最高人数查询（私信）
    elif text.startswith("/maxplayers") or text.startswith("/maxp"):
        parts = text.split(maxsplit=1)
        query_date = parts[1] if len(parts) == 2 else date.today().isoformat()
        try:
            import json as _json
            import os
            from config import MAX_PLAYERS_FILE

            if os.path.exists(MAX_PLAYERS_FILE):
                with open(MAX_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    history = _json.load(f)
            else:
                history = {}

            image_data = generate_max_players_card(history, query_date)
            if image_data:
                send_private_image(image_data, user_id)
            else:
                success, result = get_max_players_for_date(query_date)
                send_private_func(result, user_id)
        except Exception as e:
            send_private_func(f"❌ {str(e)}", user_id)

    # 玩家数量统计图（私信）
    elif text.startswith("/chart"):
        parts = text.split(maxsplit=1)
        time_range = parts[1] if len(parts) == 2 else "24h"
        try:
            history_data = []
            title = "玩家数量统计"
            if time_range in ["24h", "1d"]:
                history_data = get_player_history(hours=24)
                title = "最近24小时玩家数量统计"
            elif time_range in ["7d", "7days"]:
                start_date = (date.today() - timedelta(days=7)).isoformat()
                history_data = get_player_history_by_date(start_date)
                title = "最近7天玩家数量统计"
            elif time_range in ["30d", "30days"]:
                start_date = (date.today() - timedelta(days=30)).isoformat()
                history_data = get_player_history_by_date(start_date)
                title = "最近30天玩家数量统计"
            elif time_range in ["all"]:
                start_date = (date.today() - timedelta(days=90)).isoformat()
                history_data = get_player_history_by_date(start_date)
                title = "玩家数量历史统计"
            else:
                send_private_func("❌ 时间参数错误\n可用: 24h, 7d, 30d, all", user_id)
                return

            if not history_data:
                send_private_func("⚠️ 暂无历史数据，请稍后再试", user_id)
                return

            image_data = generate_chart_image(history_data, title, time_range)
            if image_data:
                send_private_image(image_data, user_id)
            else:
                send_private_func("⚠️ 图表生成失败", user_id)
        except Exception as e:
            logger.error(f"私信统计图失败: {e}")
            send_private_func(f"❌ 统计图生成失败: {str(e)[:50]}", user_id)

    # 每日统计图（私信）
    elif text.startswith("/daily") or text.startswith("/daychart"):
        parts = text.split(maxsplit=1)
        days = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 30
        try:
            daily_data = get_daily_max_players(days)
            if not daily_data:
                send_private_func("⚠️ 暂无历史数据", user_id)
                return

            history_data = []
            for item in daily_data:
                dt = datetime.strptime(item['date'], '%Y-%m-%d')
                history_data.append({
                    'timestamp': dt.timestamp(),
                    'player_count': item['max_players'],
                    'date': item['date']
                })

            title = f"最近{days}天每日最高在线统计"
            image_data = generate_chart_image(history_data, title, f"{days}d")
            if image_data:
                send_private_image(image_data, user_id)
            else:
                send_private_func("⚠️ 图表生成失败", user_id)
        except Exception as e:
            logger.error(f"私信每日统计失败: {e}")
            send_private_func(f"❌ 统计图生成失败: {str(e)[:50]}", user_id)

    # 帮助命令（私信）
    elif text in ["/h", "/help"]:
        image_data = generate_help_card()
        if image_data:
            send_private_image(image_data, user_id)
        else:
            send_private_func(
                "❓ 可用命令:\n"
                "/s - 服务器状态\n"
                "/maxp [日期] - 历史最高人数\n"
                "/chart [时间] - 玩家数量统计图\n"
                "/daily [天数] - 每日最高在线\n"
                "/balance - 查询余额\n"
                "/交易记录 [页码] - 查询交易记录\n"
                "/pay @玩家 金额 - 转账",
                user_id
            )


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
    
    # 服务器状态查询 - 使用图片模式
    if raw_msg in ["/status", "/服务器状态", "/s"]:
        try:
            monitor = get_monitor()
            # 先触发缓存刷新，再读取数据
            total_players = await monitor.get_total_players()
            server_data = monitor.get_raw_server_data()

            # 获取健康监控数据和可靠率数据
            health_data = await fetch_health_data()
            reliability_data = get_server_reliability_30d()

            # 生成状态卡片图片（异步版本，支持头像加载）
            image_data = await generate_status_card_async(server_data, total_players, "服务器状态", health_data, reliability_data)

            if image_data:
                send_group_image(image_data, group_id)
                logger.info(f"📊 已发送服务器状态图片 | 总玩家: {total_players}")
            else:
                status_info = await get_server_info()
                health_text = format_health_text(health_data) if health_data else ""
                send_msg_func(f"服务器状态\n{status_info}\n{health_text}", group_id)

        except Exception as e:
            logger.error(f"状态查询失败: {e}")
            send_msg_func(f"⚠️ 状态查询失败: {str(e)[:50]}", group_id)
    
    # 历史最高人数查询 - 使用图片模式
    elif raw_msg.startswith("/maxplayers") or raw_msg.startswith("/maxp"):
        parts = raw_msg.split(maxsplit=1)
        query_date = parts[1] if len(parts) == 2 else date.today().isoformat()
        
        try:
            # 读取历史数据
            import json
            import os
            from config import MAX_PLAYERS_FILE
            
            if os.path.exists(MAX_PLAYERS_FILE):
                with open(MAX_PLAYERS_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {}
            
            # 生成最高人数卡片图片
            image_data = generate_max_players_card(history, query_date)
            
            if image_data:
                send_group_image(image_data, group_id)
                logger.info(f"📈 已发送历史最高人数图片 | 日期: {query_date}")
            else:
                # 回退到文字模式
                success, result = get_max_players_for_date(query_date)
                send_msg_func(result, group_id)

        except Exception as e:
            send_msg_func(f"❌ {str(e)}", group_id)
    
    # 玩家数量统计图
    elif raw_msg.startswith("/chart"):
        parts = raw_msg.split(maxsplit=1)
        time_range = parts[1] if len(parts) == 2 else "24h"
        
        try:
            history_data = []
            title = "玩家数量统计"
            
            if time_range in ["24h", "1d"]:
                # 最近24小时
                history_data = get_player_history(hours=24)
                title = "最近24小时玩家数量统计"
            elif time_range in ["7d", "7days"]:
                # 最近7天
                start_date = (date.today() - timedelta(days=7)).isoformat()
                history_data = get_player_history_by_date(start_date)
                title = "最近7天玩家数量统计"
            elif time_range in ["30d", "30days"]:
                # 最近30天
                start_date = (date.today() - timedelta(days=30)).isoformat()
                history_data = get_player_history_by_date(start_date)
                title = "最近30天玩家数量统计"
            elif time_range in ["all"]:
                # 所有数据
                start_date = (date.today() - timedelta(days=90)).isoformat()
                history_data = get_player_history_by_date(start_date)
                title = "玩家数量历史统计"
            else:
                send_msg_func("❌ 时间参数错误\n可用: 24h, 7d, 30d, all", group_id)
                return
            
            if not history_data:
                send_msg_func("⚠️ 暂无历史数据，请稍后再试", group_id)
                return
            
            # 生成图表图片
            image_data = generate_chart_image(history_data, title, time_range)
            
            if image_data:
                send_group_image(image_data, group_id)
                logger.info(f"📊 已发送统计图 | 时间范围: {time_range} | 数据点: {len(history_data)}")
            else:
                send_msg_func("⚠️ 图表生成失败，请检查 matplotlib 是否安装", group_id)

        except Exception as e:
            logger.error(f"统计图生成失败: {e}")
            send_msg_func(f"❌ 统计图生成失败: {str(e)[:50]}", group_id)
    
    # 每日统计图（按天聚合）
    elif raw_msg.startswith("/daily") or raw_msg.startswith("/daychart"):
        parts = raw_msg.split(maxsplit=1)
        days = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 30
        
        try:
            daily_data = get_daily_max_players(days)
            
            if not daily_data:
                send_msg_func("⚠️ 暂无历史数据", group_id)
                return
            
            # 转换为图表需要的格式
            history_data = []
            for item in daily_data:
                # 将日期转换为时间戳
                dt = datetime.strptime(item['date'], '%Y-%m-%d')
                history_data.append({
                    'timestamp': dt.timestamp(),
                    'player_count': item['max_players'],
                    'date': item['date']
                })
            
            title = f"最近{days}天每日最高在线统计"
            image_data = generate_chart_image(history_data, title, f"{days}d")
            
            if image_data:
                send_group_image(image_data, group_id)
                logger.info(f"📊 已发送每日统计图 | 天数: {days}")
            else:
                send_msg_func("⚠️ 图表生成失败", group_id)

        except Exception as e:
            logger.error(f"每日统计图生成失败: {e}")
            send_msg_func(f"❌ 统计图生成失败: {str(e)[:50]}", group_id)
    # 金融相关指令提示（群内使用时引导去私信）
    
    # 帮助命令 - 使用图片模式
    elif raw_msg in ["/h", "/help"]:
        image_data = generate_help_card()
        
        if image_data:
            send_group_image(image_data, group_id)
        else:
            send_msg_func(
                "❓ 可用命令:\n"
                "/status (/s) - 服务器状态\n"
                "/maxp [日期] - 历史最高人数\n"
                "/chart [时间] - 玩家数量统计图 (24h/7d/30d)\n"
                "/daily [天数] - 每日最高在线统计\n"
                
            )


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
