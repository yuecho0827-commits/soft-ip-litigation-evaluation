from typing import Optional
"""
评估流程状态管理 — 纯逻辑函数，无 Streamlit 依赖。

包含评估流水线的状态 key 生成、默认状态构建、已完成步骤计算、
视觉状态映射和流程网格宽度计算。
"""

def eval_flow_state_key(case_id: str) -> str:
    """生成评估流程状态的 session_state key"""
    return f'eval_flow_state_{case_id}'

def default_eval_flow_state(selected_step: Optional[str]=None) -> dict:
    """构建评估流程的默认初始状态"""
    return {'running': False, 'current_step': None, 'completed_steps': [], 'selected_step': selected_step}

def completed_eval_steps(eval_data: Optional[dict], eval_flow_steps: list[dict]) -> list[str]:
    """从评估数据中提取已完成的步骤 ID 列表"""
    if not eval_data:
        return []
    completed = []
    for step in eval_flow_steps:
        if eval_data.get(step['id']):
            completed.append(step['id'])
    return completed

def eval_flow_visual_state(step_id: str, flow_state: dict) -> str:
    """
    根据流程状态确定步骤的视觉状态。
    返回: "current" | "complete" | "selected" | "upcoming"
    """
    completed = set(flow_state.get('completed_steps', []))
    if flow_state.get('running') and step_id == flow_state.get('current_step'):
        return 'current'
    if step_id in completed:
        if step_id == flow_state.get('selected_step'):
            return 'selected'
        return 'complete'
    return 'upcoming'

def eval_flow_group_widths(step_count: int) -> list[float]:
    """为评估流程网格生成列宽列表"""
    grid = [0.76, 0.08, 0.76, 0.08, 0.76, 0.08, 0.76]
    if step_count == 4:
        return grid + [2.18]
    if step_count == 2:
        return grid + [2.18]
    if step_count == 1:
        return grid + [2.18]
    widths = []
    for idx in range(step_count):
        widths.append(0.76)
        if idx < step_count - 1:
            widths.append(0.08)
    widths.append(2.18)
    return widths