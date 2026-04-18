#!/usr/bin/env python3
"""
Markdown 文件递归切分工具
用法: python split_md.py <输入目录> <输出JSON路径> <最大块字符数>
"""

import json
import re
import sys
from pathlib import Path
from typing import Iterator, List, Tuple


def split_by_paragraphs(text: str, max_len: int) -> Iterator[str]:
    """
    将文本按段落切分，保证每块不超过 max_len 字符。
    若单个段落超长，则在 max_len 处硬截断。
    """
    # 按至少一个空行分隔段落（保留段落边界）
    paragraphs = re.split(r"\n\s*\n", text)

    current_chunk = ""
    for para in paragraphs:
        # 若添加本段落后不超过限制，直接加入当前块
        if len(current_chunk) + len(para) + (2 if current_chunk else 0) <= max_len:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            # 先产出已积累的块（如果有）
            if current_chunk:
                yield current_chunk
                current_chunk = ""

            # 处理超长段落：硬截断为多个块
            while len(para) > max_len:
                # 截取 max_len 字符作为一个块
                yield para[:max_len]
                para = para[max_len:]

            # 剩余部分作为新块的开头
            if para:
                current_chunk = para

    # 产出最后一块
    if current_chunk:
        yield current_chunk


def process_markdown_file(file_path: Path, max_len: int, chunk_id_start: int) -> Tuple[List[dict], int]:
    """
    处理单个 Markdown 文件，返回块字典列表和下一个可用块 ID。
    """
    chunks = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[警告] 跳过文件 {file_path} : {e}", file=sys.stderr)
        return chunks, chunk_id_start

    for chunk_text in split_by_paragraphs(content, max_len):
        # 跳过空块（理论上不会产生，但做一下保护）
        if not chunk_text.strip():
            continue
        chunks.append({
            "index": chunk_id_start,
            "content": chunk_text
        })
        chunk_id_start += 1

    return chunks, chunk_id_start


def main():
    if len(sys.argv) != 4:
        print("用法: python split_md.py <输入目录> <输出JSON路径> <最大块字符数>", file=sys.stderr)
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    try:
        max_chunk_size = int(sys.argv[3])
    except ValueError:
        print("错误: 最大块字符数必须是整数", file=sys.stderr)
        sys.exit(1)

    if not input_dir.is_dir():
        print(f"错误: 输入目录不存在或不是目录: {input_dir}", file=sys.stderr)
        sys.exit(1)

    all_chunks = []
    next_id = 1

    # 递归遍历所有 .md 文件
    for md_file in input_dir.rglob("*.md"):
        if not md_file.is_file():
            continue
        chunks, next_id = process_markdown_file(md_file, max_chunk_size, next_id)
        all_chunks.extend(chunks)

    # 写入 JSON
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        print(f"成功切分 {len(all_chunks)} 个块，输出至 {output_file}")
    except Exception as e:
        print(f"错误: 写入输出文件失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()