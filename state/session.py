from typing import Optional
"""
会话状态管理 — 所有 st.session_state key 的统一定义。

使用方式:
    from state.session import S, has_case, get_case_id, clear_case

    不要直接用魔法字符串 st.session_state["current_case_id"]
    改用 S.CURRENT_CASE_ID 或 helper 函数
"""

class S:
    """Session State Key 常量（所有 st.session_state key 都定义在这里）"""
    PAGE = 'page'
    NAV_TARGET = 'nav_target'
    WORKBENCH_TAB = 'workbench_tab'
    CURRENT_CASE_ID = 'current_case_id'
    CURRENT_CASE_NAME = 'current_case_name'
    CASE_DELETE_NOTICE = 'case_delete_notice'
    LAST_CASE_DESC = 'last_case_desc'
    EVIDENCE_TEXT_EXTRA = 'evidence_text_extra'
    SYSTEM_CONFIG_MODE_PREVIEW = 'system_config_mode_preview'
    SYSTEM_CONFIG_MODE_SAVED = 'system_config_mode_saved'

def eval_results_key(case_id: str) -> str:
    return f'eval_results_{case_id}'

def dimension_state_key(dimension: str, case_id: str) -> str:
    return f'{dimension}_{case_id}'

def case_update_notice_key(case_id: str) -> str:
    return f'case_update_notice_{case_id}'

def case_editing_toggle_key(case_id: str) -> str:
    return f'editing_case_{case_id}'
DIMENSION_KEYS = ['rights', 'infringement', 'procedure', 'moot', 'financial', 'precedent', 'evidence']

def has_case(import_st_fn) -> bool:
    """检查是否有当前选中案件"""
    session = import_st_fn()
    return S.CURRENT_CASE_ID in session

def get_case_id(import_st_fn) -> Optional[str]:
    """获取当前选中案件 ID"""
    session = import_st_fn()
    return session.get(S.CURRENT_CASE_ID)

def clear_dimension_states(case_id: str, import_st_fn) -> None:
    """清除所有维度相关的 session state"""
    session = import_st_fn()
    for key_name in DIMENSION_KEYS:
        session.pop(dimension_state_key(key_name, case_id), None)
    session.pop(eval_results_key(case_id), None)

def clear_case_selection(import_st_fn) -> None:
    """清除当前案件选择"""
    session = import_st_fn()
    session.pop(S.CURRENT_CASE_ID, None)
    session.pop(S.CURRENT_CASE_NAME, None)
    session.pop(S.NAV_TARGET, None)