
"""

处理用户需求放在temp/requirement
首先将数据 dataRaw中的全部
doc md txt 全部转换成md，存在temp/dmd
xlsx 先清洗 再转md
然后将其转化成JSON ，存在temp/JSON/raw
然后清洗，根据日期进行清洗，存在temp/JSON/processed
然后进入RAG/存储再temp/RAG/...
然后处理模板，通过RAG判断相关度清洗然后放在temp/fill
调用脚本填写

"""


# 作为模块使用
from parserD import DocumentMarkdownConverter
import os
from parserX import extract_columns_by_template

class CONFIG:
    #文件夹
    DATARAW=r"StreamTry/v1/input/dataRaw"
    TEMPLATE=r"StreamTry/v1/input/template"
    REQUIRE=r"StreamTry/v1/input/userInput"
    OUTPUT=r"StreamTry/v1/output"
    TEMP=r"StreamTry/v1/temp"
    TREQUIRE=r"StreamTry/v1/temp/requirement"
    TMD=r"StreamTry/v1/temp/dmd"
    TXL=r"StreamTry/v1/temp/dxl"
    TPROCESSED=r"StreamTry/v1/temp/JSON/processed"
    TEMPRAG=r"StreamTry/v1/temp/RAG"
    TFILL=r"StreamTry/v1/temp/fill"
    #脚本
    TIME=r"StreamTry/v1/Scripts/extractTime.py"
    CUTTIMEXLSX=r""
    pass

config= CONFIG()

def paserDataRaw():
    
    converter = DocumentMarkdownConverter(
        input_dir=config.DATARAW,
        output_dir=config.TMD,
        recursive=True,
        extensions=(".docx", ".md", ".txt")
    )

    stats = converter.convert(
        on_file_success=lambda src, dst: print(f"完成: {src} -> {dst}")
    )
    print(f"成功: {stats.success}, 失败: {stats.failed}")
    


def main():
    
    paserDataRaw()
    
    pass


if __name__ == "__main__":
    main()