#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP 知识库服务器 - 使用向量相似度查询本地文档
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Knowledge Base Server")

# 全局变量存储向量数据
embeddings_data = None
vectors = None
documents = []
file_metadata = {}  # 存储文件元数据（permalink等）

class QueryRequest(BaseModel):
    question: str
    max_results: int = 5
    threshold: float = 0.1

class QueryResponse(BaseModel):
    answer: str
    references: List[Dict[str, Any]]

def load_embeddings(file_path: str = "docs_embeddings.json"):
    """加载向量数据"""
    global embeddings_data, vectors, documents, file_metadata
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            embeddings_data = json.load(f)
        
        # 提取向量和文档
        vectors = []
        documents = []
        
        # 加载文件元数据（从docs目录读取）
        docs_dir = Path("docs")
        for md_file in docs_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 解析YAML frontmatter
                    lines = content.split('\n')
                    if lines[0] == '---':
                        yaml_end = lines.index('---', 1) if '---' in lines[1:] else len(lines)
                        yaml_lines = lines[1:yaml_end]
                        metadata = {}
                        for line in yaml_lines:
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()
                        file_metadata[md_file.name] = metadata
            except Exception as e:
                logger.warning(f"读取文件元数据失败 {md_file.name}: {e}")
        
        for file_data in embeddings_data.get("files", []):
            file_name = file_data.get("file_name", "")
            for chunk in file_data.get("chunks", []):
                vectors.append(chunk["embedding"])
                documents.append({
                    "file_name": file_name,
                    "chunk_index": chunk["chunk_index"],
                    "chunk_text": chunk["chunk_text"],
                    "embedding": chunk["embedding"]
                })
        
        vectors = np.array(vectors)
        logger.info(f"加载向量数据完成: {len(documents)} 个段落")
        logger.info(f"加载文件元数据: {len(file_metadata)} 个文件")
        return True
    except Exception as e:
        logger.error(f"加载向量数据失败: {e}")
        return False

def cosine_similarity_vector(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """计算余弦相似度"""
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

@app.on_event("startup")
async def startup_event():
    """启动时加载向量数据"""
    logger.info("正在加载向量数据...")
    success = load_embeddings()
    if success:
        logger.info(f"✅ 向量数据加载成功: {len(documents)} 个段落")
    else:
        logger.warning("⚠️ 向量数据加载失败，服务器将以空数据模式运行")
        logger.warning("请确保 docs_embeddings.json 文件存在且格式正确")

@app.get("/")
async def root():
    """根路径"""
    return {
        "status": "running",
        "documents_count": len(documents),
        "model": embeddings_data.get("model", "unknown") if embeddings_data else "unknown"
    }

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    查询知识库
    
    Args:
        request: 查询请求
        
    Returns:
        QueryResponse: 查询结果
    """
    if vectors is None or len(documents) == 0:
        raise HTTPException(status_code=503, detail="向量数据未加载")
    
    question = request.question
    max_results = request.max_results
    threshold = request.threshold
    
    # 这里简化处理，实际应该对问题进行向量化
    # 由于我们没有嵌入 API，我们使用简单的关键词匹配
    # 在实际应用中，应该调用嵌入 API 获取问题的向量
    
    # 简单的文本匹配作为替代
    scores = []
    question_lower = question.lower()
    
    for doc in documents:
        chunk_text = doc["chunk_text"].lower()
        file_name = doc["file_name"].lower()
        
        # 计算简单的文本相似度 - 使用包含关系
        similarity = 0
        question_words = set(question_lower.split())
        
        # 如果问题中的词在文本中出现，增加相似度
        matched_words = 0
        for word in question_words:
            if word in chunk_text:
                matched_words += 1
                similarity += 1
        
        # 如果问题中包含中文，检查是否包含在文本中
        if any('\u4e00' <= c <= '\u9fff' for c in question):
            matched_chars = 0
            for c in question:
                if '\u4e00' <= c <= '\u9fff' and c in chunk_text:
                    matched_chars += 1
            similarity += matched_chars * 0.5
        
        # 归一化相似度
        total_possible = max(len(question_words), 1)
        similarity = similarity / total_possible
        
        # 如果文件名中包含问题关键词，大幅提高相似度
        filename_match_bonus = 0
        for word in question_words:
            if word in file_name:
                filename_match_bonus += 2.0  # 文件名匹配给予很高权重
        similarity += filename_match_bonus
        
        # 只有当匹配度足够高时才记录
        # 如果文件名匹配，可以降低整体要求；否则需要更高的文本匹配度
        min_similarity = 0.3 if filename_match_bonus > 0 else 0.5
        if similarity > min_similarity:
            scores.append((doc, similarity))
    
    # 排序并过滤
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # 选择最相关的结果，只返回相关性高的
    results = []
    for doc, score in scores[:max_results]:
        # 提高相关性阈值，确保返回的是真正相关的结果
        if score >= 0.5:
            # 提取文件元数据
            metadata = file_metadata.get(doc['file_name'], {})
            permalink = metadata.get('permalink', '')
            
            # 构建参考链接
            if permalink:
                # 移除开头的 / 和末尾的 /
                permalink_clean = permalink.strip('/')
                ref_url = f"https://docs.sparkpixel.top/{permalink_clean}"
            else:
                ref_url = f"document:{doc['file_name']}"
            
            results.append({
                "document_id": f"{doc['file_name']}_{doc['chunk_index']}",
                "title": metadata.get('title', doc['file_name']),
                "content": doc['chunk_text'],
                "similarity": score,
                "url": ref_url
            })
    
    # 记录匹配结果用于调试
    logger.info(f"查询 '{question}' 匹配到 {len(results)} 个结果 (阈值0.5)")
    if results:
        logger.info(f"Top 结果: {results[0]['title']} (相似度: {results[0]['similarity']:.2f})")
    if len(scores) > 0:
        logger.info(f"最高匹配: {scores[0][0]['file_name']} (分数: {scores[0][1]:.2f})")
    
    if not results:
        # 如果没有匹配结果，返回空
        return QueryResponse(answer="", references=[])
    
    # 生成答案（直接返回最相关的内容作为原文）
    top_result = results[0]
    answer = top_result["content"]
    
    # 添加参考脚注
    reference_footnote = f"\n\n📚 参考: [1]{top_result['title']} - {top_result['url']}"
    
    return QueryResponse(
        answer=answer + reference_footnote,
        references=results
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "documents_count": len(documents) if documents else 0,
        "vectors_loaded": vectors is not None
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Knowledge Base Server")
    parser.add_argument("--port", type=int, default=9000, help="Server port (default: 9000)")
    args = parser.parse_args()
    
    # 加载向量数据
    if not load_embeddings():
        logger.error("无法启动服务器：向量数据加载失败")
        logger.error("请确保 docs_embeddings.json 文件存在且格式正确")
        # 不直接退出，而是启动一个空的服务器
        logger.warning("服务器将以空数据模式启动")
    
    # 启动服务器
    uvicorn.run(app, host="0.0.0.0", port=args.port)