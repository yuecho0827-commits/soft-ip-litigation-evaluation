"""
llm/client.py 单元测试
覆盖 markdown 清理和 LLM 客户端接口。
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from llm.client import _strip_markdown_fences, call_text, call_json

class TestStripMarkdownFences:
    """Markdown 代码块清理测试"""

    def test_strips_json_fence(self):
        """清理 ```json ... ``` 包裹"""
        raw = '```json\n{"score": 80}\n```'
        assert _strip_markdown_fences(raw) == '{"score": 80}'

    def test_strips_plain_fence(self):
        """清理 ``` ... ``` 包裹"""
        raw = '```\nplain text\n```'
        assert _strip_markdown_fences(raw) == 'plain text'

    def test_no_fence_unchanged(self):
        """无代码块的文本原样返回"""
        raw = '{"score": 80}'
        assert _strip_markdown_fences(raw) == '{"score": 80}'

    def test_json_fence_with_blank_first_line(self):
        """```json 后紧跟空行再跟内容"""
        raw = '```json\n\n{"x": "y"}\n```'
        assert _strip_markdown_fences(raw) == '{"x": "y"}'

    def test_multiline_json_content(self):
        """多行 JSON 内容"""
        raw = '```json\n{\n  "score": 80,\n  "analysis": "合格"\n}\n```'
        expected = '{\n  "score": 80,\n  "analysis": "合格"\n}'
        assert _strip_markdown_fences(raw) == expected

    def test_leading_whitespace(self):
        """带前导空格"""
        raw = '  {"score": 80}  '
        assert _strip_markdown_fences(raw) == '{"score": 80}'

    def test_empty_string(self):
        """空字符串"""
        assert _strip_markdown_fences('') == ''

    def test_only_fence_marks(self):
        """只有代码块标记"""
        assert _strip_markdown_fences('```') == ''
        assert _strip_markdown_fences('```json') == ''

    def test_json_fence_multiple_lines_after_split(self):
        """```json 后有多行 → split 只去掉第一行"""
        raw = '```json\nline1\nline2\n```'
        result = _strip_markdown_fences(raw)
        assert 'line2' in result
        assert '```json' not in result
        assert '```' not in result

    def test_real_world_llm_output(self):
        """模拟真实 LLM 返回的格式"""
        raw = '```json\n{\n  "score": 82,\n  "sub_scores": {\n    "validity": {"score": 90, "reason": "有效"},\n    "coverage": {"score": 75, "reason": "覆盖"}\n  },\n  "analysis": "权利基础稳固"\n}\n```'
        result = _strip_markdown_fences(raw)
        assert 'score' in result
        assert '```' not in result
        import json
        json.loads(result)

class TestBackwardCompatibility:
    """验证重构后 llm_client 和 moot_court/agents 的接口不变"""

    def test_llm_client_call_llm_signature(self):
        """llm_client._call_llm 签名和行为不变"""
        from llm_client import _call_llm
        import inspect
        sig = inspect.signature(_call_llm)
        params = list(sig.parameters.keys())
        assert params == ['system_prompt', 'user_prompt', 'temperature']
        assert sig.parameters['temperature'].default == 0.2

    def test_moot_court_call_llm_text_signature(self):
        """moot_court.agents.call_llm_text 签名不变"""
        from moot_court.agents import call_llm_text
        import inspect
        sig = inspect.signature(call_llm_text)
        params = list(sig.parameters.keys())
        assert params == ['system_prompt', 'user_prompt', 'temperature']
        assert sig.parameters['temperature'].default == 0.3

    def test_moot_court_call_llm_json_signature(self):
        """moot_court.agents.call_llm_json 签名不变"""
        from moot_court.agents import call_llm_json
        import inspect
        sig = inspect.signature(call_llm_json)
        params = list(sig.parameters.keys())
        assert params == ['system_prompt', 'user_prompt', 'temperature']
        assert sig.parameters['temperature'].default == 0.2

    def test_llm_package_public_api(self):
        """llm 包的公开 API"""
        from llm import call_text, call_json
        import inspect
        assert callable(call_text)
        assert callable(call_json)
        sig_text = inspect.signature(call_text)
        assert sig_text.return_annotation is str
        sig_json = inspect.signature(call_json)
        assert sig_json.parameters['max_tokens'].default == 4000