#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Excel 列名语义匹配与数据提取工具

功能：
1. 从源文件夹读取所有 .xlsx 文件，忽略临时文件（如 ~$*.xlsx）。
2. 从模板文件夹读取唯一的 .xlsx 文件作为列名模板。
3. 利用 rag.embedding 函数计算列名的语义向量，通过余弦相似度进行匹配。
4. 将匹配成功（相似度 ≥ 阈值）的列数据按模板列名导出为 JSON 文件。
5. 输出 JSON 保存至指定文件夹，文件名为 {源文件名}_extracted.json。
"""

import sys
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

# 尝试导入 rag.embedding，若失败则给出明确错误提示
try:
    from rag import embedding
except ImportError as e:
    print("错误：无法导入 rag 模块中的 embedding 函数。", file=sys.stderr)
    print("请确保 rag 模块已正确安装并可导入。", file=sys.stderr)
    raise e

# ========== 可配置常量 ==========
SIMILARITY_THRESHOLD = 0.75   # 余弦相似度阈值，低于此值的列将被忽略


# ========== 工具函数 ==========

def find_single_excel(folder: str) -> str:
    """
    在指定文件夹中查找唯一的 .xlsx 文件（排除临时文件）。
    
    参数:
        folder: 文件夹路径
        
    返回:
        唯一的 .xlsx 文件完整路径
        
    异常:
        FileNotFoundError: 文件夹不存在或无 .xlsx 文件
        RuntimeError: 存在多个 .xlsx 文件
    """
    folder_path = Path(folder)
    if not folder_path.is_dir():
        raise FileNotFoundError(f"文件夹不存在: {folder}")

    # 查找所有 .xlsx 文件，排除以 ~$ 开头的临时文件
    excel_files = [
        f for f in folder_path.glob("*.xlsx")
        if not f.name.startswith("~$")
    ]
    
    if len(excel_files) == 0:
        raise FileNotFoundError(f"模板文件夹中未找到 .xlsx 文件: {folder}")
    if len(excel_files) > 1:
        raise RuntimeError(
            f"模板文件夹中存在多个 .xlsx 文件 ({len(excel_files)} 个)，"
            f"请确保只有唯一的模板文件。"
        )
    
    return str(excel_files[0])


def find_all_excel(folder: str) -> List[str]:
    """
    在指定文件夹中查找所有 .xlsx 文件（排除临时文件）。
    
    参数:
        folder: 文件夹路径
        
    返回:
        .xlsx 文件路径列表（字符串）
    """
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return []
    
    excel_files = [
        str(f) for f in folder_path.glob("*.xlsx")
        if not f.name.startswith("~$")
    ]
    return excel_files


def get_column_names(file_path: str) -> List[str]:
    """
    读取 Excel 文件首行作为列名。
    
    处理规则：
        - 保留原始顺序
        - 空值、非字符串类型均转换为字符串
        - 如果列名缺失（NaN），转为空字符串 ""
        
    参数:
        file_path: Excel 文件路径
        
    返回:
        列名字符串列表
    """
    try:
        # 只读取表头（第一行）
        df_header = pd.read_excel(file_path, nrows=0)
        raw_columns = df_header.columns.tolist()
        
        # 转换为字符串，处理 NaN 等特殊情况
        processed_columns = []
        for col in raw_columns:
            if pd.isna(col):
                processed_columns.append("")   # 空列名转为空字符串
            else:
                processed_columns.append(str(col))
        return processed_columns
    except Exception as e:
        raise RuntimeError(f"读取 Excel 列名失败: {file_path}") from e


def compute_embeddings(cols: List[str]) -> Dict[str, np.ndarray]:
    """
    为每个列名计算语义向量。
    
    参数:
        cols: 列名列表
        
    返回:
        字典 {列名: 向量数组}
        
    注意:
        若某列名为空字符串，仍会计算其向量（embedding 函数需自行处理空字符串）。
    """
    embeddings = {}
    for col in cols:
        try:
            vec = embedding(col)
            if not isinstance(vec, np.ndarray):
                vec = np.array(vec)   # 确保为 numpy 数组
            embeddings[col] = vec
        except Exception as e:
            raise RuntimeError(f"计算列名 '{col}' 的向量时出错") from e
    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    计算两个向量的余弦相似度。
    
    参数:
        a, b: 一维 numpy 数组
        
    返回:
        相似度浮点数，若范数为零则返回 0.0
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def match_columns(
    source_cols: List[str],
    source_emb: Dict[str, np.ndarray],
    template_cols: List[str],
    template_emb: Dict[str, np.ndarray],
    threshold: float
) -> Dict[str, str]:
    """
    将源列名与模板列名进行语义匹配。
    
    逻辑：
        - 每个源列独立寻找相似度最高的模板列
        - 仅当最高相似度 ≥ threshold 时才建立映射
        - 多个源列可以映射到同一个模板列
        
    参数:
        source_cols: 源文件列名列表
        source_emb: 源列名到向量的映射
        template_cols: 模板列名列表
        template_emb: 模板列名到向量的映射
        threshold: 相似度阈值
        
    返回:
        映射字典 {源列名: 匹配到的模板列名}
    """
    mapping = {}
    for src_col in source_cols:
        src_vec = source_emb[src_col]
        best_match = None
        best_sim = -1.0
        
        for tpl_col in template_cols:
            sim = cosine_similarity(src_vec, template_emb[tpl_col])
            if sim > best_sim:
                best_sim = sim
                best_match = tpl_col
                
        if best_sim >= threshold:
            mapping[src_col] = best_match
            
    return mapping


def extract_data(file_path: str, mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    从源 Excel 文件中提取数据，并按映射重命名列。
    
    参数:
        file_path: 源 Excel 文件路径
        mapping: 源列名 -> 模板列名的映射
        
    返回:
        字典列表，每个字典代表一行数据，键为模板列名，值为单元格内容
    """
    if not mapping:
        return []
    
    try:
        # 读取整个工作表
        df = pd.read_excel(file_path)
        
        # 只保留映射中存在的源列
        cols_to_keep = [col for col in mapping.keys() if col in df.columns]
        if not cols_to_keep:
            print(f"警告：文件中没有任何需要保留的列: {file_path}", file=sys.stderr)
            return []
        
        df_subset = df[cols_to_keep].copy()
        
        # 重命名列
        rename_dict = {src: tpl for src, tpl in mapping.items() if src in cols_to_keep}
        df_subset.rename(columns=rename_dict, inplace=True)
        
        # 将 NaN 替换为 None，以便 JSON 序列化为 null
        df_subset = df_subset.replace({np.nan: None, np.inf: None, -np.inf: None})
        
        # 转换为字典列表
        records = df_subset.to_dict(orient='records')
        return records
        
    except Exception as e:
        raise RuntimeError(f"提取数据时出错: {file_path}") from e


def save_json(data: List[Dict[str, Any]], output_path: str) -> None:
    """
    将数据保存为 JSON 文件。
    
    参数:
        data: 字典列表
        output_path: 输出文件路径
    """
    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def process_file(
    source_path: str,
    template_emb: Dict[str, np.ndarray],
    template_cols: List[str],
    output_dir: str,
    threshold: float
) -> bool:
    """
    处理单个源 Excel 文件：读取列名、计算向量、匹配、提取数据、保存 JSON。
    
    参数:
        source_path: 源文件路径
        template_emb: 模板列向量字典
        template_cols: 模板列名列表
        output_dir: 输出文件夹路径
        threshold: 相似度阈值
        
    返回:
        True 表示处理成功并生成了 JSON 文件，False 表示未生成（无匹配列或出错）
    """
    try:
        print(f"正在处理文件: {source_path}")
        
        # 1. 获取源文件列名
        source_cols = get_column_names(source_path)
        if not source_cols:
            print(f"警告：源文件无有效列名，跳过: {source_path}", file=sys.stderr)
            return False
        
        # 处理重复列名（保留第一个，后续忽略并警告）
        seen = set()
        unique_source_cols = []
        for col in source_cols:
            if col not in seen:
                seen.add(col)
                unique_source_cols.append(col)
            else:
                print(f"警告：源文件列名 '{col}' 重复，后续出现将被忽略", file=sys.stderr)
        source_cols = unique_source_cols
        
        # 2. 计算源列向量
        source_emb = compute_embeddings(source_cols)
        
        # 3. 列名匹配
        mapping = match_columns(source_cols, source_emb, template_cols, template_emb, threshold)
        if not mapping:
            print(f"信息：文件无任何列匹配成功，跳过: {source_path}")
            return False
        
        # 4. 提取数据
        data = extract_data(source_path, mapping)
        if not data:
            print(f"信息：提取的数据为空，跳过: {source_path}")
            return False
        
        # 5. 保存 JSON
        source_stem = Path(source_path).stem
        output_path = Path(output_dir) / f"{source_stem}_extracted.json"
        save_json(data, str(output_path))
        print(f"成功生成 JSON: {output_path} (共 {len(data)} 行, {len(mapping)} 列)")
        return True
        
    except Exception as e:
        print(f"错误：处理文件失败 {source_path}: {e}", file=sys.stderr)
        return False


# ========== 主流程 ==========

def main(source_dir: str, template_dir: str, output_dir: str) -> None:
    """
    主函数：协调整个处理流程。
    
    参数:
        source_dir: 源文件夹路径
        template_dir: 模板文件夹路径
        output_dir: 输出文件夹路径
    """
    print("=== Excel 语义提取工具启动 ===")
    print(f"源文件夹: {source_dir}")
    print(f"模板文件夹: {template_dir}")
    print(f"输出文件夹: {output_dir}")
    print(f"相似度阈值: {SIMILARITY_THRESHOLD}")
    
    # 1. 查找模板文件
    try:
        template_path = find_single_excel(template_dir)
        print(f"找到模板文件: {template_path}")
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
    
    # 2. 读取模板列名并计算向量
    try:
        template_cols = get_column_names(template_path)
        if not template_cols:
            print("错误：模板文件无有效列名", file=sys.stderr)
            sys.exit(1)
        print(f"模板列名: {template_cols}")
        
        template_emb = compute_embeddings(template_cols)
        print("模板列向量计算完成")
    except Exception as e:
        print(f"错误：处理模板文件失败: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 3. 查找所有源文件
    source_files = find_all_excel(source_dir)
    if not source_files:
        print(f"警告：源文件夹中未找到 .xlsx 文件: {source_dir}")
        sys.exit(0)
    
    print(f"找到 {len(source_files)} 个源文件")
    
    # 4. 逐个处理源文件
    success_count = 0
    for src_file in source_files:
        if process_file(src_file, template_emb, template_cols, output_dir, SIMILARITY_THRESHOLD):
            success_count += 1
    
    print(f"=== 处理完成，成功生成 {success_count} 个 JSON 文件 ===")


if __name__ == "__main__":
    # 命令行参数解析
    if len(sys.argv) != 4:
        print("用法: python excel_semantic_extractor.py <源文件夹> <模板文件夹> <输出文件夹>")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    template_dir = sys.argv[2]
    output_dir = sys.argv[3]
    
    main(source_dir, template_dir, output_dir)