"""
services/moot_helpers.py 单元测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from services.moot_helpers import moot_role_type, build_moot_round_stub, build_moot_status_snapshot

class TestMootRoleType:
    """模拟法庭角色识别测试"""

    def test_judge_by_role_field(self):
        assert moot_role_type({'role': 'judge'}) == 'judge'

    def test_judge_by_role_name(self):
        assert moot_role_type({'role_name': '审判法官'}) == 'judge'

    def test_defendant_by_role(self):
        assert moot_role_type({'role': 'defendant'}) == 'defendant'

    def test_plaintiff_by_role(self):
        assert moot_role_type({'role': 'plaintiff'}) == 'plaintiff'

    def test_none_round_item(self):
        assert moot_role_type(None) is None

    def test_empty_dict(self):
        assert moot_role_type({}) is None

    def test_unknown_role(self):
        assert moot_role_type({'role': 'witness'}) is None

    def test_speaker_field_fallback(self):
        """speaker 字段作为备选"""
        assert moot_role_type({'speaker': 'judge'}) == 'judge'

class TestBuildMootRoundStub:
    """模拟法庭占位结构测试"""

    def test_basic_stub(self):
        stub = build_moot_round_stub([])
        assert stub['rounds'] == []
        assert stub['correction_coefficient'] == 1.0
        assert stub['defense_strength'] == 50

    def test_with_rounds(self):
        rounds = [{'step': 1, 'role': 'plaintiff', 'content': '...'}]
        stub = build_moot_round_stub(rounds)
        assert len(stub['rounds']) == 1

    def test_with_error(self):
        stub = build_moot_round_stub([], error='API 超时')
        assert stub['error'] == 'API 超时'

class TestBuildMootStatusSnapshot:
    """模拟法庭态势快照测试"""

    def test_not_started(self):
        snapshot = build_moot_status_snapshot(eval_data=None, flow_state={'running': False, 'current_step': None})
        assert snapshot['status_label'] == '尚未启动'
        assert snapshot['has_rounds'] is False

    def test_waiting_for_moot(self):
        """流程已启动但还没到模拟法庭这一步"""
        snapshot = build_moot_status_snapshot(eval_data=None, flow_state={'running': True, 'current_step': 'infringement'})
        assert snapshot['status_label'] == '等待进入 1.4 模拟法庭'

    def test_completed_snapshot(self):
        eval_data = {'moot': {'rounds': [{'step': 1, 'step_name': '开庭陈述', 'role': 'plaintiff', 'role_name': '原告代理律师', 'content': '...'}, {'step': 2, 'step_name': '被告答辩', 'role': 'defendant', 'role_name': '被告代理律师', 'content': '...'}, {'step': 5, 'step_name': '法官归纳', 'role': 'judge', 'role_name': '审判法官', 'content': '...'}]}}
        snapshot = build_moot_status_snapshot(eval_data=eval_data, flow_state={'running': False, 'current_step': None})
        assert snapshot['has_rounds'] is True
        assert snapshot['status_label'] == '已完成 · 3/7 段'
        assert snapshot['role_states']['judge'] == 'complete'
        assert snapshot['role_states']['plaintiff'] == 'complete'
        assert snapshot['role_states']['defendant'] == 'complete'

    def test_running_moot_plaintiff_turn(self):
        eval_data = {'moot': {'rounds': [{'step': 1, 'step_name': '开庭陈述', 'role': 'plaintiff', 'role_name': '原告代理律师', 'content': '...'}]}}
        snapshot = build_moot_status_snapshot(eval_data=eval_data, flow_state={'running': True, 'current_step': 'moot'})
        assert snapshot['running_moot'] is True
        assert snapshot['status_label'] == '进行中 · 1/7 段'
        assert snapshot['role_states']['plaintiff'] == 'current'
        assert snapshot['role_states']['defendant'] == 'upcoming'
        assert snapshot['role_states']['judge'] == 'upcoming'

    def test_speaker_name_from_active_round(self):
        eval_data = {'moot': {'rounds': [{'step': 1, 'step_name': '开庭陈述', 'role': 'plaintiff', 'role_name': '代理律师张三', 'content': '...'}]}}
        snapshot = build_moot_status_snapshot(eval_data=eval_data, flow_state={'running': False, 'current_step': None})
        assert snapshot['speaker_name'] == '代理律师张三'
        assert snapshot['stage_name'] == '开庭陈述'