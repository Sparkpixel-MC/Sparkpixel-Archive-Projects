"""MCP知识库客户端模块 - 支持HTTP和STDIO两种模式，MCP服务不可用时自动降级到本地KB"""
import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
import aiohttp
import ssl

logger = logging.getLogger(__name__)

# 创建 SSL 上下文（禁用证书验证以兼容某些 API）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 从config导入MCP配置
try:
    from config import (
        MCP_KB_URL, 
        MCP_KB_API_KEY, 
        MCP_KB_ENABLED,
        MCP_KB_MODE,
        MCP_KB_SERVER_PATH
    )
except ImportError as e:
    logger.warning(f"导入MCP知识库配置失败: {e}")
    MCP_KB_ENABLED = False
    MCP_KB_MODE = "http"
    MCP_KB_URL = ""
    MCP_KB_API_KEY = ""
    MCP_KB_SERVER_PATH = "./knowledge-base-mcp-server"

# 尝试导入本地KB作为备用
try:
    from kb_local import get_knowledge_answer as get_local_kb_answer
    LOCAL_KB_AVAILABLE = True
except ImportError:
    logger.warning("本地KB模块不可用，MCP服务故障时将无法查询")
    LOCAL_KB_AVAILABLE = False

# 尝试导入STDIO客户端
try:
    from mcp_stdio_client import MCPStdioClient
    STDIO_CLIENT_AVAILABLE = True
except ImportError:
    logger.warning("STDIO客户端模块不可用，无法使用STDIO模式")
    STDIO_CLIENT_AVAILABLE = False
    MCPStdioClient = None

# MCP服务健康状态缓存
_mcp_service_healthy = None
_mcp_fallback_to_local = False
_stdio_client = None  # 全局STDIO客户端实例


async def _ensure_stdio_client_started():
    """确保STDIO客户端已启动"""
    global _stdio_client
    
    if _stdio_client is None and STDIO_CLIENT_AVAILABLE and MCP_KB_SERVER_PATH:
        try:
            _stdio_client = MCPStdioClient(MCP_KB_SERVER_PATH)
            await _stdio_client.start()
            logger.info(f"[STDIO客户端] 已启动: {MCP_KB_SERVER_PATH}")
        except Exception as e:
            logger.error(f"[STDIO客户端] 启动失败: {e}")
            _stdio_client = None
            raise
    
    return _stdio_client is not None


async def _query_mcp_http(question: str, max_results: int = 5, threshold: float = 0.1) -> Optional[Dict[str, Any]]:
    """通过HTTP查询MCP知识库"""
    try:
        headers = {
            "Content-Type": "application/json",
        }
        
        # 如果配置了API Key，添加到请求头
        if MCP_KB_API_KEY:
            headers["Authorization"] = f"Bearer {MCP_KB_API_KEY}"
        
        payload = {
            "question": question,
            "max_results": max_results,
            "threshold": threshold
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                MCP_KB_URL,
                headers=headers,
                json=payload,
                ssl=ssl_context,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.warning(f"[MCP HTTP] HTTP {response.status}，尝试降级到本地KB")
                    return None
                
                data = await response.json()
                logger.info(f"[MCP HTTP] 查询成功，获得{len(data.get('references', []))}个参考")
                return data
    
    except aiohttp.ClientConnectorError as e:
        logger.warning(f"[MCP HTTP] 连接失败 - {e}，将降级到本地KB")
        return None
    except asyncio.TimeoutError:
        logger.warning("[MCP HTTP] 查询超时，将降级到本地KB")
        return None
    except Exception as e:
        logger.error(f"[MCP HTTP] 查询异常 - {e}")
        return None


async def _query_mcp_stdio(question: str, max_results: int = 5, threshold: float = 0.1) -> Optional[Dict[str, Any]]:
    """通过STDIO查询MCP知识库"""
    try:
        if not await _ensure_stdio_client_started():
            logger.warning("[MCP STDIO] 客户端启动失败，将降级到本地KB")
            return None
        
        # 调用STDIO客户端查询工具
        result = await _stdio_client._call_tool(
            "query_knowledge_base",
            {
                "question": question,
                "max_results": max_results,
                "threshold": threshold
            }
        )
        
        logger.info(f"[MCP STDIO] 查询成功，获得{len(result.get('references', []))}个参考")
        return result
    
    except Exception as e:
        logger.warning(f"[MCP STDIO] 查询失败 - {e}，将降级到本地KB")
        return None


async def query_knowledge_base(question: str, max_results: int = 5, threshold: float = 0.1) -> Optional[Dict[str, Any]]:
    """
    查询知识库获取答案
    
    查询策略：
    1. 根据配置(HTTP或STDIO)选择MCP查询模式
    2. MCP服务不可用 → 自动降级到本地KB
    3. 本地KB也不可用 → 返回None
    
    Args:
        question: 用户问题
        max_results: 最大返回结果数
        threshold: 相似度阈值
        
    Returns:
        Dict: 包含答案、参考来源等信息，查询失败返回None
    """
    global _mcp_service_healthy, _mcp_fallback_to_local
    
    # 如果已经确认MCP不可用，直接使用本地KB
    if _mcp_fallback_to_local and LOCAL_KB_AVAILABLE:
        logger.debug("[MCP降级] MCP服务已知不可用，直接使用本地KB查询")
        return _query_local_kb(question)
    
    # 尝试MCP查询
    if MCP_KB_ENABLED and MCP_KB_MODE and MCP_KB_URL:
        result = None
        
        # 根据模式选择查询方式
        if MCP_KB_MODE == "stdio":
            logger.debug("[MCP查询] 使用STDIO模式")
            result = await _query_mcp_stdio(question, max_results, threshold)
        else:
            logger.debug("[MCP查询] 使用HTTP模式")
            result = await _query_mcp_http(question, max_results, threshold)
        
        # 如果MCP查询成功，返回结果
        if result:
            _mcp_service_healthy = True
            _mcp_fallback_to_local = False
            return result
        
        # MCP查询失败，标记为不可用
        logger.warning("[MCP查询] MCP服务不可用，启用自动降级")
        _mcp_service_healthy = False
        _mcp_fallback_to_local = True
    
    # MCP未启用或未配置，尝试本地KB
    if LOCAL_KB_AVAILABLE:
        logger.debug("[MCP查询] MCP未启用，使用本地KB")
        return _query_local_kb(question)
    
    logger.warning("[MCP查询] MCP和本地KB都不可用")
    return None


def _query_local_kb(question: str) -> Optional[Dict[str, Any]]:
    """
    使用本地KB查询（备用方案）
    
    Args:
        question: 用户问题
        
    Returns:
        Dict: 标准化为MCP格式的结果
    """
    if not LOCAL_KB_AVAILABLE:
        return None
    
    try:
        logger.info(f"[本地KB] 查询: {question}")
        result = get_local_kb_answer(question)
        
        if result and result.get("answer"):
            # 转换为MCP标准格式
            mcp_result = {
                "answer": result.get("answer", ""),
                "references": []
            }
            
            # 转换参考信息
            for ref in result.get("references", []):
                mcp_result["references"].append({
                    "title": ref.get("file", "本地知识库"),
                    "similarity": ref.get("score", 0.5),
                    "content": ref.get("content", "")[:100] if ref.get("content") else "",
                    "url": ref.get("url", "")  # 保留URL链接
                })
            
            logger.info(f"[本地KB] 查询成功，返回{len(mcp_result['references'])}个参考")
            return mcp_result
        else:
            logger.debug("[本地KB] 查询无结果")
            return None
    
    except Exception as e:
        logger.error(f"[本地KB] 查询失败: {e}")
        return None


async def get_kb_answer_with_references(question: str) -> Optional[str]:
    """
    从知识库获取答案并格式化为带角标和参考链接的回复
    
    Args:
        question: 用户问题
        
    Returns:
        str: 格式化的答案，包含角标和参考链接；如果查询失败或无结果返回None
    """
    result = await query_knowledge_base(question)
    
    if not result:
        return None
    
    answer = result.get("answer", "")
    references = result.get("references", [])
    
    if not answer:
        return None
    
    # 如果有参考来源，添加角标
    if references:
        numbered_answer = f"{answer}"
        
        # 构建参考链接列表
        ref_list = []
        seen_titles = set()
        unique_refs = []
        # 去重（相同标题只保留第一个），保持原始顺序
        for ref in references:
            title = ref.get("title") or ref.get("document_id") or "未知文档"
            title_key = " ".join(title.split()).lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            unique_refs.append(ref)

        for i, ref in enumerate(unique_refs, 1):
            doc_id = ref.get("document_id", f"doc_{i}")
            title = ref.get("title", doc_id)
            similarity = ref.get("similarity", 0)
            content = ref.get("content", "")
            url = ref.get("url", "")

            ref_item = f"[{i}] {title}"
            if content:
                ref_item += f"\n    相关内容: {content[:100]}..."
            if similarity:
                ref_item += f"\n    相似度: {similarity:.2f}"
            if url:
                # 单独一行显示链接，避免被中间截断
                ref_item += f"\n    链接: {url}"

            ref_list.append(ref_item)
        
        # 组合最终回复
        if ref_list:
            final_answer = f"{numbered_answer}\n\n参考来源:\n" + "\n".join(ref_list)
            return final_answer
    
    return answer


async def check_kb_available() -> bool:
    """
    检查知识库服务是否可用
    
    检查顺序：
    1. MCP服务是否可用
    2. 本地KB是否可用
    
    Returns:
        bool: 任意知识库可用返回True，否则返回False
    """
    global _mcp_service_healthy, _mcp_fallback_to_local
    
    # 检查MCP服务
    if MCP_KB_ENABLED and MCP_KB_URL:
        try:
            result = await query_knowledge_base("测试", max_results=1)
            if result is not None:
                _mcp_service_healthy = True
                _mcp_fallback_to_local = False
                logger.info("[KB检查] MCP服务可用")
                return True
        except Exception as e:
            logger.warning(f"[KB检查] MCP服务不可用: {e}")
            _mcp_service_healthy = False
    
    # 检查本地KB
    if LOCAL_KB_AVAILABLE:
        try:
            result = _query_local_kb("测试")
            if result is not None:
                _mcp_fallback_to_local = True
                logger.info("[KB检查] 本地KB可用，将用于备用")
                return True
        except Exception as e:
            logger.error(f"[KB检查] 本地KB不可用: {e}")
    
    logger.error("[KB检查] MCP和本地KB都不可用")
    return False


def get_kb_status() -> Dict[str, Any]:
    """
    获取当前知识库状态
    
    Returns:
        Dict: 包含MCP和本地KB的状态信息
    """
    global _mcp_service_healthy, _mcp_fallback_to_local
    
    return {
        "mcp_enabled": MCP_KB_ENABLED,
        "mcp_mode": MCP_KB_MODE,
        "mcp_url": MCP_KB_URL,
        "mcp_health": _mcp_service_healthy,
        "fallback_to_local": _mcp_fallback_to_local,
        "local_kb_available": LOCAL_KB_AVAILABLE,
        "mode": "STDIO" if (MCP_KB_ENABLED and MCP_KB_MODE == "stdio" and not _mcp_fallback_to_local) else (
            "HTTP" if (MCP_KB_ENABLED and not _mcp_fallback_to_local) else (
                "LocalKB" if LOCAL_KB_AVAILABLE else "None"
            )
        )
    }
