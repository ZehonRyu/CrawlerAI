# 智能导入处理，兼容不同环境
try:
    # 尝试使用相对导入（在包内运行时）
    from .model import UniversalModel
except ImportError:
    # 如果相对导入失败，使用绝对导入（在动态加载时）
    try:
        from AI.AI_rag.model import UniversalModel
    except ImportError:
        # 最后尝试直接导入
        import os
        import sys

        # 获取当前文件目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 获取项目根目录 (Project/CrawlerAI)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        # 添加到Python路径
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # 如果仍然无法导入，尝试使用相对路径直接导入
        try:
            from AI.AI_rag.model import UniversalModel
        except ImportError:
            # 尝试通过修改后的路径导入
            ai_rag_dir = os.path.dirname(current_dir)
            if ai_rag_dir not in sys.path:
                sys.path.insert(0, ai_rag_dir)
            from model import UniversalModel


def generate_summary(platform):
    """
    生成内容总结
    :param model_name: 模型名称
    :return: 总结内容
    """
    model_name = platform if platform.endswith("_model") else f"{platform}_model"
    try:
        # 加载模型
        qa_model = UniversalModel(model_name)

        # 生成总结 - 使用更结构化的提示词
        summary = qa_model.generate_summary(
            "请基于内容，以结构化的方式撰写一篇关于该主题的详细文章。要求："
            "1. 文章应包含引言、主体和结论"
            "2. 主体部分应分点论述，每点都要有明确的小标题"
            "3. 使用自然流畅的语言，避免使用项目符号或编号"
            "4. 内容要详实，涵盖主要观点和支撑细节"
            "5. 文章格式应像人工撰写的文章，不要使用类似'####'的标记"
        )
        return summary
    except FileNotFoundError as e:
        raise FileNotFoundError(f"模型未找到: {e}")
    except Exception as e:
        raise Exception(f"生成总结时出错: {e}")


def ask_question(question, platform):
    """
    回答问题
    :param question: 问题
    :param model_name: 模型名称
    :return: 回答内容
    """
    model_name = platform if platform.endswith("_model") else f"{platform}_model"
    try:
        # 加载模型
        qa_model = UniversalModel(model_name)

        # 回答问题 - 使用更安全的提示词
        safe_question = (
            f"请针对以下问题提供一个客观、中立且结构清晰的回答：{question}\n\n"
            "要求：\n"
            "1. 回答应采用自然流畅的散文形式，不要使用项目符号或编号\n"
            "2. 回答结构应包括引言、主体段落和总结\n"
            "3. 主体部分应围绕几个核心观点展开，每个观点都要有充分的细节支撑\n"
            "4. 使用准确、专业的语言，避免口语化表达\n"
            "5. 不要使用'####'、'**'等Markdown格式标记\n"
            "6. 回答应详尽但不冗长，确保信息准确且易于理解\n"
            "7. 保持客观中立的语调，避免主观判断\n"
            "8. 基于事实进行回答，避免推测或未经证实的说法"
        )
        answer = qa_model.ask_question(safe_question)
        return answer
    except FileNotFoundError as e:
        raise FileNotFoundError(f"模型未找到: {e}")
    except Exception as e:
        raise Exception(f"回答问题时出错: {e}")


def UseModel(platform: str):
    import argparse

    parser = argparse.ArgumentParser(description="使用通用问答模型")
    parser.add_argument("--model", default=f"{platform}_model", help="模型名称")
    args = parser.parse_args()

    try:
        # 加载模型
        qa_model = UniversalModel(args.model)

        # 生成总结
        print("=" * 80)
        print("开始生成内容总结...")
        summary = qa_model.generate_summary(
            "请基于内容，以结构化的方式撰写一篇关于该主题的详细文章。要求："
            "1. 文章应包含引言、主体和结论"
            "2. 主体部分应分点论述，每点都要有明确的小标题"
            "3. 使用自然流畅的语言，避免使用项目符号或编号"
            "4. 内容要详实，涵盖主要观点和支撑细节"
            "5. 文章格式应像人工撰写的文章，不要使用类似'####'的标记"
        )
        print("\n" + "=" * 40 + " 内容总结 " + "=" * 40)
        print(summary)
        print("=" * 90)

        # 进入交互式问答
        qa_model.interactive_qa()

    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请先运行 build_model.py 构建模型")


if __name__ == "__main__":
    platform = "zhihu"
    UseModel(platform=platform)
