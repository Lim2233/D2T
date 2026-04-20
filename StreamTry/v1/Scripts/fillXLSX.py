import os
import glob
import json
import logging
import argparse
from openpyxl import load_workbook

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fill_table_from_json(worksheet, column_names, json_data, start_row=2):
    """
    根据 JSON 数据填充工作表

    :param worksheet:    openpyxl 工作表对象
    :param column_names: 第一行的列名列表
    :param json_data:    JSON 数据列表，每个元素为字典
    :param start_row:    数据填充的起始行号，默认为 2
    """
    col_key_map = {
        idx: name for idx, name in enumerate(column_names, start=1) if name is not None
    }

    for row_offset, record in enumerate(json_data):
        row_idx = start_row + row_offset
        for col_idx, key in col_key_map.items():
            if key in record:
                worksheet.cell(row=row_idx, column=col_idx, value=record[key])


class ExcelFiller:
    """单个 Excel 文件填充器"""

    def __init__(
        self,
        json_path,
        template_path,
        output_path,
        sheet_name=None,
        header_row=1,
        start_row=2
    ):
        """
        :param json_path:     JSON 数据文件路径
        :param template_path: Excel 模板文件路径
        :param output_path:   输出 Excel 文件路径
        :param sheet_name:    要处理的工作表名称，None 表示使用活动工作表
        :param header_row:    列名所在行号（从 1 开始）
        :param start_row:     数据填充的起始行号
        """
        self.json_path = json_path
        self.template_path = template_path
        self.output_path = output_path
        self.sheet_name = sheet_name
        self.header_row = header_row
        self.start_row = start_row

        self._json_data = None

    def load_json(self):
        """加载 JSON 数据，并缓存"""
        if self._json_data is None:
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    self._json_data = json.load(f)
                logger.info(f"成功加载 JSON 数据，共 {len(self._json_data)} 条记录")
            except Exception as e:
                logger.error(f"读取 JSON 文件失败：{e}")
                raise
        return self._json_data

    def run(self):
        """执行填充操作"""
        try:
            wb = load_workbook(self.template_path, data_only=True)
            ws = wb[self.sheet_name] if self.sheet_name else wb.active

            # 读取指定行的列名
            header_cells = list(ws.iter_rows(min_row=self.header_row, max_row=self.header_row, values_only=True))
            if not header_cells:
                logger.warning(f"模板文件 {self.template_path} 第 {self.header_row} 行为空，跳过")
                wb.close()
                return

            column_names = header_cells[0]
            json_data = self.load_json()

            fill_table_from_json(ws, column_names, json_data, start_row=self.start_row)

            # 确保输出目录存在
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            wb.save(self.output_path)
            logger.info(f"已填充并保存：{self.output_path}")

            wb.close()
        except Exception as e:
            logger.error(f"处理文件时出错：{e}")


def find_single_file(folder, extension, description):
    """
    在指定文件夹中查找指定扩展名的文件，要求有且仅有一个。

    :param folder:      文件夹路径
    :param extension:   文件扩展名（如 ".json", ".xlsx"）
    :param description: 用于错误提示的描述文字
    :return:            找到的唯一文件的完整路径
    """
    pattern = os.path.join(folder, f"*{extension}")
    files = glob.glob(pattern)

    if not files:
        raise FileNotFoundError(f"在文件夹 '{folder}' 中未找到 {description} 文件（{extension}）。")
    if len(files) > 1:
        raise ValueError(f"文件夹 '{folder}' 中包含多个 {description} 文件，但只允许存在一个。")
    return files[0]


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="根据 JSON 数据批量填充 Excel 模板（支持多 JSON 文件）",
        usage="python %(prog)s <数据文件夹> <模板文件夹> <输出文件夹> [选项]"
    )
    parser.add_argument("data_folder", help="存放 JSON 数据文件的文件夹（可包含多个 .json 文件）")
    parser.add_argument("template_folder", help="存放 Excel 模板的文件夹（仅一个 .xlsx 文件）")
    parser.add_argument("output_folder", help="输出文件夹路径")
    parser.add_argument("--sheet", default=None, help="工作表名称，默认使用活动工作表")
    parser.add_argument("--header-row", type=int, default=1, help="列名所在行号，默认 1")
    parser.add_argument("--start-row", type=int, default=2, help="数据填充起始行号，默认 2")

    args = parser.parse_args()

    # 检查模板文件夹中是否恰好有一个 Excel 模板文件
    try:
        template_path = find_single_file(args.template_folder, ".xlsx", "Excel 模板")
    except Exception as e:
        logger.error(str(e))
        return

    # 获取数据文件夹中所有 JSON 文件
    json_pattern = os.path.join(args.data_folder, "*.json")
    json_files = glob.glob(json_pattern)

    if not json_files:
        logger.error(f"在文件夹 '{args.data_folder}' 中未找到任何 JSON 文件。")
        return

    logger.info(f"找到 {len(json_files)} 个 JSON 文件，将依次处理...")

    # 确保输出文件夹存在
    os.makedirs(args.output_folder, exist_ok=True)

    for json_path in json_files:
        # 根据 JSON 文件名生成输出文件名（将扩展名改为 .xlsx）
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        output_path = os.path.join(args.output_folder, f"{base_name}.xlsx")

        filler = ExcelFiller(
            json_path=json_path,
            template_path=template_path,
            output_path=output_path,
            sheet_name=args.sheet,
            header_row=args.header_row,
            start_row=args.start_row
        )
        filler.run()

    logger.info("所有文件处理完毕。")


if __name__ == "__main__":
    main()