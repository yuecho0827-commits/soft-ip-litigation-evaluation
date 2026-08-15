"""案件列表 — 查看和管理所有评估案件"""
from typing import Callable
import streamlit as st
from sqlalchemy.exc import OperationalError
from database import SessionLocal, Case, ScoreSnapshot, init_db
from styles import page_header, accent_notice, empty_state_notice, case_card

def render(on_delete_case: Callable, on_view_case: Callable, reset_case_outputs_fn: Callable, clear_current_selection_fn: Callable):
    page_header('案件列表', '查看和管理所有评估案件')

    def _load_case_list():
        db = SessionLocal()
        try:
            cases = db.query(Case).order_by(Case.created_at.desc()).all()
            case_data = []
            for c in cases:
                score = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == c.id).order_by(ScoreSnapshot.id.desc()).first()
                case_data.append((c, score))
            return case_data
        finally:
            db.close()
    try:
        case_data = _load_case_list()
    except OperationalError:
        init_db()
        try:
            case_data = _load_case_list()
        except OperationalError:
            st.error('案件数据库暂未就绪，请稍后刷新页面重试。')
            accent_notice('如果问题持续存在，我可以继续帮你检查本地数据库连接。')
            st.stop()
    delete_notice = st.session_state.pop('case_delete_notice', None)
    if delete_notice:
        accent_notice(delete_notice)
    if not case_data:
        empty_state_notice('暂无案件，请先创建案件')
    else:
        for i in range(0, len(case_data), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(case_data):
                    c, score = case_data[i + j]
                    with cols[j]:
                        case_card(c.id, c.name, c.cause_type, c.goal_type, c.status, score.final_score if score else None, score.recommendation if score else None)
                        action_cols = st.columns(2, gap='small')
                        if action_cols[0].button('删除', key=f'd_{c.id}', use_container_width=True, help='删除后会同时清空该案件的评估结果与报告'):
                            db = SessionLocal()
                            try:
                                target_case = db.query(Case).filter(Case.id == c.id).first()
                                if not target_case:
                                    st.error('案件不存在或已删除')
                                else:
                                    reset_case_outputs_fn(db, c.id)
                                    db.delete(target_case)
                                    db.commit()
                                    clear_current_selection_fn(c.id)
                                    st.session_state['case_delete_notice'] = f'案件「{c.name}」已删除。'
                                    st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f'删除失败: {e}')
                            finally:
                                db.close()
                        if action_cols[1].button('查看 →', key=f'v_{c.id}', use_container_width=True):
                            st.session_state['current_case_id'] = c.id
                            st.session_state['current_case_name'] = c.name
                            st.session_state['nav_target'] = '评估分析'
                            st.rerun()