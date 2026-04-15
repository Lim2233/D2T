"""
基于 LlamaIndex 和阿里百炼 (DashScope) 的混合检索 RAG 系统
支持向量检索 + 自定义 BM25 关键词检索（中文分词）
使用 RR F (Reciprocal Rank Fusion) 融合两种检索结果
"""

import os
import sys
from typing import List, Optional, Callable

# LlamaIndex 核心组件
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import (
    VectorIndexRetriever,
    QueryFusionRetriever,
    BaseRetriever,
)
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

# 百炼模型组件
from llama_index.llms.dashscope import DashScope
from llama_index.embeddings.dashscope import DashScopeEmbedding

# BM25 算法实现与中文分词工具
from rank_bm25 import BM25Okapi
import jieba


# ============================================
# 自定义 BM25 检索器（替代 LlamaIndex 原生的 BM25Retriever）
# 原因：原生版本对中文支持不理想，且依赖旧版库
# ============================================
class CustomBM25Retriever(BaseRetriever):
    """
    基于 rank_bm25 库实现的自定义 BM25 检索器，继承自 LlamaIndex BaseRetriever。
    支持自定义分词器，默认使用空格分词，但可通过 tokenizer 参数传入中文分词函数（如 jieba）。
    """

    def __init__(
        self,
        nodes: List[TextNode],
        similarity_top_k: int = 5,
        tokenizer: Optional[Callable[[str], List[str]]] = None,
    ) -> None:
        """
        初始化 BM25 检索器。

        :param nodes: 文档节点列表（从索引中提取）
        :param similarity_top_k: 返回的相关文档数量
        :param tokenizer: 分词函数，输入文本字符串，返回词语列表。默认为按空格分词。
        """
        super().__init__()
        self._nodes = nodes
        self._similarity_top_k = similarity_top_k
        # 若未提供分词器，则使用简单的空格分词（适用于英文，中文需传入 jieba.lcut）
        self._tokenizer = tokenizer or (lambda x: x.split())

        # 对每个节点的文本内容进行分词，构建语料库
        self._corpus = [self._tokenizer(node.get_content()) for node in nodes]
        # 初始化 BM25 模型
        self._bm25 = BM25Okapi(self._corpus)

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """
        核心检索方法：根据查询字符串计算 BM25 得分，返回 Top-K 节点。

        :param query_bundle: 包含查询字符串的 QueryBundle 对象
        :return: 带有相关性分数的 NodeWithScore 列表
        """
        query_str = query_bundle.query_str
        # 对查询语句进行同样的分词处理
        tokenized_query = self._tokenizer(query_str)
        # 获取每个文档的 BM25 分数
        scores = self._bm25.get_scores(tokenized_query)

        # 按分数降序排序，取前 similarity_top_k 个索引
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:self._similarity_top_k]

        # 构建返回结果
        result_nodes = []
        for idx in top_indices:
            node = self._nodes[idx]
            result_nodes.append(
                NodeWithScore(node=node, score=float(scores[idx]))
            )
        return result_nodes


# ============================================
# 系统配置类
# ============================================
class RAGConfig:
    """
    RAG 系统配置参数集中管理类。
    包含路径、模型参数、检索参数等，便于调整和扩展。
    """
    # 文档目录：存放待索引的原始文件（PDF、TXT、Markdown 等）
    DOCUMENTS_DIR = "testrun/new/RAG3/data"
    # 索引持久化目录：保存向量索引以便重复使用
    PERSIST_DIR = "testrun/new/RAG3/Index"

    # 文本分块参数
    CHUNK_SIZE = 512          # 每个文本块的最大 token 数（近似）
    CHUNK_OVERLAP = 50        # 相邻块之间的重叠 token 数，防止信息断裂

    # 检索参数
    SIMILARITY_TOP_K = 5      # 向量检索返回的候选数量
    BM25_TOP_K = 5            # BM25 检索返回的候选数量
    FUSION_TOP_K = 5          # 融合后最终返回的数量
    SIMILARITY_CUTOFF = 0.3   # 相似度阈值，低于此值的节点将被过滤（当前未启用）

    # 百炼模型配置
    LLM_MODEL = "qwen-plus"               # 对话生成模型
    EMBED_MODEL = "text-embedding-v4"     # 文本嵌入模型
    # ⚠️ 注意：API Key 不应硬编码在代码中，建议通过环境变量传入
    DASHSCOPE_API_KEY = "sk-xxxxxx"       # 实际使用时请替换或从环境变量读取


# ============================================
# 初始化全局设置
# ============================================
def initialize_settings(config: RAGConfig) -> None:
    """
    配置 LlamaIndex 的全局 Settings 对象，包括：
    - 大语言模型 (LLM)
    - 嵌入模型 (Embedding Model)
    - 文本分割器 (Text Splitter)

    :param config: 系统配置对象
    """
    # 优先从环境变量读取 API Key，若无则使用配置中的值（仅用于演示，不推荐硬编码）
    api_key = config.DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 错误：请设置环境变量 DASHSCOPE_API_KEY")
        sys.exit(1)

    # 设置 LLM（通义千问）
    Settings.llm = DashScope(
        model_name=config.LLM_MODEL,
        temperature=0.1,                     # 较低的温度使回答更确定、更少随机性
        api_key=api_key,
    )

    # 设置嵌入模型（百炼文本嵌入）
    Settings.embed_model = DashScopeEmbedding(
        model_name=config.EMBED_MODEL,
        api_key=api_key,
        embed_batch_size=10,                 # 批量嵌入大小，根据 API 限制调整
    )

    # 设置文本分割器（按句子切分，保持语义连贯）
    Settings.text_splitter = SentenceSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )

    print(f"✅ 已配置 LLM (百炼): {config.LLM_MODEL}")
    print(f"✅ 已配置嵌入模型 (百炼): {config.EMBED_MODEL}")
    print(f"✅ 文本块大小: {config.CHUNK_SIZE}, 重叠: {config.CHUNK_OVERLAP}")


# ============================================
# 索引构建与加载
# ============================================
def create_or_load_index(config: RAGConfig) -> VectorStoreIndex:
    """
    从持久化目录加载已存在的索引；若不存在，则从文档目录读取文档并创建新索引，
    随后将索引持久化到磁盘。

    :param config: 系统配置对象
    :return: 构建好的 VectorStoreIndex 实例
    """
    # 检查持久化目录是否存在且非空
    if os.path.exists(config.PERSIST_DIR) and os.listdir(config.PERSIST_DIR):
        print(f"📂 发现已有索引，正在从 '{config.PERSIST_DIR}' 加载...")
        storage_context = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        print("✅ 索引加载成功！")
    else:
        print(f"📂 正在从 '{config.DOCUMENTS_DIR}' 加载文档并创建新索引...")
        # 确保文档目录存在
        if not os.path.exists(config.DOCUMENTS_DIR):
            os.makedirs(config.DOCUMENTS_DIR)
            print(f"⚠️ 文档目录 '{config.DOCUMENTS_DIR}' 不存在，已自动创建。")
            print("   请将文档放入该目录后重新运行。")
            sys.exit(1)

        # 使用 SimpleDirectoryReader 加载目录下所有支持的文件
        documents = SimpleDirectoryReader(config.DOCUMENTS_DIR).load_data()
        if not documents:
            print(f"❌ 错误：目录 '{config.DOCUMENTS_DIR}' 中没有找到任何文档。")
            sys.exit(1)
        print(f"   已加载 {len(documents)} 个文档。")

        # 根据文档创建向量索引（会自动调用 Settings 中的嵌入模型和分割器）
        index = VectorStoreIndex.from_documents(documents)
        # 持久化索引到磁盘
        index.storage_context.persist(persist_dir=config.PERSIST_DIR)
        print(f"✅ 索引创建成功，并已保存至 '{config.PERSIST_DIR}'。")

    return index


# ============================================
# 构建混合检索查询引擎
# ============================================
def create_hybrid_query_engine(index: VectorStoreIndex, config: RAGConfig) -> RetrieverQueryEngine:
    """
    构建一个混合检索的查询引擎，包含：
    - 向量检索器（基于嵌入相似度）
    - 自定义 BM25 检索器（基于关键词匹配）
    - 使用 RR F (Reciprocal Rank Fusion) 融合两种检索结果
    - （可选）相似度后处理器过滤低相关度结果

    :param index: 已构建或加载的向量索引
    :param config: 系统配置对象
    :return: 配置好的 RetrieverQueryEngine 实例
    """
    # 1. 向量检索器：基于嵌入向量的语义相似度检索
    vector_retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=config.SIMILARITY_TOP_K,
    )

    # 2. 获取索引中的所有节点（TextNode 对象列表），用于构建 BM25 语料库
    #    注意：docstore.docs 是一个字典，键为节点ID，值为节点对象
    all_nodes = list(index.docstore.docs.values())

    # 3. 自定义 BM25 检索器，使用 jieba 进行中文分词
    bm25_retriever = CustomBM25Retriever(
        nodes=all_nodes,
        similarity_top_k=config.BM25_TOP_K,
        tokenizer=lambda text: jieba.lcut(text)   # 中文分词
    )

    # 4. 融合检索器：使用 QueryFusionRetriever 将多个检索器结果进行融合
    #    mode="reciprocal_rerank" 表示使用 RR F 算法（倒序排名融合）
    hybrid_retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=config.FUSION_TOP_K,
        num_queries=1,                  # 仅使用原始查询，不生成额外变体
        mode="reciprocal_rerank",
        use_async=False,                # 同步模式，若需提升性能可改为 True 并配合异步运行
    )

    # 5. 后处理器：根据相似度阈值过滤低质量结果（当前注释掉，可按需启用）
    postprocessor = SimilarityPostprocessor(
        similarity_cutoff=config.SIMILARITY_CUTOFF
    )

    # 6. 组装查询引擎
    query_engine = RetrieverQueryEngine.from_args(
        retriever=hybrid_retriever,
        # node_postprocessors=[postprocessor],   # 启用后处理可过滤低相关度节点
    )
    return query_engine


# ============================================
# 问答交互函数
# ============================================
def ask_question(query_engine: RetrieverQueryEngine, question: str, verbose: bool = False) -> None:
    """
    向查询引擎提问并打印回答，可选择显示详细的来源信息。

    :param query_engine: 配置好的查询引擎
    :param question: 用户输入的问题
    :param verbose: 是否显示引用来源和相关性分数
    """
    print(f"\n🤔 问题: {question}")
    print("-" * 50)

    # 执行查询
    response = query_engine.query(question)
    print(f"🤖 回答: {response}")

    # 若开启详细模式，打印检索到的来源节点信息
    if verbose and hasattr(response, 'source_nodes'):
        print("\n📚 信息来源:")
        for i, node_with_score in enumerate(response.source_nodes):
            node = node_with_score.node
            score = node_with_score.score
            # 从元数据中提取文件名，若不存在则显示“未知文档”
            file_name = node.metadata.get('file_name', '未知文档')
            if score is not None:
                print(f"  [{i+1}] {file_name} (相关度: {score:.4f})")
            else:
                print(f"  [{i+1}] {file_name} (BM25 节点，无相似度分数)")


# ============================================
# 主程序入口
# ============================================
def main() -> None:
    """主函数：启动 RAG 系统并进入交互式问答循环。"""
    print("=" * 60)
    print("🚀 LlamaIndex 混合检索 RAG 系统启动中（自定义 BM25）...")
    print("=" * 60)

    # 加载配置
    config = RAGConfig()
    # 初始化全局设置
    initialize_settings(config)
    # 创建或加载索引
    index = create_or_load_index(config)
    # 构建混合检索查询引擎
    query_engine = create_hybrid_query_engine(index, config)

    print("\n🎉 系统准备就绪！支持向量 + 关键词混合检索。")
    print("   (输入 'exit' 或 'quit' 退出，输入 'verbose' 切换详细模式)\n")

    verbose_mode = False
    while True:
        try:
            user_input = input("📝 你的问题: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ('exit', 'quit', 'q'):
                print("👋 再见！")
                break
            elif user_input.lower() == 'verbose':
                verbose_mode = not verbose_mode
                status = "开启" if verbose_mode else "关闭"
                print(f"🔍 详细模式已{status}")
                continue

            # 提问并获取回答
            ask_question(query_engine, user_input, verbose=verbose_mode)

        except KeyboardInterrupt:
            print("\n👋 检测到中断，程序退出。")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")


if __name__ == "__main__":
    main()