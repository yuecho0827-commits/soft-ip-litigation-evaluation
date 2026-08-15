"""
Soft IP 主诉评估系统 - Streamlit 主程序
专业法律科技 UI · 三维乘法评分 · 多Agent模拟法庭
"""
import streamlit as st
import sys
import os
import math
import time
import re
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional
from sqlalchemy.exc import OperationalError
sys.path.append(str(Path(__file__).parent))
from config import APP_TITLE, APP_VERSION, get_runtime_configuration_status, get_runtime_settings, save_runtime_settings
from database import init_db, SessionLocal, Case, Party, RuleHit, RetrievalRecord, ScoreSnapshot, Report
from evidence_parser import parse_pdf, ocr_image, is_pdf_file, is_image_file
from report_generator import generate_markdown_report, generate_pdf_bytes
from pkulaw_api import search_for_rights_foundation, search_for_infringement, search_for_procedure, search_for_moot_court, search_for_financial, search_for_precedent, run_verification_phase, get_linked_content
from qcc_api import search_for_financial_qcc_full
from styles import inject_global_css, page_header, section_banner, dim_card, score_bar, final_score_card, case_card, chat_bubble, metric_card, form_section_title, empty_state_notice, accent_notice, COLORS, ROLE_COLORS
from cache import eval_cache_path, load_eval_cache, save_eval_cache, pkulaw_cache_path, clear_case_cache_files
from services import build_dimension_result, build_external_failure, label_dimension_names, build_integrity_payload, moot_round_to_dict, moot_role_type, build_moot_round_stub, build_moot_status_snapshot, extract_defendant_info_result, build_external_results, create_engine
from state import eval_flow_state_key, default_eval_flow_state, completed_eval_steps, eval_flow_visual_state, eval_flow_group_widths, S, eval_results_key, dimension_state_key, DIMENSION_KEYS

def _use_mock_mode() -> bool:
    return bool(RUNTIME_CONFIG.get('use_mock', False))
_eval_engine = {}

def _ensure_engine():
    global _eval_engine
    if not _eval_engine:
        _eval_engine = create_engine(use_mock=_use_mock_mode())
    return _eval_engine

def evaluate_rights_foundation(*args, **kwargs):
    return _ensure_engine()['evaluate_rights_foundation'](*args, **kwargs)

def evaluate_infringement(*args, **kwargs):
    return _ensure_engine()['evaluate_infringement'](*args, **kwargs)

def evaluate_procedure(*args, **kwargs):
    return _ensure_engine()['evaluate_procedure'](*args, **kwargs)

def evaluate_financial_return(*args, **kwargs):
    return _ensure_engine()['evaluate_financial_return'](*args, **kwargs)

def evaluate_precedent_value(*args, **kwargs):
    return _ensure_engine()['evaluate_precedent_value'](*args, **kwargs)

def evaluate_evidence_readiness(*args, **kwargs):
    return _ensure_engine()['evaluate_evidence_readiness'](*args, **kwargs)

def extract_defendant_info(*args, **kwargs):
    return _ensure_engine()['extract_defendant_info'](*args, **kwargs)

def run_moot_court_simulation(*args, **kwargs):
    if _use_mock_mode():
        return mock_llm.run_moot_court_simulation(*args, **kwargs)
    return run_moot_court_real(*args, **kwargs)
from legal_rules import run_rule_engine
from scoring import calculate_legal_feasibility, calculate_business_expectation, calculate_overall_score, calculate_confidence_score, evaluate_data_integrity, generate_recommendation
from legal_database import format_laws_for_report, format_cases_for_report
from pkulaw_integration import generate_all_queries, save_results, get_validation_status
st.set_page_config(page_title=APP_TITLE, page_icon='⚖️', layout='wide', initial_sidebar_state='expanded')
inject_global_css()

@st.cache_resource
def _init_db():
    init_db()
    return True
_init_db()
RUNTIME_CONFIG = get_runtime_configuration_status()
RUNTIME_DIR = Path(RUNTIME_CONFIG.get('runtime_dir') or Path(__file__).parent / 'runtime')
CRITICAL_DIMENSIONS = ['rights', 'infringement', 'procedure', 'financial', 'precedent', 'evidence']
DIMENSION_LABELS = {'rights': '权利基础', 'infringement': '侵权认定', 'procedure': '诉讼程序', 'moot': '模拟法庭', 'financial': '财务回报', 'precedent': '判例价值', 'evidence': '证据就绪度'}
RETRIEVAL_LABELS = {'rights_retrieval': '权利基础法条检索', 'infringement_retrieval': '侵权认定类案检索', 'procedure_retrieval': '程序法条检索', 'moot_retrieval': '抗辩模式检索', 'financial_retrieval': '判赔数据检索', 'precedent_retrieval': '首案检索'}
EVAL_FLOW_STEPS = [{'id': 'rights', 'full_title': '1.1 权利基础', 'source': '来源：模型分析 + 北大法宝法条缓存'}, {'id': 'infringement', 'full_title': '1.2 侵权认定', 'source': '来源：模型分析 + 北大法宝类案缓存'}, {'id': 'procedure', 'full_title': '1.3 诉讼程序', 'source': '来源：模型分析 + 北大法宝程序法条缓存'}, {'id': 'moot', 'full_title': '1.4 模拟法庭', 'source': '来源：多 Agent 对抗检验 + 北大法宝抗辩模式缓存'}, {'id': 'financial', 'full_title': '2.1 财务回报', 'source': '来源：模型分析 + 北大法宝判赔缓存 + 企查查画像'}, {'id': 'precedent', 'full_title': '2.2 判例价值', 'source': '来源：模型分析 + 北大法宝首案检索缓存'}, {'id': 'evidence', 'full_title': '3 证据就绪度', 'source': '来源：模型分析 + 已上传证据文本'}]
EVAL_FLOW_GROUPS = [('法律可行性', ['rights', 'infringement', 'procedure', 'moot']), ('业务预期', ['financial', 'precedent']), ('证据就绪度', ['evidence'])]
EVAL_FLOW_MAP = {step['id']: step for step in EVAL_FLOW_STEPS}

def _eval_cache_path(case_id: str) -> Path:
    return eval_cache_path(case_id)

def _load_eval_cache(case_id: str):
    return load_eval_cache(case_id)

def _save_eval_cache(case_id: str, payload: dict) -> None:
    save_eval_cache(case_id, payload)

def _case_status_label(status: str) -> str:
    return {'draft': '待评估', 'pending': '待评估', 'evaluating': '评估中', 'partial': '部分完成', 'completed': '已完成'}.get(status or 'pending', '未知')

def _case_status_text_color(status: str) -> str:
    return {'draft': COLORS['text_muted'], 'pending': COLORS['text_muted'], 'evaluating': COLORS['warning'], 'partial': COLORS['warning'], 'completed': COLORS['accent']}.get(status or 'pending', COLORS['text_muted'])

def _pkulaw_cache_path(case_id: str) -> Path:
    return pkulaw_cache_path(case_id)

def _clear_case_runtime_state(case_id: str) -> None:
    clear_case_cache_files(case_id)
    for key in [f'eval_results_{case_id}', f'rights_{case_id}', f'infringement_{case_id}', f'procedure_{case_id}', f'moot_{case_id}', f'financial_{case_id}', f'precedent_{case_id}', f'evidence_{case_id}']:
        st.session_state.pop(key, None)

def _reset_case_outputs(db, case_id: str) -> None:
    report_rows = db.query(Report).filter(Report.case_id == case_id).all()
    for report_row in report_rows:
        if not report_row.pdf_uri:
            continue
        try:
            report_path = Path(report_row.pdf_uri)
            if report_path.exists():
                report_path.unlink()
        except Exception:
            pass
    db.query(RetrievalRecord).filter(RetrievalRecord.case_id == case_id).delete(synchronize_session=False)
    db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).delete(synchronize_session=False)
    db.query(Report).filter(Report.case_id == case_id).delete(synchronize_session=False)
    _clear_case_runtime_state(case_id)

def _clear_current_case_selection(case_id: str) -> None:
    if st.session_state.get('current_case_id') == case_id:
        st.session_state.pop('current_case_id', None)
        st.session_state.pop('current_case_name', None)
        st.session_state.pop('nav_target', None)
        if st.session_state.get('workbench_tab') in ('评估分析', '模拟法庭', '评估报告'):
            st.session_state[S.WORKBENCH_TAB] = '案件列表'

def _build_dimension_result(result: dict, fallback: dict, label: str) -> dict:
    return build_dimension_result(result, fallback, label)

def _build_external_failure(label: str, error: str, status: str='failed', include_collections: bool=True) -> dict:
    return build_external_failure(label, error, status, include_collections)

def _safe_external_call(label: str, func, include_collections: bool=True):
    if _use_mock_mode():
        return _build_external_failure(label, f'Mock 模式未调用{label}', status='skipped', include_collections=include_collections)
    try:
        result = func() or {}
        if not isinstance(result, dict):
            raise RuntimeError('返回结果不是字典')
        result.setdefault('label', label)
        result.setdefault('status', 'completed')
        result.setdefault('error', None)
        if include_collections:
            result.setdefault('laws', [])
            result.setdefault('cases', [])
            result.setdefault('_summary', f'{label}已完成')
        return result
    except Exception as exc:
        return _build_external_failure(label, f'{label}失败: {str(exc)[:200]}', include_collections=include_collections)

def _collect_retrieval_status(external_results: dict) -> dict:
    completed = 0
    total = 0
    for key in RETRIEVAL_LABELS:
        total += 1
        if external_results.get(key, {}).get('status') == 'completed':
            completed += 1
    if external_results.get('qcc_data', {}).get('status') in ('completed', 'not_applicable'):
        completed += 1
    total += 1
    return {'completed': completed, 'total': total}

def _label_dimension_names(names):
    return label_dimension_names(names, DIMENSION_LABELS)

def _build_integrity_payload(integrity: dict) -> dict:
    return build_integrity_payload(integrity, DIMENSION_LABELS)

def _persist_external_cache(case_id: str, external_results: dict) -> None:
    save_results(case_id, external_results)

def _render_dimension_alert(result: dict, fallback_message: str=''):
    status = result.get('status')
    if status == 'failed':
        accent_notice(result.get('error') or fallback_message or '当前维度未完成')
    elif status == 'skipped':
        accent_notice(result.get('_summary') or fallback_message)

def _render_cached_retrieval(title: str, retrieval: dict, item_kind: str='mixed', expanded: bool=False):
    with st.expander(title, expanded=expanded):
        if not retrieval:
            accent_notice('暂无缓存检索结果')
            return
        status = retrieval.get('status')
        if status == 'failed':
            accent_notice(retrieval.get('error') or retrieval.get('_summary') or '检索失败')
            return
        if status == 'skipped':
            accent_notice(retrieval.get('_summary') or '当前模式未执行外部检索')
            return
        st.caption(retrieval.get('_summary', '已读取缓存检索结果'))
        if item_kind in ('mixed', 'laws'):
            for law in retrieval.get('laws', [])[:5]:
                st.markdown(f"**{law.get('title', '?')}**")
                if law.get('content'):
                    st.caption(str(law.get('content'))[:300])
                if law.get('timeliness'):
                    st.caption(f"时效: {law.get('timeliness')}")
        if item_kind in ('mixed', 'cases'):
            for case_item in retrieval.get('cases', [])[:8]:
                st.markdown(f"**{case_item.get('title', '?')}**")
                meta = ' · '.join([x for x in [case_item.get('court', ''), case_item.get('date', '')] if x])
                if meta:
                    st.caption(meta)
                if case_item.get('summary'):
                    st.caption(str(case_item.get('summary'))[:200])

def _extract_primary_defendant(case_description: str) -> dict:
    return extract_defendant_info_result(case_description, extract_defendant_info_fn=extract_defendant_info, use_mock=_use_mock_mode())

def _refresh_external_results(case, report_markdown: str='') -> dict:
    return build_external_results(search_rights=search_for_rights_foundation, search_infringement=search_for_infringement, search_procedure=search_for_procedure, search_moot_court=search_for_moot_court, search_financial=search_for_financial, search_precedent=search_for_precedent, safe_external_call=_safe_external_call, build_external_failure=_build_external_failure, extract_defendant_info_fn=extract_defendant_info, search_financial_qcc=search_for_financial_qcc_full, run_verification_phase=run_verification_phase, retrieval_labels=RETRIEVAL_LABELS, mode_label=RUNTIME_CONFIG['mode_label'], use_mock=_use_mock_mode(), case_description=case.case_description, report_markdown=report_markdown)

def _eval_flow_state_key(case_id: str) -> str:
    return eval_flow_state_key(case_id)

def _default_eval_flow_state(selected_step: Optional[str]=None) -> dict:
    return default_eval_flow_state(selected_step)

def _completed_eval_steps(eval_data: Optional[dict]) -> list[str]:
    return completed_eval_steps(eval_data, EVAL_FLOW_STEPS)

def _ensure_eval_flow_state(case_id: str, eval_data: Optional[dict]=None) -> dict:
    key = _eval_flow_state_key(case_id)
    existing = st.session_state.get(key)
    if existing and existing.get('running'):
        return existing
    completed = _completed_eval_steps(eval_data)
    default_selected = completed[-1] if completed else EVAL_FLOW_STEPS[0]['id']
    valid_choices = set(completed) or {default_selected}
    selected = existing.get('selected_step') if existing and existing.get('selected_step') in valid_choices else default_selected
    state = {'running': False, 'current_step': None, 'completed_steps': completed, 'selected_step': selected}
    st.session_state[key] = state
    return state

def _set_eval_flow_state(case_id: str, *, running=None, current_step=None, completed_steps=None, selected_step=None) -> dict:
    key = _eval_flow_state_key(case_id)
    state = dict(st.session_state.get(key) or _default_eval_flow_state())
    if running is not None:
        state['running'] = running
    if current_step is not None or running is False:
        state['current_step'] = current_step
    if completed_steps is not None:
        state['completed_steps'] = list(completed_steps)
    if selected_step is not None:
        state['selected_step'] = selected_step
    st.session_state[key] = state
    return state

def _eval_flow_visual_state(step_id: str, flow_state: dict) -> str:
    return eval_flow_visual_state(step_id, flow_state)

def _eval_flow_group_widths(step_count: int) -> list[float]:
    return eval_flow_group_widths(step_count)

def _render_eval_flow_card(case_id: str, flow_state: dict, interactive: bool=True, render_token: str='base') -> None:
    if flow_state.get('running') and flow_state.get('current_step'):
        status_text = f"当前进行：{EVAL_FLOW_MAP[flow_state['current_step']]['full_title']}"
    elif flow_state.get('completed_steps'):
        status_text = f"已完成 {len(flow_state.get('completed_steps', []))}/{len(EVAL_FLOW_STEPS)} 个环节"
    else:
        status_text = '尚未开始评估'
    with st.container(key=f'eval_flow_card_shell_{render_token}'):
        st.markdown(f'\n            <div class="eval-flow-header">\n                <div>\n                    <div class="eval-flow-title">评估主流程</div>\n                    <div class="eval-flow-subtitle">点击已完成节点可回看对应评估内容。进行中的节点会以淡橙色呼吸高亮显示。</div>\n                </div>\n                <div class="eval-flow-status">{status_text}</div>\n            </div>\n            ', unsafe_allow_html=True)
        completed = set(flow_state.get('completed_steps', []))
        for group_name, step_ids in EVAL_FLOW_GROUPS:
            st.markdown(f'<div class="eval-flow-group-title">{group_name}</div>', unsafe_allow_html=True)
            widths = _eval_flow_group_widths(len(step_ids))
            cols = st.columns(widths)
            col_idx = 0
            for idx, step_id in enumerate(step_ids):
                step_meta = EVAL_FLOW_MAP[step_id]
                visual_state = _eval_flow_visual_state(step_id, flow_state)
                with cols[col_idx]:
                    with st.container(key=f'eval_flow_step_{visual_state}_{case_id}_{step_id}_{render_token}'):
                        can_click = interactive and step_id in completed
                        disabled = not interactive or visual_state == 'upcoming'
                        if st.button(step_meta['full_title'], key=f'eval_flow_btn_{case_id}_{step_id}_{render_token}', use_container_width=True, type='primary' if visual_state == 'current' else 'secondary', disabled=disabled):
                            if can_click:
                                _set_eval_flow_state(case_id, running=flow_state.get('running'), current_step=flow_state.get('current_step'), completed_steps=flow_state.get('completed_steps', []), selected_step=step_id)
                                st.rerun()
                col_idx += 1
                if idx < len(step_ids) - 1:
                    with cols[col_idx]:
                        st.markdown('<div class="eval-flow-arrow">→</div>', unsafe_allow_html=True)
                    col_idx += 1
MOOT_ROLE_META = {'judge': {'label': '法官', 'role_name': '审判法官'}, 'plaintiff': {'label': '原告', 'role_name': '原告代理律师'}, 'defendant': {'label': '被告', 'role_name': '被告代理律师'}}

def _moot_round_to_dict(round_result) -> dict:
    return moot_round_to_dict(round_result)

def _moot_role_type(round_item: Optional[dict]) -> Optional[str]:
    return moot_role_type(round_item)

def _build_moot_round_stub(rounds: list[dict], error: Optional[str]=None) -> dict:
    return build_moot_round_stub(rounds, error)

def _build_moot_status_snapshot(eval_data: Optional[dict], flow_state: dict) -> dict:
    return build_moot_status_snapshot(eval_data, flow_state)

def _render_moot_status_card(case_id: str, eval_data: Optional[dict], flow_state: dict, render_token: str='base') -> None:
    snapshot = _build_moot_status_snapshot(eval_data, flow_state)

    def _role_node_html(role_key: str) -> str:
        meta = MOOT_ROLE_META[role_key]
        state = snapshot['role_states'][role_key]
        note = '当前发言' if state == 'current' else '已入场' if state == 'complete' else '待发言'
        return f"""<div class="moot-role-node moot-role-{role_key} moot-state-{state}"><div class="moot-role-name">{meta['label']}</div><div class="moot-role-note">{note}</div></div>"""
    with st.container(key=f'moot_status_card_shell_{render_token}'):
        st.markdown(f"""\n            <div class="moot-status-header">\n                <div>\n                    <div class="moot-status-title">模拟法庭态势</div>\n                    <div class="moot-status-subtitle">固定脚本式三角色庭审编排。这里展示当前是谁在发言，以及已推进到哪一段。</div>\n                </div>\n                <div class="moot-status-badge">{snapshot['status_label']}</div>\n            </div>\n            <div class="moot-status-summary">\n                <div class="moot-status-metric"><span class="moot-status-metric-label">当前阶段</span><span class="moot-status-metric-value">{snapshot['stage_name']}</span></div>\n                <div class="moot-status-metric"><span class="moot-status-metric-label">当前发言</span><span class="moot-status-metric-value">{snapshot['speaker_name']}</span></div>\n                <div class="moot-status-metric"><span class="moot-status-metric-label">已完成轮次</span><span class="moot-status-metric-value">{snapshot['completed_count']}/{snapshot['total_rounds']}</span></div>\n            </div>\n            <div class="moot-triangle-shell">\n                <div class="moot-link moot-link-left"></div>\n                <div class="moot-link moot-link-right"></div>\n                <div class="moot-link moot-link-base"></div>\n                {_role_node_html('judge')}\n                {_role_node_html('plaintiff')}\n                {_role_node_html('defendant')}\n            </div>\n            """, unsafe_allow_html=True)
        st.caption('进入 1.4 模拟法庭后，右侧态势卡会跟随当前轮次更新；完整庭审全文仍保留在独立的「模拟法庭」页中。')
        if st.button('查看完整模拟法庭 →', key=f'goto_moot_full_{case_id}_{render_token}', use_container_width=True, disabled=not snapshot['has_rounds']):
            st.session_state['nav_target'] = '模拟法庭'
            st.rerun()

def _render_eval_moot_live_content(eval_data: dict) -> None:
    moot_r = eval_data.get('moot') or {}
    rounds = list(moot_r.get('rounds', []) or [])
    if not rounds:
        empty_state_notice('模拟法庭开始后，这里会展示当前轮次的发言内容。')
        return
    current_round = rounds[-1]
    role_key = _moot_role_type(current_round) or 'plaintiff'
    role_color = ROLE_COLORS.get(role_key, COLORS['accent'])
    total_rounds = max(7, len(rounds))
    cols = st.columns(3)
    cols[0].metric('当前发言', current_round.get('role_name', MOOT_ROLE_META[role_key]['role_name']))
    cols[1].metric('当前阶段', current_round.get('step_name', '模拟法庭'))
    cols[2].metric('已完成轮次', f'{len(rounds)}/{total_rounds}')
    st.markdown(f"""\n        <div style="margin:14px 0 10px 0;padding:12px 14px;border:1px solid {role_color};border-left:4px solid {role_color};background:#fffaf8;">\n            <div style="font-size:0.72rem;color:{role_color};text-transform:uppercase;letter-spacing:0.08em;font-weight:700;margin-bottom:4px;">当前发言内容</div>\n            <div style="font-size:0.85rem;color:#666;">本轮由 {current_round.get('role_name', MOOT_ROLE_META[role_key]['role_name'])} 发言，内容已同步展示在下方。</div>\n        </div>\n        """, unsafe_allow_html=True)
    chat_bubble(current_round.get('role_name', MOOT_ROLE_META[role_key]['role_name']), current_round.get('step_name', '模拟法庭'), current_round.get('content', ''), role_key, truncate=400)
    if len(rounds) > 1:
        previous_round = rounds[-2]
        st.caption(f"上一轮：{previous_round.get('role_name', '')} · {previous_round.get('step_name', '')}")

def _run_moot_court_with_updates(case_description: str, rights_assessment: str, infringement_assessment: str, evidence_summary: str, on_round=None) -> dict:
    total_rounds = 7
    engine = _ensure_engine()
    final_result = engine['run_moot_court_simulation'](case_description, rights_assessment=rights_assessment, infringement_assessment=infringement_assessment, evidence_summary=evidence_summary)
    rounds = list(final_result.get('rounds', []) or [])
    if not rounds:
        return final_result
    total_rounds = max(total_rounds, len(rounds))
    for idx in range(len(rounds)):
        partial = _build_moot_round_stub(rounds[:idx + 1], error=final_result.get('error'))
        if idx == len(rounds) - 1:
            partial = dict(final_result)
            partial['rounds'] = rounds[:idx + 1]
        if on_round:
            on_round(partial, idx, total_rounds)
        time.sleep(0.16)
    return final_result

def _render_eval_rights_content(eval_data: dict) -> None:
    external_cache = eval_data.get('external_results', {})
    rights_r = eval_data.get('rights') or {}
    sub_scores = []
    for key, value in rights_r.get('sub_scores', {}).items():
        label = {'validity': '商标有效性', 'usage_continuity': '连续使用', 'coverage': '覆盖范围', 'well_known_status': '驰名地位', 'risk_of_invalidation': '无效风险'}.get(key, key)
        if isinstance(value, dict):
            sub_scores.append({'name': label, 'score': value.get('score', 0), 'detail': value.get('reason', ''), 'status': 'pass' if value.get('score', 0) >= 60 else 'warning'})
        else:
            sub_scores.append({'name': label, 'score': value, 'status': 'pass' if value >= 60 else 'warning'})
    dim_card('1.1 权利基础评估', rights_r.get('score', 0), rights_r.get('analysis', ''), sub_items=sub_scores, extra='优势: ' + ', '.join(rights_r.get('strengths', ['-'])) + '\n\n风险: ' + ', '.join(rights_r.get('risks', ['-'])))
    _render_dimension_alert(rights_r)
    _render_cached_retrieval('北大法宝 · 法条检索', external_cache.get('rights_retrieval', {}), 'laws', True)

def _render_eval_infringement_content(eval_data: dict) -> None:
    external_cache = eval_data.get('external_results', {})
    infr_r = eval_data.get('infringement') or {}
    el_items = [{'name': el.get('name', '未知要素'), 'score': el.get('score', 0), 'status': el.get('status', 'pass'), 'detail': el.get('analysis', '')} for el in infr_r.get('elements', [])]
    dim_card('1.2 侵权认定评估', infr_r.get('score', 0), infr_r.get('analysis', ''), sub_items=el_items)
    _render_dimension_alert(infr_r)
    _render_cached_retrieval('北大法宝 · 类案检索', external_cache.get('infringement_retrieval', {}), 'mixed', True)

def _render_eval_procedure_content(eval_data: dict) -> None:
    external_cache = eval_data.get('external_results', {})
    proc_r = eval_data.get('procedure') or {}
    proc_items = [{'name': item.get('name', '未知程序项'), 'status': item.get('status', 'pass'), 'detail': item.get('detail', '')} for item in proc_r.get('items', [])]
    dim_card('1.3 诉讼程序审查', proc_r.get('score', 0), proc_r.get('analysis', ''), sub_items=proc_items)
    _render_dimension_alert(proc_r)
    _render_cached_retrieval('北大法宝 · 法条检索', external_cache.get('procedure_retrieval', {}), 'laws', True)

def _render_eval_moot_content(eval_data: dict) -> None:
    external_cache = eval_data.get('external_results', {})
    moot_r = eval_data.get('moot') or {}
    coeff = eval_data.get('correction_coeff', 1.0)
    if moot_r.get('status') == 'failed' and (not moot_r.get('rounds')):
        accent_notice(moot_r.get('error', '模拟法庭未完成'))
    else:
        defense_strength = moot_r.get('defense_strength', 50)
        coeff_color = COLORS['danger'] if coeff < 0.9 else COLORS['warning'] if coeff < 1.0 else COLORS['success']
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            metric_card('对抗修正系数', f'{coeff:.2f}', '中性=1.0', coeff_color)
        with col_c2:
            metric_card('被告抗辩强度', f'{defense_strength}/100', '用于理解对抗压力', COLORS['warning'])
        focus_points = moot_r.get('focus_points', [])
        if focus_points:
            st.markdown(f"""\n                <div class="card" style="border-left:4px solid {COLORS['accent']};">\n                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">争议焦点</div>\n                    {''.join((f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">{i + 1}. {fp}</div>' for i, fp in enumerate(focus_points)))}\n                </div>\n                """, unsafe_allow_html=True)
        rounds = moot_r.get('rounds', [])
        if rounds:
            st.markdown(f"""\n                <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">\n                    庭审记录（共{len(rounds)}轮发言）\n                </div>\n                """, unsafe_allow_html=True)
            for rnd in rounds:
                role_name = rnd.get('role_name', rnd.get('role', rnd.get('speaker', '')))
                step_name = rnd.get('step_name', '')
                content = rnd.get('content', '')
                role_type = _moot_role_type(rnd) or 'plaintiff'
                chat_bubble(role_name, step_name, content, role_type)
        weak_points = moot_r.get('weak_points', [])
        if weak_points:
            st.markdown(f"""\n                <div class="card" style="border-left:4px solid {COLORS['danger']};">\n                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">对抗暴露的薄弱环节</div>\n                    {''.join((f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">- {wp}</div>' for wp in weak_points))}\n                </div>\n                """, unsafe_allow_html=True)
    _render_cached_retrieval('北大法宝 · 抗辩模式类案', external_cache.get('moot_retrieval', {}), 'cases', True)

def _render_eval_financial_content(eval_data: dict) -> None:
    external_cache = eval_data.get('external_results', {})
    fin_r = eval_data.get('financial') or {}
    qcc_d = eval_data.get('qcc_data', {})
    fin_score = fin_r.get('score', 0)
    de = fin_r.get('damages_estimate', {})
    te = fin_r.get('time_estimate', {})
    fin_extra = []
    if de:
        fin_extra.append(f"判赔预测: P10=¥{de.get('p10', '-')} / P50=¥{de.get('p50', '-')} / P90=¥{de.get('p90', '-')}")
    fin_extra.append(f"预估成本: ¥{fin_r.get('cost_estimate', '-')}")
    if te:
        fin_extra.append(f"时间: 一审{te.get('first_instance_months', '-')}月 + 二审{te.get('second_instance_months', '-')}月 + 执行{te.get('enforcement_months', '-')}月")
    fin_extra.append(f"回款概率: {fin_r.get('recovery_probability', '-')}%")
    dim_card('2.1 财务回报评估', fin_score, fin_r.get('analysis', ''), extra='\n'.join(fin_extra))
    _render_dimension_alert(fin_r)
    if qcc_d.get('status') == 'completed' and qcc_d.get('stages'):
        stages = qcc_d.get('stages', {})
        metrics = qcc_d.get('metrics', {})
        defend_info = external_cache.get('defendant_info', {})
        b_stage = stages.get('B_基本盘', {})
        d_stage = stages.get('D_风险下钻', {})
        with st.expander('🏢 企查查 · 被告财务画像（实时查询）', expanded=True):
            if defend_info.get('name'):
                dtype_label = {'enterprise': '企业', 'individual': '自然人', 'self_employed': '个体户'}.get(defend_info.get('type', ''), defend_info.get('type', ''))
                hints = []
                if defend_info.get('industry_hint'):
                    hints.append(defend_info['industry_hint'])
                if defend_info.get('scale_hint'):
                    hints.append(defend_info['scale_hint'])
                hint_text = f"（{' · '.join(hints)}）" if hints else ''
                st.markdown(f"### 🔍 被告识别\n**{defend_info['name']}** · {dtype_label} {hint_text}")
            reg_items = b_stage.get('工商登记', {}).get('_items', [])
            reg_info = reg_items[0] if isinstance(reg_items, list) and reg_items else None
            jdebt_count = d_stage.get('被执行人', {}).get('_count', 0) if d_stage else 0
            if reg_info or jdebt_count is not None:
                st.markdown('### 🔑 关键项')
                k1, k2, k3, k4 = st.columns(4)
                capital = paid = status = insured = '-'
                if isinstance(reg_info, dict):
                    capital = reg_info.get('注册资本', reg_info.get('注册资金', '-'))
                    paid = reg_info.get('实缴资本', reg_info.get('实缴资金', '-'))
                    status = reg_info.get('登记状态', reg_info.get('企业状态', '-'))
                    insured = reg_info.get('参保人数', '-')
                k1.metric('注册资本', f'{capital}', f'实缴{paid}' if paid and paid != capital else '')
                k2.metric('经营状态', status)
                k3.metric('参保人数', f'{insured}人' if insured != '-' else '-')
                if jdebt_count > 0:
                    k4.metric('被执行', f'{jdebt_count}条', delta_color='inverse')
                else:
                    k4.metric('被执行', '无记录 ✅')
            st.caption(qcc_d.get('_summary', ''))
            st.markdown('### 📊 QCC 实测指标')
            c1, c2, c3 = st.columns(3)
            c1.metric('回款概率（QCC测算）', f"{metrics.get('recovery_probability', '-')}%")
            c2.metric('判赔方向', metrics.get('damages_adjustment', '-'))
            c3.metric('时间延长', f"+{metrics.get('time_extra_months', 0)}月")
            reds = metrics.get('red_flags', [])
            greens = metrics.get('green_flags', [])
            if reds:
                st.error('🚨 风险信号: ' + ' | '.join(reds))
            if greens:
                st.success('✅ 利好信号: ' + ' | '.join(greens))
            a = stages.get('A_主体锁定', {})
            if a.get('locked_name'):
                st.markdown('### 🎯 主体锁定')
                st.markdown(f"**{a.get('locked_name')}**（信用代码: {a.get('credit_code', '-')}）")
                candidates = a.get('candidates', [])
                if len(candidates) > 1:
                    with st.expander(f'查看更多候选（{len(candidates)}个）', expanded=False):
                        for c in candidates:
                            st.caption(f"- {c.get('name', '?')}")
            if b_stage:
                st.markdown('### 📋 基本盘（工商 / 财务 / 人员）')
                b_lines = []
                for label in ('企业简介', '财务数据', '上市信息', '分支机构', '对外投资', '年报', '核心人员', '实际控制人'):
                    v = b_stage.get(label, {})
                    if isinstance(v, dict) and v.get('_count', 0) > 0:
                        b_lines.append(f"- **{label}**: {v.get('_summary', '-')}")
                if b_lines:
                    st.markdown('\n'.join(b_lines))
            c_stage = stages.get('C_风险分诊', {})
            if d_stage:
                st.markdown('### ⚠️ 风险明细')
                risk_hit = []
                for label in ('失信信息', '被执行人', '终本案件', '限高消费', '经营异常', '严重违法', '股权冻结', '动产抵押', '土地抵押', '股权出质', '司法拍卖', '欠税公告', '税收违法', '税务异常', '行政处罚', '惩戒名单', '违约信息', '裁判文书', '法院立案', '限制出境'):
                    v = d_stage.get(label, {})
                    if isinstance(v, dict) and v.get('_count', 0) > 0:
                        risk_hit.append(f"- 🚨 **{label}**: {v.get('_summary', '-')}")
                if risk_hit:
                    st.markdown('\n'.join(risk_hit))
                else:
                    st.success('✅ 无命中风险项')
                if c_stage.get('_summary'):
                    st.caption(f"风险分诊: {c_stage['_summary']}")
            f_stage = stages.get('F_经营规模', {})
            if f_stage:
                st.markdown('### 🏭 经营规模与侵权渠道')
                ch_lines = []
                for label in ('商标资产', '线上店铺', 'APP信息', '小程序', '微信公众号', '抖音账号', '招投标', '融资记录', '荣誉信息', '榜单排名', '招聘信息'):
                    v = f_stage.get(label, {})
                    if isinstance(v, dict):
                        ch_lines.append(f"- **{label}**: {v.get('_summary', '-')}")
                if ch_lines:
                    st.markdown('\n'.join(ch_lines))
                if f_stage.get('_summary'):
                    st.caption(f"汇总: {f_stage['_summary']}")
            st.markdown('---')
            st.caption('📐 **数据链**: 案文 → DeepSeek NER 识别被告 → 企查查 MCP 实时查询 → 回款概率指标 → 注入 DeepSeek 财务分析\n\n💡 上方「2.1 财务回报评估」卡片中的评分由 DeepSeek 综合北大法宝判赔数据 + 以上企查查实测指标后给出。')
    elif qcc_d.get('_summary'):
        accent_notice(qcc_d.get('_summary'))
    _render_cached_retrieval('北大法宝 · 判赔数据类案', external_cache.get('financial_retrieval', {}), 'cases', True)

def _render_eval_precedent_content(eval_data: dict, goal_type: str) -> None:
    external_cache = eval_data.get('external_results', {})
    prec_r = eval_data.get('precedent') or {}
    fin_r = eval_data.get('financial') or {}
    biz_s = eval_data.get('business_score', 0)
    dim_card('2.2 判例价值评估', prec_r.get('score', 0), prec_r.get('analysis', ''), extra=f"首案指数: {prec_r.get('first_case_index', '-')} | 影响力级别: {prec_r.get('influence_level', '-')}")
    _render_dimension_alert(prec_r)
    _render_cached_retrieval('北大法宝 · 首案检索', external_cache.get('precedent_retrieval', {}), 'cases', True)
    accent_notice(f'维度二 业务预期综合得分: {biz_s} 分')
    if goal_type == '要钱':
        st.caption(f"公式: 0.9×财务({fin_r.get('score', 0)}) + 0.1×判例({prec_r.get('score', 0)}) = {biz_s}")
    else:
        st.caption(f"公式: 0.1×财务({fin_r.get('score', 0)}) + 0.9×判例({prec_r.get('score', 0)}) = {biz_s}")

def _render_eval_evidence_content(eval_data: dict) -> None:
    evid_r = eval_data.get('evidence') or {}
    evid_s = eval_data.get('evidence_score', 0)
    ev_items = [{'name': item.get('requirement', '未知证据项'), 'status': item.get('status', '不足'), 'detail': item.get('analysis', '')} for item in evid_r.get('evidence_matrix', [])]
    dim_card('证据就绪度评估', evid_r.get('score', 0), evid_r.get('analysis', ''), sub_items=ev_items, extra='补证建议: ' + '; '.join(evid_r.get('remediation_suggestions', ['无'])) + '\n\n取证技术建议: ' + evid_r.get('collection_advice', '根据证据类型自行判断'))
    _render_dimension_alert(evid_r)
    if evid_r.get('status') == 'failed':
        accent_notice('证据维度未完成，系统不会输出完整综合建议。')
    else:
        accent_notice(f'维度三 证据就绪度得分: {evid_s} 分')

def _render_eval_compact_summary(eval_data: dict, case_id: str, render_token: str='base') -> None:
    integrity_info = eval_data.get('integrity', {'is_complete': True, 'label': '完整', 'critical_issues': []})
    rec_data = eval_data.get('recommendation', {})
    final_s = eval_data.get('final_score')
    with st.container(key=f'eval_result_card_shell_{render_token}'):
        st.markdown('\n            <div class="eval-result-header">\n                <div>\n                    <div class="eval-result-title">最终结果</div>\n                    <div class="eval-result-subtitle">展示当前案件的三维得分、综合建议与结果校验状态。</div>\n                </div>\n            </div>\n            ', unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].metric('法律可行性', eval_data.get('legal_score', 0))
        cols[1].metric('业务预期', eval_data.get('business_score', 0))
        cols[2].metric('证据就绪度', eval_data.get('evidence_score', 0))
        cols[3].metric('综合分', '未生成' if final_s is None else final_s)
        st.caption(f"综合建议：{rec_data.get('recommendation', '待评估')} · 数据完整性：{integrity_info.get('label', '未知')} · 置信度：{eval_data.get('confidence_score', 0)}%")
        if integrity_info.get('critical_issues'):
            accent_notice('关键未完成项：' + '、'.join(integrity_info.get('critical_issues', [])))
        if eval_data.get('external_results', {}).get('generated_at'):
            st.caption(f"结果页默认展示缓存数据，最近缓存时间：{eval_data['external_results']['generated_at']}")
        if not _use_mock_mode():
            valid_status = get_validation_status(case_id)
            st.caption(f"法条验证：{('通过' if valid_status.get('provisions_validated') else '待验证')} · 法规识别：{('通过' if valid_status.get('laws_validated') else '待验证')} · 案号识别：{('通过' if valid_status.get('cases_validated') else '待验证')}")

def _render_eval_detail_card(case_id: str, case, eval_data: Optional[dict], flow_state: dict, pending_message: Optional[str]=None, render_token: str='base') -> None:
    selected_step = flow_state.get('current_step') if flow_state.get('running') and flow_state.get('current_step') else flow_state.get('selected_step')
    selected_step = selected_step or EVAL_FLOW_STEPS[0]['id']
    step_meta = EVAL_FLOW_MAP[selected_step]
    tag_label = '当前进行' if flow_state.get('running') and selected_step == flow_state.get('current_step') else '当前展示'
    with st.container(key=f'eval_detail_card_shell_{render_token}'):
        st.markdown(f"""\n            <div class="eval-detail-header">\n                <div>\n                    <div class="eval-detail-title">{step_meta['full_title']}</div>\n                    <div class="eval-detail-subtitle">{step_meta['source']}</div>\n                </div>\n                <div class="eval-detail-tag">{tag_label}</div>\n            </div>\n            """, unsafe_allow_html=True)
        if pending_message:
            accent_notice(pending_message)
        if not eval_data or not eval_data.get(selected_step):
            empty_state_notice('开始评估后，这里会展示当前环节的详细分析内容。评估完成后，可点击上方已完成节点回看。')
            return
        if selected_step == 'rights':
            _render_eval_rights_content(eval_data)
        elif selected_step == 'infringement':
            _render_eval_infringement_content(eval_data)
        elif selected_step == 'procedure':
            _render_eval_procedure_content(eval_data)
        elif selected_step == 'moot':
            if flow_state.get('running') and selected_step == flow_state.get('current_step'):
                _render_eval_moot_live_content(eval_data)
            else:
                _render_eval_moot_content(eval_data)
        elif selected_step == 'financial':
            _render_eval_financial_content(eval_data)
        elif selected_step == 'precedent':
            _render_eval_precedent_content(eval_data, case.goal_type if case else '要钱')
        elif selected_step == 'evidence':
            _render_eval_evidence_content(eval_data)

def render_radar_svg(scores: dict, size: int=340) -> str:
    labels = ['法律可行性', '业务预期', '证据就绪度']
    values = [scores.get(k, 0) for k in labels]
    cx, cy, r = (size // 2, size // 2, size // 2 - 50)
    angles = [math.radians(90), math.radians(210), math.radians(330)]

    def point(angle, dist_ratio):
        x = cx + r * dist_ratio * math.cos(angle)
        y = cy - r * dist_ratio * math.sin(angle)
        return (x, y)
    grid_paths = ''
    for level in [0.33, 0.67, 1.0]:
        pts = [point(a, level) for a in angles]
        pts_str = ' '.join((f'{x:.1f},{y:.1f}' for x, y in pts))
        grid_paths += f'<polygon points="{pts_str}" fill="none" stroke="#e5e7eb" stroke-width="1"/>\n'
    axis_lines = ''
    for a in angles:
        x, y = point(a, 1.0)
        axis_lines += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>\n'
    label_texts = ''
    label_offsets = [(0, -15), (-10, 12), (10, 12)]
    for i, (a, lb) in enumerate(zip(angles, labels)):
        x, y = point(a, 1.15)
        ox, oy = label_offsets[i]
        label_texts += f'<text x="{x + ox:.1f}" y="{y + oy:.1f}" text-anchor="middle" font-size="13" fill="#374151">{lb}</text>\n'
    data_pts = [point(a, v / 100.0) for a, v in zip(angles, values)]
    data_str = ' '.join((f'{x:.1f},{y:.1f}' for x, y in data_pts))
    dots = ''
    for x, y in data_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#0d1429"/>\n'
    score_texts = ''
    for i, (a, v) in enumerate(zip(angles, values)):
        x, y = point(a, v / 100.0 + 0.08)
        score_texts += f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="16" font-weight="bold" fill="#0d1429">{v}分</text>\n'
    svg = f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">\n<rect width="{size}" height="{size}" fill="white" rx="2"/>\n{grid_paths}\n{axis_lines}\n{label_texts}\n<polygon points="{data_str}" fill="#0d1429" fill-opacity="0.08" stroke="#0d1429" stroke-width="2.5"/>\n{dots}\n{score_texts}\n</svg>'
    return svg

def render_radar_html(scores: dict, size: int=340) -> str:
    svg = render_radar_svg(scores, size)
    b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:{size}px;display:block;margin:0 auto;"/>'
TOP_LEVEL_PAGES = ['工作台', '系统配置', '关于']
WORKBENCH_PAGES = ['案件列表', '新建案件', '评估分析', '模拟法庭', '评估报告']
WORKBENCH_PROGRESS = {'新建案件': 1, '案件列表': 2, '评估分析': 3, '模拟法庭': 4, '评估报告': 5}

def _build_workbench_summary() -> dict:
    active_tab = st.session_state.get('workbench_tab', WORKBENCH_PAGES[0])
    current_case_name = st.session_state.get('current_case_name', '尚未选择案件')
    if 'current_case_id' in st.session_state:
        case_hint = f"当前案件 ID: {st.session_state['current_case_id']}"
    else:
        case_hint = '先新建案件，或从案件列表中选择一个继续。'
    progress_value = WORKBENCH_PROGRESS.get(active_tab, 1)
    progress_hint = f'工作台当前停留在「{active_tab}」'
    if active_tab == '评估分析':
        progress_hint = '工作台当前聚焦核心评估结果'
    elif active_tab == '模拟法庭':
        progress_hint = '工作台当前聚焦对抗检验'
    elif active_tab == '评估报告':
        progress_hint = '工作台当前聚焦结论与下载输出'
    return {'active_tab': active_tab, 'current_case_name': current_case_name, 'case_hint': case_hint, 'progress_text': f'{progress_value}/{len(WORKBENCH_PAGES)}', 'progress_hint': progress_hint}

def _activate_workbench_tab(target: str) -> None:
    st.session_state[S.PAGE] = '工作台'
    st.session_state[S.WORKBENCH_TAB] = target

def render_workbench_tab_row() -> None:
    active_tab = st.session_state.get('workbench_tab', WORKBENCH_PAGES[0])
    container_key = 'workbench_tabs_main'
    with st.container(key=container_key, horizontal=True, horizontal_alignment='distribute', gap=None):
        for tab_name in WORKBENCH_PAGES:
            if st.button(tab_name, key=f'{container_key}_{tab_name}', type='primary' if tab_name == active_tab else 'secondary', use_container_width=True):
                _activate_workbench_tab(tab_name)
                st.rerun()

def render_workbench_shell() -> None:
    summary = _build_workbench_summary()
    st.markdown(f"""\n    <div class="workbench-hero workbench-hero-compact">\n        <div class="workbench-stat-card compact">\n            <div class="workbench-stat-label">当前案件</div>\n            <div class="workbench-stat-value current-case">{summary['current_case_name']}</div>\n            <div class="workbench-stat-sub">{summary['case_hint']}</div>\n        </div>\n        <div class="workbench-stat-card compact">\n            <div class="workbench-stat-label">流程位置</div>\n            <div class="workbench-stat-value progress-value">{summary['progress_text']}</div>\n            <div class="workbench-stat-sub">当前停留在「{summary['active_tab']}」 · {summary['progress_hint']}</div>\n        </div>\n    </div>\n    """, unsafe_allow_html=True)
    render_workbench_tab_row()
    st.markdown("<div class='workbench-shell-gap'></div>", unsafe_allow_html=True)
if 'page' not in st.session_state:
    st.session_state[S.PAGE] = '工作台'
if 'workbench_tab' not in st.session_state:
    st.session_state['workbench_tab'] = '新建案件'
if st.session_state.get(S.NAV_TARGET):
    target = st.session_state.pop(S.NAV_TARGET)
    if target in WORKBENCH_PAGES:
        _activate_workbench_tab(target)
    elif target in TOP_LEVEL_PAGES:
        st.session_state['page'] = target
    st.rerun()
st.sidebar.markdown('\n<div style="padding:12px 8px 18px 8px;">\n    <div style="font-size:1.8rem;font-weight:800;color:#ffffff;letter-spacing:-0.04em;line-height:1;">\n        诉算\n    </div>\n    <div style="font-size:0.72rem;color:rgba(255,255,255,0.68);margin-top:6px;letter-spacing:0.12em;text-transform:uppercase;">\n        Soft IP Litigation Evaluation\n    </div>\n</div>\n', unsafe_allow_html=True)
st.sidebar.divider()
for opt in TOP_LEVEL_PAGES:
    is_active = st.session_state['page'] == opt
    if st.sidebar.button(opt, key=f'nav_{opt}', use_container_width=True, disabled=is_active):
        st.session_state['page'] = opt
        st.rerun()
st.sidebar.markdown('\n<style>\nsection[data-testid="stSidebar"] div[data-testid="stButton"] {\n    margin: 0 !important;\n    padding: 0 !important;\n}\nsection[data-testid="stSidebar"] button[kind="secondary"] {\n    background: transparent !important;\n    border: none !important;\n    box-shadow: none !important;\n    text-align: left !important;\n    justify-content: flex-start !important;\n    align-items: center !important;\n    padding: 14px 16px !important;\n    font-size: 0.95rem !important;\n    font-weight: 500 !important;\n    color: rgba(255,255,255,0.76) !important;\n    border-radius: 14px !important;\n    transition: all 0.18s ease !important;\n    width: 100% !important;\n    min-height: 46px !important;\n    line-height: 1.2 !important;\n    box-sizing: border-box !important;\n}\nsection[data-testid="stSidebar"] button[kind="secondary"] p,\nsection[data-testid="stSidebar"] button[kind="secondary"] div {\n    text-align: left !important;\n    justify-content: flex-start !important;\n    width: 100% !important;\n    line-height: 1.2 !important;\n    color: inherit !important;\n}\nsection[data-testid="stSidebar"] button[kind="secondary"]:not(:disabled):hover {\n    background: rgba(255,255,255,0.08) !important;\n    color: #ffffff !important;\n}\nsection[data-testid="stSidebar"] button[kind="secondary"]:disabled {\n    background: rgba(214,89,56,0.12) !important;\n    color: #ffffff !important;\n    cursor: default !important;\n    opacity: 1 !important;\n    box-shadow: inset 3px 0 0 #d65938 !important;\n}\nsection[data-testid="stSidebar"] button[kind="secondary"]:disabled p,\nsection[data-testid="stSidebar"] button[kind="secondary"]:disabled div {\n    color: #ffffff !important;\n    opacity: 1 !important;\n}\n</style>\n', unsafe_allow_html=True)
top_level_page = st.session_state['page']
if top_level_page == '工作台':
    render_workbench_shell()
page = st.session_state.get('workbench_tab', WORKBENCH_PAGES[0]) if top_level_page == '工作台' else top_level_page
if 'current_case_id' in st.session_state:
    st.sidebar.divider()
    st.sidebar.markdown('\n    <div style="font-size:0.65rem;color:#cce8eb;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;opacity:0.6;">\n        当前案件\n    </div>\n    ', unsafe_allow_html=True)
    st.sidebar.markdown(f"""\n    <div style="border:1px solid rgba(204,232,235,0.2);border-left:3px solid #d65938;padding:12px 14px;margin-bottom:4px;">\n        <div style="font-size:0.9rem;font-weight:600;color:#ffffff;">\n            {st.session_state.get('current_case_name', '未知案件')}\n        </div>\n        <div style="font-size:0.7rem;color:#cce8eb;opacity:0.6;margin-top:2px;">\n            ID: {st.session_state['current_case_id']}\n        </div>\n    </div>\n    """, unsafe_allow_html=True)
st.sidebar.divider()
mode_label = RUNTIME_CONFIG['mode_label']
mode_color = '#d65938' if RUNTIME_CONFIG['use_mock'] else '#a5d8dd'
st.sidebar.markdown(f'\n<div style="font-size:0.72rem;color:#cce8eb;opacity:0.7;">\n    <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{mode_color};margin-right:6px;"></span>\n    {mode_label}\n</div>\n<div style="font-size:0.65rem;color:#cce8eb;opacity:0.4;margin-top:4px;">\n    v{APP_VERSION} · © 2026 诉算\n</div>\n', unsafe_allow_html=True)
if RUNTIME_CONFIG['missing_required']:
    st.sidebar.markdown(f"""<div style="margin:10px 0;padding:10px 12px;border:1px solid #d65938;background:#fbe8e3;color:#0d1429;font-size:0.82rem;line-height:1.6;">真实 Demo 模式缺少配置：{'、'.join(RUNTIME_CONFIG['missing_required'])}。</div>""", unsafe_allow_html=True)
for warning in RUNTIME_CONFIG['optional_warnings']:
    st.sidebar.markdown(f'<div style="margin:10px 0;padding:10px 12px;border:1px solid #d65938;background:#fbe8e3;color:#0d1429;font-size:0.82rem;line-height:1.6;">{warning}</div>', unsafe_allow_html=True)
if RUNTIME_CONFIG.get('storage_notice'):
    st.sidebar.markdown(f"""<div style="margin:10px 0;padding:10px 12px;border:1px solid #d65938;background:#fbe8e3;color:#0d1429;font-size:0.82rem;line-height:1.6;">{RUNTIME_CONFIG['storage_notice']}</div>""", unsafe_allow_html=True)
if page == '新建案件':
    from ui.pages.new_case import render as render_new_case
    render_new_case()
elif page == '案件列表':
    from ui.pages.case_list import render as render_case_list
    render_case_list(on_delete_case=lambda case_id: None, on_view_case=lambda case_id: None, reset_case_outputs_fn=_reset_case_outputs, clear_current_selection_fn=_clear_current_case_selection)
elif page == '评估分析':
    from ui.pages.eval_analysis import render as render_eval_analysis
    render_eval_analysis(COLORS=COLORS, CRITICAL_DIMENSIONS=CRITICAL_DIMENSIONS, EVAL_FLOW_STEPS=EVAL_FLOW_STEPS, EVAL_FLOW_GROUPS=EVAL_FLOW_GROUPS, EVAL_FLOW_MAP=EVAL_FLOW_MAP, DIMENSION_LABELS=DIMENSION_LABELS, RETRIEVAL_LABELS=RETRIEVAL_LABELS, RUNTIME_CONFIG=RUNTIME_CONFIG, RUNTIME_DIR=RUNTIME_DIR, use_mock_mode=_use_mock_mode, ensure_eval_flow_state=_ensure_eval_flow_state, set_eval_flow_state=_set_eval_flow_state, render_eval_flow_card=_render_eval_flow_card, render_moot_status_card=_render_moot_status_card, render_eval_detail_card=_render_eval_detail_card, render_eval_compact_summary=_render_eval_compact_summary, render_radar_html=render_radar_html, render_radar_svg=render_radar_svg, case_status_label=_case_status_label, case_status_text_color=_case_status_text_color, collect_retrieval_status=_collect_retrieval_status, safe_external_call_fn=_safe_external_call, refresh_external_results=_refresh_external_results, reset_case_outputs=_reset_case_outputs, run_moot_court_with_updates=_run_moot_court_with_updates, persist_external_cache=_persist_external_cache, MOOT_ROLE_META=MOOT_ROLE_META, evaluate_rights_foundation=evaluate_rights_foundation, evaluate_infringement=evaluate_infringement, evaluate_procedure=evaluate_procedure, evaluate_financial_return=evaluate_financial_return, evaluate_precedent_value=evaluate_precedent_value, evaluate_evidence_readiness=evaluate_evidence_readiness, extract_defendant_info=extract_defendant_info, search_for_rights_foundation=search_for_rights_foundation, search_for_infringement=search_for_infringement, search_for_procedure=search_for_procedure, search_for_moot_court=search_for_moot_court, search_for_financial=search_for_financial, search_for_precedent=search_for_precedent, search_for_financial_qcc_full=search_for_financial_qcc_full, run_verification_phase=run_verification_phase, get_linked_content=get_linked_content, generate_all_queries=generate_all_queries, APP_VERSION=APP_VERSION)
elif page == '模拟法庭':
    from ui.pages.moot_court import render as render_moot_court
    render_moot_court(use_mock_mode_fn=_use_mock_mode)
elif page == '评估报告':
    from ui.pages.eval_report import render as render_eval_report
    render_eval_report(render_radar_html_fn=render_radar_html, render_radar_svg_fn=render_radar_svg)
elif page == '系统配置':
    from ui.pages.settings import render as render_settings
    render_settings()
elif page == '关于':
    from ui.pages.about import render as render_about
    render_about()