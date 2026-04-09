# Docling Batch Converter

## 简介

批量将 `.txt`、`.xlsx`、`.docx`、`.md` 等文档转换为 Markdown 格式的 Python 模块。支持递归目录、自定义处理器、回调钩子，可集成到 ETL、RAG 预处理等自动化流水线。



## 用法

### 命令行

```bash
python docling_batch_converter.py -i ./source_docs -o ./markdown_output -r
```

| 参数 | 说明 |
|------|------|
| `-i, --input` | 输入目录 |
| `-o, --output` | 输出目录 |
| `-r, --recursive` | 递归子目录 |
| `-e, --extensions` | 扩展名（默认 `.docx .xlsx .md .txt`） |
| `--no-overwrite` | 不覆盖已有文件 |

### Python 模块

```python
from docling_batch_converter import DocumentMarkdownConverter

converter = DocumentMarkdownConverter(
    input_dir="./source_docs",
    output_dir="./markdown_output",
    recursive=True
)
stats = converter.convert()
print(f"成功: {stats.success}, 失败: {stats.failed}")
```

#### 扩展自定义格式

```python
def pdf_handler(path: Path) -> str:
    return "# PDF 内容"

converter.register_handler(".pdf", pdf_handler)
```

#### 使用回调

```python
converter.convert(
    on_file_success=lambda src, dst: print(f"完成: {src.name}")
)
```