"""
LLM 客户端包 — DeepSeek API 统一调用入口

使用:
    from llm import call_text, call_json

    # 纯文本调用
    text = call_text("你是律师", "分析这个案件", temperature=0.3)

    # JSON 调用
    result = call_json("你是法官", "归纳争议焦点", temperature=0.2)
"""
from .client import call_text, call_json
__all__ = ['call_text', 'call_json']