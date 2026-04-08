# D2T
D2E的改进版
使用了不一样的工作流程  
之前是全部使用AI来完成的  
现在我打算先从github上找到成熟的技术再使用AI连接他们  
希望可以成功

根据《A23 竞赛执行方案》，我们需要完成的核心工作是：**构建一个能够自动理解文档内容并将关键信息转化为结构化数据的智能系统**。具体任务包括：

1. 读取多种格式的文档（Word、Excel、Markdown、TXT），并将其转换为统一的文本结构。
2. 从文本中自动识别关键信息，例如项目名称、合同金额、日期、单位名称等。
3. 根据用户提供的模板表格（Excel或Word），将这些信息自动填入对应字段，生成结构化的业务表格。
4. 在保证准确率的前提下，在规定时间内完成上述过程，满足竞赛评测指标。

为了实现这一目标，系统需划分为五个核心模块并分别开发：
- 文档解析模块：统一解析不同格式文档，输出JSON结构。
- 信息抽取模块：通过规则、实体识别模型和大语言模型三层机制抽取关键信息，存入知识池。
- 字段语义匹配模块：通过向量相似度和规则校验，将模板字段与文档中的实体匹配。
- 数据结构化与知识池：统一存储实体信息及其来源、置信度，支持快速查询。
- 自动填表模块：根据模板自动填写数据，并处理格式统一。

此外，团队还需完成系统整合、性能优化（缓存、多线程）、前端界面、测试评估、风险应对及竞赛答辩材料准备。

这份“A23 竞赛执行方案”设计了一个非常完整且具有工业参考价值的文档处理流水线。基于方案中提出的五个核心模块以及你对理论机器学习（MLE、正规方程等）和中文技术内容的偏好，我为你推荐以下业内成熟的开源方案，并将其整合为一个自动化流程。

---

## 1. 核心模块开源选型建议

针对方案中的五个模块，以下是目前业内性能最优、社区活跃度最高的开源工具组合：

### **模块 1：文档解析 (Document Parsing)**
* **推荐方案：** **Unstructured.io** 或 **Docling (IBM 开源)**
* [cite_start]**理由：** 方案要求处理 Word、Excel、Markdown 和 TXT [cite: 19][cite_start]。`Unstructured` 提供统一的 `partition` 接口，能自动识别文档结构（标题、段落、表格）并输出标准 JSON [cite: 71, 234][cite_start]。对于 Excel，它内部集成了 `pandas` [cite: 228]；对于 Word，它比 `python-docx` 更擅长保留层级信息。
* **技术点：** 建议使用 `Unstructured` 的 **Chunking策略**，将长文档切分为语义完整的块（Chunks），方便后续 LLM 处理。

### **模块 2：信息抽取 (Information Extraction, IE)**
* **推荐方案：** **PaddleNLP (UIE)** + **Qwen-2.5-7B (LLM)**
* [cite_start]**理由：** 方案采用了“三层抽取机制” [cite: 94]。
    1.  [cite_start]**规则层：** 使用 Python `re` 模块处理金额、日期等强特征字段 [cite: 96]。
    2.  [cite_start]**实体识别层：** 推荐百度开源的 **UIE (Universal Information Extraction)**，它是目前中文 NER（命名实体识别）领域效果最好的小模型，适合处理公司、人名等 [cite: 101, 246]。
    3.  [cite_start]**大模型补全层：** **Qwen-2.5-7B** 是目前中文理解能力最强的开源模型，非常适合处理复杂语义下的信息识别 [cite: 103, 248]。

### **模块 3：字段语义匹配 (Field Semantic Matching)**
* **推荐方案：** **BGE-M3 (BAAI)** + **Faiss**
* [cite_start]**理由：** 方案提出通过向量相似度判断含义是否相同 [cite: 115]。**BGE-M3** 是目前中文语义表示（Embedding）的顶尖模型。
* [cite_start]**技术点：** 将模板字段（如“项目预算”）和抽取字段（如“合同金额”）映射到同一空间，计算**余弦相似度 (Cosine Similarity)** [cite: 115, 253]。

### **模块 4：知识池与数据结构化 (Knowledge Pool)**
* **推荐方案：** **SQLite** (元数据) + **ChromaDB** (向量库)
* [cite_start]**理由：** 方案建议使用 SQLite [cite: 143] [cite_start]存储文档 ID、置信度和来源 [cite: 144-148][cite_start]。同时，引入 **ChromaDB** 存储字段向量，可以实现方案要求的“避免重复计算”和“快速查询” [cite: 172, 175]。

### **模块 5：自动填表 (Auto-filling)**
* [cite_start]**推荐方案：** **Openpyxl** [cite: 159] + **Docxtpl**
* [cite_start]**理由：** 对于 Excel，`openpyxl` 是标准方案 [cite: 159]；对于 Word 模板，推荐 `docxtpl`，它允许像写网页模板（Jinja2）一样在 Word 里预留变量占位符，填充极其稳定。

---

## 2. 自动化流程链路设计

我们将上述工具链接，构建如下系统流转路径：

1.  [cite_start]**输入层：** 用户通过 **FastAPI** [cite: 263] 上传原始文档。
2.  [cite_start]**解析层 (负责人 1)：** 调用 `Unstructured` 解析文档，清洗空格和乱码 [cite: 235]，产出统一 JSON。
3.  **抽取层 (负责人 2)：** * 先过正则（Regex）提取日期/金额。
    * 再过 UIE 模型提取单位/负责人。
    * 难点字段调用 Qwen-2.5 进行提示词工程（Prompt Engineering）抽取。
4.  [cite_start]**中枢层 (负责人 4)：** 将结果存入 SQLite。同时为抽取出的 Key（字段名）计算 BGE 向量，存入 ChromaDB 缓存 [cite: 264]。
5.  [cite_start]**匹配层 (负责人 3)：** 用户上传模板，系统提取模板表头，计算向量并在 ChromaDB 中检索相似度最高的实体 [cite: 255]。
6.  [cite_start]**输出层 (负责人 5)：** 格式化日期/金额（如 YYYY-MM-DD）[cite: 165]，使用 `openpyxl` 写入 Excel 单元格并返回下载链接。

---

## 3. 建议的 TODO List

[cite_start]按照五个负责人的角色划分 [cite: 184-188][cite_start]，以下是第一阶段（基础搭建期 [cite: 195]）的任务列表：

### **Phase 1: 基础设施 (Week 1)**
- [ ] [cite_start]**负责人 1 (文档)：** 环境配置，实现 `Unstructured` 对 `.docx` 和 `.xlsx` 的解析脚本，输出方案要求的 `paragraphs` 和 `tables` 结构 [cite: 75-81]。
- [ ] [cite_start]**负责人 4 (架构)：** 搭建 **FastAPI** 骨架，配置 **SQLite** 表结构（建立 `documents` 和 `entities` 表）[cite: 143]。
- [ ] [cite_start]**负责人 5 (前端)：** 使用 **Streamlit** (快速原型) 或 **Vue** 搭建基础的文件上传页面 [cite: 270]。

### **Phase 2: 核心算法 (Week 2)**
- [ ] **负责人 2 (抽取)：** 编写正则库；部署 **Qwen-2.5-7B** (推荐使用 vLLM 或 Ollama 加速) 进行推理测试。
- [ ] [cite_start]**负责人 3 (匹配)：** 集成 `sentence-transformers` 加载 **BGE-M3** 模型，实现字段相似度计算函数 [cite: 254]。
- [ ] [cite_start]**负责人 4 (优化)：** 实现**多线程解析**逻辑，确保多个文档上传时不会阻塞 [cite: 177, 265]。

### **Phase 3: 集成与填表 (Week 3)**
- [ ] [cite_start]**负责人 1 & 2：** 完成“知识池”数据入库逻辑，确保每个实体都有 `source_doc` 和 `confidence` 记录 [cite: 106, 141]。
- [ ] [cite_start]**负责人 5 (填表)：** 实现 `openpyxl` 写入逻辑，增加金额/日期格式化（Format Normalization）功能 [cite: 163-165]。
- [ ] [cite_start]**全员：** 进行“端到端”冒烟测试，模拟比赛流程：上传 10 份合同 $\rightarrow$ 上传 1 个汇总表模板 $\rightarrow$ 检查填充准确率 [cite: 204]。

**技术提示：** 鉴于你对深度学习架构的关注，在信息抽取模块（负责人 2），建议尝试 **RAG (Retrieval-Augmented Generation)** 模式，即先从解析文本中检索相关段落，再让 LLM 提取，这能显著降低大模型的幻觉（Hallucination）并提升置信度。


要实现基于 **Docling**、**Qwen-2.5** 和 **Docxtpl** 的最小可行性产品（MVP），核心逻辑是将非结构化文档转化为 LLM 易读的 Markdown，再通过结构化 Prompt 提取数据，最后映射到 Word 模板中。

以下是详细的执行步骤和代码逻辑架构：

---

### 第一步：环境配置与模型准备

你需要安装核心库。建议在虚拟环境中使用 Python 3.10+。

```bash
# 安装文档解析引擎
pip install docling
# 安装 Word 模板引擎
pip install docxtpl
# 建议使用 Ollama 本地运行 Qwen-2.5 (或者使用 API)
# ollama run qwen2.5:7b
```

---

### 第二步：使用 Docling 进行高保真解析

Docling 的优势在于它能将复杂的 PDF 或 Word 转换为结构化的 **Markdown**，这对大模型理解表格和层级至关重要。

**执行代码 (parser.py):**
```python
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter

def parse_document(file_path):
    converter = DocumentConverter()
    result = converter.convert(file_path)
    # 将文档转换为 Markdown，这是 LLM 最友好的格式
    md_content = result.document.export_to_markdown()
    return md_content
```

---

### 第三步：利用 Qwen-2.5 进行结构化抽取

为了保证输出能直接用于填表，我们需要强制要求 Qwen 返回 **JSON 格式**。

**Prompt 策略：**
> “你是一个专业的合同分析助手。请从以下 Markdown 文本中提取信息，并严格以 JSON 格式输出。
> 需要提取的字段包括：{'project_name': '项目名称', 'amount': '合同金额', 'date': '签署日期'}。
> 文本内容如下：{md_content}”

**执行逻辑 (extractor.py):**
```python
import json
import requests

def extract_info(text):
    prompt = f"请从以下文本中提取‘项目名称’、‘合同金额’、‘负责人’。以JSON格式返回：\n\n{text}"
    
    # 假设使用 Ollama 本地接口
    response = requests.post("http://localhost:11434/api/generate", 
                             json={
                                 "model": "qwen2.5:7b",
                                 "prompt": prompt,
                                 "stream": False,
                                 "format": "json" # 强制 JSON 输出
                             })
    return json.loads(response.json()['response'])
```

---

### 第四步：使用 Docxtpl 自动化填表

在 Word 模板（template.docx）中，你需要使用 Jinja2 语法设置占位符，例如 `{{ project_name }}`。

**执行代码 (generator.py):**
```python
from docxtpl import DocxTemplate

def fill_template(data, template_path, output_path):
    doc = DocxTemplate(template_path)
    # data 为上一步获取的 JSON 字典
    doc.render(data)
    doc.save(output_path)
```

---

### 第五步：串联自动化流水线 (MVP 主程序)

将上述环节链接成一个完整的自动化流程。

```python
def run_mvp_pipeline(input_file, template_file):
    print("🚀 正在解析文档...")
    raw_text = parse_document(input_file)
    
    print("🧠 正在提取关键信息...")
    extracted_data = extract_info(raw_text)
    print(f"提取结果: {extracted_data}")
    
    print("📝 正在生成结构化文档...")
    output_name = f"result_{extracted_data.get('project_name', 'output')}.docx"
    fill_template(extracted_data, template_file, output_name)
    
    print(f"✅ 完成！文件已保存为: {output_name}")

# 执行示例
# run_mvp_pipeline("contract_v1.pdf", "standard_template.docx")
```

---

### TODO List：从 MVP 到进阶

1.  **模板定义：** 创建一个包含 `{{ amount }}` 等占位符的 `template.docx` 作为测试样张。
2.  **Prompt 优化：** 针对“金额单位”（元/万元）编写清洗逻辑，确保 Qwen 输出的格式统一。
3.  **置信度校验：** 在 JSON 中要求 Qwen 输出一个 `confidence` 字段，对于低于 0.8 的结果标记为“人工待审核”。
4.  **异常处理：** 增加对 Docling 解析失败（如加密 PDF）的错误捕获。
5.  **批量处理：** 使用 `os.listdir` 实现文件夹内所有文档的自动循环处理。



你打算先从哪种类型的文档（如技术标书、财务报表或法律合同）开始进行第一次端到端测试？