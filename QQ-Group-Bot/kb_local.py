"""本地知识库模块 - 使用本地docs_embeddings.json，支持参考链接"""
import json
import logging
import math
import re
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 缓存的嵌入数据
_embeddings_cache = None
_embeddings_path = Path(__file__).parent / "docs_embeddings.json"

# 文件名到 permalink 的映射表（当无法从文档中提取时使用）
FILENAME_TO_PERMALINK_MAP = {
    "towny plugin user guide (detailed).md": "/guide/preview/Towny/Guide-Detailed/",
    "towny plugin user guide (simple).md": "/guide/preview/Towny/Guide-Simple/",
    "mcmmo.md": "/guide/preview/MCMMO/",
}


def load_embeddings():
    """加载本地嵌入数据"""
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    
    try:
        with open(_embeddings_path, 'r', encoding='utf-8') as f:
            _embeddings_cache = json.load(f)
        
        # 统计向量数据
        total_files = _embeddings_cache.get('total_files', 0)
        total_vectors = 0
        for file_info in _embeddings_cache.get('files', []):
            total_vectors += len(file_info.get('chunks', []))
        
        model = _embeddings_cache.get('model', 'unknown')
        logger.info(f"✅ 已加载本地知识库 - {total_files} 个文件, {total_vectors} 个向量块")
        logger.info(f"   模型: {model}")
        return _embeddings_cache
    except Exception as e:
        logger.error(f"❌ 加载嵌入数据失败: {e}")
        return None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算两个向量的余弦相似度"""
    if not vec1 or not vec2:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = math.sqrt(sum(a * a for a in vec1))
    mag2 = math.sqrt(sum(b * b for b in vec2))
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    return dot_product / (mag1 * mag2)


def simple_embed(text: str) -> List[float]:
    """简单的文本嵌入 - 基于词频和长度"""
    text_lower = text.lower()
    words = text_lower.split()
    
    # 计算字符级别的特征向量（768维 - 与bce-embedding-base_v1一致）
    embedding = [0.0] * 768
    
    # 基于字符的频率分布
    char_freq = {}
    for char in text_lower:
        char_freq[char] = char_freq.get(char, 0) + 1
    
    # 将字符频率映射到向量
    for i, (char, freq) in enumerate(sorted(char_freq.items())):
        idx = (ord(char) * 31 + i) % 768
        embedding[idx] = min(1.0, freq / 10.0)
    
    # 归一化
    norm = math.sqrt(sum(x * x for x in embedding))
    if norm > 0:
        embedding = [x / norm for x in embedding]
    
    return embedding


def _extract_title(text: str) -> str:
    """从chunk_text中提取title字段
    
    Args:
        text: chunk文本内容
    
    Returns:
        title值，如果不存在返回空字符串
    """
    # 匹配 title: ... 格式，支持带引号或不带引号
    # 使用单行模式，只匹配title所在的行
    match = re.search(r'^title:\s*["\']?([^"\'\n]+?)["\']?\s*$', text, re.MULTILINE)
    if match:
        title = match.group(1).strip()
        # 确保不包含tags或permalink等其他字段标记
        if not any(keyword in title for keyword in ['tags:', 'permalink:', 'writer:', 'createTime:']):
            return title
    return ""


def _extract_permalink(text: str) -> str:
    """从chunk_text中提取permalink字段
    
    Args:
        text: chunk文本内容
    
    Returns:
        permalink值，如果不存在返回空字符串
    """
    # 匹配 permalink: /.../ 格式，只匹配单行
    match = re.search(r'^permalink:\s*(/[^\s]*)\s*$', text, re.MULTILINE)
    if match:
        return match.group(1).rstrip('/')  # 去掉末尾斜杠，保证格式统一
    return ""


def search_knowledge_base(query: str, top_k: int = 5) -> List[Dict]:
    """搜索知识库
    
    Args:
        query: 查询文本
        top_k: 返回结果数量
    
    Returns:
        匹配的文档块列表
    """
    embeddings_data = load_embeddings()
    if not embeddings_data:
        return []
    
    try:
        # 生成查询的嵌入向量
        query_embedding = simple_embed(query)
        
        # 智能提取关键词 - 优先提取英文词和有意义的词组
        query_terms = set()
        query_text = query.lower()
        
        # 1. 提取连续的英文单词（如"mcmmo"、"towny"）
        english_words = re.findall(r'[a-z]+', query_text)
        for word in english_words:
            if len(word) > 1:  # 只要长度>1的英文词
                query_terms.add(word)
        
        # 2. 提取由空格分隔的词
        for word in query_text.split():
            if len(word) > 2 or any(c.isalpha() for c in word):  # 有字母或长度>2
                query_terms.add(word)
        
        # 3. 提取整个查询（短语匹配）
        query_terms.add(query_text)
        
        logger.debug(f"查询关键词: {query_terms}")
        
        # 收集所有块和相似度
        results = []
        
        for file_info in embeddings_data.get('files', []):
            file_name = file_info.get('file_name', 'unknown')
            file_name_lower = file_name.lower()
            
            # 提取该文件的permalink和title（从第一个chunk提取）
            file_permalink = ""
            file_title = ""
            file_chunks = file_info.get('chunks', [])
            if file_chunks:
                chunk_text = file_chunks[0].get('chunk_text', '')
                file_permalink = _extract_permalink(chunk_text)
                file_title = _extract_title(chunk_text)  # 提取title
            
            # 如果chunk中没有title，用文件名去掉.md
            if not file_title:
                file_title = file_name.replace('.md', '')
            
            # 文件名匹配得分（强烈优先）
            file_match_score = 0.0
            for term in query_terms:
                if len(term) > 2 and term in file_name_lower:  # 只匹配有意义的词
                    file_match_score = 1.0
                    break
            
            for chunk in file_chunks:
                chunk_text = chunk.get('chunk_text', '')
                chunk_embedding = chunk.get('embedding', [])
                
                if not chunk_embedding or not chunk_text:
                    continue
                
                # 计算向量相似度
                vector_similarity = cosine_similarity(query_embedding, chunk_embedding)
                
                # 关键词匹配得分
                chunk_text_lower = chunk_text.lower()
                matched_terms = 0
                
                # 检查查询词是否出现在文本中（优先长词汇）
                for term in sorted(query_terms, key=len, reverse=True):
                    if len(term) > 2 and term in chunk_text_lower:  # 只计数有意义的词
                        matched_terms += 1
                
                # 关键词得分
                keyword_score = matched_terms / max(len([t for t in query_terms if len(t) > 2]), 1)
                
                # 短语完整匹配得分
                phrase_score = 0.0
                if len(query) > 2:
                    if query_text in chunk_text_lower:
                        phrase_score = 1.0
                
                # 组合多个评分 - 文件名匹配优先级最高
                if file_match_score > 0:
                    # 如果文件名匹配，大幅提升该文件的所有chunk得分
                    combined_score = (
                        vector_similarity * 0.20 +  # 向量相似度权重降低
                        keyword_score * 0.30 +      # 关键词权重
                        phrase_score * 0.25 +       # 短语匹配权重
                        file_match_score * 0.25     # 文件名匹配权重
                    )
                else:
                    combined_score = (
                        vector_similarity * 0.35 +  # 向量相似度权重
                        keyword_score * 0.40 +      # 关键词权重
                        phrase_score * 0.25         # 短语匹配权重
                    )
                
                # 包含条件：文件名匹配 或 有有意义词汇匹配 或 短语匹配
                meaningful_keywords = len([t for t in query_terms if len(t) > 2])
                if file_match_score > 0 or matched_terms > 0 or phrase_score > 0 or vector_similarity > 0.1:
                    # 获取完整的文件permalink（优先从file_info中获取，其次从chunk中提取）
                    file_permalink = file_info.get('permalink', file_permalink)
                    results.append({
                        'file': file_title,  # 保存文件的title（不是filename）
                        'file_name': file_name,  # 保存文件名供内部使用
                        'file_permalink': file_permalink,  # 保存文件的完整permalink
                        'chunk_index': chunk.get('chunk_index', 0),
                        'text': chunk_text,
                        'similarity': combined_score,
                        'vector_similarity': vector_similarity,
                        'keyword_score': keyword_score,
                        'phrase_score': phrase_score,
                        'file_match_score': file_match_score,
                        'matched_terms': matched_terms
                    })
        
        # 按相似度排序，同时考虑匹配的词数
        results.sort(key=lambda x: (x['similarity'], x['matched_terms']), reverse=True)
        
        logger.debug(f"知识库搜索: '{query}' -> {len(results)} 结果 (top {top_k})")
        
        return results[:top_k]
    
    except Exception as e:
        logger.error(f"知识库搜索失败: {e}")
        return []


def get_knowledge_answer(query: str) -> Dict:
    """获取知识库答案
    
    Args:
        query: 用户问题
    
    Returns:
        包含答案和参考资料的字典（只返回匹配率最高的60%结果）
    """
    logger.debug(f"[知识库] 开始查询: {query}")
    results = search_knowledge_base(query, top_k=9999)
    
    logger.debug(f"[知识库] 搜索结果: {len(results)} 个")
    
    if not results:
        logger.debug(f"[知识库] 未找到相关文档")
        return {"answer": "", "references": []}
    
    # 只保留匹配率最高的60%结果
    cutoff_index = max(1, int(len(results) * 0.6))
    filtered_results = results[:cutoff_index]
    
    logger.debug(f"[知识库] 筛选后: {len(filtered_results)} 个 (原始{len(results)}个, 保留60%)")
    
    # 使用第一个搜索结果作为答案
    best_result = filtered_results[0]
    
    logger.debug(f"[知识库] 最佳匹配: {best_result['file']} (相似度: {best_result['similarity']:.3f})")
    
    # 构建参考资料列表
    references = []
    for i, result in enumerate(filtered_results, 1):
        # 获取文件的title（result['file']现在就是title）
        title = result.get('file', 'unknown')
        if not title:
            # 如果没有title，用文件名去掉.md作为展示
            title = result.get('file_name', 'unknown').replace('.md', '')
        
        # 使用文件的permalink构建完整URL
        permalink = result.get('file_permalink', '')
        
        # 如果没有从chunk中提取到permalink，尝试从映射表中查找
        if not permalink:
            file_name_lower = result.get('file_name', '').lower()
            for map_file, map_permalink in FILENAME_TO_PERMALINK_MAP.items():
                if file_name_lower == map_file.lower():
                    permalink = map_permalink
                    logger.debug(f"从映射表找到 permalink: {permalink}")
                    break
        
        # 从permalink直接构建完整URL
        if permalink:
            # permalink格式: /guide/preview/mcmmo/ 或 /guide/preview/Towny/Guide-Detailed/
            # 直接拼接域名
            ref_url = f"https://docs.sparkpixel.top{permalink}"
        else:
            # 如果没有permalink，用文件名生成
            file_name = result['file'].replace('.md', '').lower()
            clean_name = re.sub(r'[^a-z0-9]+', '-', file_name).strip('-')
            ref_url = f"https://docs.sparkpixel.top/guide/preview/{clean_name}/"
        
        references.append({
            'file': title,  # 使用title而不是file_name
            'content': result['text'][:400],  # 前400个字符作为预览
            'similarity': result['similarity'],
            'url': ref_url
        })
        
        logger.debug(f"[知识库] 参考{i}: {title} -> {ref_url} (相似度: {result['similarity']:.3f})")
    
    return {
        "answer": best_result['text'][:1000],  # 截断为前1000个字符
        "references": references
    }
