
"""

处理用户需求放在temp/requirement
首先将数据全部转换成md，存在temp/md
然后将其转化成JSON ，存在temp/JSON/raw
然后清洗，根据日期进行清洗，存在temp/JSON/processed
然后进入RAG/存储再temp/RAG/...
然后处理模板，通过RAG判断相关度清洗然后放在temp/fill
调用脚本填写

"""

