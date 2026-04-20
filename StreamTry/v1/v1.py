
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


class CONFIG:
    #文件夹
    INDATA=r"StreamTry/v1/input/dataRaw"
    INTEM=r"StreamTry/v1/input/template"
    INUSER=r"StreamTry/v1/input/userInput"
    
    OUTPUT=r"StreamTry/v1/output"
    
    TEMPTIME=r"StreamTry/v1/temp/time"
    TEMPXLSX=r"StreamTry/v1/temp/XLSX"
    TEMPXLSX2=r"StreamTry/v1/temp/XLSX2"
    
    TEMPMD=r"StreamTry/v1/temp/md"
    
    TEMPFILL=r"StreamTry/v1/temp/fill"
    #脚本
    FEXTRACTIME=r"StreamTry/v1/Scripts/extractTime.py"
    FCUTTIMEXLSX=r"StreamTry/v1/Scripts/cutTimeXLSX.py"
    FCUTCOLUMNXLSX=r"StreamTry/v1/Scripts/cutColumnXLSX.py"
    FFILLXLSX=r"StreamTry/v1/Scripts/fillXLSX.py"
    FXLSX2JSON=r"StreamTry/v1/Scripts/xlsx2JSON.py"
    FD2MD=r"StreamTry/v1/Scripts/d2md.py"
    FMD2JSON=r"StreamTry/v1/Scripts/md2JSON.py"
    
    pass

config= CONFIG()

import os

def f(*args: str):
    """
    将任意数量的字符串参数按顺序用空格连接，并在前面加上 "python "。

    参数:
        *args: 可变长度的字符串参数
    """
    os.system("python " + " ".join(args))

def main():
    f(config.FEXTRACTIME,config.INUSER,config.TEMPTIME)
    f(config.FCUTTIMEXLSX,config.INDATA,config.TEMPTIME,config.TEMPXLSX)
    f(config.FCUTCOLUMNXLSX,config.TEMPXLSX,config.INTEM,config.TEMPXLSX2)
    f(config.FXLSX2JSON,config.TEMPXLSX2,config.TEMPFILL)
    
    # f(config.FD2MD)
    # f(config.FMD2JSON)
    
    
    f(config.FFILLXLSX,config.TEMPFILL,config.INTEM,config.OUTPUT)
    pass


if __name__ == "__main__":
    main()