"""
services/eval_helpers.py 单元测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from services.eval_helpers import build_dimension_result, build_external_failure, label_dimension_names, build_integrity_payload
SAMPLE_LABELS = {'rights': '权利基础', 'infringement': '侵权认定', 'procedure': '诉讼程序', 'moot': '模拟法庭'}

class TestBuildDimensionResult:
    """构建维度结果测试"""

    def test_normal_result(self):
        result = {'score': 80, 'analysis': '稳妥'}
        fallback = {'score': 0, 'analysis': ''}
        merged = build_dimension_result(result, fallback, '权利基础')
        assert merged['score'] == 80
        assert merged['status'] == 'completed'
        assert merged['is_complete'] is True

    def test_result_with_error(self):
        result = {'error': 'API 超时'}
        fallback = {}
        merged = build_dimension_result(result, fallback, '侵权认定')
        assert merged['status'] == 'failed'
        assert merged['is_complete'] is False
        assert '侵权认定' in merged['analysis']

    def test_fallback_values_used(self):
        result = {}
        fallback = {'score': 50, 'analysis': '默认分析'}
        merged = build_dimension_result(result, fallback, '程序审查')
        assert merged['score'] == 50

    def test_status_explicitly_failed(self):
        result = {'status': 'failed', 'score': 0}
        fallback = {}
        merged = build_dimension_result(result, fallback, '证据')
        assert merged['is_complete'] is False

    def test_none_result_uses_fallback(self):
        merged = build_dimension_result(None, {'score': 100}, '权利基础')
        assert merged['score'] == 100

class TestBuildExternalFailure:
    """构建外部失败响应测试"""

    def test_basic_failure(self):
        resp = build_external_failure('企查查', 'Token 未配置')
        assert resp['label'] == '企查查'
        assert resp['status'] == 'failed'
        assert 'laws' in resp
        assert 'cases' in resp

    def test_skipped_status(self):
        resp = build_external_failure('北大法宝', 'Mock 模式', status='skipped')
        assert resp['status'] == 'skipped'

    def test_no_collections(self):
        resp = build_external_failure('QCC', '超时', include_collections=False)
        assert 'laws' not in resp
        assert 'cases' not in resp

class TestLabelDimensionNames:
    """维度标签映射测试"""

    def test_known_dimensions(self):
        result = label_dimension_names(['rights', 'moot'], SAMPLE_LABELS)
        assert result == ['权利基础', '模拟法庭']

    def test_unknown_dimension_passthrough(self):
        result = label_dimension_names(['unknown_dim'], SAMPLE_LABELS)
        assert result == ['unknown_dim']

    def test_empty_list(self):
        result = label_dimension_names([], SAMPLE_LABELS)
        assert result == []

    def test_mixed(self):
        result = label_dimension_names(['rights', '未知维度', 'procedure'], SAMPLE_LABELS)
        assert result == ['权利基础', '未知维度', '诉讼程序']

class TestBuildIntegrityPayload:
    """构建完整性 payload 测试"""

    def test_complete(self):
        integrity = {'is_complete': True, 'critical_missing': [], 'critical_failed': [], 'optional_incomplete': []}
        payload = build_integrity_payload(integrity, SAMPLE_LABELS)
        assert payload['is_complete'] is True
        assert payload['label'] == '完整'
        assert payload['critical_issues'] == []

    def test_partial_with_missing(self):
        integrity = {'is_complete': False, 'critical_missing': ['rights', 'infringement'], 'critical_failed': [], 'optional_incomplete': []}
        payload = build_integrity_payload(integrity, SAMPLE_LABELS)
        assert payload['is_complete'] is False
        assert payload['label'] == '部分完成'
        assert '权利基础' in payload['critical_issues']
        assert '侵权认定' in payload['critical_issues']

    def test_with_optional_issues(self):
        integrity = {'is_complete': False, 'critical_missing': [], 'critical_failed': [], 'optional_incomplete': ['moot']}
        payload = build_integrity_payload(integrity, SAMPLE_LABELS)
        assert '模拟法庭' in payload['optional_issues']