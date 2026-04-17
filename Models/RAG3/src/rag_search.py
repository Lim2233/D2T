"""
基于 LlamaIndex 和阿里百炼 (DashScope) 的混合检索 RAG 系统
支持向量检索 + 自定义 BM25 关键词检索（中文分词）
重构为：根据关键词返回全部超过阈值的文本块及其索引信息
"""

import os
import sys
from typing import List, Optional, Callable, Dict, Union, Literal

# LlamaIndex 核心组件
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.retrievers import (
    VectorIndexRetriever,
    QueryFusionRetriever,
    BaseRetriever,
)
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

# 百炼模型组件
from llama_index.llms.dashscope import DashScope
from llama_index.embeddings.dashscope import DashScopeEmbedding

# BM25 算法实现与中文分词工具
from rank_bm25 import BM25Okapi
import jieba


# ============================================
# 自定义 BM25 检索器（支持中文分词）
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
        super().__init__()
        self._nodes = nodes
        self._similarity_top_k = similarity_top_k
        self._tokenizer = tokenizer or (lambda x: x.split())

        # 对每个节点的文本内容进行分词，构建语料库
        self._corpus = [self._tokenizer(node.get_content()) for node in nodes]
        self._bm25 = BM25Okapi(self._corpus)

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """核心检索：返回 Top-K 节点及其 BM25 分数"""
        query_str = query_bundle.query_str
        tokenized_query = self._tokenizer(query_str)
        scores = self._bm25.get_scores(tokenized_query)

        # 按分数降序排序，取前 similarity_top_k 个索引
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:self._similarity_top_k]

        result_nodes = []
        for idx in top_indices:
            node = self._nodes[idx]
            result_nodes.append(NodeWithScore(node=node, score=float(scores[idx])))
        return result_nodes

    def retrieve_all_with_scores(self, query: str) -> List[NodeWithScore]:
        """
        扩展方法：返回所有节点的 BM25 分数，不截取 Top-K。
        便于后续按阈值过滤。
        """
        tokenized_query = self._tokenizer(query)
        scores = self._bm25.get_scores(tokenized_query)
        result_nodes = []
        for idx, score in enumerate(scores):
            node = self._nodes[idx]
            result_nodes.append(NodeWithScore(node=node, score=float(score)))
        return result_nodes


# ============================================
# 系统配置类
# ============================================
class RAGConfig:
    """RAG 系统配置参数集中管理类"""
    # 文档目录
    DOCUMENTS_DIR = "testrun/new/RAG3/data"
    # 索引持久化目录
    PERSIST_DIR = "testrun/new/RAG3/Index"

    # 文本分块参数
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 50

    # 检索参数（原用于 Top-K 检索，重构后仍保留以便复用）
    SIMILARITY_TOP_K = 5
    BM25_TOP_K = 5
    FUSION_TOP_K = 5
    SIMILARITY_CUTOFF = 0.3   # 默认相似度阈值

    # 百炼模型配置
    LLM_MODEL = "qwen-plus"
    EMBED_MODEL = "text-embedding-v4"
    # API Key 建议通过环境变量设置
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-xxxxxx")


# ============================================
# 初始化全局设置
# ============================================
def initialize_settings(config: RAGConfig) -> None:
    """配置 LlamaIndex 的全局 Settings 对象"""
    api_key = config.DASHSCOPE_API_KEY
    if not api_key:
        print("❌ 错误：请设置环境变量 DASHSCOPE_API_KEY")
        sys.exit(1)

    Settings.llm = DashScope(
        model_name=config.LLM_MODEL,
        temperature=0.1,
        api_key=api_key,
    )

    Settings.embed_model = DashScopeEmbedding(
        model_name=config.EMBED_MODEL,
        api_key=api_key,
        embed_batch_size=10,
    )

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
    """加载已有索引或创建新索引"""
    if os.path.exists(config.PERSIST_DIR) and os.listdir(config.PERSIST_DIR):
        print(f"📂 发现已有索引，正在从 '{config.PERSIST_DIR}' 加载...")
        storage_context = StorageContext.from_defaults(persist_dir=config.PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        print("✅ 索引加载成功！")
    else:
        print(f"📂 正在从 '{config.DOCUMENTS_DIR}' 加载文档并创建新索引...")
        if not os.path.exists(config.DOCUMENTS_DIR):
            os.makedirs(config.DOCUMENTS_DIR)
            print(f"⚠️ 文档目录 '{config.DOCUMENTS_DIR}' 不存在，已自动创建。")
            print("   请将文档放入该目录后重新运行。")
            sys.exit(1)

        documents = SimpleDirectoryReader(config.DOCUMENTS_DIR).load_data()
        if not documents:
            print(f"❌ 错误：目录 '{config.DOCUMENTS_DIR}' 中没有找到任何文档。")
            sys.exit(1)
        print(f"   已加载 {len(documents)} 个文档。")

        index = VectorStoreIndex.from_documents(documents)
        index.storage_context.persist(persist_dir=config.PERSIST_DIR)
        print(f"✅ 索引创建成功，并已保存至 '{config.PERSIST_DIR}'。")

    return index


# ============================================
# 检索工具构建器（封装检索器初始化）
# ============================================
class RetrieverHub:
    """
    集中管理各种检索器（向量、BM25、混合），并暴露给上层调用。
    """
    def __init__(self, index: VectorStoreIndex, config: RAGConfig):
        self.index = index
        self.config = config

        # 获取所有节点（用于 BM25 语料库）
        self.all_nodes = list(index.docstore.docs.values())
        print(f"📊 索引中共有 {len(self.all_nodes)} 个文本块。")

        # 初始化向量检索器
        self.vector_retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=config.SIMILARITY_TOP_K,
        )

        # 初始化 BM25 检索器
        self.bm25_retriever = CustomBM25Retriever(
            nodes=self.all_nodes,
            similarity_top_k=config.BM25_TOP_K,
            tokenizer=lambda text: jieba.lcut(text)
        )

        # 初始化混合融合检索器（RRF）
        self.hybrid_retriever = QueryFusionRetriever(
            retrievers=[self.vector_retriever, self.bm25_retriever],
            similarity_top_k=config.FUSION_TOP_K,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
        )


# ============================================
# 核心检索函数：返回全部超过阈值的块
# ============================================
def retrieve_above_threshold(
    hub: RetrieverHub,
    query: str,
    mode: Literal["vector", "bm25", "hybrid"] = "hybrid",
    threshold: Optional[float] = None,
    config: Optional[RAGConfig] = None,
) -> List[Dict]:
    """
    根据查询词检索所有相关性分数超过阈值的文本块。

    :param hub: RetrieverHub 实例
    :param query: 用户输入的关键词或查询语句
    :param mode: 检索模式，可选 "vector"（向量相似度）、"bm25"（BM25 分数）、"hybrid"（RRF 融合分数）
    :param threshold: 分数阈值。若为 None，则使用 config.SIMILARITY_CUTOFF
    :param config: 配置对象，用于提供默认阈值
    :return: 列表，每个元素为字典，包含节点信息：
        {
            "node_id": str,
            "text": str,
            "score": float,
            "metadata": dict,
        }
    """
    if threshold is None and config is not None:
        threshold = config.SIMILARITY_CUTOFF
    elif threshold is None:
        threshold = 0.0

    result_nodes = []

    if mode == "vector":
        # 向量检索：使用原始检索器获取所有结果（设置一个很大的 top_k 以获取全部节点）
        # 注意：VectorIndexRetriever 默认只返回 top_k 个，这里通过临时修改 top_k 来实现
        top_k_original = hub.vector_retriever._similarity_top_k
        hub.vector_retriever._similarity_top_k = len(hub.all_nodes)  # 获取全部
        retrieved = hub.vector_retriever.retrieve(query)
        hub.vector_retriever._similarity_top_k = top_k_original  # 恢复原值
        # 过滤并格式化
        for node_with_score in retrieved:
            if node_with_score.score is not None and node_with_score.score >= threshold:
                result_nodes.append({
                    "node_id": node_with_score.node.node_id,
                    "text": node_with_score.node.get_content(),
                    "score": node_with_score.score,
                    "metadata": node_with_score.node.metadata,
                })

    elif mode == "bm25":
        # BM25 检索：使用自定义方法获取全部分数
        all_scored = hub.bm25_retriever.retrieve_all_with_scores(query)
        for node_with_score in all_scored:
            if node_with_score.score >= threshold:
                result_nodes.append({
                    "node_id": node_with_score.node.node_id,
                    "text": node_with_score.node.get_content(),
                    "score": node_with_score.score,
                    "metadata": node_with_score.node.metadata,
                })

    elif mode == "hybrid":
        # 混合检索：RRF 融合分数通常范围在 [0, 1] 附近，阈值较易设定
        # QueryFusionRetriever 只能返回 Top-K，为了获取全部融合分数，
        # 需要手动计算 RRF 分数，或临时设置 large top_k
        # 这里采用设置大 top_k 的方式
        top_k_original = hub.hybrid_retriever._similarity_top_k
        hub.hybrid_retriever._similarity_top_k = len(hub.all_nodes)
        retrieved = hub.hybrid_retriever.retrieve(query)
        hub.hybrid_retriever._similarity_top_k = top_k_original
        for node_with_score in retrieved:
            if node_with_score.score is not None and node_with_score.score >= threshold:
                result_nodes.append({
                    "node_id": node_with_score.node.node_id,
                    "text": node_with_score.node.get_content(),
                    "score": node_with_score.score,
                    "metadata": node_with_score.node.metadata,
                })
    else:
        raise ValueError(f"未知的检索模式: {mode}，可选 'vector', 'bm25', 'hybrid'")

    # 按分数降序排序
    result_nodes.sort(key=lambda x: x["score"], reverse=True)
    return result_nodes


# ============================================
# 主程序示例
# ============================================
def main():
    """演示如何使用重构后的检索功能"""
    print("=" * 60)
    print("🚀 LlamaIndex 关键词检索系统（返回全部超阈值块）")
    print("=" * 60)

    config = RAGConfig()
    initialize_settings(config)
    index = create_or_load_index(config)
    hub = RetrieverHub(index, config)

    # 示例查询
    queries = [
        ("向量检索示例", "vector", 0.3),
        ("BM25 检索示例", "bm25", 5.0),   # BM25 分数阈值需根据实际语料调整
        ("混合检索示例", "hybrid", 0.1),
    ]

    for desc, mode, threshold in queries:
        print(f"\n🔍 {desc} - 模式: {mode}, 阈值: {threshold}")
        query_text = input("请输入关键词或查询语句: ").strip()
        if not query_text:
            query_text = "人工智能"  # 默认示例

        results = retrieve_above_threshold(
            hub=hub,
            query=query_text,
            mode=mode,
            threshold=threshold,
            config=config,
        )

        print(f"📌 找到 {len(results)} 个相关块（分数 ≥ {threshold}）:")
        for i, res in enumerate(results[:10]):  # 只显示前10个
            file_name = res["metadata"].get("file_name", "未知文档")
            print(f"  [{i+1}] 文档: {file_name} | 分数: {res['score']:.4f}")
            print(f"       节点ID: {res['node_id']}")
            print(f"       片段: {res['text'][:100]}...")

        if len(results) > 10:
            print(f"  ... 还有 {len(results)-10} 个结果未显示")


if __name__ == "__main__":
    main()