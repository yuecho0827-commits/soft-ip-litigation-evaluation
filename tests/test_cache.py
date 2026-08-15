"""
cache/eval_cache.py 单元测试
"""
import json
import pytest
import sys
import tempfile
from pathlib import Path
from importlib import reload
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def temp_runtime_dir(monkeypatch):
    """用临时目录替换 RUNTIME_DIR，重新加载 cache 模块"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        import config
        monkeypatch.setattr(config, 'RUNTIME_DIR', tmp_path)
        import cache.eval_cache
        reload(cache.eval_cache)
        import cache
        reload(cache)
        yield tmp_path

class TestEvalCachePath:
    """评估缓存路径测试"""

    def test_returns_path(self, temp_runtime_dir):
        from cache import eval_cache_path
        path = eval_cache_path('case-123')
        assert isinstance(path, Path)
        assert path.name == 'eval_results_case-123.json'

    def test_creates_directory(self, temp_runtime_dir):
        from cache import eval_cache_path
        eval_cache_path('case-456')
        assert temp_runtime_dir.exists()

class TestLoadSaveEvalCache:
    """缓存读写测试"""

    def test_save_and_load_roundtrip(self, temp_runtime_dir):
        from cache import save_eval_cache, load_eval_cache
        data = {'score': 85, 'recommendation': '建议起诉', 'dimensions': {'rights': 80}}
        save_eval_cache('case-1', data)
        loaded = load_eval_cache('case-1')
        assert loaded is not None
        assert loaded['score'] == 85
        assert loaded['recommendation'] == '建议起诉'

    def test_load_nonexistent(self, temp_runtime_dir):
        from cache import load_eval_cache
        result = load_eval_cache('nonexistent-case')
        assert result is None

    def test_load_corrupted_file(self, temp_runtime_dir):
        from cache import eval_cache_path, load_eval_cache
        corrupt_path = eval_cache_path('corrupt-case')
        corrupt_path.write_text('this is not json', encoding='utf-8')
        result = load_eval_cache('corrupt-case')
        assert result is None

    def test_save_unicode_content(self, temp_runtime_dir):
        from cache import save_eval_cache, load_eval_cache
        data = {'案件名称': '测试侵权案', '分析': '商标近似性成立'}
        save_eval_cache('unicode-case', data)
        loaded = load_eval_cache('unicode-case')
        assert loaded['案件名称'] == '测试侵权案'

    def test_overwrite_existing(self, temp_runtime_dir):
        from cache import save_eval_cache, load_eval_cache
        save_eval_cache('case-overwrite', {'v': 1})
        save_eval_cache('case-overwrite', {'v': 2})
        loaded = load_eval_cache('case-overwrite')
        assert loaded['v'] == 2

class TestPkulawCachePath:
    """北大法宝缓存路径测试"""

    def test_returns_correct_filename(self, temp_runtime_dir):
        from cache import pkulaw_cache_path
        path = pkulaw_cache_path('case-abc')
        assert path.name == 'pkulaw_results_case-abc.json'

class TestClearCaseCacheFiles:
    """缓存清理测试"""

    def test_clears_existing_files(self, temp_runtime_dir):
        from cache import save_eval_cache, clear_case_cache_files, load_eval_cache, pkulaw_cache_path
        save_eval_cache('clear-test', {'data': 'test'})
        pkulaw_path = pkulaw_cache_path('clear-test')
        pkulaw_path.write_text('{"laws": []}', encoding='utf-8')
        reports_dir = temp_runtime_dir / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / 'clear-test_report.md'
        report_path.write_text('# test report', encoding='utf-8')
        assert load_eval_cache('clear-test') is not None
        assert pkulaw_path.exists()
        assert report_path.exists()
        clear_case_cache_files('clear-test')
        assert load_eval_cache('clear-test') is None
        assert not pkulaw_path.exists()
        assert not report_path.exists()

    def test_no_error_on_nonexistent_case(self, temp_runtime_dir):
        from cache import clear_case_cache_files
        clear_case_cache_files('never-existed')