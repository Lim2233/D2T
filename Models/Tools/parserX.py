import sys
import os
import pandas as pd

def extract_columns_by_template(data_path, template_path):
    """
    从数据表A中提取模板表B中指定的列，生成带"_Extracted"后缀的新文件。

    Parameters
    ----------
    data_path : str
        源数据Excel文件路径（表格A）
    template_path : str
        模板Excel文件路径（表格B，第一行为目标列名）
    """
    # ---------- 1. 读取模板文件列名 ----------
    try:
        # 只读取第一行获取列名
        template_df = pd.read_excel(template_path, header=0, nrows=1)
    except Exception as e:
        print(f"❌ 读取模板文件失败: {e}")
        return

    # 清理列名：去空格、去重、去空
    raw_columns = template_df.columns.tolist()
    template_columns = []
    seen = set()
    for col in raw_columns:
        col_clean = str(col).strip()
        if col_clean and col_clean not in seen:
            template_columns.append(col_clean)
            seen.add(col_clean)

    if not template_columns:
        print("⚠️ 模板文件中没有有效的列名，程序终止。")
        return

    # ---------- 2. 读取数据文件的列名（仅头部） ----------
    try:
        data_head = pd.read_excel(data_path, header=0, nrows=0)
    except Exception as e:
        print(f"❌ 读取数据文件失败: {e}")
        return

    data_columns = [str(col).strip() for col in data_head.columns]

    # ---------- 3. 匹配需要提取的列 ----------
    extract_cols = [col for col in template_columns if col in data_columns]
    missing_cols = [col for col in template_columns if col not in data_columns]

    if missing_cols:
        print(f"⚠️ 以下模板列在数据文件中不存在，已跳过: {missing_cols}")

    if not extract_cols:
        print("❌ 没有找到任何匹配的列，未生成输出文件。")
        return

    # ---------- 4. 读取完整数据，仅提取所需列 ----------
    try:
        df = pd.read_excel(data_path, header=0, usecols=extract_cols)
    except Exception as e:
        print(f"❌ 读取数据内容失败: {e}")
        return

    # ---------- 5. 生成输出路径并保存 ----------
    base, ext = os.path.splitext(data_path)
    if ext.lower() in ['.xlsx', '.xls']:
        output_path = f"{base}_Extracted{ext}"
    else:
        output_path = f"{data_path}_Extracted.xlsx"  # 兜底处理非标准后缀

    try:
        df.to_excel(output_path, index=False, engine='openpyxl')
        print(f"✅ 成功提取 {len(extract_cols)} 列，输出文件: {output_path}")
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")


def main():
    if len(sys.argv) != 3:
        print("用法: python extract_columns.py <数据文件A.xlsx> <模板文件B.xlsx>")
        print("示例: python extract_columns.py sales_data.xlsx column_template.xlsx")
        sys.exit(1)

    data_file = sys.argv[1]
    template_file = sys.argv[2]

    # 检查输入文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        sys.exit(1)
    if not os.path.exists(template_file):
        print(f"❌ 模板文件不存在: {template_file}")
        sys.exit(1)

    extract_columns_by_template(data_file, template_file)


if __name__ == "__main__":
    main()