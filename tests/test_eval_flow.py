"""
state/eval_flow.py 单元测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from state.eval_flow import eval_flow_state_key, default_eval_flow_state, completed_eval_steps, eval_flow_visual_state, eval_flow_group_widths
SAMPLE_FLOW_STEPS = [{'id': 'rights', 'full_title': '1.1 权利基础'}, {'id': 'infringement', 'full_title': '1.2 侵权认定'}, {'id': 'procedure', 'full_title': '1.3 诉讼程序'}, {'id': 'moot', 'full_title': '1.4 模拟法庭'}]

class TestEvalFlowStateKey:

    def test_generates_correct_key(self):
        assert eval_flow_state_key('case-001') == 'eval_flow_state_case-001'

    def test_empty_case_id(self):
        assert eval_flow_state_key('') == 'eval_flow_state_'

class TestDefaultEvalFlowState:

    def test_defaults(self):
        state = default_eval_flow_state()
        assert state['running'] is False
        assert state['current_step'] is None
        assert state['completed_steps'] == []

    def test_with_selected_step(self):
        state = default_eval_flow_state(selected_step='rights')
        assert state['selected_step'] == 'rights'

class TestCompletedEvalSteps:

    def test_all_completed(self):
        eval_data = {'rights': {'score': 80}, 'infringement': {'score': 75}, 'procedure': {'score': 90}, 'moot': {'rounds': []}}
        result = completed_eval_steps(eval_data, SAMPLE_FLOW_STEPS)
        assert result == ['rights', 'infringement', 'procedure', 'moot']

    def test_partial(self):
        eval_data = {'rights': {'score': 80}}
        result = completed_eval_steps(eval_data, SAMPLE_FLOW_STEPS)
        assert result == ['rights']

    def test_none_eval_data(self):
        result = completed_eval_steps(None, SAMPLE_FLOW_STEPS)
        assert result == []

    def test_empty_eval_data(self):
        result = completed_eval_steps({}, SAMPLE_FLOW_STEPS)
        assert result == []

    def test_empty_dict_not_counted(self):
        """空 dict 是 falsy，不算已完成步骤"""
        eval_data = {'rights': {}, 'infringement': 0}
        result = completed_eval_steps(eval_data, SAMPLE_FLOW_STEPS)
        assert 'rights' not in result
        assert 'infringement' not in result

class TestEvalFlowVisualState:

    def test_current(self):
        state = {'running': True, 'current_step': 'rights', 'completed_steps': [], 'selected_step': 'rights'}
        assert eval_flow_visual_state('rights', state) == 'current'

    def test_selected(self):
        state = {'running': False, 'current_step': None, 'completed_steps': ['rights'], 'selected_step': 'rights'}
        assert eval_flow_visual_state('rights', state) == 'selected'

    def test_complete(self):
        state = {'running': False, 'current_step': None, 'completed_steps': ['rights', 'infringement'], 'selected_step': 'infringement'}
        assert eval_flow_visual_state('rights', state) == 'complete'

    def test_upcoming(self):
        state = {'running': False, 'current_step': None, 'completed_steps': [], 'selected_step': None}
        assert eval_flow_visual_state('rights', state) == 'upcoming'

class TestEvalFlowGroupWidths:

    def test_four_steps(self):
        result = eval_flow_group_widths(4)
        assert len(result) == 8
        assert result[-1] == 2.18

    def test_two_steps(self):
        result = eval_flow_group_widths(2)
        assert len(result) == 8

    def test_one_step(self):
        result = eval_flow_group_widths(1)
        assert len(result) == 8

    def test_custom_step_count(self):
        result = eval_flow_group_widths(3)
        assert len(result) == 6
        assert result[-1] == 2.18