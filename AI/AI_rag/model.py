import os

from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain
from langchain.document_loaders import JSONLoader, TextLoader
from langchain.memory import ConversationBufferMemory
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

try:
    from .base_model import BaseModel
    from .utils import safe_print
except (ImportError, ValueError):
    # 如果相对导入失败，尝试其他方式
    import os
    import sys

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from base_model import BaseModel
    from utils import safe_print

load_dotenv()

DASHSCOPE_API_KEY = os.environ["OPENAI_API_KEY"]


class UniversalModel(BaseModel):
    """通用模型类，支持多种数据源"""

    def __init__(self, model_name):
        """
        加载通用模型
        :param model_name: 模型名称（对应文件夹）
        """
        super().__init__(model_name)
        if model_name.startswith("model_"):
            model_dir = model_name
        else:
            model_dir = f"model_{model_name}"

        # 验证模型目录
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"模型目录 {model_dir} 不存在，请先构建模型")

        print(f"加载模型: {model_name}")

        # 1. 加载向量数据库
        embedding = DashScopeEmbeddings(
            model="text-embedding-v1", dashscope_api_key=DASHSCOPE_API_KEY
        )
        self.db = Chroma(persist_directory=model_dir, embedding_function=embedding)

        # 2. 加载提示模板
        template_path = f"{model_dir}/prompt_template.txt"
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                system_template = f.read()
        else:
            # 使用默认模板 - 更自然的文章风格提示
            system_template = (
                "你是一个专业的编辑和作家，能够根据提供的资料撰写结构清晰、内容详实的文章。"
                "请遵循以下要求："
                "1. 使用自然流畅的语言，避免生硬的列表或编号"
                "2. 文章应有清晰的结构，包括引言、主体段落和结论"
                "3. 主体部分应围绕几个核心观点展开，每个观点都要有充分的细节支撑"
                "4. 不要使用'####'、'**'等Markdown格式标记"
                "5. 保持客观、准确，基于提供的资料进行撰写"
                "6. 避免涉及敏感话题，保持客观中立的语调"
            )

        # 3. 创建提示模板
        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)

        # 4. 创建语言模型
        llm = ChatTongyi(
            dashscope_api_key=DASHSCOPE_API_KEY,
            model="qwen-flash",
            temperature=0.2,
            top_p=0.9,
        )

        # 5. 创建检索链
        retriever = self.db.as_retriever(search_kwargs={"k": 10})
        self.qa = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=ConversationBufferMemory(
                memory_key="chat_history", return_messages=True, output_key="answer"
            ),
            combine_docs_chain_kwargs={"prompt": prompt},
            return_source_documents=True,
        )

        print(f"✅ 模型加载完成")

    def generate_summary(self, question: str) -> str:
        """生成内容总结"""
        result = self.qa({"question": question})
        return result["answer"]

    def ask_question(self, question: str) -> str:
        """回答单个问题"""
        result = self.qa({"question": question})
        return result["answer"]

    def interactive_qa(self):
        """交互式问答模式"""
        print("\n💬 进入交互式问答模式（输入'exit'退出）")
        while True:
            user_input = input("\n您的问题: ")

            if user_input.lower() == "exit":
                print("问答结束")
                break

            if not user_input.strip():
                print("问题不能为空")
                continue

            # 执行查询，使用优化后的提示词
            formatted_question = (
                f"请针对以下问题提供一个客观、中立且结构清晰的回答：{user_input}\n\n"
                "要求：\n"
                "1. 回答应采用自然流畅的散文形式，不要使用项目符号或编号\n"
                "2. 回答结构应包括引言、主体段落和总结\n"
                "3. 主体部分应围绕几个核心观点展开，每个观点都要有充分的细节支撑\n"
                "4. 使用准确、专业的语言，避免口语化表达\n"
                "5. 不要使用'####'、'**'等Markdown格式标记\n"
                "6. 回答应详尽但不冗长，确保信息准确且易于理解\n"
                "7. 保持客观中立的语调，避免主观判断\n"
                "8. 基于事实进行回答，避免推测或未经证实的说法\n"
                "9. 在回答结尾处简要告诉用户信息来源"
            )

            print("\n" + "=" * 40 + f" 问题: {user_input} " + "=" * 40)
            try:
                result = self.qa({"question": formatted_question})
                print(f"\n答案: {result['answer']}")
            except Exception as e:
                print(f"\n回答问题时出错: {str(e)}")
                print("这可能是由于内容审查机制导致的，请尝试重新表述问题。")
                continue

            # 可选：显示来源文档
            show_source = input("显示来源文档? (y/n): ")
            if show_source.lower() == "y":
                print("\n来源文档:")
                for i, doc in enumerate(result["source_documents"]):
                    print(f"文档 {i+1}:")
                    safe_print(doc.page_content, max_length=200)
                    print("...\n")
