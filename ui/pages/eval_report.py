"""评估报告 — 三维评分总览 + 可下载总结文档"""
import streamlit as st
from datetime import datetime
from typing import Callable
from config import APP_VERSION
from database import SessionLocal, Case, ScoreSnapshot, Report
from report_generator import generate_pdf_bytes
from styles import page_header, score_bar, accent_notice, empty_state_notice, COLORS
from cache import load_eval_cache

def render(render_radar_html_fn: Callable, render_radar_svg_fn: Callable):
    page_header('评估报告', '三维评分总览 · 可下载总结文档')
    if 'current_case_id' not in st.session_state:
        empty_state_notice('请先在「案件列表」中选择一个已评估的案件')
        st.stop()
    case_id = st.session_state['current_case_id']
    case_name = st.session_state.get('current_case_name', '未知案件')
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error('案件不存在')
            st.stop()
        score = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
        report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()
        if not score:
            empty_state_notice('该案件尚未评估，请先进行评估')
            st.stop()
        report_eval_data = st.session_state.get(f'eval_results_{case_id}') or load_eval_cache(case_id) or {}
        integrity_info = report_eval_data.get('integrity', {'is_complete': score.final_score is not None, 'label': '完整' if score.final_score is not None else '部分完成', 'critical_issues': [], 'optional_issues': []})
        report_content = report.markdown_content if report else report_eval_data.get('report_markdown', '')
        legal_score_value = int(score.legal_score or 0)
        business_score_value = int(score.business_score or 0)
        evidence_score_value = int(score.evidence_score or 0)
        final_score_display = '未生成' if score.final_score is None else str(score.final_score)
        final_score_suffix = '' if score.final_score is None else '/100'
        rec_color = {'建议起诉': COLORS['success'], '补证后起诉': COLORS['warning'], '评估未完成': COLORS['warning'], '暂不建议起诉': COLORS['danger'], '暂缓起诉': COLORS['danger']}.get(score.recommendation, COLORS['primary'])
        st.markdown(f"""\n        <div class="card" style="border-left:6px solid {rec_color};">\n            <div style="font-size:0.72rem;color:{COLORS['text_muted']};margin-bottom:4px;text-transform:uppercase;letter-spacing:0.08em;">{case.cause_type} · 评估报告</div>\n            <div style="font-size:1.5rem;font-weight:800;color:{COLORS['text_dark']};letter-spacing:-0.02em;">{case.name}</div>\n            <div style="margin-top:16px;display:flex;gap:40px;flex-wrap:wrap;">\n                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">综合评分</span><br>\n                     <span style="font-size:3rem;font-weight:800;color:{rec_color};letter-spacing:-0.04em;">{final_score_display}</span>\n                     <span style="color:{COLORS['text_muted']};font-size:0.9rem;">{final_score_suffix}</span></div>\n                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">建议</span><br>\n                     <span style="font-size:1.2rem;font-weight:700;color:{rec_color};">{score.recommendation}</span></div>\n                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">置信度</span><br>\n                     <span style="font-size:1.2rem;font-weight:600;">{score.confidence_score}%</span></div>\n            </div>\n        </div>\n        """, unsafe_allow_html=True)
        col_chart, col_bars = st.columns([1, 1])
        with col_chart:
            st.markdown('##### 三维评分雷达图')
            radar_html = render_radar_html_fn({'法律可行性': legal_score_value, '业务预期': business_score_value, '证据就绪度': evidence_score_value})
            st.markdown(radar_html, unsafe_allow_html=True)
        with col_bars:
            st.markdown('##### 各维度得分详情')
            score_bar('法律可行性', legal_score_value, COLORS['primary'], '权利 × 侵权 × 程序 × 对抗修正')
            score_bar('业务预期', business_score_value, COLORS['warning'], '要钱/要名自适应加权')
            score_bar('证据就绪度', evidence_score_value, COLORS['success'], '证据完整性与补证')
            st.divider()
            st.markdown(f'**乘法模型**: {legal_score_value} × {business_score_value} × {evidence_score_value} = **{final_score_display}**')
            st.caption(f'置信度: {score.confidence_score}% · 一票否决逻辑')
        st.markdown('---')
        st.markdown('##### 完整评估报告')
        if report_content:
            st.markdown(report_content)
        else:
            accent_notice('报告内容未保存')
        st.markdown('---')
        st.markdown('##### 📥 下载总结文档')
        radar_svg_str = render_radar_svg_fn({'法律可行性': legal_score_value, '业务预期': business_score_value, '证据就绪度': evidence_score_value})
        summary_html = f"""<!DOCTYPE html>\n<html lang="zh-CN">\n<head><meta charset="utf-8"><title>诉算评估报告 - {case.name}</title>\n<style>\nbody{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;max-width:800px;margin:0 auto;padding:40px;color:#333}}\nh1{{color:#0d1429;border-bottom:3px solid {rec_color};padding-bottom:12px}}\nh2{{color:#0d1429;margin-top:28px}}\ntable{{border-collapse:collapse;width:100%;margin:12px 0}}\nth,td{{border:1px solid #ddd;padding:8px 12px;text-align:left}}\nth{{background:#f8f9fa}}\n.score-big{{font-size:3rem;font-weight:bold;color:{rec_color}}}\n.rec{{font-size:1.3rem;font-weight:bold;color:{rec_color};margin:8px 0}}\n</style></head>\n<body>\n<h1>诉算 · Soft IP 主诉评估报告</h1>\n<p><strong>案件名称:</strong> {case.name} &nbsp;|&nbsp; <strong>案由:</strong> {case.cause_type} &nbsp;|&nbsp; <strong>评估日期:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>\n\n<h2>一、结论摘要</h2>\n<div class="score-big">{final_score_display}{(' / 100' if final_score_suffix else '')}</div>\n<div class="rec">{score.recommendation}</div>\n\n<h2>二、三维评分总览</h2>\n<div style="text-align:center;margin:24px 0">{radar_svg_str}</div>\n<table>\n<tr><th>维度</th><th>得分</th><th>说明</th></tr>\n<tr><td>法律可行性</td><td>{score.legal_score}/100</td><td>权利 × 侵权 × 程序 × 对抗修正</td></tr>\n<tr><td>业务预期</td><td>{score.business_score}/100</td><td>要钱/要名自适应加权</td></tr>\n<tr><td>证据就绪度</td><td>{score.evidence_score}/100</td><td>证据完整性与补证</td></tr>\n<tr><td><strong>综合得分（乘法模型）</strong></td><td><strong>{final_score_display}{final_score_suffix}</strong></td><td>一票否决逻辑</td></tr>\n</table>\n\n<h2>三、评估说明</h2>\n<p>本评估基于用户提供的案情描述和证据材料，通过规则引擎和 AI 分析生成。评估覆盖法律可行性、业务预期、证据就绪度三个维度，采用乘法评分模型（一票否决逻辑）。</p>\n<p><strong>置信度:</strong> {score.confidence_score}%</p>\n\n<h2>四、后续建议</h2>\n<ol>\n<li>根据红线和警告项补充关键证据</li>\n<li>与法律顾问或外部律师讨论诉讼策略</li>\n<li>持续监控侵权行为并收集更多证据</li>\n</ol>\n\n<p style="margin-top:40px;color:#999;font-size:0.85rem;">\n<em>Generated by 诉算 v{APP_VERSION} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</em>\n</p>\n<p style="color:#999;font-size:0.8rem;">免责声明: 本报告为 AI 辅助生成，仅供内部决策参考，不构成正式法律意见。</p>\n</body></html>"""
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        pdf_bytes = None
        try:
            pdf_bytes = generate_pdf_bytes(report_content if report_content else summary_html)
        except Exception as e:
            st.caption(f'PDF 生成失败: {e}')
        with col_dl1:
            if pdf_bytes:
                st.download_button('下载 PDF', data=pdf_bytes, file_name=f'{case_id}_评估报告.pdf', mime='application/pdf', use_container_width=True, type='primary')
            else:
                st.download_button('下载 HTML', data=summary_html.encode('utf-8'), file_name=f'{case_id}_评估报告.html', mime='text/html', use_container_width=True, type='primary')
        with col_dl2:
            if report:
                st.download_button('完整报告 (.md)', data=report.markdown_content, file_name=f'{case_id}_完整报告.md', mime='text/markdown', use_container_width=True)
        with col_dl3:
            st.download_button('🌐 总结文档 (.html)', data=summary_html, file_name=f'{case_id}_总结报告.html', mime='text/html', use_container_width=True)
        if pdf_bytes:
            st.caption('PDF 已生成，点击上方按钮一键下载（含中文字体）')
        else:
            st.caption('PDF 生成失败，请使用 HTML 或 Markdown 格式下载')
    finally:
        db.close()