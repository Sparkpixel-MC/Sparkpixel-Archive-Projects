"""一言缓存模块 - 从 hitokoto-osc/sentences-bundle 本地缓存获取一言"""
import json
import os
import random
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 缓存配置
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hitokoto_data")
CACHE_INDEX_FILE = os.path.join(CACHE_DIR, "index.json")
CACHE_TTL = 86400  # 缓存有效期（秒）= 24小时

# 一言类型映射
HITOKOTO_TYPES = {
    "a": "动画", "b": "漫画", "c": "游戏", "d": "文学",
    "e": "原创", "f": "来自网络", "g": "其他", "h": "影视",
    "i": "诗词", "j": "网易云", "k": "哲学", "l": "抖机灵"
}

# GitHub 仓库配置
REPO_BASE_URL = "https://raw.githubusercontent.com/hitokoto-osc/sentences-bundle/master/sentences"
SENTENCE_FILES = [
    "a.json", "b.json", "c.json", "d.json", "e.json", "f.json",
    "g.json", "h.json", "i.json", "j.json", "k.json", "l.json"
]

# 内存缓存
_sentences_cache: List[Dict] = []
_cache_loaded: bool = False
_last_cache_time: float = 0.0


def _ensure_cache_dir():
    """确保缓存目录存在"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        logger.info(f"创建一言缓存目录: {CACHE_DIR}")


def _is_cache_expired() -> bool:
    """检查缓存是否过期"""
    if not os.path.exists(CACHE_INDEX_FILE):
        return True
    try:
        with open(CACHE_INDEX_FILE, 'r', encoding='utf-8') as f:
            index = json.load(f)
        return (time.time() - index.get("timestamp", 0)) > CACHE_TTL
    except Exception:
        return True


def _download_sentence_file(filename: str) -> bool:
    """下载单个句子文件"""
    import urllib.request
    url = f"{REPO_BASE_URL}/{filename}"
    filepath = os.path.join(CACHE_DIR, filename)

    try:
        logger.debug(f"下载一言文件: {filename}")
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/vnd.github.v3.raw')

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode('utf-8')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(data)

        return True
    except Exception as e:
        logger.warning(f"下载 {filename} 失败: {e}")
        return False


def _download_all_sentences():
    """下载所有句子文件"""
    _ensure_cache_dir()
    success_count = 0

    for filename in SENTENCE_FILES:
        if _download_sentence_file(filename):
            success_count += 1

    # 更新索引
    if success_count > 0:
        index = {
            "timestamp": time.time(),
            "files_count": success_count,
            "download_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(CACHE_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        logger.info(f"一言缓存更新完成: {success_count}/{len(SENTENCE_FILES)} 个文件")

    return success_count > 0


def _load_sentences_to_memory() -> bool:
    """加载句子到内存"""
    global _sentences_cache, _cache_loaded, _last_cache_time

    if _cache_loaded and (time.time() - _last_cache_time) < 300:
        return True

    _sentences_cache = []
    loaded_count = 0

    for filename in SENTENCE_FILES:
        filepath = os.path.join(CACHE_DIR, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sentences = json.load(f)
            _sentences_cache.extend(sentences)
            loaded_count += 1
        except Exception as e:
            logger.warning(f"加载 {filename} 失败: {e}")

    if _sentences_cache:
        _cache_loaded = True
        _last_cache_time = time.time()
        logger.info(f"已加载 {len(_sentences_cache)} 条一言到内存")
        return True

    return False


def _ensure_data_ready() -> bool:
    """确保数据已准备好"""
    global _cache_loaded

    if _cache_loaded and _sentences_cache:
        return True

    # 检查本地缓存
    if _is_cache_expired():
        logger.info("一言缓存过期或不存在，开始下载...")
        _download_all_sentences()

    return _load_sentences_to_memory()


def get_hitokoto() -> Dict[str, str]:
    """
    获取随机一言

    Returns:
        dict: {"content": "内容", "from": "出处", "creator": "作者"}
    """
    if not _ensure_data_ready():
        return {
            "content": "人生如逆旅，我亦是行人。",
            "from": "苏轼",
            "creator": ""
        }

    # 随机选择一条
    sentence = random.choice(_sentences_cache)

    return {
        "content": sentence.get("hitokoto", ""),
        "from": sentence.get("from", ""),
        "creator": sentence.get("from_who") or sentence.get("creator") or ""
    }


def get_hitokoto_by_type(type_code: str) -> Dict[str, str]:
    """
    按类型获取一言

    Args:
        type_code: 类型代码 (a-l)

    Returns:
        dict: {"content": "内容", "from": "出处", "creator": "作者"}
    """
    if not _ensure_data_ready():
        return get_hitokoto()

    # 按类型筛选
    filtered = [s for s in _sentences_cache if s.get("type") == type_code]

    if not filtered:
        return get_hitokoto()

    sentence = random.choice(filtered)

    return {
        "content": sentence.get("hitokoto", ""),
        "from": sentence.get("from", ""),
        "creator": sentence.get("from_who") or sentence.get("creator") or ""
    }


def get_hitokoto_text(include_author: bool = True) -> str:
    """
    获取格式化的一言文本

    Args:
        include_author: 是否包含作者信息

    Returns:
        str: 格式化的一言文本
    """
    h = get_hitokoto()
    if include_author:
        if h["creator"]:
            return f"{h['content']} ——{h['creator']}《{h['from']}》"
        return f"{h['content']} ——《{h['from']}》"
    return h["content"]


def get_hitokoto_for_sender() -> str:
    """获取用于消息发送的一言格式"""
    h = get_hitokoto()
    if h["creator"]:
        return f"\n 每日一言： {h['content']} ——《{h['from']}》  作者：{h['creator']}"
    return f"\n 每日一言： {h['content']} ——《{h['from']}》"


def get_cache_stats() -> Dict:
    """获取缓存统计信息"""
    stats = {
        "cache_dir": CACHE_DIR,
        "cache_exists": os.path.exists(CACHE_DIR),
        "index_exists": os.path.exists(CACHE_INDEX_FILE),
        "memory_loaded": _cache_loaded,
        "sentences_count": len(_sentences_cache)
    }

    if os.path.exists(CACHE_INDEX_FILE):
        try:
            with open(CACHE_INDEX_FILE, 'r', encoding='utf-8') as f:
                index = json.load(f)
            stats["last_update"] = index.get("download_time", "未知")
            stats["files_count"] = index.get("files_count", 0)
        except Exception:
            pass

    # 统计各文件大小
    stats["files"] = {}
    for filename in SENTENCE_FILES:
        filepath = os.path.join(CACHE_DIR, filename)
        if os.path.exists(filepath):
            stats["files"][filename] = os.path.getsize(filepath)

    return stats


def refresh_cache() -> bool:
    """手动刷新缓存"""
    global _cache_loaded
    _cache_loaded = False
    return _download_all_sentences()


def invalidate_cache() -> None:
    """手动使缓存失效"""
    global _cache_loaded
    _cache_loaded = False
    logger.debug("一言缓存已手动失效")


# 不在启动时下载，首次调用 get_hitokoto() 时自动加载
