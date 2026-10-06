"""消息发送模块 - 处理QQ消息发送"""
import json
import logging
import time
import requests
from collections import defaultdict
from config import BASE_URL, BASE_TOKEN

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
        # 获取每日一言
        hitokoto_url = "https://api.baiwumm.com/api/hitokoto"
        params = {"format": "json"}
        hitokoto_resp = requests.get(hitokoto_url, params=params, timeout=3)
        if hitokoto_resp.status_code == 200:
            hitokoto_data = hitokoto_resp.json()
            creator = hitokoto_data['data'].get('creator')  
           
            if creator is None or creator == "" or creator == "null":
                hitokoto_text = f"\n 每日一言： {hitokoto_data['data']['content']} ——《{hitokoto_data['data']['from']}》"
            else:
                hitokoto_text = f"\n 每日一言： {hitokoto_data['data']['content']} ——《{hitokoto_data['data']['from']}》  作者：{creator}"
            
            msg = msg + hitokoto_text
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