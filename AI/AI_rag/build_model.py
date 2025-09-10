import json
import os

import tiktoken
from dotenv import load_dotenv
from langchain.document_loaders import JSONLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

load_dotenv()

# 设置API密钥
DASHSCOPE_API_KEY = os.environ["OPENAI_API_KEY"]


def count_tokens(text: str) -> int:
    """使用tiktoken精确计算文本token数"""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def safe_split_documents(documents, max_tokens=1900):
    """确保分割后的文档不超过token限制"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,  # 从800增加到1200，减少分割碎片
        chunk_overlap=200,  # 从150增加到200，增强上下文连贯性
        length_function=count_tokens,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )

    splits = []
    for doc in documents:
        if not doc.page_content.strip():  # 跳过空内容
            continue

        chunks = text_splitter.split_documents([doc])
        for chunk in chunks:
            token_count = count_tokens(chunk.page_content)
            if token_count > max_tokens:
                # 如果单个chunk仍然超过限制，则进一步分割
                start = 0
                while start < len(chunk.page_content):
                    end = min(start + 500, len(chunk.page_content))
                    sub_chunk = chunk.page_content[start:end]
                    new_doc = Document(page_content=sub_chunk, metadata=chunk.metadata)
                    splits.append(new_doc)
                    start = end
            else:
                splits.append(chunk)
    return splits


def load_json_to_splittext(file_path: str):
    """加载文档，支持文本和预处理后的JSON格式"""
    if file_path.endswith(".txt"):
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()
        return safe_split_documents(docs)

    elif file_path.endswith(".json"):
        # 加载预处理后的JSON数据
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                docs = []

                # 处理不同格式的预处理数据
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str):
                            # 字符串数组格式
                            docs.append(Document(page_content=item, metadata={}))
                        elif isinstance(item, dict):
                            # 对象数组格式
                            content = (
                                item.get("content_text")
                                or item.get("content")
                                or str(item)
                            )
                            # 移除内容字段，其余作为metadata
                            metadata = {
                                k: v
                                for k, v in item.items()
                                if k not in ["content_text", "content"]
                            }
                            docs.append(
                                Document(page_content=content, metadata=metadata)
                            )
                elif isinstance(data, dict):
                    # 单个对象格式
                    content = (
                        data.get("content_text") or data.get("content") or str(data)
                    )
                    metadata = {
                        k: v
                        for k, v in data.items()
                        if k not in ["content_text", "content"]
                    }
                    docs.append(Document(page_content=content, metadata=metadata))

                print(f"成功加载 {len(docs)} 个文档")
                return safe_split_documents(docs)

        except Exception as e:
            print(f"JSON加载失败: {e}")
            raise ValueError(f"无法加载JSON文件 {file_path}: {e}")

    else:
        raise ValueError("不支持的文档格式，仅支持.txt和.json")


def create_vector_db(documents, persist_dir: str):
    """创建并持久化向量数据库"""
    # 创建嵌入模型
    embedding = DashScopeEmbeddings(
        model="text-embedding-v1", dashscope_api_key=DASHSCOPE_API_KEY
    )

    try:
        # 创建并持久化向量数据库
        db = Chroma.from_documents(documents, embedding, persist_directory=persist_dir)
        db.persist()
        print(f"向量数据库已保存到 {persist_dir}")
        return db
    except Exception as e:
        print(f"创建向量数据库失败: {e}")
        print("尝试截断文档后重建...")

        # 紧急处理：截断过长的文档
        smaller_docs = []
        for doc in documents:
            if not doc.page_content.strip():
                continue

            # 确保文档不超过token限制
            while count_tokens(doc.page_content) > 1500:
                doc.page_content = doc.page_content[:-100] + " [截断]"
            smaller_docs.append(doc)

        # 重建向量数据库
        db = Chroma.from_documents(
            smaller_docs, embedding, persist_directory=persist_dir
        )
        db.persist()
        print("使用截断后文档重建向量数据库成功")
        return db


def build_and_save_model(
    data_path: str, model_name: str = "zhihu_model", model_type: str = "zhihu_model"
):
    """构建并保存问答模型"""
    # 创建模型目录
    model_dir = f"model_{model_name}"
    os.makedirs(model_dir, exist_ok=True)

    print(f"🛠️ 开始构建模型: {model_name}")

    # 1. 加载文档
    print("🔍 加载文档...")
    documents = load_json_to_splittext(data_path)

    # 2. 创建向量数据库
    print("🧠 创建向量数据库...")
    db = create_vector_db(documents, persist_dir=model_dir)

    # 3. 保存提示模板
    if model_type == "zhihu_model":
        prompt_template = """
【角色定位】
你是一位专业的社交媒体内容分析专家，专门负责整理和归纳知乎平台上围绕特定问题的多角度回答内容。

【核心任务】
基于提供的围绕同一知乎问题的多个回答内容，生成一个全面、结构化的分析总结，将不同回答者观点有机整合，为后续问答交互提供丰富的背景知识支持。

【处理要求】
1. 问题焦点识别：明确识别并强调核心问题，确保所有回答都围绕该问题展开
2. 观点分类归纳：将不同回答按主题或立场进行分类（如支持、反对、中立、补充等）
3. 多角度整合：识别并展示问题的不同角度和层面，体现回答的多样性
4. 观点关联分析：分析不同回答间的隐含关系（如相互支持、相互反驳、互补等）
5. 代表性保留：确保每个重要观点都有代表性回答的支持内容和回答者信息

【输出格式】
严格按照以下结构组织输出：
- 核心问题重述：清晰表述原始问题
- 主要观点分类：按主题/立场分类回答内容
  * 每个观点类别下包含：
    - 观点概述
    - 主要论据和支撑细节
    - 典型回答示例（引用关键内容）
    - 相关回答者标识（如可识别）
- 观点关系图谱：简要说明不同观点间的关系
- 争议焦点总结：明确标出存在分歧的关键点
- 补充信息汇总：整理有价值的补充信息和边缘观点

【特殊注意事项】
- 尊重原始回答的独立性，避免强行建立不存在的逻辑联系
- 保持各回答观点的原意，不进行主观判断或价值评价
- 对于相互矛盾的观点，客观呈现其对立关系

【背景知识】
{context}
"""
    elif model_type == "bili_model":
        prompt_template = """
【角色定位】
你是一位专业的内容分析专家，擅长处理从音频转录而来的文字内容，能够识别和修正转录错误。

【核心任务】
基于提供的视频转录内容，生成准确、连贯、易于理解的总结，为后续问答交互提供可靠的知识基础。

【处理要求】
1. 错误识别与修正：识别转录中可能存在的错误（如语音识别错误、断句问题），进行合理修正
2. 内容提炼：提取视频中的核心观点、关键信息和重要论据
3. 逻辑重建：重新组织可能因转录而变得混乱的逻辑结构
4. 信息分层：区分主要观点和补充说明，构建清晰的信息层次
5. 上下文保持：保持内容的完整上下文，避免断章取义

【输出格式】
- 核心内容概述
- 主要观点及支撑细节
- 重要时间节点或关键信息点
- 可能存在的转录问题说明

【背景知识】
{context}
"""
    elif model_type == "xhs_model":
        prompt_template = """
【角色定位】
你是一位专业的社交媒体数据分析专家，专门负责分析小红书平台上的帖子内容和用户评论，为互联网从业者提供深度洞察。

【核心任务】
基于提供的小红书帖子内容和评论区数据，生成全面、结构化的分析报告，帮助互联网分析从业者理解用户行为、观点分布和内容趋势。

【处理要求】
1. 帖子内容分析：
   - 准确理解并总结帖子的核心问题或主题
   - 分析帖子内容的情感倾向（求助、分享、抱怨等）
   - 识别帖子的关键信息点（如用户背景、具体困扰等）

2. 评论区深度分析：
   - 地域分布分析：统计并分析评论用户的IP地理位置分布，识别地域性特征
   - 热度分析：根据点赞数识别高热度评论，分析其内容特征和观点倾向
   - 观点分类：将评论按主题或立场进行分类（如支持、反对、中立、建议等）
   - 讨论方向识别：识别用户讨论的主要方向和解决方案类型
   - 情感分析：分析评论的整体情感倾向（正面、负面、中性）

3. 用户行为洞察：
   - 识别高参与度用户特征（高赞评论者、多回复者等）
   - 分析用户互动模式（回复、讨论等）
   - 识别内容传播特征

4. 专业建议提供：
   - 基于数据分析提供专业的互联网内容运营建议
   - 识别潜在的商业机会或风险点
   - 提供用户需求洞察和内容策略建议

【输出格式】
严格按照以下结构组织输出：
- 帖子内容概要：
  * 核心主题
  * 用户背景信息
  * 关键问题描述

- 用户评论分析：
  * 地域分布统计（按评论数和热度两个维度）
  * 高热度评论摘要（点赞数前10，需包含具体内容和点赞数）
  * 观点分类及占比（如医美方案、运动健身、日常护理、遗传因素等）
  * 主要讨论方向总结
  * 情感倾向分析

- 深度洞察：
  * 用户需求洞察
  * 内容传播特征
  * 潜在商业机会
  * 运营策略建议

- 专业建议：
  * 针对内容创作者的建议
  * 针对平台运营的建议
  * 针对相关行业从业者的建议

【特殊注意事项】
- 保持原始数据的完整性，确保分析基于真实用户反馈
- 客观呈现不同观点，避免主观偏见
- 注重数据驱动的分析方法，提供量化指标支持结论
- 保护用户隐私，不泄露具体用户信息

【背景知识】
{context}
"""
    else:
        prompt_template = """
【角色定位】
你是一位经验丰富的知识整理专家，擅长从各类文本中提取关键信息并构建结构化知识体系。

【核心任务】
基于提供的文档内容，生成全面、准确、结构化的知识总结，为后续的问答交互提供坚实基础。

【处理要求】
1. 信息完整性：确保不遗漏重要信息点
2. 结构化处理：将内容按照逻辑关系进行组织
3. 关键点突出：明确标识核心观点和关键数据
4. 语义连贯：保持内容的语义完整性和逻辑连贯性
5. 易于检索：生成便于后续查询和问答的结构化内容

【输出格式】
- 内容概要
- 核心要点分项说明
- 关键信息索引
- 重要内容引用

【背景知识】
{context}
"""

    with open(f"{model_dir}/prompt_template.txt", "w", encoding="utf-8") as f:
        f.write(prompt_template)

    print(f"✅ 模型构建完成并保存到 {model_dir}")


if __name__ == "__main__":
    # 示例用法
    data_path = "data/video_fan_transcription.txt"
    build_and_save_model(
        data_path, model_name="default_model", model_type="default_model"
    )
