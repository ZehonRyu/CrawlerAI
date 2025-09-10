import json

import tiktoken


def count_tokens(text: str) -> int:
    """使用tiktoken精确计算文本token数"""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def safe_print(text: str, max_length=200):
    """安全打印中文字符，避免Unicode转义"""
    try:
        # 尝试直接打印
        print(text[:max_length])
    except UnicodeEncodeError:
        # 如果遇到编码问题，使用json确保中文显示
        print(json.dumps(text[:max_length], ensure_ascii=False))
