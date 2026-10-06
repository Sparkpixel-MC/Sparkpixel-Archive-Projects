"""转账模块 - 通过RCON执行Minecraft服务器转账命令"""
import logging
import re
from typing import Optional, Tuple
logger = logging.getLogger(__name__)

# RCON配置
RCON_HOST = "172.17.0.1"
RCON_PORT = 42375
RCON_PASSWORD = "SparkPixel@888SEFER%#%"


def execute_rcon_command(command: str) -> str:
    """执行RCON命令并返回结果"""
    try:
        from mcrcon import MCRcon
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(command)
            logger.info(f"RCON命令执行成功: {command} -> {response}")
            return response
    except ImportError:
        logger.error("mcrcon模块未安装，请运行: pip install mcrcon")
        raise
    except Exception as e:
        logger.error(f"RCON命令执行失败: {command} - {e}")
        raise


def parse_at_or_name(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    解析@玩家或直接输入的名字

    Args:
        text: 原始输入字符串

    Returns:
        tuple: (qq_id, player_name)
        - 匹配到 CQ 码: (qq_id, name或None)
        - 未匹配到 CQ 码且文本非空: (None, text)
        - 其他情况: (None, None)
    """
    text = text.strip()

    # 修正正则：兼容可选的 ,name= 字段，并正确转义闭合括号
    pattern = r'\[CQ:at,qq=(\d+)(?:,name=([^\]]*))?\]'
    cq_match = re.search(pattern, text)

    if cq_match:
        qq_id = cq_match.group(1)
        player_name = cq_match.group(2)  # 若缺失 name 字段，group(2) 自动返回 None
        return qq_id, None

    # 未匹配到 CQ 码时的降级逻辑
    if text:
        return None, text

    return None, None


def transfer_money(sender_name: str, receiver_name: str, amount: int) -> dict:
    """
    执行转账操作

    Args:
        sender_name: 转账人游戏昵称
        receiver_name: 收款人游戏昵称
        amount: 转账金额

    Returns:
        dict: {"success": bool, "message": str, "response": str}
    """
    try:
        # 定义错误识别关键词
        error_keywords = [
            "未知", "不存在", "error", "失败", "insufficient", "not enough",
            "余额不足", "unknown", "invalid", "cannot", "unable"
        ]

        # 辅助函数：判断响应是否包含错误特征
        def contains_error(response: str | None) -> bool:
            if not response:
                return True
            return any(kw in response.lower() for kw in error_keywords)

        # 1. 执行扣款命令
        command_take = f"money take {sender_name} {amount}"
        response1 = execute_rcon_command(command_take)
        
        if contains_error(response1):
            return {
                "success": False,
                "message": f"扣款失败 (转账人: {sender_name}): {response1 or '无响应'}",
                "response": response1 or ""
            }

        # 2. 执行发钱命令
        command_give = f"money give {receiver_name} {amount}"
        response2 = execute_rcon_command(command_give)
        
        if contains_error(response2):
            # 发钱失败，尝试资金回滚
            logger.warning(f"发钱失败，执行回滚操作。收款人: {receiver_name}, 原始响应: {response2}")
            command_refund = f"money give {sender_name} {amount}"
            refund_resp = execute_rcon_command(command_refund)
            
            if contains_error(refund_resp):
                logger.error(f"资金回滚亦失败: {refund_resp}")
                
            return {
                "success": False,
                "message": f"发钱失败 (收款人: {receiver_name}): {response2 or '无响应'}。已尝试回滚扣款。",
                "response": f"发钱响应: {response2} | 回滚响应: {refund_resp}"
            }

        # 3. 双命令均成功
        return {
            "success": True,
            "message": f"转账成功: {sender_name} -> {receiver_name} ({amount} Sptoken)",
            "response": f"扣款响应: {response1} | 发钱响应: {response2}"
        }

    except Exception as e:
        logger.error(f"转账系统异常: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"转账执行异常: {str(e)}",
            "response": ""
        }


