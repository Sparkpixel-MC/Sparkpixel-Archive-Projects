#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 netease-youdao/bce-embedding-base_v1 模型对 docs 目录下的所有文件进行向量化
"""

import json
import os
from pathlib import Path
import aiohttp
import asyncio
from typing import List, Dict, Any
import re
import ssl

# 加载配置
def load_config():
    config_path = Path(__file__).parent / "environment.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()

# 使用配置中的 API
API_URL = config["ai_api_url"]
API_KEY = config["ai_api_key"]
MODEL_NAME = "netease-youdao/bce-embedding-base_v1"

# 创建 SSL 上下文（禁用证书验证以兼容某些 API）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def create_embedding(session: aiohttp.ClientSession, text: str) -> List[float]:
    """
    调用嵌入 API 获取文本的向量表示
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "input": text,
        "encoding_format": "float"
    }
    
    try:
        async with session.post(API_URL.replace("/chat/completions", "/embeddings"),
                               headers=headers,
                               json=payload,
                               ssl=ssl_context,
                               timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"API 错误: {response.status} - {error_text}")
                return None
            
            result = await response.json()
            # 提取 embedding 向量
            if "data" in result and len(result["data"]) > 0:
                return result["data"][0]["embedding"]
            return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

def read_file_content(file_path: Path) -> str:
    """
    读取文件内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件失败 {file_path}: {e}")
        return None

def split_text_into_chunks(text: str, max_tokens: int = 100) -> List[str]:
    """
    将文本分成更细的段落，每个段落不超过 max_tokens 个 token
    这里用字符数近似估算 token 数（中文约 1.5 字符 = 1 token）
    """
    max_chars = int(max_tokens * 1.5)
    chunks = []
    
    # 清理文本：移除多余空白
    text = text.strip()
    if not text:
        return chunks
    
    # 先按句子分割（更细粒度）
    # 添加常见中文和英文标点作为分割点
    sentences = []
    temp = ""
    i = 0
    while i < len(text):
        char = text[i]
        temp += char
        
        # 句子结束标记
        if char in ['。', '！', '？', '.', '!', '?', '\n', '\r']:
            sentences.append(temp.strip())
            temp = ""
        i += 1
    
    if temp.strip():
        sentences.append(temp.strip())
    
    # 处理每个句子，确保不超过限制
    current_chunk = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # 如果单个句子就超过限制，按字符强制分割
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # 强制按字符分割
            for start in range(0, len(sentence), max_chars):
                chunk = sentence[start:start + max_chars]
                chunks.append(chunk)
        else:
            # 如果当前 chunk 添加后会超限
            if len(current_chunk) + len(sentence) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

def extract_title_from_yaml(text: str) -> str:
    # 匹配 title: ... 格式，支持带引号或不带引号
    match = re.search(r'^title:\s*["\']?([^"\']+?)["\']?\s*$', text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""

async def vectorize_file(session: aiohttp.ClientSession, file_path: Path) -> Dict[str, Any]:
    """
    向量化单个文件（分段处理）
    """
    print(f"正在处理文件: {file_path.name}")
    
    content = read_file_content(file_path)
    if not content:
        return None
    
    # 提取title
    title = extract_title_from_yaml(content)

    # 将文件分段（更细粒度）
    chunks = split_text_into_chunks(content, max_tokens=100)
    print(f"  分成 {len(chunks)} 个段落")
    
    embeddings = []
    failed_chunks = 0
    
    for i, chunk in enumerate(chunks, 1):
        embedding = await create_embedding(session, chunk)
        if embedding:
            embeddings.append({
                "chunk_index": i,
                "chunk_text": chunk[:100] + "..." if len(chunk) > 100 else chunk,
                "embedding": embedding
            })
            print(f"  段落 {i}/{len(chunks)} ✓")
        else:
            failed_chunks += 1
            print(f"  段落 {i}/{len(chunks)} ✗")
    
    if embeddings:
        result = {
            "file": title,  # 新增title字段
            "file_name": file_path.name,
            "file_path": str(file_path),
            "content_length": len(content),
            "total_chunks": len(chunks),
            "successful_chunks": len(embeddings),
            "failed_chunks": failed_chunks,
            "chunks": embeddings,
            "model": MODEL_NAME
        }
        print(f"✓ {file_path.name} 向量化完成: {len(embeddings)}/{len(chunks)} 段落成功")
        return result
    else:
        print(f"✗ {file_path.name} 向量化失败")
        return None

async def main():
    """
    主函数：处理 docs 目录下的所有文件
    """
    docs_dir = Path(__file__).parent / "docs"
    
    if not docs_dir.exists():
        print(f"错误: docs 目录不存在: {docs_dir}")
        return
    
    # 获取所有 markdown 文件
    md_files = list(docs_dir.glob("*.md"))
    
    if not md_files:
        print(f"错误: docs 目录下没有找到 .md 文件")
        return
    
    print(f"找到 {len(md_files)} 个文件待处理")
    print(f"使用模型: {MODEL_NAME}")
    print(f"API 地址: {API_URL}")
    print("-" * 50)
    
    results = []
    
    async with aiohttp.ClientSession() as session:
        for file_path in md_files:
            result = await vectorize_file(session, file_path)
            if result:
                results.append(result)
    
    # 保存结果
    output_file = Path(__file__).parent / "docs_embeddings.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "model": MODEL_NAME,
            "total_files": len(results),
            "files": results
        }, f, ensure_ascii=False, indent=2)
    
    print("-" * 50)
    print(f"处理完成!")
    print(f"成功向量化: {len(results)} 个文件")
    print(f"结果已保存到: {output_file}")
    
    # 显示统计信息
    if results:
        total_chunks = sum(r["total_chunks"] for r in results)
        successful_chunks = sum(r["successful_chunks"] for r in results)
        failed_chunks = sum(r["failed_chunks"] for r in results)
        print(f"总段落数: {total_chunks}")
        print(f"成功段落: {successful_chunks}")
        print(f"失败段落: {failed_chunks}")
        
        if successful_chunks > 0:
            dims = set(len(embedding["embedding"]) for r in results for embedding in r["chunks"])
            print(f"向量维度: {dims}")

if __name__ == "__main__":
    asyncio.run(main())