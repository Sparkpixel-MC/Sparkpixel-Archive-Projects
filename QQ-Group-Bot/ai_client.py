"""AI客户端模块 - 调用OpenAI接口进行消息分析，通过MCP工具集成KB"""
import aiohttp
import asyncio
import json
import logging
import re
import ssl
from config import CONFIG
from mcp_kb_client import query_knowledge_base

logger = logging.getLogger(__name__)

# 创建 SSL 上下文（禁用证书验证以兼容某些 API）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 从配置中获取AI接口配置
AI_API_URL = CONFIG.get("ai_api_url", "")
AI_API_KEY = CONFIG.get("ai_api_key", "")
AI_MODEL = CONFIG.get("ai_model", "Qwen/Qwen3-8B")
AI_API_URL2 = CONFIG.get("ai_api_url2", "")
AI_API_KEY2 = CONFIG.get("ai_api_key2", "")
AI_MODEL2 = CONFIG.get("ai_model2", "qwen3-max")
AI_API_URL3 = CONFIG.get("ai_api_key3", "")
AI_API_KEY3 = CONFIG.get("ai_api_key3", "")
AI_MODEL3 = CONFIG.get("ai_model3", "openai/gpt-4.1")
PLList = CONFIG.get("pluginslist", "")


async def ai_decide_kb_needed(message: str) -> bool:
    """【MCP集成】让AI通过MCP工具来判断是否需要查询知识库
    
    流程：
    - AI 判断是否需要使用MCP工具查询知识库
    - 不是预先查询，而是AI自主决策
    - 如果AI说需要 → 返回True，由上层调用MCP查询
    - 如果AI说否 或 API失败 → 返回False
    """
    if not AI_API_URL2 or not AI_API_KEY2:
        logger.warning(f"[MCP决策] 无AI接口配置，返回False")
        return False
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY2}"
        }
        
        payload = {
            "model": AI_MODEL2,
            "messages": [
                {
                    "role": "system",
                    "content": '''你是一个《我的世界》玩法助手。你可以使用MCP工具查询知识库。

【判断标准】
查询知识库的情况（返回true）:
✅ 用户问关于插件的具体信息："MCMMO是什么?" "Towny怎么用?" "如何创建城镇?"
✅ 用户问操作步骤："怎么挖矿?" "如何升级技能?" "怎么建城镇?"
✅ 用户问游戏机制："MCMMO有哪些技能?" "Towny的地皮怎么购买?"
✅ 用户问命令："MCMMO命令是什么?" "/t 命令怎么用?"
✅ 用户问指南或教程相关内容

不查询知识库的情况（返回false）:
❌ 简单聊天或问候："你好" "谢谢" "再见"
❌ 闲聊："你叫什么名字?" "你是谁?"
❌ 询问与游戏无关的内容
❌ 表达情感或意见】
❌ 陈述句，如"群文件有投影"
【输出要求】
仅返回JSON，无任何其他内容：
{"need_kb": true} 或 {"need_kb": false}'''
                },
                {
                    "role": "user",
                    "content": f"用户消息: {message}\n\n这个问题需要查询知识库吗？只返回JSON。"
                }
            ],
            "temperature": 0.0,
            "max_tokens": 20
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                AI_API_URL2,
                headers=headers,
                json=payload,
                ssl=ssl_context,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                # 处理429频率限制
                if response.status == 429:
                    logger.warning(f"[MCP决策] API频率限制(429)，使用启发式判断")
                    return local_heuristic_kb_needed(message)
                
                # 处理其他错误
                elif response.status != 200:
                    logger.warning(f"[MCP决策] API返回错误 {response.status}，返回False")
                    return False
                
                result = await response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"].strip()
                    logger.debug(f"[MCP决策] AI返回: {content}")
                    
                    try:
                        response_data = json.loads(content)
                        need_kb = response_data.get("need_kb", False)
                        logger.info(f"[MCP决策] AI判断: need_kb={need_kb}")
                        return need_kb
                    except json.JSONDecodeError:
                        logger.warning(f"[MCP决策] JSON解析失败: {content}，返回False")
                        return False
                else:
                    logger.warning(f"[MCP决策] 无有效响应，使用启发式判断")
                    return local_heuristic_kb_needed(message)
    
    except asyncio.TimeoutError:
        logger.warning(f"[MCP决策] API超时，使用启发式判断")
        return local_heuristic_kb_needed(message)
    
    except aiohttp.ClientError as e:
        logger.warning(f"[MCP决策] 网络错误: {e}，使用启发式判断")
        return local_heuristic_kb_needed(message)
    
    except Exception as e:
        logger.error(f"[MCP决策] 未预期的错误: {e}")
        return local_heuristic_kb_needed(message)


async def check_if_kb_needed(message: str) -> bool:
    """【MCP决策】检查是否需要查询知识库
    
    流程：
    - 由AI决策是否需要查询知识库
    - 如果AI说需要 → 返回True，上层通过MCP查询
    - 如果AI说不需要 → 返回False，直接AI回答
    - 如果API出错 → 使用启发式判断
    """
    logger.info(f"[MCP决策] 检查问题: {message}")
    return await ai_decide_kb_needed(message)


async def summarize_with_ai(content: str, question: str) -> str:
    """使用AI基于知识库内容用自己话回答用户问题"""
    if not AI_API_URL2 or not AI_API_KEY2:
        return None
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY2}"
        }
        
        payload = {
            "model": AI_MODEL2,
            "messages": [
                {
                    "role": "system",
                    "content": f'''你是一个《我的世界》玩法助手，根据提供的参考资料回答用户问题。请严格遵守：

【回答规则】
- 理解参考内容后，用自己的话重新组织回答
- 必须给出具体的操作步骤和指令，不要只说概念
- 结合所有相关信息，给出完整的解决方案
- 不要直接复制原文，要用自己的表达方式
- 保持信息的准确性和完整性
- 回复要简洁明了，控制在150字以内
- 纯文本自然书写，禁用任何markdown格式
- 末尾可加1个相关emoji收尾

【示例】
原文：MCMMO是一个技能系统，玩家可以通过挖掘、战斗等活动获得经验值。每个技能都有不同的等级和奖励。
问题：MCMMO是什么？
回答：这是个技能玩法 让你通过挖掘战斗这些操作来提升能力 每个技能都有独特的奖励⚔️

原文：使用/town new命令创建城镇，需要花费500金币。创建后可以用/town claim命令圈地。
问题：如何创建城镇？
回答：先准备500金币 然后输入/town new命令加上你想要的城镇名 创建成功后用/town claim在脚下圈地🏡'''
                },
                {
                    "role": "user",
                    "content": f"用户问题：{question}\n\n参考资料：\n{content}\n\n请根据以上资料，用自己的话给出具体的操作步骤："
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1200
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                AI_API_URL2,
                headers=headers,
                json=payload,
                ssl=ssl_context,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return None
                
                result = await response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"].strip()
                return None
    except Exception as e:
        logger.error(f"AI回答失败: {e}")
        return None

async def generate_direct_ai_reply(message: str) -> str:
    """AI直接回答，不使用知识库"""
    if not AI_API_URL2 or not AI_API_KEY2:
        return None
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY2}"
        }
        
        payload = {
            "model": AI_MODEL2,
            "messages": [
                {
                    "role": "system",
                    "content": f'''你是一个《我的世界》玩法助手，只回答原版游戏及白名单插件 {PLList} 的玩法问题。请严格遵守：

【硬性规则】
⚠️ 遇到以下情况直接拒绝回答，回复固定语句："这个问题我帮不了你哦"
- 提及任何非白名单插件（如EssentialsX、OptiFine等）白名单：{PLList}
- 游戏价格/购买/服务器租赁等商业咨询
- 时事政治，宗教，色情，暴力，违法，违反公序良俗等敏感话题
- 其他游戏（如GTA、英雄联盟等）或非游戏相关问题
⚠️ 仅当问题明确属于《我的世界》原版或白名单插件玩法时才回答

【回答规范】
- 内容≤3句话，直给解决方案，不解释原理
- 纯文本自然书写，禁用任何markdown/符号列表
- 末句不加句号，可加1个相关emoji收尾
- 不回答时只输出固定拒绝语，无额外说明
- 用上1,2，3,4这种序号，序号话，合理运用换行符，优化用户呈现
- 让用户慢慢来，充分给予细心耐心'''
                },
                {
                    "role": "user",
                    "content": f"不要用markdown格式回复！用户需要关于游戏的帮助，请根据用户消息生成一个简短的回复，提供有用的信息或建议。\n用户消息：{message}"
                }
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                AI_API_URL2,
                headers=headers,
                json=payload,
                ssl=ssl_context,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return None
                
                result = await response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"].strip()
                    return f"{content}\n⚠️ 本回答由人工智能生成，生成的内容可能不准确，请自行甄辨"
                return None
    except Exception as e:
        logger.error(f"AI直接回答失败: {e}")
        return None

async def generate_ai_reply_with_kb_access(message: str) -> str:
    """AI自主处理回复，通过MCP查询知识库
    
    流程：
    1. AI判断是否需要查询知识库（通过check_if_kb_needed）
    2. 如果需要 → 通过MCP调用query_knowledge_base查询
    3. 基于KB结果用自己的话回答
    4. 如果不需要 → 直接AI回答
    """
    if not AI_API_URL2 or not AI_API_KEY2:
        return None
    
    logger.info(f"[MCP处理] 开始处理用户问题: {message}")
    
    try:
        # 让AI判断是否需要查询知识库
        kb_needed = await check_if_kb_needed(message)
        logger.info(f"[MCP处理] AI决策: {'需要' if kb_needed else '不需要'}查询KB")
        
        # 如果需要查询知识库，通过MCP查询
        if kb_needed:
            logger.info(f"[MCP处理] 通过MCP查询知识库")
            kb_result = await query_knowledge_base(message)
            
            if kb_result and kb_result.get("answer"):
                # 有KB结果，基于KB内容让AI生成回答
                logger.info(f"[MCP处理] MCP查询成功，基于KB生成回答")
                content = kb_result.get("answer", "")
                references = kb_result.get("references", [])

                answer = await summarize_with_ai(content, message)
                if answer:
                    # 添加参考信息 - 去重并使用文档链接（同样的文件名只显示一次）
                    ref_lines = []
                    if references:
                        seen_files = set()
                        unique_refs = []
                        for ref in references:
                            file_name = (ref.get("file") or ref.get("title") or "未知文档").strip()
                            # 归一化文件名以便去重（小写并去除多余空白）
                            file_key = re.sub(r"\s+", " ", file_name).lower()
                            if file_key in seen_files:
                                continue
                            seen_files.add(file_key)
                            unique_refs.append({"file": file_name, "url": ref.get("url", "")})

                        for i, r in enumerate(unique_refs, 1):
                            # 直接使用title（已经是中文名称）
                            file_title = r['file']
                            if r.get("url"):
                                # 直接使用完整URL，不破坏格式
                                ref_lines.append(f"{i}. {file_title}\n{r['url']}")
                            else:
                                ref_lines.append(f"{i}. {file_title}")
                    if ref_lines:
                        ref_info = "\n📚 参考：\n" + "\n".join(ref_lines)
                        return f"{answer}\n{ref_info}\n⚠️ 本回答由人工智能生成，生成的内容可能不准确，请自行甄辨"
                    return f"{answer}\n⚠️ 本回答由人工智能生成，生成的内容可能不准确，请自行甄辨"
                else:
                    # AI总结失败，返回原始内容
                    logger.warning(f"[MCP处理] AI总结失败，返回原始内容")
                    return f"{content}\n⚠️ 本回答由人工智能生成，生成的内容可能不准确，请自行甄辨"
            else:
                # MCP查询无结果，降级使用AI直接回答
                logger.info(f"[MCP处理] MCP查询无结果，使用AI直接回答")
                return await generate_direct_ai_reply(message)
        else:
            # AI判断不需要查询知识库，直接AI回答
            logger.info(f"[MCP处理] AI判断不需要KB，直接回答")
            return await generate_direct_ai_reply(message)
        
    except Exception as e:
        logger.error(f"[MCP处理] 处理失败: {e}", exc_info=True)
        return None

async def game_help_reply(message: str) -> str:
    """
    生成游戏相关的求助回复
    
    让AI完全自主处理，包括是否查询知识库、如何回答等
    
    Args:
        message: 用户消息内容
        
    Returns:
        str: AI生成的回复内容
    """
    if not AI_API_URL2 or not AI_API_KEY2:
        logger.warning("AI接口配置未设置，无法生成回复")
        return None
    
    try:
        # 直接让AI处理，AI会自己决定是否需要查询知识库
        # 我们给AI提供知识库查询的能力，让AI自主决定是否使用
        return await generate_ai_reply_with_kb_access(message)
        
    except Exception as e:
        logger.error(f"AI生成回复失败: {e}")
        return "抱歉，我暂时无法回答这个问题🙏"

async def detect_game_help_request(message: str) -> bool:
    """
    检测消息是否为游戏相关的求助请求
    
    Args:
        message: 用户消息内容
        
    Returns:
        bool: 如果是游戏求助返回True，否则返回False
    """
    if not AI_API_URL or not AI_API_KEY:
        logger.warning("AI接口配置未设置，跳过AI检测")
        return False
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            prompt = f"用户的这句话是一个求助，关于游戏的吗？\n用户消息：{message}"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AI_API_KEY}"
            }
            # 确保 PLList 是字符串类型
            plugins_list_str = str(PLList) if isinstance(PLList, (list, set)) else PLList
            con='''# 角色
你是一个严格的《我的世界》玩法求助检测器。仅当用户表达**明确的玩法操作疑问**时返回true，其他情况一律false。

# 核心规则（必须同时满足才返回true）
✅ TRUE 条件（三者缺一不可）：
1. 【游戏范畴】问题针对《我的世界》原版或白名单插件''' + plugins_list_str + ''' 的**游戏内玩法**（建造/红石/合成/生物/进度等）
2. 【求助信号】消息含明确疑问词或卡点表达（怎么/如何/为什么/卡住/不会/求教/求助）
3. 【操作导向】用户询问"如何完成某个游戏内动作"，而非陈述状态或要求管理操作

❌ FALSE 强制规则（满足任一条即返回false）：
• 无疑问词的陈述句（"做完了"/"还差一点"/"调了区块数量"）
• 服务器管理类（配置修改/插件启用/权限设置/区块调整）
• 模糊短语（"新手引导"/"加个检测"/"启用回来"无具体对象）
• 其他游戏讨论、价格咨询、闲聊、表情符号
• 消息长度<4字符（防误触）

# 输出规范
仅输出纯净JSON，无任何额外字符：
{"is_help_request": boolean, "reason": "6字内关键词"}

# 典型示例（基于真实误判场景）
"生存内容全做完了"          → {"is_help_request": false, "reason": "状态陈述"}
"还差一点表面工作"           → {"is_help_request": false, "reason": "状态陈述"}
"新手引导"                   → {"is_help_request": false, "reason": "无疑问词"}
"随机tp得启用回来"           → {"is_help_request": false, "reason": "管理操作"}
"我调了towny区块数量"       → {"is_help_request": false, "reason": "配置陈述"}
"建立国家能再加1000区块"    → {"is_help_request": false, "reason": "讨论陈述"}
"末影龙怎么打"               → {"is_help_request": true, "reason": "Boss求助"}
"红石中继器怎么连"          → {"is_help_request": true, "reason": "机制疑问"}'''
            
            payload = {
                "model": AI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": con
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 100
            }
            logger.debug(f"AI检测请求负载: {payload}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    AI_API_URL,
                    headers=headers,
                    json=payload,
                    ssl=ssl_context,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.error(f"AI接口请求失败: HTTP {response.status} (尝试 {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            continue
                        return False
                    
                    result = await response.json()
                    
                    # 解析响应
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"].strip()
                        logger.debug(f"AI检测结果: {content}")

                        # 尝试解析JSON响应
                        try:
                            response_data = json.loads(content)
                            is_help = response_data.get("is_help_request", False)
                            reason = response_data.get("reason", "")
                            logger.debug(f"AI检测结果: is_help_request={is_help}, reason={reason}")
                            return is_help
                        except json.JSONDecodeError:
                            # 如果JSON解析失败，回退到简单判断
                            logger.warning(f"AI返回非JSON格式，回退到简单判断: {content} (尝试 {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                continue
                            return "是" in content or "true" in content.lower()
                    else:
                        logger.error(f"AI接口返回格式错误: {result} (尝试 {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            continue
                        return False
                        
        except aiohttp.ClientError as e:
            logger.error(f"AI接口请求异常: {e} (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                continue
            return False
        except Exception as e:
            logger.error(f"AI检测失败: {e} (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                continue
            return False
    
    return False