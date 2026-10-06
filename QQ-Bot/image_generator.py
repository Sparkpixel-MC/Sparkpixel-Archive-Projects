"""图片生成模块 - 黑底黄字卡片样式 + 玩家头像 + 折线图"""
import io
import os
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from hitokoto_cache import get_hitokoto

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

MATPLOTLIB_AVAILABLE = None  # None = 未检测, True/False = 已检测

def _lazy_import_matplotlib():
    """懒加载 matplotlib，只在实际使用时才导入"""
    global MATPLOTLIB_AVAILABLE
    if MATPLOTLIB_AVAILABLE is not None:
        return MATPLOTLIB_AVAILABLE
    try:
        global plt, mdates, FontProperties, np
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.font_manager import FontProperties
        import numpy as np
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False
    return MATPLOTLIB_AVAILABLE

logger = logging.getLogger(__name__)

# 颜色配置
BG_COLOR = (18, 18, 18)  # 深黑色背景
CARD_BG_COLOR = (30, 30, 30)  # 卡片背景
YELLOW_COLOR = (255, 200, 0)  # 金黄色
ACCENT_COLOR = (255, 215, 0)  # 强调色
TEXT_SECONDARY = (180, 180, 180)  # 次要文字颜色
SUCCESS_COLOR = (46, 204, 113)  # 绿色
ERROR_COLOR = (231, 76, 60)  # 红色
WARNING_COLOR = (241, 196, 15)  # 警告色

# 分辨率缩放因子（2 = 2倍分辨率）
SCALE_FACTOR = 6

# 头像缓存
_avatar_cache: Dict[str, Optional[Image.Image]] = {}
_avatar_cache_lock = asyncio.Lock()

# 字体缓存
_font_cache: Dict[int, ImageFont.FreeTypeFont] = {}

# 健康监控服务名映射
HEALTH_NAME_MAP = {
    "lobby_server": "大厅",
    "survival_server": "生存",
    "creative_server": "创造",
    "minigame_server": "小游戏",
    "auth_server": "认证",
    "vc_server": "语音",
    "bbs_forum": "论坛",
    "skin": "皮肤",
    "qq_bot_ping": "QQ机器人",
    "web": "官网",
}


def get_title_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    """获取标题字体 - 使用得意黑（带缓存）"""
    cache_key = f"title_{size}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    font_paths = [
        os.path.join(script_dir, "SmileySans-Oblique.otf"),
        "SmileySans-Oblique.otf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size, layout_engine=ImageFont.LAYOUT_RAQM)
                _font_cache[cache_key] = font
                return font
            except Exception:
                continue

    font = get_font(size, bold=False)
    if font:
        _font_cache[cache_key] = font
    return font


def get_body_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    """获取正文字体 - 使用得意黑（带缓存）"""
    cache_key = f"body_{size}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    font_paths = [
        os.path.join(script_dir, "SmileySans-Oblique.otf"),
        "SmileySans-Oblique.otf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size, layout_engine=ImageFont.LAYOUT_RAQM)
                _font_cache[cache_key] = font
                return font
            except Exception:
                continue

    font = get_font(size, bold=False)
    if font:
        _font_cache[cache_key] = font
    return font


def get_number_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    """获取数字字体 - 使用得意黑 + tnum 等宽数字特性（带缓存）"""
    cache_key = f"number_{size}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    font_paths = [
        os.path.join(script_dir, "SmileySans-Oblique.otf"),
        "SmileySans-Oblique.otf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size, layout_engine=ImageFont.LAYOUT_RAQM)
                try:
                    font.set_variation_by_name('tnum')
                except (AttributeError, OSError):
                    pass
                _font_cache[cache_key] = font
                return font
            except Exception:
                continue

    font = get_body_font(size)
    if font:
        _font_cache[cache_key] = font
    return font


def get_font(size: int, bold: bool = False) -> Optional[ImageFont.FreeTypeFont]:
    """获取字体 - 通用回退字体（带缓存）"""
    cache_key = f"font_{size}_{bold}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    font_paths = [
        os.path.join(script_dir, "SmileySans-Oblique.otf"),
        os.path.join(script_dir, "SourceHanSansSC-Regular-2.otf"),
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[cache_key] = font
                return font
            except Exception:
                continue

    try:
        font = ImageFont.load_default()
        if font:
            _font_cache[cache_key] = font
        return font
    except Exception:
        return None


async def fetch_player_avatar(player_name: str, size: int = 32) -> Optional[Image.Image]:
    """
    获取玩家头像
    优先从 mcskin.bu7.top 获取，失败则用 Mojang 官方 API
    
    Args:
        player_name: 玩家名称
        size: 头像尺寸
        
    Returns:
        PIL Image 对象或 None
    """
    if not PIL_AVAILABLE:
        return None
    
    cache_key = f"{player_name}_{size}"
    
    # 检查缓存
    if cache_key in _avatar_cache:
        return _avatar_cache[cache_key]
    
    # 头像源列表（优先级从高到低）
    avatar_sources = [
        # 优先：mcskin.bu7.top
        f"https://mcskin.bu7.top/avatar/player/{player_name}",
        # 备选：Crafatar (Mojang 官方皮肤)
        f"https://crafatar.com/avatars/{player_name}?size={size}&overlay",
        # 备选：minotar
        f"https://minotar.net/helm/{player_name}/{size}",
    ]
    
    for url in avatar_sources:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        avatar_img = Image.open(io.BytesIO(image_data))
                        
                        # 确保是 RGBA 模式
                        if avatar_img.mode != 'RGBA':
                            avatar_img = avatar_img.convert('RGBA')
                        
                        # 调整尺寸
                        avatar_img = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
                        
                        # 缓存结果
                        async with _avatar_cache_lock:
                            _avatar_cache[cache_key] = avatar_img
                        
                        return avatar_img
        except Exception as e:
            logger.debug(f"从 {url} 获取 {player_name} 头像失败: {e}")
            continue
    
    # 所有源都失败，缓存 None
    async with _avatar_cache_lock:
        _avatar_cache[cache_key] = None
    
    return None


def create_rounded_rect_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    """创建圆角矩形蒙版"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw, 
    xy: Tuple[int, int, int, int], 
    radius: int, 
    fill: Tuple[int, int, int]
):
    """绘制圆角矩形"""
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_avatar_with_name(
    img: Image.Image,
    avatar: Optional[Image.Image],
    name: str,
    x: int,
    y: int,
    font: Optional[ImageFont.FreeTypeFont],
    avatar_size: int = 24,
    line_height: int = 32
) -> int:
    """
    在指定位置绘制头像和玩家名称（居中对齐）
    
    Args:
        img: 图片对象
        avatar: 头像图片
        name: 玩家名称
        x: 起始 x 坐标
        y: 行起始 y 坐标
        font: 字体
        avatar_size: 头像尺寸（实际会更小）
        line_height: 行高
        
    Returns:
        绘制内容的宽度
    """
    draw = ImageDraw.Draw(img)
    
    # 计算文字高度
    if font:
        bbox = draw.textbbox((0, 0), name, font=font)
        text_height = bbox[3] - bbox[1]
        text_width = bbox[2] - bbox[0]
    else:
        text_height = 16
        text_width = len(name) * 10
    
    # 实际头像尺寸比传入的小
    actual_avatar_size = int(avatar_size * 0.75)
    
    # 计算头像和文字的居中位置
    text_y = y + (line_height - text_height) // 2
    avatar_y = y + (line_height - actual_avatar_size) // 2 + 3  # 头像下降3px + 5  # 头像下降5px
    
    if avatar:
        # 调整头像尺寸
        resized_avatar = avatar.resize((actual_avatar_size, actual_avatar_size), Image.Resampling.LANCZOS)
        # 绘制头像
        img.paste(resized_avatar, (x, avatar_y), resized_avatar)
        text_x = x + actual_avatar_size + 4
    else:
        text_x = x
    
    # 绘制名称（垂直居中）
    if font:
        draw.text((text_x, text_y), name, font=font, fill=TEXT_SECONDARY)
    
    total_width = (actual_avatar_size + 4 + text_width) if avatar else text_width
    return total_width


def calculate_players_layout(
    player_list: List[str],
    card_width: int,
    card_padding: int,
    font: Optional[ImageFont.FreeTypeFont],
    avatar_size: int = 24,
    player_spacing: int = 15
) -> Tuple[List[List[str]], int, int]:
    """
    计算玩家列表的自动布局
    
    Args:
        player_list: 玩家名称列表
        card_width: 卡片宽度
        card_padding: 卡片内边距
        font: 字体
        avatar_size: 头像尺寸
        player_spacing: 玩家之间的间距
        
    Returns:
        (按行分组的玩家列表, 每行高度, 总行数)
    """
    if not player_list:
        return [], 0, 0
    
    available_width = card_width - card_padding * 2 - 22  # 减去左侧缩进
    
    rows: List[List[str]] = []
    current_row: List[str] = []
    current_row_width = 0
    
    line_height = avatar_size + 4
    
    for player in player_list:
        # 计算单个玩家占用的宽度
        if font:
            draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
            bbox = draw.textbbox((0, 0), player, font=font)
            text_width = bbox[2] - bbox[0]
        else:
            text_width = len(player) * 10
        
        player_width = avatar_size + 6 + text_width + player_spacing
        
        if current_row_width + player_width > available_width:
            # 当前行放不下，换行
            if current_row:
                rows.append(current_row)
            current_row = [player]
            current_row_width = player_width
        else:
            current_row.append(player)
            current_row_width += player_width
    
    # 添加最后一行
    if current_row:
        rows.append(current_row)
    
    return rows, line_height, len(rows)


def calculate_card_width(
    server_data: Dict[str, Dict[str, Any]],
    title: str,
    title_font: Optional[ImageFont.FreeTypeFont],
    server_font: Optional[ImageFont.FreeTypeFont],
    player_font: Optional[ImageFont.FreeTypeFont],
    card_padding: int,
    avatar_size: int,
    player_spacing: int,
    min_width: int = 400,
    max_width: int = 800
) -> int:
    """
    根据内容自动计算卡片宽度
    
    Args:
        server_data: 服务器数据
        title: 标题
        title_font: 标题字体
        server_font: 服务器名称字体
        player_font: 玩家名称字体
        card_padding: 内边距
        avatar_size: 头像尺寸
        player_spacing: 玩家间距
        min_width: 最小宽度
        max_width: 最大宽度
        
    Returns:
        计算后的卡片宽度
    """
    content_width = 0
    
    # 计算标题宽度
    if title_font:
        draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = bbox[2] - bbox[0]
        content_width = max(content_width, title_width)
    
    # 计算服务器名称和玩家数量宽度
    for uuid, data in server_data.items():
        server_name = data.get('name', '未知服务器')
        player_count = data.get('player_count', 0)
        
        # 服务器名称宽度
        if server_font:
            draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
            bbox = draw.textbbox((0, 0), server_name, font=server_font)
            server_name_width = bbox[2] - bbox[0]
            # 加上状态指示器和玩家数量
            server_line_width = server_name_width + 32 + 80  # 状态点 + 间距 + 玩家数量
            content_width = max(content_width, server_line_width)
        
        # 计算玩家列表最大行宽
        player_list = data.get('player_list', [])
        if player_list and player_font:
            row_width = 22  # 左侧缩进
            for player in player_list:
                draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
                bbox = draw.textbbox((0, 0), player, font=player_font)
                text_width = bbox[2] - bbox[0]
                player_width = avatar_size + 6 + text_width + player_spacing
                row_width += player_width
            
            content_width = max(content_width, row_width)
    
    # 计算最终宽度（加上内边距）
    final_width = content_width + card_padding * 2 + 20  # 额外边距
    
    # 限制在最小和最大宽度之间
    return max(min_width, min(max_width, final_width))


async def generate_status_card_async(
    server_data: Dict[str, Dict[str, Any]],
    total_players: int,
    title: str = "服务器状态",
    health_data: dict = None,
    reliability_data: dict = None
) -> Optional[bytes]:
    """
    异步生成服务器状态卡片图片（带玩家头像，7天可靠率网格）

    Args:
        reliability_data: get_server_reliability_30d() 返回的数据
    """
    if not PIL_AVAILABLE:
        logger.error("PIL 未安装，无法生成图片")
        return None
    
    try:
        # 缩放因子（放大所有元素）
        scale = 20

        # 卡片尺寸参数（放大，优化边界）
        card_padding = 35 * scale  # 增大内边距
        card_spacing = 10 * scale  # 增大服务器间距
        card_margin = 15 * scale   # 卡片外边距
        min_width = 400 * scale
        max_width = 800 * scale
        
        # 获取字体（放大）
        title_font = get_title_font(28 * scale)
        server_font = get_body_font(20 * scale)
        player_font = get_body_font(18 * scale)
        small_font = get_body_font(14 * scale)
        number_font = get_number_font(20 * scale)
        small_number_font = get_number_font(14 * scale)
        
        avatar_size = 20 * scale
        player_spacing = 10 * scale
        
        # 自动计算卡片宽度
        card_width = calculate_card_width(
            server_data, title, title_font, server_font, player_font,
            card_padding, avatar_size, player_spacing, min_width, max_width
        )
        
        # 第一遍：计算布局和实际高度
        total_server_height = 0
        layout_info = {}
        
        for uuid, data in server_data.items():
            player_list = data.get('player_list', [])
            rows, line_height, num_rows = calculate_players_layout(
                player_list, card_width, card_padding, player_font, avatar_size, player_spacing
            )
            
            layout_info[uuid] = {
                'rows': rows,
                'line_height': line_height,
                'num_rows': num_rows
            }
            
            # 服务器名称行高 + 玩家列表高度
            # 服务器名称占 30px，玩家每行 32px（放大）
            server_name_height = 50 * scale
            players_height = num_rows * 32 * scale if player_list else 0
            server_height = server_name_height + players_height
            total_server_height += server_height
        
        server_count = len(server_data)
        # 标题区域 + 顶部边距 + 服务器间间距 + 底部总计区域 + 一言区域（多行，放大）
        title_area_height = 70 * scale
        top_margin = 40 * scale
        bottom_area_height = 50 * scale
        hitokoto_height = 60 * scale  # 一言区域高度（支持多行）
        # 健康监控区域高度
        health_height = 0
        if health_data and "monitors" in health_data:
            monitor_count = len(health_data["monitors"])
            health_height = (30 + monitor_count * 20) * scale  # 标题 + 每个服务一行
        total_height = top_margin + title_area_height + total_server_height + (server_count - 1) * card_spacing + bottom_area_height + hitokoto_height + health_height + card_padding + card_margin * 2
        
        # 创建图片
        img = Image.new('RGB', (card_width, total_height), BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # 绘制主卡片背景（使用新的外边距）
        draw_rounded_rect(
            draw,
            (card_margin, card_margin, card_width - card_margin, total_height+30 - card_margin),
            radius=20 * scale,
            fill=CARD_BG_COLOR
        )
        
        # 绘制标题区域（调整起始位置）
        y_offset = card_padding + card_margin
        content_left = card_padding + 5 * scale  # 统一内容左边距，避免圆角

        # 标题装饰线
        draw.rectangle([(content_left, y_offset + 35 * scale), (content_left + 60 * scale, y_offset + 38 * scale)], fill=YELLOW_COLOR)

        # 标题文字
        if title_font:
            draw.text((content_left, y_offset), title, font=title_font, fill=YELLOW_COLOR)

        # 时间戳（根据卡片宽度自适应位置，使用等宽字体）
        current_time = datetime.now().strftime("%H:%M:%S")
        if small_number_font:
            # 使用等宽字体计算宽度
            draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
            bbox = draw_temp.textbbox((0, 0), current_time, font=small_number_font)
            time_text_width = bbox[2] - bbox[0] + 10 * scale
            time_x = card_width - card_padding - time_text_width
            draw.text((time_x, y_offset + 8 * scale), current_time, font=small_number_font, fill=TEXT_SECONDARY)

        y_offset += 60 * scale

        # 绘制分隔线
        draw.rectangle([(content_left, y_offset), (card_width - content_left, y_offset + scale)], fill=(60, 60, 60))
        y_offset += 20 * scale
        
        # 预加载所有玩家头像
        all_players = []
        for uuid, data in server_data.items():
            all_players.extend(data.get('player_list', []))
        
        # 并行获取所有头像
        avatar_tasks = [fetch_player_avatar(name, avatar_size) for name in all_players]
        avatar_results = await asyncio.gather(*avatar_tasks, return_exceptions=True)
        
        # 构建头像映射
        avatar_map = {}
        for i, name in enumerate(all_players):
            if isinstance(avatar_results[i], Image.Image):
                avatar_map[name] = avatar_results[i]
            elif not isinstance(avatar_results[i], Exception):
                avatar_map[name] = avatar_results[i]
            else:
                avatar_map[name] = None
        
        # 绘制服务器状态
        for uuid, data in server_data.items():
            server_name = data.get('name', '未知服务器')
            player_count = data.get('player_count', 0)
            success = data.get('success', False)
            player_list = data.get('player_list', [])
            status_result = data.get('status_result', {})
            mcsm_status = status_result.get('status', '') if isinstance(status_result, dict) else ''

            # 状态指示器（调整位置避免与圆角重叠）
            status_color = SUCCESS_COLOR if success else ERROR_COLOR
            dot_x = card_padding + 5 * scale  # 向右偏移避免圆角
            draw.ellipse(
                [(dot_x, y_offset + 5 * scale), (dot_x + 10 * scale, y_offset + 15 * scale)],
                fill=status_color
            )

            # 服务器名称
            if server_font:
                draw.text((dot_x + 16 * scale, y_offset), server_name, font=server_font, fill=YELLOW_COLOR)

            # MCSM 状态文字（显示在服务器名称右侧）
            if small_font and mcsm_status:
                # 计算服务器名称宽度
                draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
                bbox = draw_temp.textbbox((0, 0), server_name, font=server_font)
                name_width = bbox[2] - bbox[0]
                status_x = dot_x + 16 * scale + name_width + 10 * scale
                # 根据状态选择颜色
                if '运行' in mcsm_status:
                    status_text_color = SUCCESS_COLOR
                elif '停止' in mcsm_status or '连接' in mcsm_status:
                    status_text_color = ERROR_COLOR
                elif '启动' in mcsm_status or '忙碌' in mcsm_status:
                    status_text_color = WARNING_COLOR
                else:
                    status_text_color = TEXT_SECONDARY
                draw.text((status_x, y_offset + 4 * scale), mcsm_status, font=small_font, fill=status_text_color)

            # 玩家数量（根据卡片宽度自适应位置，使用等宽字体）
            player_text = f"{player_count} 人"
            if number_font:
                # 使用等宽字体精确计算宽度
                draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
                bbox = draw_temp.textbbox((0, 0), player_text, font=number_font)
                player_text_width = bbox[2] - bbox[0] + 20 * scale
                player_x = card_width - card_padding - player_text_width
                draw.text((player_x, y_offset + 2 * scale), player_text, font=number_font, fill=TEXT_SECONDARY)
            
            # 玩家列表（带头像，自动布局）
            y_offset += 30 * scale  # 服务器名称行高
            
            if player_list:
                info = layout_info.get(uuid, {})
                rows = info.get('rows', [])

                for row in rows:
                    x_pos = dot_x + 6 * scale  # 玩家列表缩进对齐
                    
                    for player in row:
                        avatar = avatar_map.get(player)
                        width = draw_avatar_with_name(
                            img, avatar, player, x_pos, y_offset, player_font, avatar_size, line_height=32 * scale
                        )
                        x_pos += width + player_spacing
                    
                    y_offset += 32 * scale
        
        # 绘制总计
        y_offset += card_spacing + 5 * scale
        draw.rectangle([(content_left, y_offset), (card_width - content_left, y_offset + scale)], fill=(60, 60, 60))

        if number_font:
            total_text = f"总在线: {total_players} 人"
            draw.text((content_left, y_offset + 5 * scale), total_text, font=number_font, fill=ACCENT_COLOR)

        # 绘制一言（卡片底部）
        y_offset += 35 * scale
        draw.rectangle([(content_left, y_offset), (card_width - content_left, y_offset + scale)], fill=(60, 60, 60))
        y_offset += 10

        # 获取一言（带缓存）
        hitokoto = get_hitokoto()
        hitokoto_content = hitokoto["content"]
        hitokoto_from = hitokoto["from"]
        hitokoto_author = hitokoto["creator"]

        y_offset += 8 * scale

        if small_font and hitokoto_content:
            # 自动换行显示内容
            max_width = card_width - content_left * 2
            lines = []
            current_line = ""
            for char in hitokoto_content:
                test_line = current_line + char
                bbox = draw.textbbox((0, 0), test_line, font=small_font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = char
            if current_line:
                lines.append(current_line)

            # 绘制内容行
            for line in lines:
                draw.text((content_left, y_offset), line, font=small_font, fill=TEXT_SECONDARY)
                y_offset += 20 * scale

            # 出处单独一行，写在开头
            y_offset += 2 * scale
            if hitokoto_author:
                source_text = f"——{hitokoto_author}《{hitokoto_from}》"
            else:
                source_text = f"——《{hitokoto_from}》"
            draw.text((content_left, y_offset), source_text, font=small_font, fill=(150, 150, 150))

        # 绘制7天可靠率网格（每个服务器一行，7个方块代表7天）
        y_offset += 25 * scale
        draw.rectangle([(content_left, y_offset), (card_width - content_left, y_offset + scale)], fill=(60, 60, 60))
        y_offset += 8 * scale

        if small_font:
            draw.text((content_left, y_offset), "7天可靠率", font=small_font, fill=ACCENT_COLOR)
            y_offset += 25 * scale

            block_size = 12 * scale  # 增大方块尺寸
            block_gap = 4 * scale    # 增大间距
            name_col_width = 80 * scale
            grid_x_start = content_left + name_col_width

            # 需要绘制的服务器列表（从 server_data 和 reliability_data 合并）
            server_names = list(server_data.keys())

            for uuid in server_names:
                sdata = server_data[uuid]
                sname = sdata.get('name', uuid)

                # 服务器名
                draw.text((content_left + 5 * scale, y_offset), sname, font=small_font, fill=TEXT_SECONDARY)

                # 获取该服务器的可靠率数据
                rel_info = reliability_data.get(sname, {}) if reliability_data else {}
                reliabilities = rel_info.get("reliability", [])

                # 只取最近7天数据
                recent_7d = reliabilities[-7:] if len(reliabilities) >= 7 else reliabilities

                # 绘制7天方块
                for i in range(7):
                    bx = grid_x_start + i * (block_size + block_gap)
                    if i < len(recent_7d) and recent_7d[i] is not None:
                        rel = recent_7d[i]
                        if rel >= 95:
                            block_color = SUCCESS_COLOR
                        elif rel >= 80:
                            block_color = WARNING_COLOR
                        elif rel >= 50:
                            block_color = (255, 165, 0)  # 橙色
                        else:
                            block_color = ERROR_COLOR
                    else:
                        block_color = (60, 60, 60)  # 无数据灰色

                    draw.rounded_rectangle(
                        [(bx, y_offset + 2 * scale), (bx + block_size, y_offset + 2 * scale + block_size)],
                        radius=2 * scale,
                        fill=block_color
                    )

                # 可靠率百分比（取最近7天平均）
                recent = [r for r in recent_7d if r is not None]
                if recent:
                    avg_rel = sum(recent) / len(recent)
                    rel_text = f"{avg_rel:.0f}%"
                    rel_x = grid_x_start + 7 * (block_size + block_gap) + 5 * scale
                    rel_color = SUCCESS_COLOR if avg_rel >= 95 else WARNING_COLOR if avg_rel >= 80 else ERROR_COLOR
                    draw.text((rel_x, y_offset), rel_text, font=small_font, fill=rel_color)

                y_offset += 22 * scale  # 增加行高

            # 健康监控数据（外部API）
            if health_data and "monitors" in health_data:
                y_offset += 5 * scale
                draw.rectangle([(content_left, y_offset), (card_width - content_left, y_offset + scale)], fill=(60, 60, 60))
                y_offset += 8 * scale

                up_count = health_data.get("up", 0)
                down_count = health_data.get("down", 0)
                total_count = up_count + down_count
                reliability = (up_count / total_count * 100) if total_count > 0 else 0

                draw.text((content_left, y_offset), f"服务: {up_count}在线 {down_count}离线 ", font=small_font, fill=ACCENT_COLOR)
                y_offset += 20 * scale

                for name, info in health_data["monitors"].items():
                    is_up = info.get("up", False)
                    cn_name = HEALTH_NAME_MAP.get(name, name)

                    draw.text((content_left + 5 * scale, y_offset), cn_name, font=small_font, fill=TEXT_SECONDARY)

                    block_x = content_left + name_col_width
                    block_color = SUCCESS_COLOR if is_up else ERROR_COLOR
                    draw.rounded_rectangle(
                        [(block_x, y_offset + 2 * scale), (block_x + block_size, y_offset + 2 * scale + block_size)],
                        radius=1 * scale,
                        fill=block_color
                    )

                    status_text = "在线" if is_up else "离线"
                    status_color = SUCCESS_COLOR if is_up else ERROR_COLOR
                    draw.text((block_x + block_size + 8 * scale, y_offset), status_text, font=small_font, fill=status_color)

                    y_offset += 18 * scale

        # 转换为 bytes（高 DPI）
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', dpi=(300, 300))
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"生成状态卡片失败: {e}")
        return None


def generate_status_card(
    server_data: Dict[str, Dict[str, Any]],
    total_players: int,
    title: str = "服务器状态",
    health_data: dict = None,
    reliability_data: dict = None
) -> Optional[bytes]:
    """
    同步版本：生成服务器状态卡片图片
    """
    import concurrent.futures

    def run_async():
        return asyncio.run(generate_status_card_async(server_data, total_players, title, health_data, reliability_data))

    try:
        return asyncio.run(generate_status_card_async(server_data, total_players, title, health_data, reliability_data))
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            # 在线程池中运行，避免事件循环冲突
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async)
                return future.result(timeout=30)
        logger.error(f"同步生成状态卡片失败: {e}")
        return None
    except Exception as e:
        logger.error(f"同步生成状态卡片失败: {e}")
        return None


def generate_chart_image(
    history_data: List[Dict[str, Any]],
    title: str = "玩家数量统计",
    time_range: str = "24h"
) -> Optional[bytes]:
    """
    生成玩家数量折线图
    """
    if not _lazy_import_matplotlib():
        logger.error("matplotlib 未安装，无法生成图表")
        return None
    
    if not history_data:
        return None
    
    try:
        # 设置中文字体 - 直接注册字体文件
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, "SourceHanSansSC-Regular-2.otf")

        from matplotlib import font_manager
        if os.path.exists(font_path):
            font_manager.fontManager.addfont(font_path)
            prop = font_manager.FontProperties(fname=font_path)
            font_name = prop.get_name()
            plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
        else:
            plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 创建图表（宽度2005px，高度自适应）
        fig, ax = plt.subplots(figsize=(20.05, 10), facecolor='#121212')
        plt.subplots_adjust(bottom=0.18)  # 增加底部边距
        ax.set_facecolor('#121212')
        
        # 处理数据
        timestamps = []
        player_counts = []
        
        for item in history_data:
            if isinstance(item.get('timestamp'), (int, float)):
                dt = datetime.fromtimestamp(item['timestamp'])
            elif isinstance(item.get('timestamp'), str):
                try:
                    dt = datetime.fromisoformat(item['timestamp'])
                except ValueError:
                    continue
            else:
                continue
            
            timestamps.append(dt)
            player_counts.append(item.get('player_count', 0))
        
        if not timestamps:
            return None
        
        # 绘制折线
        ax.plot(
            timestamps, 
            player_counts, 
            color='#FFC800', 
            linewidth=2, 
            marker='o', 
            markersize=4,
            markerfacecolor='#FFD700',
            markeredgecolor='#FFC800'
        )
        
        # 填充区域
        ax.fill_between(timestamps, player_counts, alpha=0.3, color='#FFC800')
        
        # 设置样式
        ax.set_title(title, color='#FFC800', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('时间', color='#B4B4B4', fontsize=12, labelpad=10)
        ax.set_ylabel('玩家数量', color='#B4B4B4', fontsize=12)
        
        # 设置网格
        ax.grid(True, linestyle='--', alpha=0.3, color='#444444')
        
        # 设置轴颜色
        ax.spines['bottom'].set_color('#444444')
        ax.spines['top'].set_color('#121212')
        ax.spines['left'].set_color('#444444')
        ax.spines['right'].set_color('#121212')
        
        ax.tick_params(axis='x', colors='#B4B4B4')
        ax.tick_params(axis='y', colors='#B4B4B4')

        # 添加一言（带缓存）
        hitokoto = get_hitokoto()
        if hitokoto["creator"]:
            hitokoto_text = f"{hitokoto['content']} ——{hitokoto['creator']}《{hitokoto['from']}》"
        else:
            hitokoto_text = f"{hitokoto['content']} ——《{hitokoto['from']}》"
        fig.text(0.5, -0.035, hitokoto_text, ha='center', va='bottom', fontsize=10, color='#B4B4B4')
        
        # 格式化 x 轴时间
        if time_range in ['24h', '1d']:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        elif time_range in ['7d', '7days']:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator())
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # 转换为 bytes（高 DPI）
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, facecolor='#121212', edgecolor='none')
        plt.close(fig)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"生成图表失败: {e}")
        return None


def generate_max_players_card(
    history: Dict[str, int],
    query_date: Optional[str] = None
) -> Optional[bytes]:
    """
    生成历史最高人数卡片
    """
    if not PIL_AVAILABLE:
        return None
    
    try:
        card_width = 500
        card_height = 350  # 增加高度以容纳一言
        
        img = Image.new('RGB', (card_width, card_height), BG_COLOR)
        draw = ImageDraw.Draw(img)
        
        # 绘制卡片背景
        draw_rounded_rect(draw, (10, 10, card_width - 10, card_height - 10), radius=20, fill=CARD_BG_COLOR)
        
        # 获取字体
        title_font = get_title_font(24)
        value_font = get_number_font(48)  # 数字使用等宽字体
        date_font = get_number_font(16)   # 日期数字使用等宽字体
        
        # 标题
        y_offset = 40
        if title_font:
            draw.text((30, y_offset), "历史最高在线", font=title_font, fill=YELLOW_COLOR)
        
        # 日期
        y_offset += 45
        display_date = query_date or datetime.now().strftime("%Y-%m-%d")
        if date_font:
            draw.text((30, y_offset), display_date, font=date_font, fill=TEXT_SECONDARY)
        
        # 数值
        y_offset += 40
        max_players = history.get(query_date or datetime.now().strftime("%Y-%m-%d"), 0)
        if value_font:
            draw.text((30, y_offset), f"{max_players}", font=value_font, fill=ACCENT_COLOR)
            # 计算数字实际宽度来定位"人"字
            bbox = draw.textbbox((30, y_offset), f"{max_players}", font=value_font)
            text_width = bbox[2] - bbox[0]
        
        # 单位
        body_font = get_body_font(16)
        if body_font:
            draw.text((30 + text_width + 10, y_offset + 15), "人", font=body_font, fill=TEXT_SECONDARY)
        
        # 一言区域
        y_offset += 75
        draw.rectangle([(30, y_offset), (card_width - 30, y_offset + 1)], fill=(60, 60, 60))
        y_offset += 10

        # 获取一言（带缓存）
        small_font = get_body_font(12)
        hitokoto = get_hitokoto()
        if hitokoto["creator"]:
            hitokoto_text = f"{hitokoto['content']} ——{hitokoto['creator']}《{hitokoto['from']}》"
        else:
            hitokoto_text = f"{hitokoto['content']} ——《{hitokoto['from']}》"
        if small_font and hitokoto_text:
            draw.text((30, y_offset), hitokoto_text, font=small_font, fill=(150, 150, 150))
        
        # 底部装饰
        draw.rectangle([(30, card_height - 50), (card_width - 30, card_height - 48)], fill=YELLOW_COLOR)
        
        # 放大图片提高分辨率
        if SCALE_FACTOR > 1:
            new_size = (img.width * SCALE_FACTOR, img.height * SCALE_FACTOR)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 转换为 bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', dpi=(300, 300))
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"生成最高人数卡片失败: {e}")
        return None


def generate_balance_card(player_name: str, balance: float, bank_balance: float = 0.0) -> Optional[bytes]:
    """生成余额卡片图片"""
    if not PIL_AVAILABLE:
        return None

    try:
        scale = 6
        card_width = 400 * scale
        card_height = 200 * scale

        img = Image.new('RGB', (card_width, card_height), BG_COLOR)
        draw = ImageDraw.Draw(img)
        draw_rounded_rect(draw, (10 * scale, 10 * scale, card_width - 10 * scale, card_height - 10 * scale),
                          radius=18 * scale, fill=CARD_BG_COLOR)

        title_font = get_title_font(20 * scale)
        value_font = get_number_font(32 * scale)
        label_font = get_body_font(14 * scale)

        y = 30 * scale
        if title_font:
            draw.text((30 * scale, y), f"{player_name}", font=title_font, fill=YELLOW_COLOR)
        y += 45 * scale

        if label_font:
            draw.text((30 * scale, y), "现金", font=label_font, fill=TEXT_SECONDARY)
        y += 22 * scale
        if value_font:
            draw.text((30 * scale, y), f"{balance:,.2f}", font=value_font, fill=ACCENT_COLOR)
        y += 50 * scale

        if bank_balance > 0:
            if label_font:
                draw.text((30 * scale, y), "银行", font=label_font, fill=TEXT_SECONDARY)
            y += 22 * scale
            if value_font:
                draw.text((30 * scale, y), f"{bank_balance:,.2f}", font=value_font, fill=ACCENT_COLOR)
            y += 50 * scale

        # 底部装饰线
        draw.rectangle([(30 * scale, card_height - 30 * scale), (card_width - 30 * scale, card_height - 28 * scale)],
                       fill=YELLOW_COLOR)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG', dpi=(300, 300))
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        logger.error(f"生成余额卡片失败: {e}")
        return None


def generate_transactions_card(
    player_name: str,
    transactions: list,
    page: int = 1,
    total_pages: int = 1,
    total: int = 0
) -> Optional[bytes]:
    """生成交易记录卡片图片"""
    if not PIL_AVAILABLE:
        return None

    try:
        scale = 6
        card_padding = 20 * scale
        row_height = 28 * scale

        title_font = get_title_font(22 * scale)
        header_font = get_body_font(14 * scale)
        body_font = get_body_font(13 * scale)
        small_font = get_body_font(11 * scale)
        number_font = get_number_font(13 * scale)

        card_width = 580 * scale
        header_height = 55 * scale
        footer_height = 40 * scale
        table_header_height = 30 * scale
        content_height = len(transactions) * row_height
        card_height = card_padding + header_height + table_header_height + content_height + footer_height + card_padding

        img = Image.new('RGB', (card_width, card_height), BG_COLOR)
        draw = ImageDraw.Draw(img)
        draw_rounded_rect(draw, (10 * scale, 10 * scale, card_width - 10 * scale, card_height - 10 * scale),
                          radius=18 * scale, fill=CARD_BG_COLOR)

        y = card_padding

        if title_font:
            draw.text((card_padding, y), f"交易记录 - {player_name}", font=title_font, fill=YELLOW_COLOR)

        page_text = f"第{page}/{total_pages}页 共{total}条"
        if small_font:
            bbox = draw.textbbox((0, 0), page_text, font=small_font)
            page_x = card_width - card_padding - (bbox[2] - bbox[0])
            draw.text((page_x, y + 8 * scale), page_text, font=small_font, fill=TEXT_SECONDARY)

        y += header_height
        draw.rectangle([(card_padding, y), (card_width - card_padding, y + scale)], fill=(60, 60, 60))
        y += 6 * scale

        col_x = {
            "type": card_padding + 5 * scale,
            "amount": card_padding + 80 * scale,
            "target": card_padding + 220 * scale,
            "balance": card_padding + 340 * scale,
            "time": card_padding + 470 * scale,
        }
        if header_font:
            draw.text((col_x["type"], y), "类型", font=header_font, fill=TEXT_SECONDARY)
            draw.text((col_x["amount"], y), "金额", font=header_font, fill=TEXT_SECONDARY)
            draw.text((col_x["target"], y), "收款方", font=header_font, fill=TEXT_SECONDARY)
            draw.text((col_x["balance"], y), "余额", font=header_font, fill=TEXT_SECONDARY)
            draw.text((col_x["time"], y), "时间", font=header_font, fill=TEXT_SECONDARY)

        y += table_header_height

        op_icons = {"DEPOSIT": "收", "WITHDRAW": "支"}
        op_colors = {"DEPOSIT": SUCCESS_COLOR, "WITHDRAW": ERROR_COLOR}

        for t in transactions:
            op = (t.get("operation") or "").upper()
            icon = op_icons.get(op, "?")
            color = op_colors.get(op, TEXT_SECONDARY)
            amount = t.get("amount", 0)
            if op == "WITHDRAW":
                amount = -amount
            target = t.get("target") or "-"
            balance = t.get("balance", 0)
            dt = str(t.get("datetime", ""))
            if len(dt) > 16:
                dt = dt[5:16]

            if body_font:
                draw.text((col_x["type"], y), icon, font=body_font, fill=color)
            if number_font:
                draw.text((col_x["amount"], y), f"{amount:+,.2f}", font=number_font, fill=color)
            if body_font:
                draw.text((col_x["target"], y), target[:12], font=body_font, fill=TEXT_SECONDARY)
            if number_font:
                draw.text((col_x["balance"], y), f"{balance:,.0f}", font=number_font, fill=TEXT_SECONDARY)
            if small_font:
                draw.text((col_x["time"], y + 2 * scale), dt, font=small_font, fill=TEXT_SECONDARY)

            y += row_height

        y += 5 * scale
        draw.rectangle([(card_padding, y), (card_width - card_padding, y + scale)], fill=(60, 60, 60))

        if small_font:
            hint = "发送 /交易记录 [页码] 查看其他页"
            draw.text((card_padding, y + 8 * scale), hint, font=small_font, fill=(120, 120, 120))

        draw.rectangle([(card_padding, card_height - 35 * scale), (card_width - card_padding, card_height - 33 * scale)],
                       fill=YELLOW_COLOR)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG', dpi=(300, 300))
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        logger.error(f"生成交易记录卡片失败: {e}")
        return None


def generate_help_card() -> Optional[bytes]:
    """生成帮助卡片"""
    if not PIL_AVAILABLE:
        return None
    
    try:
        card_width = 500
        card_height = 520

        img = Image.new('RGB', (card_width, card_height), BG_COLOR)
        draw = ImageDraw.Draw(img)

        draw_rounded_rect(draw, (10, 10, card_width - 10, card_height - 10), radius=20, fill=CARD_BG_COLOR)

        title_font = get_title_font(24)
        cmd_font = get_body_font(16)

        y_offset = 35
        if title_font:
            draw.text((30, y_offset), "可用命令（私聊可用）", font=title_font, fill=YELLOW_COLOR)

        commands = [
            ("/s", "查询服务器状态"),
            ("/maxp [日期]", "查询历史最高人数"),
            ("/chart [时间]", "玩家数量统计图"),
            ("/daily [天数]", "每日最高在线统计"),
            ("/balance", "查询余额"),
            ("/交易记录 [页码]", "查询交易记录"),
            ("/pay @玩家 金额", "转账给玩家"),
        ]
        
        y_offset += 50
        if cmd_font:
            for cmd, desc in commands:
                draw.text((30, y_offset), cmd, font=cmd_font, fill=ACCENT_COLOR)
                draw.text((180, y_offset), desc, font=cmd_font, fill=TEXT_SECONDARY)
                y_offset += 35
        
        # 一言区域
        draw.rectangle([(30, y_offset), (card_width - 30, y_offset + 1)], fill=(60, 60, 60))
        y_offset += 10

        # 获取一言（带缓存）
        small_font = get_body_font(12)
        hitokoto = get_hitokoto()
        if hitokoto["creator"]:
            hitokoto_text = f"{hitokoto['content']} ——{hitokoto['creator']}《{hitokoto['from']}》"
        else:
            hitokoto_text = f"{hitokoto['content']} ——《{hitokoto['from']}》"
        if small_font and hitokoto_text:
            draw.text((30, y_offset), hitokoto_text, font=small_font, fill=(150, 150, 150))
        
        # 底部装饰
        draw.rectangle([(30, card_height - 50), (card_width - 30, card_height - 48)], fill=YELLOW_COLOR)
        
        # 放大图片提高分辨率
        if SCALE_FACTOR > 1:
            new_size = (img.width * SCALE_FACTOR, img.height * SCALE_FACTOR)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', dpi=(300, 300))
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"生成帮助卡片失败: {e}")
        return None