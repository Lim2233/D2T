# 作为模块使用
from docling_batch_converter import DocumentMarkdownConverter

#填写地址即可转换所有文件
converter = DocumentMarkdownConverter(
    input_dir=r"testrun\test-parser\docus",
    output_dir=r"output",
    recursive=True,
    extensions=(".docx", ".md", ".txt", ".xlsx")
)

# # 注册 PDF 处理器（示例）
# def pdf_to_markdown(path):
#     return f"<!-- PDF 内容: {path.name} -->"

# converter.register_handler(".pdf", pdf_to_markdown)

stats = converter.convert(
    on_file_success=lambda src, dst: print(f"完成: {src} -> {dst}")
)
print(f"成功: {stats.success}, 失败: {stats.failed}")