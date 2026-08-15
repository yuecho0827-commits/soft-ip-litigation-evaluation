"""模拟法庭 — 庭审记录复现与法官归纳"""
import streamlit as st
from typing import Callable
from database import SessionLocal, Case
from styles import page_header, accent_notice, empty_state_notice, metric_card, chat_bubble, score_bar, COLORS
from cache import load_eval_cache
MOOT_ROLE_META = {'judge': {'label': '法官', 'role_name': '审判法官'}, 'plaintiff': {'label': '原告', 'role_name': '原告代理律师'}, 'defendant': {'label': '被告', 'role_name': '被告代理律师'}}

def render(use_mock_mode_fn: Callable):
    page_header('模拟法庭', '固定脚本庭审复现 · 查看已完成评估案件的庭审记录与法官归纳')
    if 'current_case_id' not in st.session_state:
        empty_state_notice('请先在「案件列表」中选择一个案件')
        st.stop()
    case_id = st.session_state['current_case_id']
    case_name = st.session_state.get('current_case_name', '未知案件')
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error('案件不存在')
            st.stop()
        st.markdown(f"""\n        <div class="card" style="border-left:4px solid {COLORS['accent']};">\n            <div style="font-size:1.05rem;font-weight:700;color:{COLORS['text_dark']};letter-spacing:-0.01em;">{case_name}</div>\n            <div style="font-size:0.78rem;color:{COLORS['text_muted']};margin-top:4px;">\n                ID: {case_id} | 案由: {case.cause_type} | 模式: {('Mock 模拟' if use_mock_mode_fn() else 'DeepSeek API')}\n            </div>\n        </div>\n        """, unsafe_allow_html=True)
        eval_key = f'eval_results_{case_id}'
        eval_data = st.session_state.get(eval_key) or load_eval_cache(case_id) or {}
        if eval_data and eval_key not in st.session_state:
            st.session_state[eval_key] = eval_data
        moot_key = f'moot_{case_id}'
        moot_result = (eval_data.get('moot') if isinstance(eval_data, dict) else None) or st.session_state.get(moot_key)
        if moot_result and moot_result.get('rounds'):
            coeff = moot_result.get('correction_coefficient', 1.0)
            ds = moot_result.get('defense_strength', 50)
            accent_notice(f'已生成庭审复现报告 | 修正系数: {coeff:.2f} | 抗辩强度: {ds}/100')
            st.caption('本页仅复现已完成评估案件的模拟法庭结果，不再单独启动一次模拟法庭。')
        elif moot_result and moot_result.get('error'):
            accent_notice(f"当前案件的模拟法庭结果未完整生成：{moot_result.get('error', '未知错误')}")
        else:
            empty_state_notice('当前案件尚未生成模拟法庭复现结果。请先在「评估分析」中完成整案评估，系统会自动生成并缓存模拟法庭报告。')
        st.markdown('')
        if moot_result and moot_result.get('rounds'):
            rounds = moot_result.get('rounds', [])
            coeff = moot_result.get('correction_coefficient', 1.0)
            ds = moot_result.get('defense_strength', 50)
            coeff_color = COLORS['danger'] if coeff < 0.9 else COLORS['warning'] if coeff < 1.0 else COLORS['success']
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                metric_card('对抗修正系数', f'{coeff:.2f}', '抗辩有效削弱' if coeff < 1.0 else '原告论证成立', coeff_color)
            with col_s2:
                metric_card('被告抗辩强度', f'{ds}/100', '有力' if ds >= 60 else '一般' if ds >= 40 else '薄弱', COLORS['warning'])
            with col_s3:
                wp_count = len(moot_result.get('weak_points', []))
                metric_card('暴露薄弱环节', f'{wp_count} 项', '需关注补强', COLORS['danger'])
            step_names = ['开庭陈述', '被告答辩', '举证质证', '法庭辩论', '法官归纳']
            progress_segments = []
            for i, step_name in enumerate(step_names):
                completed = i < len(rounds)
                border_color = '#0d1429' if completed else '#e5e5e5'
                text_color = '#0d1429' if completed else '#cccccc'
                fill_color = '#0d1429' if completed else 'transparent'
                step_weight = '600' if completed else '400'
                step_index_html = f'<span style="color:#fff;">{i + 1}</span>' if completed else str(i + 1)
                progress_segments.append(f'<div style="flex:1;text-align:center;position:relative;"><div style="width:32px;height:32px;border:2px solid {border_color};border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700;color:{text_color};background:{fill_color};">{step_index_html}</div><div style="font-size:0.72rem;color:{text_color};margin-top:6px;font-weight:{step_weight};">{step_name}</div></div>')
                if i < len(step_names) - 1:
                    connector_color = '#0d1429' if completed else '#e5e5e5'
                    progress_segments.append(f'<div style="flex:0.3;height:2px;background:{connector_color};"></div>')
            st.markdown(f"""<div style="margin:20px 0;padding:16px 0;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;"><div style="display:flex;justify-content:space-between;align-items:center;">{''.join(progress_segments)}</div></div>""", unsafe_allow_html=True)
            focus_points = moot_result.get('focus_points', [])
            if focus_points:
                st.markdown(f"""\n                <div class="card" style="border-left:4px solid {COLORS['accent']};">\n                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">争议焦点</div>\n                    {''.join((f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">{i + 1}. {fp}</div>' for i, fp in enumerate(focus_points)))}\n                </div>\n                """, unsafe_allow_html=True)
            st.markdown('')
            st.markdown(f"""\n            <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">\n                庭审记录（共{len(rounds)}轮发言）\n            </div>\n            """, unsafe_allow_html=True)
            current_step = None
            for rnd in rounds:
                role = rnd.get('role', rnd.get('speaker', ''))
                role_name = rnd.get('role_name', role)
                step_name = rnd.get('step_name', '')
                content = rnd.get('content', '')
                step_num = rnd.get('step', 0)
                if step_num != current_step:
                    current_step = step_num
                    step_label_map = {1: '第一步 · 开庭陈述', 2: '第二步 · 被告答辩', 3: '第三步 · 举证质证', 4: '第四步 · 法庭辩论', 5: '第五步 · 法官归纳'}
                    st.markdown(f'\n                    <div style="margin:20px 0 8px 0;padding:8px 0;border-bottom:2px solid #0d1429;">\n                        <span style="font-size:0.9rem;font-weight:700;color:#0d1429;letter-spacing:-0.01em;">{step_label_map.get(step_num, step_name)}</span>\n                    </div>\n                    ', unsafe_allow_html=True)
                if 'plaintiff' in str(role) or '原告' in str(role_name):
                    chat_bubble(role_name, step_name, content, 'plaintiff', truncate=200)
                elif 'defendant' in str(role) or '被告' in str(role_name):
                    chat_bubble(role_name, step_name, content, 'defendant', truncate=200)
                else:
                    chat_bubble(role_name, step_name, content, 'judge')
            structured = moot_result.get('summary_structured', {}) or {}
            judge_summary = moot_result.get('judge_summary', '')
            if structured or judge_summary:
                st.markdown('')
                if structured:
                    st.markdown(f"""\n                    <div class="card" style="border:3px solid {COLORS['accent']};background:linear-gradient(135deg, #fffaf0 0%, #ffffff 100%);margin-top:24px;padding:20px 24px;">\n                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">\n                            <span style="font-size:1.4rem;">⚖️</span>\n                            <span style="font-size:1.15rem;font-weight:800;color:{COLORS['accent']};letter-spacing:-0.01em;">法官最终判决书</span>\n                        </div>\n                    </div>\n                    """, unsafe_allow_html=True)
                    for key in ('一、争议焦点归纳', '二、本院裁判理由', '三、裁判结论'):
                        text = structured.get(key, '')
                        if text:
                            st.markdown(text)
                elif judge_summary:
                    st.markdown(f"""\n                    <div class="card" style="border:3px solid {COLORS['accent']};background:linear-gradient(135deg, #fffaf0 0%, #ffffff 100%);margin-top:24px;padding:18px 22px;">\n                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">\n                            <span style="font-size:1.4rem;">⚖️</span>\n                            <span style="font-size:1.1rem;font-weight:800;color:{COLORS['accent']};letter-spacing:-0.01em;">法官最终判决</span>\n                        </div>\n                        <div style="font-size:0.95rem;color:#222;line-height:1.9;white-space:pre-wrap;">{judge_summary}</div>\n                    </div>\n                    """, unsafe_allow_html=True)
            judge_scores = moot_result.get('judge_scores', {})
            if judge_scores and judge_scores.get('plaintiff'):
                st.markdown('')
                st.markdown(f"""\n                <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">\n                    法官评分对比\n                </div>\n                """, unsafe_allow_html=True)
                p_scores = judge_scores.get('plaintiff', {})
                d_scores = judge_scores.get('defendant', {})
                p_detail = judge_scores.get('plaintiff_detail', {})
                d_detail = judge_scores.get('defendant_detail', {})
                col_p, col_d = st.columns(2)
                with col_p:
                    p_avg = sum(p_scores.values()) / len(p_scores) if p_scores else 0
                    st.markdown(f"""\n                    <div style="border:1px solid {COLORS['primary']};border-left:3px solid {COLORS['primary']};padding:10px 16px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">\n                        <div style="font-weight:700;color:{COLORS['primary']};font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">原告论证强度</div>\n                        <div style="font-size:1.4rem;font-weight:800;color:{COLORS['primary']};">{p_avg:.0f}</div>\n                    </div>\n                    """, unsafe_allow_html=True)
                    label_map = {'rights': '权利基础', 'infringement': '侵权认定', 'evidence': '证据体系', 'legal_application': '法律适用', 'claim_reasonableness': '诉求合理性'}
                    for k, v in p_scores.items():
                        detail = p_detail.get(k, '')
                        score_bar(label_map.get(k, k), v, COLORS['primary'], detail)
                with col_d:
                    d_avg = sum(d_scores.values()) / len(d_scores) if d_scores else 0
                    st.markdown(f"""\n                    <div style="border:1px solid {COLORS['danger']};border-left:3px solid {COLORS['danger']};padding:10px 16px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">\n                        <div style="font-weight:700;color:{COLORS['danger']};font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">被告抗辩强度</div>\n                        <div style="font-size:1.4rem;font-weight:800;color:{COLORS['danger']};">{d_avg:.0f}</div>\n                    </div>\n                    """, unsafe_allow_html=True)
                    d_label_map = {'fact_defense': '事实抗辩', 'legal_defense': '法律抗辩', 'evidence_challenge': '证据质疑', 'alternative_explanation': '替代解释', 'procedural_defense': '程序抗辩'}
                    for k, v in d_scores.items():
                        detail = d_detail.get(k, '')
                        score_bar(d_label_map.get(k, k), v, COLORS['danger'], detail)
                reasoning = judge_scores.get('coefficient_reasoning', '')
                if reasoning:
                    accent_notice(f'<strong>修正系数推理：</strong>{reasoning}')
            weak_points = moot_result.get('weak_points', [])
            if weak_points:
                st.markdown(f"""\n                <div class="card" style="border-left:4px solid {COLORS['danger']};">\n                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">对抗暴露的薄弱环节</div>\n                    {''.join((f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">— {wp}</div>' for wp in weak_points))}\n                </div>\n                """, unsafe_allow_html=True)
        elif moot_result and moot_result.get('error'):
            st.error(f"模拟法庭出错: {moot_result['error']}")
    finally:
        db.close()