#!/usr/bin/env python3
"""
Excel to JSON Converter
将 Excel 文件转换为 JSON 格式，支持命令行参数和模块导入。
依赖：pandas, openpyxl（如需支持 .xlsx 格式）
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Union

try:
    import pandas as pd
except ImportError:
    print("错误：未安装 pandas 库。请执行: pip install pandas openpyxl")
    sys.exit(1)


def excel_to_json(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    sheet_name: Optional[Union[str, int]] = 0,
    orient: str = "records",
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """
    将 Excel 文件转换为 JSON 并保存。

    Args:
        input_path: 输入的 Excel 文件路径 (.xlsx, .xls)
        output_path: 输出的 JSON 文件路径
        sheet_name: 工作表名称或索引（默认第一个工作表）
        orient: JSON 格式方向，默认为 'records'（每行一个对象）
        indent: JSON 缩进空格数，设为 None 则紧凑输出
        ensure_ascii: 是否转义非 ASCII 字符
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    # 检查输入文件是否存在
    if not input_path.is_file():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    if input_path.suffix.lower() not in (".xlsx", ".xls", ".xlsm"):
        raise ValueError(f"不支持的文件类型: {input_path.suffix}，仅支持 .xlsx/.xls/.xlsm")

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 读取 Excel
        print(f"正在读取: {input_path}")
        df = pd.read_excel(input_path, sheet_name=sheet_name, dtype=str)

        # 处理缺失值：NaN -> None (JSON 中为 null)
        df = df.where(pd.notnull(df), None)

        # 转换为 JSON 字典列表
        data = df.to_dict(orient=orient)

        # 写入 JSON 文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, default=str)

        print(f"成功转换 {len(data)} 条记录")
        print(f"JSON 已保存至: {output_path}")

    except pd.errors.EmptyDataError:
        raise ValueError("Excel 文件为空或无有效数据")
    except Exception as e:
        raise RuntimeError(f"转换过程中发生错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="将 Excel 文件转换为 JSON 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s input.xlsx output.json
  %(prog)s data.xlsx result.json --sheet "Sheet2"
  %(prog)s report.xlsx out.json --orient table --indent 4
        """
    )
    parser.add_argument("input", help="输入的 Excel 文件路径")
    parser.add_argument("output", help="输出的 JSON 文件路径")
    parser.add_argument(
        "-s", "--sheet",
        default=0,
        help="工作表名称或索引（默认第一个工作表）"
    )
    parser.add_argument(
        "--orient",
        default="records",
        choices=["records", "index", "columns", "values", "table"],
        help="JSON 数据方向（默认 records：每行一个对象）"
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON 缩进空格数（默认 2，设为 0 则紧凑输出）"
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="使用 ASCII 编码转义（默认关闭，保留中文等字符）"
    )

    args = parser.parse_args()

    # 处理 sheet 参数：尝试转为整数索引
    try:
        sheet = int(args.sheet)
    except ValueError:
        sheet = args.sheet

    # 缩进为 0 时设为 None
    indent = args.indent if args.indent > 0 else None

    try:
        excel_to_json(
            input_path=args.input,
            output_path=args.output,
            sheet_name=sheet,
            orient=args.orient,
            indent=indent,
            ensure_ascii=args.ascii,
        )
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()