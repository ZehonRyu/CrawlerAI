from abc import ABC, abstractmethod


class BaseModel(ABC):
    """模型基类"""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def generate_summary(self, question: str) -> str:
        """生成总结"""
        pass

    @abstractmethod
    def ask_question(self, question: str) -> str:
        """回答问题"""
        pass

    @abstractmethod
    def interactive_qa(self):
        """交互式问答"""
        pass
