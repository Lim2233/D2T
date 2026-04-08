# excel_filler 模块

## 功能
从 JSON 数据文件读取记录，按列名匹配填充到指定文件夹内所有 `.xlsx` 模板，并保存到输出文件夹。

## 依赖
- `openpyxl`

## 核心类

### `ExcelFiller`
```python
ExcelFiller(json_path, input_folder, output_folder, sheet_name=None, header_row=1, start_row=2)
```
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `json_path` | str | - | JSON 文件路径，内容为对象数组 |
| `input_folder` | str | - | 模板文件夹（扫描 `*.xlsx`） |
| `output_folder` | str | - | 输出文件夹（自动创建） |
| `sheet_name` | str\|None | None | 工作表名，None 则用活动表 |
| `header_row` | int | 1 | 列名行号（从1开始） |
| `start_row` | int | 2 | 数据起始行号 |

方法：
- `run()` — 执行批量填充

## 使用示例

### Python API
```python
from excel_filler import ExcelFiller
filler = ExcelFiller(
    json_path="./data.json",
    input_folder="./templates",
    output_folder="./output"
)
filler.run()
```

### 命令行
```bash
python excel_filler.py --json data.json --input ./templates --output ./output
```

## JSON 格式要求
```json
[ {"colA": "val1", "colB": 123}, {"colA": "val2", "colB": 456} ]
```
列名与 Excel 第一行单元格内容完全匹配（区分大小写）。

## 注意事项
- 路径含反斜杠时用原始字符串：`r"C:\path"`
- 单个文件出错不中断整体流程，日志输出错误信息