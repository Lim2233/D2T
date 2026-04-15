import re
import argparse
from pathlib import Path
import pandas as pd


def identify_date_column(df: pd.DataFrame, sample_rows: int = 100) -> str | None:
    """
    智能识别 DataFrame 中的日期列。
    1. 优先根据列名正则匹配。
    2. 若匹配失败，尝试内容转换（抽样检测）。
    """
    # 正则匹配列名
    pattern = re.compile(r'(?i)(date|time|日期|时间)')
    for col in df.columns:
        if pattern.search(str(col)):
            return col

    # 内容推断：对每列尝试转换抽样行，检查成功率
    sample = df.head(sample_rows)
    best_col = None
    best_ratio = 0.0

    for col in df.columns:
        # 跳过全数值列（可能是时间戳），但保留 object 类型列
        if sample[col].dtype.kind in 'iufc':  # 整数、浮点数、复数
            # 数值列可能是时间戳，也尝试转换
            pass
        try:
            converted = pd.to_datetime(sample[col], errors='coerce')
            valid_ratio = converted.notna().mean()
            if valid_ratio > best_ratio:
                best_ratio = valid_ratio
                best_col = col
        except (ValueError, TypeError):
            continue

    if best_ratio >= 0.8:  # 80% 以上成功转换则采纳
        return best_col
    return None


def filter_by_date(df: pd.DataFrame, date_col: str, start_date: str, end_date: str) -> pd.DataFrame:
    """根据日期列过滤 DataFrame，保留位于 [start_date, end_date] 内的行。"""
    # 统一转换为 datetime
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    mask = (df[date_col] >= start) & (df[date_col] <= end)
    return df.loc[mask].copy()


def process_excel(file_path: Path, start_date: str, end_date: str) -> None:
    """主处理函数：读取 Excel → 识别日期列 → 过滤 → 保存新文件。"""
    # 读取所有 sheet
    with pd.ExcelFile(file_path) as xls:
        sheet_names = xls.sheet_names

    output_path = file_path.with_stem(file_path.stem + '_Processed')

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet in sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)
            if df.empty:
                df.to_excel(writer, sheet_name=sheet, index=False)
                continue

            date_col = identify_date_column(df)
            if date_col is None:
                print(f"警告：工作表 '{sheet}' 未找到日期列，将原样保存。")
                df.to_excel(writer, sheet_name=sheet, index=False)
                continue

            print(f"工作表 '{sheet}' 识别日期列：'{date_col}'")
            filtered_df = filter_by_date(df, date_col, start_date, end_date)
            filtered_df.to_excel(writer, sheet_name=sheet, index=False)

    print(f"处理完成，已生成文件：{output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='根据日期范围过滤 Excel 表格，自动识别日期列。'
    )
    parser.add_argument('file_path', type=str, help='输入 Excel 文件路径')
    parser.add_argument('start_date', type=str, help='起始日期（格式灵活，如 2024-01-01）')
    parser.add_argument('end_date', type=str, help='结束日期')
    args = parser.parse_args()

    file_path = Path(args.file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    try:
        process_excel(file_path, args.start_date, args.end_date)
    except Exception as e:
        print(f"处理失败：{e}")
        raise


if __name__ == '__main__':
    main()