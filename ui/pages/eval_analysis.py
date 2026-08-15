"""评估分析 — 七步评估流水线 + 三维评分 + 模拟法庭实时展示"""
import streamlit as st
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from cache import load_eval_cache, save_eval_cache
from services import build_dimension_result, build_external_failure, build_integrity_payload, extract_defendant_info_result
from state import default_eval_flow_state
from database import SessionLocal, Case, ScoreSnapshot, Report
from report_generator import generate_markdown_report
from scoring import calculate_legal_feasibility, calculate_business_expectation, calculate_overall_score, calculate_confidence_score, evaluate_data_integrity, generate_recommendation
from styles import page_header, accent_notice, empty_state_notice, metric_card, form_section_title

def render(*, COLORS: dict, CRITICAL_DIMENSIONS: list, EVAL_FLOW_STEPS: list, EVAL_FLOW_GROUPS: list, EVAL_FLOW_MAP: dict, DIMENSION_LABELS: dict, RETRIEVAL_LABELS: dict, RUNTIME_CONFIG: dict, RUNTIME_DIR: Path, use_mock_mode: Callable, ensure_eval_flow_state: Callable, set_eval_flow_state: Callable, render_eval_flow_card: Callable, render_moot_status_card: Callable, render_eval_detail_card: Callable, render_eval_compact_summary: Callable, render_radar_html: Callable, render_radar_svg: Callable, case_status_label: Callable, case_status_text_color: Callable, collect_retrieval_status: Callable, safe_external_call_fn: Callable, refresh_external_results: Callable, reset_case_outputs: Callable, run_moot_court_with_updates: Callable, persist_external_cache: Callable, MOOT_ROLE_META: dict, evaluate_rights_foundation: Callable, evaluate_infringement: Callable, evaluate_procedure: Callable, evaluate_financial_return: Callable, evaluate_precedent_value: Callable, evaluate_evidence_readiness: Callable, extract_defendant_info: Callable, search_for_rights_foundation: Callable, search_for_infringement: Callable, search_for_procedure: Callable, search_for_moot_court: Callable, search_for_financial: Callable, search_for_precedent: Callable, search_for_financial_qcc_full: Callable, run_verification_phase: Callable, get_linked_content: Callable, generate_all_queries: Callable, APP_VERSION: str):
    page_header('诉前评估分析', '三维乘法评分模型 · 法律可行性 × 业务预期 × 证据就绪度')
    if 'current_case_id' not in st.session_state:
        preview_state = default_eval_flow_state(selected_step=EVAL_FLOW_STEPS[0]['id'])
        preview_cols = st.columns([1.7, 1.0], gap='medium')
        with preview_cols[0]:
            render_eval_flow_card('preview', preview_state, interactive=False, render_token='preview')
        with preview_cols[1]:
            render_moot_status_card('preview', None, preview_state, render_token='preview')
        render_eval_detail_card('preview', None, None, preview_state, render_token='preview')
        st.stop()
    case_id = st.session_state['current_case_id']
    case_name = st.session_state.get('current_case_name', '未知案件')
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error('案件不存在')
            st.stop()
        eval_key = f'eval_results_{case_id}'
        eval_data = st.session_state.get(eval_key) or load_eval_cache(case_id)
        if eval_data and eval_key not in st.session_state:
            st.session_state[eval_key] = eval_data
        status_text = case_status_label(case.status)
        st_color = case_status_text_color(case.status)
        notice_key = f'case_update_notice_{case_id}'
        edit_toggle_key = f'editing_case_{case_id}'
        with st.container(key=f'eval_case_panel_{case_id}'):
            st.html(f"""\n                <div class="eval-case-summary">\n                    <div class="eval-case-summary-main">\n                        <div class="eval-case-summary-title">{case_name}</div>\n                        <div class="eval-case-summary-meta">\n                            ID: {case_id} &nbsp;|&nbsp; 案由: {case.cause_type} &nbsp;|&nbsp; 目标: {case.goal_type}\n                            {(f' &nbsp;|&nbsp; 我司主体: {case.client_org}' if case.client_org else '')}\n                        </div>\n                    </div>\n                    <div class="eval-case-summary-status">\n                        <span class="status-badge" style="background:{'#ffffff'};color:{st_color};border-color:{st_color};">{status_text}</span>\n                    </div>\n                </div>\n                """)
            notice_message = st.session_state.pop(notice_key, None)
            if notice_message:
                accent_notice(notice_message)
            col_edit_action, col_edit_note = st.columns([0.9, 2.1], vertical_alignment='center')
            with col_edit_action:
                edit_label = '关闭编辑' if st.session_state.get(edit_toggle_key, False) else '编辑案件信息'
                if st.button(edit_label, key=f'toggle_edit_case_{case_id}', use_container_width=True):
                    st.session_state[edit_toggle_key] = not st.session_state.get(edit_toggle_key, False)
                    st.rerun()
            with col_edit_note:
                st.markdown('<div class="eval-case-edit-note">修改案件名称、业务目标或案情描述后，系统会自动清空旧评估结果并将案件状态重置为待评估。</div>', unsafe_allow_html=True)
            if st.session_state.get(edit_toggle_key, False):
                with st.form(f'edit_case_form_{case_id}'):
                    edited_name = st.text_input('案件名称 *', value=case.name or '')
                    edited_client_org = st.text_input('我司主体名称', value=case.client_org or '')
                    goal_options = ['要钱', '要名']
                    goal_index = goal_options.index(case.goal_type) if case.goal_type in goal_options else 0
                    edited_goal_type = st.radio('业务目标', goal_options, index=goal_index, horizontal=True)
                    edited_description = st.text_area('案情描述 *', value=case.case_description or '', height=180)
                    col_save, col_cancel = st.columns(2)
                    save_edit = col_save.form_submit_button('保存修改', type='primary', use_container_width=True)
                    cancel_edit = col_cancel.form_submit_button('取消', use_container_width=True)
                    if cancel_edit:
                        st.session_state[edit_toggle_key] = False
                        st.rerun()
                    if save_edit:
                        normalized_name = edited_name.strip()
                        normalized_desc = edited_description.strip()
                        normalized_client = edited_client_org.strip()
                        if not normalized_name or not normalized_desc:
                            st.error('请填写必填项：案件名称、案情描述。')
                        else:
                            requires_reanalysis = any([normalized_name != (case.name or '').strip(), edited_goal_type != (case.goal_type or ''), normalized_desc != (case.case_description or '').strip()])
                            try:
                                case.name = normalized_name
                                case.client_org = normalized_client
                                case.goal_type = edited_goal_type
                                case.case_description = normalized_desc
                                if requires_reanalysis:
                                    reset_case_outputs(db, case_id)
                                    case.status = 'pending'
                                db.commit()
                                st.session_state['current_case_name'] = normalized_name
                                st.session_state[edit_toggle_key] = False
                                st.session_state[notice_key] = '案件信息已更新。' + (' 如涉及关键字段变更，系统已清空旧评估结果。' if requires_reanalysis else '')
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f'更新失败: {e}')
            with st.expander('查看案情描述', expanded=True):
                st.markdown(case.case_description)
            if case.status in ('completed', 'partial') and (not eval_data):
                latest = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
                if latest:
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        metric_card('综合得分', '未生成' if latest.final_score is None else f'{latest.final_score}', '分' if latest.final_score is not None else '')
                    with col_m2:
                        metric_card('置信度', f'{latest.confidence_score}%', '')
                    with col_m3:
                        metric_card('建议', latest.recommendation, '', COLORS['primary'])
                    st.markdown('')
            if not RUNTIME_CONFIG['ready'] and (not use_mock_mode()):
                st.error('真实 Demo 模式缺少必要配置：' + '、'.join(RUNTIME_CONFIG['missing_required']) + '。当前不允许发起真实评估或刷新外部检索。')
            disable_real_actions = not RUNTIME_CONFIG['ready'] and (not use_mock_mode())
            col_sp1, col_btn, col_refresh, col_sp2 = st.columns([1, 1.4, 1.4, 1])
            with col_btn:
                btn_label = '重新评估' if eval_data else '开始评估'
                do_eval = st.button(btn_label, type='primary', use_container_width=True, disabled=disable_real_actions)
            with col_refresh:
                do_refresh = st.button('刷新外部检索', use_container_width=True, disabled=disable_real_actions or not eval_data or use_mock_mode(), help='会刷新北大法宝/企查查缓存，并更新结果展示。' if not use_mock_mode() else 'Mock 模式下不执行真实外部检索。')
        overview_placeholder = st.empty()
        detail_placeholder = st.empty()
        result_placeholder = st.empty()
        render_counter = {'value': 0}

        def _render_workspace(view_data=None, pending_message=None, interactive=True):
            data = view_data if view_data is not None else eval_data
            render_counter['value'] += 1
            rt = f"{case_id}_{render_counter['value']}"
            flow_state = ensure_eval_flow_state(case_id, data)
            with overview_placeholder.container():
                top_cols = st.columns([1.7, 1.0], gap='medium')
                with top_cols[0]:
                    render_eval_flow_card(case_id, flow_state, interactive=interactive and (not flow_state.get('running')), render_token=rt)
                with top_cols[1]:
                    render_moot_status_card(case_id, data, flow_state, render_token=rt)
            with detail_placeholder.container():
                render_eval_detail_card(case_id, case, data, flow_state, pending_message=pending_message, render_token=rt)
            result_placeholder.empty()
            if data and (not flow_state.get('running')):
                with result_placeholder.container():
                    render_eval_compact_summary(data, case_id, render_token=rt)
            return flow_state
        _render_workspace(eval_data, interactive=bool(eval_data))
        if do_refresh and eval_data:
            latest_report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()
            refreshed_external = refresh_external_results(case, latest_report.markdown_content if latest_report else '')
            eval_data['external_results'] = refreshed_external
            eval_data['retrieval_status'] = collect_retrieval_status(refreshed_external)
            eval_data['confidence_score'] = calculate_confidence_score({name: eval_data.get(name, {}) for name in ['rights', 'infringement', 'procedure', 'moot', 'financial', 'precedent', 'evidence']}, eval_data['retrieval_status'], CRITICAL_DIMENSIONS)
            st.session_state[eval_key] = eval_data
            save_eval_cache(case_id, eval_data)
            persist_external_cache(case_id, refreshed_external)
            accent_notice('外部检索缓存已刷新，结果页将继续展示缓存版本。')
            st.rerun()
        if do_eval:
            progress = st.progress(0, '初始化评估引擎...')
            evidence_texts = st.session_state.get('evidence_text_extra', '')
            completed_steps = []
            live_eval_data = {'external_results': {}, 'qcc_data': {}}

            def sync_eval_step(step_id: str, pending_message: Optional[str]=None):
                set_eval_flow_state(case_id, running=True, current_step=step_id, completed_steps=completed_steps, selected_step=step_id)
                _render_workspace(live_eval_data, pending_message=pending_message, interactive=False)
            sync_eval_step('rights', '正在进行权利基础分析：北大法宝检索法条，并结合案情与证据文本生成判断。')
            external = {'generated_at': datetime.now().isoformat(), 'mode': RUNTIME_CONFIG['mode_label']}
            live_eval_data['external_results'] = external
            rights_default = {'score': 0, 'sub_scores': {}, 'analysis': '', 'strengths': [], 'risks': [], 'red_flag': False}
            progress.progress(8, '1/7 权利基础评估...')
            with st.spinner('北大法宝检索法条 -> 模型分析...'):
                pkulaw_rights = safe_external_call_fn(RETRIEVAL_LABELS['rights_retrieval'], search_for_rights_foundation)
                external['rights_retrieval'] = pkulaw_rights
                try:
                    rights_raw = evaluate_rights_foundation(case.case_description, uploaded_texts=evidence_texts, pkulaw_data=pkulaw_rights if pkulaw_rights.get('status') == 'completed' else None)
                except Exception as exc:
                    rights_raw = {'error': str(exc)[:200]}
            rights_result = build_dimension_result(rights_raw, rights_default, '权利基础')
            live_eval_data['rights'] = rights_result
            live_eval_data['external_results'] = external
            completed_steps.append('rights')
            sync_eval_step('rights')
            sync_eval_step('infringement', '正在进行侵权认定分析：检索类案并校验侵权构成要素。')
            inf_default = {'score': 0, 'elements': [], 'analysis': '', 'strengths': [], 'risks': [], 'red_flag': False}
            progress.progress(22, '2/7 侵权认定评估...')
            with st.spinner('北大法宝检索类案 -> 五要件分析...'):
                pkulaw_inf = safe_external_call_fn(RETRIEVAL_LABELS['infringement_retrieval'], search_for_infringement)
                external['infringement_retrieval'] = pkulaw_inf
                try:
                    infringement_raw = evaluate_infringement(case.case_description, rights_assessment=str(rights_result.get('analysis', '')), uploaded_texts=evidence_texts, pkulaw_data=pkulaw_inf if pkulaw_inf.get('status') == 'completed' else None)
                except Exception as exc:
                    infringement_raw = {'error': str(exc)[:200]}
            infringement_result = build_dimension_result(infringement_raw, inf_default, '侵权认定')
            live_eval_data['infringement'] = infringement_result
            live_eval_data['external_results'] = external
            completed_steps.append('infringement')
            sync_eval_step('infringement')
            sync_eval_step('procedure', '正在进行诉讼程序审查：校验时效、管辖与主体适格等程序条件。')
            proc_default = {'score': 0, 'items': [], 'analysis': '', 'block_items': [], 'red_flag': False}
            progress.progress(36, '3/7 程序审查...')
            with st.spinner('北大法宝检索程序法条 -> 程序审查...'):
                pkulaw_proc = safe_external_call_fn(RETRIEVAL_LABELS['procedure_retrieval'], search_for_procedure)
                external['procedure_retrieval'] = pkulaw_proc
                try:
                    procedure_raw = evaluate_procedure(case.case_description, party_info=case.client_org or '', pkulaw_data=pkulaw_proc if pkulaw_proc.get('status') == 'completed' else None)
                except Exception as exc:
                    procedure_raw = {'error': str(exc)[:200]}
            procedure_result = build_dimension_result(procedure_raw, proc_default, '诉讼程序')
            live_eval_data['procedure'] = procedure_result
            live_eval_data['external_results'] = external
            completed_steps.append('procedure')
            sync_eval_step('procedure')
            sync_eval_step('moot', '正在进行模拟法庭对抗检验：模拟原告、被告与法官多轮交锋。')
            moot_default = {'correction_coefficient': 1.0, 'rounds': [], 'judge_summary': '', 'defense_strength': 0, 'focus_points': [], 'weak_points': [], 'judge_scores': {}}
            progress.progress(50, '4/7 模拟法庭对抗检验...')
            with st.spinner('北大法宝检索抗辩模式 -> 五步庭审...'):
                pkulaw_moot = safe_external_call_fn(RETRIEVAL_LABELS['moot_retrieval'], search_for_moot_court)
                external['moot_retrieval'] = pkulaw_moot
                try:

                    def on_moot_round(partial_moot, round_index, total_rounds):
                        live_eval_data['moot'] = partial_moot
                        live_eval_data['external_results'] = external
                        cr = (partial_moot.get('rounds') or [{}])[-1]
                        curr_role = cr.get('role_name', '角色')
                        curr_stage = cr.get('step_name', '模拟法庭')
                        sp = 50 + int((round_index + 1) / max(total_rounds, 1) * 12)
                        progress.progress(min(sp, 62), f'4/7 模拟法庭进行中：{curr_stage} · {curr_role}')
                        sync_eval_step('moot', f'模拟法庭进行中：{curr_stage} · {curr_role}')
                    moot_raw = run_moot_court_with_updates(case.case_description, rights_assessment=str(rights_result.get('analysis', '')), infringement_assessment=str(infringement_result.get('analysis', '')), evidence_summary=evidence_texts[:1500] if evidence_texts else '', on_round=on_moot_round)
                except Exception as exc:
                    moot_raw = {'error': str(exc)[:200]}
            moot_result = build_dimension_result(moot_raw, moot_default, '模拟法庭')
            live_eval_data['moot'] = moot_result
            live_eval_data['external_results'] = external
            completed_steps.append('moot')
            correction_coeff = moot_result.get('correction_coefficient', 1.0) if moot_result.get('status') != 'failed' else 1.0
            live_eval_data['correction_coeff'] = correction_coeff
            sync_eval_step('moot', '模拟法庭已完成，正在汇总对抗结果。')
            legal_score = calculate_legal_feasibility(rights_result.get('score', 0), infringement_result.get('score', 0), procedure_result.get('score', 0), correction_coeff)
            live_eval_data['legal_score'] = legal_score
            sync_eval_step('financial', '正在进行财务回报评估：结合企查查画像与判赔类案估算回款空间。')
            fin_default = {'score': 0, 'damages_estimate': {}, 'cost_estimate': '-', 'time_estimate': {}, 'recovery_probability': '-', 'analysis': ''}
            progress.progress(64, '5/7 财务回报评估...')
            defend_info = extract_defendant_info_result(case.case_description, extract_defendant_info_fn=extract_defendant_info, use_mock=use_mock_mode())
            external['defendant_info'] = defend_info
            if use_mock_mode():
                qcc_data = build_external_failure('企查查被告财务画像', 'Mock 模式未调用企查查', status='skipped', include_collections=False)
            elif defend_info.get('status') == 'completed' and defend_info.get('name'):
                dname = defend_info.get('name', '')
                dtype = defend_info.get('type', 'enterprise')
                with st.spinner(f"企查查调取被告财务画像（{dname}，{('企业' if dtype != 'individual' else '自然人')}）..."):
                    qcc_data = safe_external_call_fn('企查查被告财务画像', lambda: search_for_financial_qcc_full(defend_info), include_collections=False)
            else:
                qcc_data = {'status': 'not_applicable', 'error': defend_info.get('error', '未识别到被告主体名称'), '_summary': '未识别到被告主体名称，未执行企查查检索', 'stages': {}, 'metrics': {}}
            external['qcc_data'] = qcc_data
            with st.spinner('北大法宝检索判赔数据 -> 财务预测...'):
                pkulaw_fin = safe_external_call_fn(RETRIEVAL_LABELS['financial_retrieval'], search_for_financial)
                external['financial_retrieval'] = pkulaw_fin
                try:
                    financial_raw = evaluate_financial_return(case.case_description, infringement_severity=str(infringement_result.get('analysis', '')), case_law_references='', pkulaw_data=pkulaw_fin if pkulaw_fin.get('status') == 'completed' else None, qcc_data=qcc_data)
                except Exception as exc:
                    financial_raw = {'error': str(exc)[:200]}
            financial_result = build_dimension_result(financial_raw, fin_default, '财务回报')
            live_eval_data['financial'] = financial_result
            live_eval_data['qcc_data'] = qcc_data or {}
            live_eval_data['external_results'] = external
            completed_steps.append('financial')
            sync_eval_step('financial')
            sync_eval_step('precedent', '正在进行判例价值评估：检索首案价值并判断影响力空间。')
            prec_default = {'score': 0, 'first_case_index': '-', 'influence_level': '-', 'analysis': ''}
            progress.progress(78, '6/7 判例价值评估...')
            with st.spinner('北大法宝首案检索 -> 判例价值判断...'):
                pkulaw_prec = safe_external_call_fn(RETRIEVAL_LABELS['precedent_retrieval'], lambda: search_for_precedent(case.case_description))
                external['precedent_retrieval'] = pkulaw_prec
                try:
                    precedent_raw = evaluate_precedent_value(case.case_description, case_law_references='', pkulaw_data=pkulaw_prec if pkulaw_prec.get('status') == 'completed' else None)
                except Exception as exc:
                    precedent_raw = {'error': str(exc)[:200]}
            precedent_result = build_dimension_result(precedent_raw, prec_default, '判例价值')
            live_eval_data['precedent'] = precedent_result
            live_eval_data['business_score'] = calculate_business_expectation(financial_result.get('score', 0), precedent_result.get('score', 0), case.goal_type)
            live_eval_data['external_results'] = external
            completed_steps.append('precedent')
            sync_eval_step('precedent')
            business_score = calculate_business_expectation(financial_result.get('score', 0), precedent_result.get('score', 0), case.goal_type)
            sync_eval_step('evidence', '正在进行证据就绪度评估：逐项检查关键证据是否充足，并生成补证建议。')
            progress.progress(92, '7/7 证据就绪度评估...')
            evid_default = {'score': 0, 'evidence_matrix': [], 'analysis': '', 'missing_items': [], 'remediation_suggestions': [], 'collection_advice': ''}
            with st.spinner('正在逐项核验证据完整性...'):
                try:
                    evidence_raw = evaluate_evidence_readiness(case.case_description, uploaded_evidence_texts=evidence_texts, evidence_count=0)
                except Exception as exc:
                    evidence_raw = {'error': str(exc)[:200]}
            evidence_result = build_dimension_result(evidence_raw, evid_default, '证据就绪度')
            live_eval_data['evidence'] = evidence_result
            live_eval_data['external_results'] = external
            completed_steps.append('evidence')
            evidence_score = evidence_result.get('score', 0)
            live_eval_data['evidence_score'] = evidence_score
            sync_eval_step('evidence')
            dimension_results = {'rights': rights_result, 'infringement': infringement_result, 'procedure': procedure_result, 'moot': moot_result, 'financial': financial_result, 'precedent': precedent_result, 'evidence': evidence_result}
            integrity = evaluate_data_integrity(dimension_results, CRITICAL_DIMENSIONS)
            retrieval_status = collect_retrieval_status(external)
            confidence_score = calculate_confidence_score(dimension_results, retrieval_status, CRITICAL_DIMENSIONS)
            integrity_payload = build_integrity_payload(integrity, DIMENSION_LABELS)
            progress.progress(97, '计算综合评分...')
            final_score = calculate_overall_score(legal_score, business_score, evidence_score) if integrity.get('is_complete') else None
            missing_dimensions = integrity_payload.get('critical_issues', [])
            rec = generate_recommendation(final_score, procedure_result.get('items', []), integrity.get('is_complete'), missing_dimensions)
            action_items = []
            if integrity_payload.get('critical_issues'):
                action_items.append('优先完成以下关键维度：' + '、'.join(integrity_payload['critical_issues']))
            for suggestion in evidence_result.get('remediation_suggestions', [])[:2]:
                action_items.append(suggestion)
            rule_results_for_verif = [{'rule_name': it.get('name', '未知程序项'), 'severity': it.get('status', 'warning') if it.get('status') in ('pass', 'warning', 'block') else 'warning', 'result': it.get('detail', ''), 'reason': it.get('detail', '')} for it in procedure_result.get('items', [])]
            report_score_payload = {'legal_feasibility': legal_score, 'business_expectation': business_score, 'evidence_readiness': evidence_score, 'final_score': final_score, 'recommendation': rec['recommendation'], 'confidence_score': confidence_score, 'reason': rec['reason'], 'action_items': action_items, 'data_integrity': integrity_payload}
            legal_analysis_payload = {'elements': [{'element': '权利基础', 'score': rights_result.get('score', 0), 'analysis': rights_result.get('analysis', ''), 'evidence_status': '-', 'risks': rights_result.get('risks', [])}, {'element': '侵权认定', 'score': infringement_result.get('score', 0), 'analysis': infringement_result.get('analysis', ''), 'evidence_status': '-', 'risks': infringement_result.get('risks', [])}, {'element': '诉讼程序', 'score': procedure_result.get('score', 0), 'analysis': procedure_result.get('analysis', ''), 'evidence_status': '-', 'risks': procedure_result.get('block_items', [])}]}
            report_md_pre = generate_markdown_report({'name': case.name, 'cause_type': case.cause_type, 'goal_type': case.goal_type, 'client_org': case.client_org}, report_score_payload, rule_results_for_verif, legal_analysis_payload)
            if use_mock_mode():
                vresult = build_external_failure('北大法宝防幻觉验证', 'Mock 模式未执行防幻觉验证', status='skipped', include_collections=False)
                vresult['summary'] = {'laws_verified': False, 'cases_verified': False, 'laws_found': 0, 'cases_found': 0, 'hallucinations': []}
            else:
                with st.spinner('北大法宝防幻觉验证...'):
                    vresult = safe_external_call_fn('北大法宝防幻觉验证', lambda: run_verification_phase(report_md_pre), include_collections=False)
            vs = vresult.get('summary', {'laws_verified': False, 'cases_verified': False, 'laws_found': 0, 'cases_found': 0, 'hallucinations': []})
            external['verification'] = vresult
            if isinstance(vresult, dict):
                for key in ('adjust_provisions', 'law_recognition', 'anhao_recognition'):
                    if key in vresult:
                        external[key] = vresult.get(key)
            st.markdown('---')
            if vresult.get('status') == 'skipped':
                accent_notice(vresult.get('_summary', '当前模式未执行防幻觉验证。'))
            else:
                with st.expander('北大法宝 · 防幻觉验证', expanded=True):
                    col_v1, col_v2, col_v3, col_v4 = st.columns(4)
                    with col_v1:
                        st.metric('法条校验', '通过' if vs.get('laws_verified') else '待复查', delta=f"识别{vs.get('laws_found', 0)}条" if vs.get('laws_found') else '未引用')
                    with col_v2:
                        st.metric('案号校验', '通过' if vs.get('cases_verified') else '待复查', delta=f"{vs.get('cases_found', 0)}案号" if vs.get('cases_found') else '0案号')
                    with col_v3:
                        hall_count = len(vs.get('hallucinations', []))
                        st.metric('幻觉排查', '通过' if not hall_count else '待复查', delta='无' if not hall_count else f'{hall_count}条')
                    with col_v4:
                        st.metric('总体', '完整' if integrity.get('is_complete') else '部分完成')
                    for hallucination in vs.get('hallucinations', []):
                        accent_notice(hallucination)
            rule_results_for_report = [{'rule_name': it.get('name', '未知程序项'), 'severity': it.get('status', 'warning') if it.get('status') in ('pass', 'warning', 'block') else {'满足': 'pass', '存疑': 'warning', '不满足': 'block'}.get(it.get('status', '存疑'), 'warning'), 'result': it.get('detail', ''), 'reason': it.get('detail', '')} for it in procedure_result.get('items', [])]
            report_md = generate_markdown_report({'name': case.name, 'cause_type': case.cause_type, 'goal_type': case.goal_type, 'client_org': case.client_org}, report_score_payload, rule_results_for_report, legal_analysis_payload)
            hall_count = len(vs.get('hallucinations', []))
            report_md += f"\n## 七、北大法宝防幻觉验证\n\n- 法条校验: {vs.get('laws_found', 0)} 条\n- 案号校验: {vs.get('cases_found', 0)} 个\n- 幻觉排查: {('通过' if not hall_count else f'发现 {hall_count} 处可疑引用')}\n"
            if not use_mock_mode():
                try:
                    legal_analysis_text = f"权利基础：{rights_result.get('analysis', '')}。侵权认定：{infringement_result.get('analysis', '')}。诉讼程序：{procedure_result.get('analysis', '')}。"
                    enhance_resp = get_linked_content(legal_analysis_text[:3000])
                    if enhance_resp and 'result' in enhance_resp:
                        structured = enhance_resp['result'].get('structuredContent', enhance_resp['result'])
                        linked_text = structured.get('result', '') if isinstance(structured, dict) else str(structured)
                        if linked_text:
                            report_md += f'\n## 八、法律分析（法宝超链增强版）\n\n{linked_text}\n'
                except Exception:
                    pass
            eval_data = {'rights': rights_result, 'infringement': infringement_result, 'procedure': procedure_result, 'moot': moot_result, 'financial': financial_result, 'precedent': precedent_result, 'evidence': evidence_result, 'qcc_data': qcc_data or {}, 'external_results': external, 'retrieval_status': retrieval_status, 'integrity': integrity_payload, 'legal_score': legal_score, 'business_score': business_score, 'evidence_score': evidence_score, 'confidence_score': confidence_score, 'final_score': final_score, 'recommendation': rec, 'correction_coeff': correction_coeff, 'report_markdown': report_md}
            live_eval_data = eval_data
            st.session_state[eval_key] = eval_data
            save_eval_cache(case_id, eval_data)
            persist_external_cache(case_id, external)
            for key, value in [('rights', rights_result), ('infringement', infringement_result), ('procedure', procedure_result), ('moot', moot_result), ('financial', financial_result), ('precedent', precedent_result), ('evidence', evidence_result)]:
                st.session_state[f'{key}_{case_id}'] = value
            db.add(ScoreSnapshot(case_id=case_id, legal_score=legal_score, business_score=business_score, evidence_score=evidence_score, confidence_score=confidence_score, final_score=final_score, recommendation=rec['recommendation']))
            db.commit()
            report_dir = RUNTIME_DIR / 'reports'
            report_dir.mkdir(parents=True, exist_ok=True)
            md_path = report_dir / f'{case_id}_report.md'
            md_path.write_text(report_md, encoding='utf-8')
            db.add(Report(case_id=case_id, report_type='评估报告', markdown_content=report_md, pdf_uri=str(md_path)))
            case.status = 'completed' if integrity.get('is_complete') else 'partial'
            db.commit()
            if not use_mock_mode():
                deepseek_results = {'rights': rights_result, 'infringement': infringement_result, 'procedure': procedure_result, 'financial': financial_result, 'precedent': precedent_result, 'evidence': evidence_result}
                generate_all_queries(case_id, case.case_description, deepseek_results)
            set_eval_flow_state(case_id, running=False, current_step=None, completed_steps=completed_steps, selected_step=completed_steps[-1] if completed_steps else EVAL_FLOW_STEPS[0]['id'])
            _render_workspace(eval_data, interactive=True)
            progress.progress(100, '评估完成')
            if integrity.get('is_complete'):
                accent_notice('评估完成，结果页将继续展示本次缓存结果。')
            else:
                accent_notice('评估已结束，但存在未完成关键维度；系统未输出完整综合结论。')
            accent_notice('评估报告已生成，请切换到「评估报告」标签页查看完整报告。')
            st.rerun()
    finally:
        db.close()