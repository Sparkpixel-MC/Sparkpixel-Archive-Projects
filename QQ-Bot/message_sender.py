"""消息发送模块 - 处理QQ消息发送"""
import base64
import json
import logging
import time
import requests
from collections import defaultdict
from config import BASE_URL, BASE_TOKEN
from hitokoto_cache import get_hitokoto_for_sender

logger = logging.getLogger(__name__)

func_calls_log = defaultdict(lambda: {'last_called': 0, 'calls': 0})

def rate_limited(max_calls, period):
    """速率限制装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_time = time.time()
            record = func_calls_log[func.__name__]
            if (current_time - record['last_called']) < period and record['calls'] >= max_calls:
                raise Exception("访问太频繁，请稍后再试。")
            record['last_called'] = current_time
            record['calls'] += 1
            result = func(*args, **kwargs)
            if (current_time - record['last_called']) > period:
                record['calls'] = 0
            return result
        return wrapper
    return decorator

@rate_limited(max_calls=20, period=10)
def send_group_msg(msg: str, group: str):
    """发送群消息"""
    try:
        # Debug: 记录将要发送的完整消息内容，便于排查URL是否在发送端被截断
        logger.debug(f"发送群消息 (len={len(msg)}): {msg}")
        # 获取每日一言（带缓存）
        msg = msg + get_hitokoto_for_sender()
    except Exception as e:
        logger.warning(f"获取每日一言失败: {e}")

    url = f"{BASE_URL}/send_group_msg"
    payload = json.dumps({
        "group_id": group,
        "message": [{"type": "text", "data": {"text": msg}}]
    })
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {BASE_TOKEN}'
    }
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=5)
        logger.debug(f"群消息发送状态: {response.status_code}")
    except Exception as e:
        logger.error(f"发送群消息失败: {e}")

def send_private_msg(msg: str, user: str):
    """发送私聊消息"""
    try:
        logger.debug(f"发送私聊消息 (len={len(msg)}): {msg}")
        url = f"{BASE_URL}/send_private_msg"
        payload = json.dumps({"user_id": user, "message": [{"type": "text", "data": {"text": msg}}]})
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {BASE_TOKEN}'}
        requests.post(url, headers=headers, data=payload, timeout=5)
    except Exception as e:
        logger.error(f"发送私信失败: {e}")


def send_group_image(image_data: bytes, group: str, caption: str = ""):
    """
    发送群图片消息
    
    Args:
        image_data: 图片的二进制数据
        group: 群号
        caption: 图片说明文字（可选）
    """
    try:
        # 将图片转换为 base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        url = f"{BASE_URL}/send_group_msg"
        
        # 构建消息内容
        message = []
        
        # 如果有说明文字，先发送文字
        if caption:
            message.append({"type": "text", "data": {"text": caption + "\n"}})
        
        # 添加图片
        message.append({
            "type": "image", 
            "data": {
                "file": f"base64://{image_base64}"
            }
        })
        
        payload = json.dumps({
            "group_id": group,
            "message": message
        })
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {BASE_TOKEN}'
        }
        
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        logger.debug(f"群图片发送状态: {response.status_code}")
        
    except Exception as e:
        logger.error(f"发送群图片失败: {e}")


def send_private_image(image_data: bytes, user: str, caption: str = ""):
    """
    发送私聊图片消息
    
    Args:
        image_data: 图片的二进制数据
        user: 用户ID
        caption: 图片说明文字（可选）
    """
    try:
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        url = f"{BASE_URL}/send_private_msg"
        
        message = []
        if caption:
            message.append({"type": "text", "data": {"text": caption + "\n"}})
        
        message.append({
            "type": "image", 
            "data": {
                "file": f"base64://{image_base64}"
            }
        })
        
        payload = json.dumps({
            "user_id": user,
            "message": message
        })
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {BASE_TOKEN}'
        }
        
        requests.post(url, headers=headers, data=payload, timeout=10)
        
    except Exception as e:
        logger.error(f"发送私聊图片失败: {e}")