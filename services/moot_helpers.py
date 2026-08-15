from typing import Optional
"""
模拟法庭辅助函数 — 庭审数据结构转换和状态快照构建。

所有函数均为纯函数，无副作用、无 Streamlit 依赖。
"""

def moot_round_to_dict(round_result) -> dict:
    """将 RoundResult 对象转为可序列化的 dict"""
    return {'step': round_result.step, 'step_name': round_result.step_name, 'role': round_result.speaker, 'role_name': round_result.role_name, 'content': round_result.content}

def moot_role_type(round_item: Optional[dict]) -> Optional[str]:
    """从模拟法庭轮次 dict 中识别发言者角色"""
    if not round_item:
        return None
    role = str(round_item.get('role', round_item.get('speaker', ''))).lower()
    role_name = str(round_item.get('role_name', ''))
    if 'judge' in role or '法官' in role_name:
        return 'judge'
    if 'defendant' in role or '被告' in role_name:
        return 'defendant'
    if 'plaintiff' in role or '原告' in role_name:
        return 'plaintiff'
    return None

def build_moot_round_stub(rounds: list[dict], error: Optional[str]=None) -> dict:
    """构建模拟法庭结果的占位结构"""
    return {'rounds': list(rounds), 'correction_coefficient': 1.0, 'defense_strength': 50, 'judge_summary': '', 'weak_points': [], 'focus_points': [], 'judge_scores': {}, 'error': error}

def build_moot_status_snapshot(eval_data: Optional[dict], flow_state: dict) -> dict:
    """从评估数据和流程状态构建模拟法庭态势快照"""
    moot_r = (eval_data or {}).get('moot') or {}
    rounds = list(moot_r.get('rounds', []) or [])
    running_moot = bool(flow_state.get('running') and flow_state.get('current_step') == 'moot')
    active_round = rounds[-1] if rounds else None
    active_role = moot_role_type(active_round)
    all_roles = {moot_role_type(r) for r in rounds if moot_role_type(r)}
    completed_roles = {moot_role_type(r) for r in (rounds[:-1] if running_moot and rounds else rounds) if moot_role_type(r)}
    role_states = {}
    for role_key in ('judge', 'plaintiff', 'defendant'):
        if running_moot and role_key == active_role:
            role_states[role_key] = 'current'
        elif role_key in completed_roles or (not running_moot and role_key in all_roles):
            role_states[role_key] = 'complete'
        else:
            role_states[role_key] = 'upcoming'
    total_rounds = max(7, len(rounds)) if rounds else 7
    if running_moot and active_round:
        status_label = f'进行中 · {len(rounds)}/{total_rounds} 段'
    elif rounds:
        status_label = f'已完成 · {len(rounds)}/{total_rounds} 段'
    elif flow_state.get('running'):
        status_label = '等待进入 1.4 模拟法庭'
    else:
        status_label = '尚未启动'
    stage_name = active_round.get('step_name', '') if active_round else ''
    speaker_name = active_round.get('role_name', '') if active_round else ''
    if not stage_name:
        stage_name = '模拟法庭态势'
    if not speaker_name:
        speaker_name = '待启动'
    return {'has_rounds': bool(rounds), 'running_moot': running_moot, 'status_label': status_label, 'stage_name': stage_name, 'speaker_name': speaker_name, 'completed_count': len(rounds), 'total_rounds': total_rounds, 'role_states': role_states, 'active_round': active_round}