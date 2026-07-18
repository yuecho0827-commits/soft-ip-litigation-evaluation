"""
Soft IP 主诉评估系统 - Streamlit 主程序
专业法律科技 UI · 三维乘法评分 · 多Agent模拟法庭
"""

import streamlit as st
import sys
import os
import math
import re
import base64
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from config import APP_TITLE, APP_VERSION, USE_MOCK
from database import init_db, SessionLocal, Case, Party, RuleHit, ScoreSnapshot, Report
from evidence_parser import parse_pdf, ocr_image, is_pdf_file, is_image_file
from report_generator import generate_markdown_report, generate_pdf_bytes
from pkulaw_api import (
    search_for_rights_foundation, search_for_infringement, search_for_procedure,
    search_for_moot_court, search_for_financial, search_for_precedent,
    run_verification_phase, get_linked_content
)
from qcc_api import search_for_financial_qcc_full
from styles import (
    inject_global_css, page_header, section_banner, dim_card,
    score_bar, final_score_card, case_card, chat_bubble,
    metric_card, form_section_title, COLORS, ROLE_COLORS
)

# 评估引擎
if USE_MOCK:
    from mock_llm import (
        evaluate_rights_foundation,
        evaluate_infringement,
        evaluate_procedure,
        evaluate_financial_return,
        evaluate_precedent_value,
        evaluate_evidence_readiness,
        run_moot_court_simulation,
    )
    _mock = True
else:
    from llm_client import (
        evaluate_rights_foundation,
        evaluate_infringement,
        evaluate_procedure,
        evaluate_financial_return,
        evaluate_precedent_value,
        evaluate_evidence_readiness,
        extract_defendant_info,
    )
    from moot_court import run_moot_court as run_moot_court_simulation
    _mock = False

from legal_rules import run_rule_engine
from scoring import (
    calculate_legal_feasibility,
    calculate_business_expectation,
    calculate_overall_score,
    generate_recommendation,
)
from legal_database import format_laws_for_report, format_cases_for_report
from pkulaw_integration import (
    generate_all_queries, load_results, get_validation_status, get_dimension_results
)

# ============================================================
# 页面配置 + 全局样式
# ============================================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_global_css()

# 初始化数据库
@st.cache_resource
def _init_db():
    init_db()
    return True
_init_db()


# ============================================================
# 工具函数：雷达图
# ============================================================

def render_radar_svg(scores: dict, size: int = 340) -> str:
    labels = ["法律可行性", "业务预期", "证据就绪度"]
    values = [scores.get(k, 0) for k in labels]
    cx, cy, r = size // 2, size // 2, size // 2 - 50
    angles = [math.radians(90), math.radians(210), math.radians(330)]

    def point(angle, dist_ratio):
        x = cx + r * dist_ratio * math.cos(angle)
        y = cy - r * dist_ratio * math.sin(angle)
        return x, y

    grid_paths = ""
    for level in [0.33, 0.67, 1.0]:
        pts = [point(a, level) for a in angles]
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        grid_paths += f'<polygon points="{pts_str}" fill="none" stroke="#e5e7eb" stroke-width="1"/>\n'

    axis_lines = ""
    for a in angles:
        x, y = point(a, 1.0)
        axis_lines += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>\n'

    label_texts = ""
    label_offsets = [(0, -15), (-10, 12), (10, 12)]
    for i, (a, lb) in enumerate(zip(angles, labels)):
        x, y = point(a, 1.15)
        ox, oy = label_offsets[i]
        label_texts += f'<text x="{x + ox:.1f}" y="{y + oy:.1f}" text-anchor="middle" font-size="13" fill="#374151">{lb}</text>\n'

    data_pts = [point(a, v / 100.0) for a, v in zip(angles, values)]
    data_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)

    dots = ""
    for x, y in data_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#0d1429"/>\n'

    score_texts = ""
    for i, (a, v) in enumerate(zip(angles, values)):
        x, y = point(a, v / 100.0 + 0.08)
        score_texts += f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="16" font-weight="bold" fill="#0d1429">{v}分</text>\n'

    svg = f'''<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
<rect width="{size}" height="{size}" fill="white" rx="2"/>
{grid_paths}
{axis_lines}
{label_texts}
<polygon points="{data_str}" fill="#0d1429" fill-opacity="0.08" stroke="#0d1429" stroke-width="2.5"/>
{dots}
{score_texts}
</svg>'''
    return svg

def render_radar_html(scores: dict, size: int = 340) -> str:
    svg = render_radar_svg(scores, size)
    b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:{size}px;display:block;margin:0 auto;"/>'


# ============================================================
# 侧边栏
# ============================================================

# 页面定义
page_options = ["新建案件", "案件列表", "评估分析", "模拟法庭", "评估报告", "关于"]

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "新建案件"

if st.session_state.get("nav_target"):
    target = st.session_state.pop("nav_target")
    if target in page_options:
        st.session_state.nav_page = target
    st.rerun()

# 侧边栏品牌区
st.sidebar.markdown("""
<div style="padding:8px 0 16px 0;">
    <div style="font-size:1.5rem;font-weight:800;color:#ffffff;letter-spacing:-0.03em;line-height:1;">
        诉算
    </div>
    <div style="font-size:0.7rem;color:#cce8eb;margin-top:4px;letter-spacing:0.05em;">
        SOFT IP LITIGATION EVAL
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()

# ── 自定义滑块导航（替代 st.radio 避免圆点）──
if "page" not in st.session_state:
    st.session_state["page"] = "新建案件"
# 关键：所有项（无论是否激活）都用 st.sidebar.button 渲染
# 激活项通过 disabled=True 标记；外层容器统一是 stButton → 尺寸天然一致
# 激活态用 button:disabled CSS 选择器单独定义左侧滑块 + 浅橙背景 + 纯白文字
for opt in page_options:
    is_active = st.session_state["page"] == opt
    if st.sidebar.button(
        opt,
        key=f"nav_{opt}",
        use_container_width=True,
        disabled=is_active,
    ):
        st.session_state["page"] = opt
        st.rerun()

# 侧边栏导航按钮样式：所有项共享一套尺寸，仅 disabled 状态切换视觉
st.sidebar.markdown("""
<style>
/* 容器：去掉 stButton 默认外边距，保证与未激活项 1:1 对齐 */
section[data-testid="stSidebar"] div[data-testid="stButton"] {
    margin: 0 !important;
    padding: 0 !important;
}

/* 基础样式：所有导航按钮共享的 padding / 高度 / 圆角 / 左边框 */
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    box-shadow: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    align-items: center !important;
    padding: 12px 16px !important;
    font-size: 0.9rem !important;
    font-weight: 400 !important;
    color: #cfd5e0 !important;
    border-radius: 0 4px 4px 0 !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
    min-height: 40px !important;
    line-height: 1.2 !important;
    box-sizing: border-box !important;
}
section[data-testid="stSidebar"] button[kind="secondary"] p,
section[data-testid="stSidebar"] button[kind="secondary"] div {
    text-align: left !important;
    justify-content: flex-start !important;
    width: 100% !important;
    font-weight: 400 !important;
    line-height: 1.2 !important;
    color: inherit !important;
}

/* 未激活：hover 提示（仅作用于非 disabled） */
section[data-testid="stSidebar"] button[kind="secondary"]:not(:disabled):hover {
    background: rgba(255,255,255,0.05) !important;
    border-left-color: rgba(214,89,56,0.4) !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:not(:disabled):focus:not(:active) {
    background: transparent !important;
    border-color: transparent !important;
    box-shadow: none !important;
    color: #cfd5e0 !important;
}

/* 激活态：disabled 按钮 — 橙色滑块 + 浅橙背景 + 纯白文字 */
section[data-testid="stSidebar"] button[kind="secondary"]:disabled {
    background: rgba(214,89,56,0.12) !important;
    border-left: 3px solid #d65938 !important;
    color: #ffffff !important;
    cursor: default !important;
    opacity: 1 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:disabled:hover {
    background: rgba(214,89,56,0.12) !important;
    border-left: 3px solid #d65938 !important;
    color: #ffffff !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:disabled p,
section[data-testid="stSidebar"] button[kind="secondary"]:disabled div {
    color: #ffffff !important;
    font-weight: 400 !important;
    opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)

page = st.session_state["page"]

# 当前案件上下文
if "current_case_id" in st.session_state:
    st.sidebar.divider()
    st.sidebar.markdown("""
    <div style="font-size:0.65rem;color:#cce8eb;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;opacity:0.6;">
        当前案件
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown(f"""
    <div style="border:1px solid rgba(204,232,235,0.2);border-left:3px solid #d65938;padding:12px 14px;margin-bottom:4px;">
        <div style="font-size:0.9rem;font-weight:600;color:#ffffff;">
            {st.session_state.get("current_case_name", "未知案件")}
        </div>
        <div style="font-size:0.7rem;color:#cce8eb;opacity:0.6;margin-top:2px;">
            ID: {st.session_state["current_case_id"]}
        </div>
    </div>
    """, unsafe_allow_html=True)

# 底部信息
st.sidebar.divider()
mode_label = "Mock 模拟模式" if USE_MOCK else "DeepSeek API 模式"
mode_color = "#d65938" if USE_MOCK else "#a5d8dd"
st.sidebar.markdown(f"""
<div style="font-size:0.72rem;color:#cce8eb;opacity:0.7;">
    <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{mode_color};margin-right:6px;"></span>
    {mode_label}
</div>
<div style="font-size:0.65rem;color:#cce8eb;opacity:0.4;margin-top:4px;">
    v{APP_VERSION} · © 2026 诉算
</div>
""", unsafe_allow_html=True)


# ============================================================
# 页面 1: 新建案件
# ============================================================
if page == "新建案件":
    page_header("新建商标侵权案件", "左侧填写案件信息，右侧上传证据材料")

    # ── 整页两栏：左 = 案件信息表单 / 右 = 证据上传 ──
    col_form, col_evidence = st.columns([1, 1], gap="medium")

    # ════════ 左栏：案件信息表单 ════════
    with col_form:
        form_section_title("案件信息")
        default_desc = st.session_state.get("last_case_desc", "")

        with st.form("new_case_form"):
            case_name = st.text_input("案件名称 *", placeholder="例如：某品牌诉某电商商标侵权案")
            cause_type = st.selectbox("案由", ["商标侵权", "著作权侵权", "不正当竞争"], disabled=True)
            evidence_extra = st.session_state.get("evidence_text_extra", "")
            prefill = (evidence_extra + "\n\n" + default_desc).strip()
            case_description = st.text_area(
                "案情描述 *", height=110, value=prefill,
                placeholder="请详细描述案情，包括：\n- 原告商标信息（注册号、类别、有效期）\n- 被告侵权行为（何时发现、如何侵权）\n- 侵权商品销售情况\n- 已收集的证据"
            )
            client_org = st.text_input("委托客户", placeholder="例如：某知名品牌公司")
            goal_type = st.radio("业务目标", ["要钱", "要名"], horizontal=True)

            submitted = st.form_submit_button("创建案件并开始评估", type="primary", use_container_width=True)

            if submitted:
                full_desc = case_description.strip()
                if not case_name or not full_desc:
                    st.error("请填写必填项（案件名称、案情描述）")
                else:
                    db = SessionLocal()
                    try:
                        new_case = Case(
                            name=case_name, cause_type="商标侵权",
                            goal_type=goal_type, client_org=client_org or "",
                            case_description=full_desc, status="draft"
                        )
                        db.add(new_case)
                        db.commit()
                        db.refresh(new_case)
                        st.session_state["current_case_id"] = new_case.id
                        st.session_state["current_case_name"] = new_case.name
                        st.session_state["last_case_desc"] = full_desc
                        st.session_state["evidence_text_extra"] = ""
                        st.session_state["nav_target"] = "评估分析"
                        st.rerun()
                    except Exception as e:
                        st.error(f"创建失败: {e}")
                        db.rollback()
                    finally:
                        db.close()

    # ════════ 右栏：证据上传 ════════
    with col_evidence:
        form_section_title("证据文件上传")
        uploaded_files = st.file_uploader(
            "支持 PDF（自动提取文本）和图片（OCR 识别文字）",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="evidence_uploader",
            help="上传商标注册证、侵权截图、公证文书等证据文件",
            label_visibility="collapsed"
        )

        parsed_evidences = []
        if uploaded_files:
            for f in uploaded_files:
                cache_key = f"parsed_{f.name}_{f.size}"
                if cache_key not in st.session_state:
                    with st.spinner(f"正在解析 {f.name} ..."):
                        file_bytes = f.getvalue()
                        if is_pdf_file(f.name):
                            result = parse_pdf(file_bytes, f.name)
                        elif is_image_file(f.name):
                            result = ocr_image(file_bytes, f.name)
                        else:
                            result = {"success": False, "text": "", "error": "不支持的文件格式"}
                        if result["success"] and len(result["text"]) > 3000:
                            result["text"] = result["text"][:3000] + "\n\n... (文本过长，已截取)"
                        st.session_state[cache_key] = result
                parsed = st.session_state[cache_key]
                parsed_evidences.append((f.name, f.size, parsed))

        for fname, fsize, result in parsed_evidences:
            if result["success"]:
                text_len = len(result["text"])
                with st.expander(f"{fname}（{text_len} 字）"):
                    st.text_area(f"内容 - {fname}", value=result["text"], height=120,
                                 key=f"preview_{fname}", label_visibility="collapsed")
                    if st.button("追加到案情描述", key=f"append_{hash(fname)}"):
                        current_extra = st.session_state.get("evidence_text_extra", "")
                        st.session_state["evidence_text_extra"] = current_extra + f"\n\n【证据文件: {fname}】\n{result['text']}"
                        st.rerun()
            else:
                st.warning(f"{fname}: {result['error']}")

        evidence_extra_show = st.session_state.get("evidence_text_extra", "")
        if evidence_extra_show:
            st.success(f"已追加 {len(evidence_extra_show)} 字证据文本到案情描述")
            if st.button("清除已追加的证据文本", type="secondary"):
                st.session_state["evidence_text_extra"] = ""
                st.rerun()


# ============================================================
# 页面 2: 案件列表
# ============================================================
elif page == "案件列表":
    page_header("案件列表", "查看和管理所有评估案件")

    db = SessionLocal()
    try:
        cases = db.query(Case).order_by(Case.created_at.desc()).all()
        if not cases:
            st.info("暂无案件，请先创建案件")
        else:
            # 预取所有评分
            case_data = []
            for c in cases:
                score = db.query(ScoreSnapshot).filter(
                    ScoreSnapshot.case_id == c.id
                ).order_by(ScoreSnapshot.id.desc()).first()
                case_data.append((c, score))

            # 两列网格布局
            for i in range(0, len(case_data), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i + j < len(case_data):
                        c, score = case_data[i + j]
                        with cols[j]:
                            case_card(c.id, c.name, c.cause_type, c.goal_type, c.status,
                                     score.final_score if score else None,
                                     score.recommendation if score else None)
                            if st.button("查看 →", key=f"v_{c.id}", use_container_width=True):
                                st.session_state["current_case_id"] = c.id
                                st.session_state["current_case_name"] = c.name
                                st.session_state["nav_target"] = "评估分析"
                                st.rerun()
    finally:
        db.close()


# ============================================================
# 页面 3: 评估分析
# ============================================================
elif page == "评估分析":
    page_header("诉前评估分析", "三维乘法评分模型 · 法律可行性 × 业务预期 × 证据就绪度")

    if "current_case_id" not in st.session_state:
        st.warning("请先在「案件列表」中选择一个案件，或在「新建案件」中创建案件")
        st.stop()

    case_id = st.session_state["current_case_id"]
    case_name = st.session_state.get("current_case_name", "未知案件")

    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error("案件不存在")
            st.stop()

        # ── 案件信息卡片 ──
        status_map = {"draft": "草稿", "evaluating": "评估中", "completed": "已完成"}
        status_text = status_map.get(case.status, "未知")
        status_colors = {"draft": COLORS["text_muted"], "evaluating": COLORS["warning"], "completed": COLORS["accent"]}
        st_color = status_colors.get(case.status, COLORS["text_muted"])

        st.html(f"""
        <div class="card" style="border-left:4px solid {COLORS['primary']};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:1.1rem;font-weight:700;color:{COLORS['text_dark']};letter-spacing:-0.01em;">{case_name}</div>
                    <div style="font-size:0.78rem;color:{COLORS['text_muted']};margin-top:4px;">
                        ID: {case_id} &nbsp;|&nbsp; 案由: {case.cause_type} &nbsp;|&nbsp; 目标: {case.goal_type}
                        {f' &nbsp;|&nbsp; 客户: {case.client_org}' if case.client_org else ''}
                    </div>
                </div>
                <div>
                    <span class="status-badge" style="background:{'#ffffff'};color:{st_color};border-color:{st_color};">{status_text}</span>
                </div>
            </div>
        </div>
        """)

        with st.expander("查看案情描述", expanded=True):
            st.markdown(case.case_description)

        # ── 检查评估结果是否已在 session state ──
        eval_key = f"eval_results_{case_id}"
        eval_data = st.session_state.get(eval_key)

        # 已完成案件但 session state 无结果 → 从 DB 显示摘要
        if case.status == "completed" and not eval_data:
            latest = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
            if latest:
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    metric_card("综合得分", f"{latest.final_score}", "分")
                with col_m2:
                    metric_card("置信度", f"{latest.confidence_score}%", "")
                with col_m3:
                    metric_card("建议", latest.recommendation, "", COLORS["primary"])
                st.markdown("")

        # ── 评估按钮 ──
        col_sp1, col_btn, col_sp2 = st.columns([1, 2, 1])
        with col_btn:
            btn_label = "重新评估" if eval_data else "开始评估"
            do_eval = st.button(btn_label, type="primary", use_container_width=True)

        # ════════════════════════════════════════════════════
        # 评估执行流水线
        # ════════════════════════════════════════════════════
        if do_eval:
            progress = st.progress(0, "初始化评估引擎...")
            evidence_texts = st.session_state.get("evidence_text_extra", "")

            # ── 维度一：法律可行性 ──
            section_banner("维度一：法律可行性", "回答「能不能诉」", COLORS["primary"])

            # 1.1 权利基础
            rights_default = {"score": 60, "sub_scores": {}, "analysis": "评估失败", "strengths": [], "risks": ["评估异常"], "red_flag": False}
            progress.progress(8, "1/7 权利基础评估...")
            with st.spinner("📚 北大法宝检索法条 → DeepSeek 分析..."):
                try: pkulaw_rights = search_for_rights_foundation()
                except: pkulaw_rights = {"laws": [], "cases": []}
                try:
                    rights_result = evaluate_rights_foundation(case.case_description, uploaded_texts=evidence_texts, pkulaw_data=pkulaw_rights)
                except Exception as exc:
                    rights_result = {"error": str(exc)[:200]}
            if rights_result.get("error"):
                st.warning("⚠️ 权利基础异常，使用默认分")
                rights_result = rights_default
            sub_scores = [{"name": {"validity":"商标有效性","usage_continuity":"连续使用","coverage":"覆盖范围","well_known_status":"驰名地位","risk_of_invalidation":"无效风险"}.get(k, k),
                           "score": v, "status": "pass" if v >= 60 else "warning"}
                          for k, v in rights_result.get('sub_scores', {}).items()]
            dim_card("1.1 权利基础评估", rights_result.get('score', 0),
                     rights_result.get('analysis', ''), sub_items=sub_scores,
                     extra="优势: " + ", ".join(rights_result.get('strengths', ['-'])) + "\n\n风险: " + ", ".join(rights_result.get('risks', ['-'])))
            st.caption("📚 北大法宝（实时检索）" if rights_result.get("source") == "pkulaw" else "🤖 DeepSeek")

            # 1.2 侵权认定
            inf_default = {"score": 60, "elements": [], "analysis": "评估失败", "strengths": [], "risks": ["评估异常"], "red_flag": False}
            progress.progress(22, "2/7 侵权认定评估...")
            with st.spinner("📚 北大法宝检索类案 → DeepSeek 五要件分析..."):
                try: pkulaw_inf = search_for_infringement()
                except: pkulaw_inf = {"laws": [], "cases": []}
                try:
                    infringement_result = evaluate_infringement(case.case_description,
                        rights_assessment=str(rights_result.get('analysis', '')),
                        uploaded_texts=evidence_texts, pkulaw_data=pkulaw_inf)
                except Exception as exc:
                    infringement_result = {"error": str(exc)[:200]}
            if infringement_result.get("error"):
                st.warning("⚠️ 侵权认定异常，使用默认分")
                infringement_result = inf_default
            el_items = [{"name": el['name'], "score": el['score'], "status": el.get('status','pass'), "detail": el.get('analysis','')} for el in infringement_result.get('elements', [])]
            dim_card("1.2 侵权认定评估", infringement_result.get('score', 0),
                     infringement_result.get('analysis', ''), sub_items=el_items)
            st.caption("📚 北大法宝（实时检索）" if infringement_result.get("source") == "pkulaw" else "🤖 DeepSeek")

            # 1.3 诉讼程序
            proc_default = {"score": 60, "items": [], "analysis": "评估失败", "block_items": [], "red_flag": False}
            progress.progress(36, "3/7 程序审查...")
            with st.spinner("📚 北大法宝检索程序法条 → DeepSeek 审查..."):
                try: pkulaw_proc = search_for_procedure()
                except: pkulaw_proc = {"laws": [], "cases": []}
                try:
                    procedure_result = evaluate_procedure(case.case_description, party_info=case.client_org or "", pkulaw_data=pkulaw_proc)
                except Exception as exc:
                    procedure_result = {"error": str(exc)[:200]}
            if procedure_result.get("error"):
                st.warning("⚠️ 程序审查异常，使用默认分")
                procedure_result = proc_default
            proc_items = [{"name": p['name'], "status": p.get('status','pass'), "detail": p.get('detail','')} for p in procedure_result.get('items', [])]
            dim_card("1.3 诉讼程序审查", procedure_result.get('score', 0),
                     procedure_result.get('analysis', ''), sub_items=proc_items)
            st.caption("📚 北大法宝（实时检索）" if procedure_result.get("source") == "pkulaw" else "🤖 DeepSeek")

            # 1.4 模拟法庭
            moot_default = {"correction_coefficient": 1.0, "rounds": [], "judge_summary": "模拟法庭异常"}
            progress.progress(50, "4/7 模拟法庭对抗检验...")
            section_banner("1.4 模拟法庭（多Agent对抗检验）", "原告Agent ↔ 被告Agent ↔ 法官Agent", COLORS["accent"])
            with st.spinner("📚 北大法宝检索抗辩模式 → DeepSeek 五步庭审..."):
                try: pkulaw_moot = search_for_moot_court()
                except: pkulaw_moot = {"laws": [], "cases": []}
                try:
                    moot_result = run_moot_court_simulation(case.case_description,
                        rights_assessment=str(rights_result.get('analysis', '')),
                        infringement_assessment=str(infringement_result.get('analysis', '')),
                        evidence_summary=evidence_texts[:1500] if evidence_texts else "",
                        pkulaw_data=pkulaw_moot)
                except Exception as exc:
                    moot_result = {"error": str(exc)[:200]}
            if moot_result.get("error") and not moot_result.get("rounds"):
                st.warning("⚠️ 模拟法庭异常，使用默认系数 1.0")
                moot_result = moot_default
            correction_coeff = moot_result.get('correction_coefficient', 1.0)

            # 维度一小计
            legal_score = calculate_legal_feasibility(
                rights_result.get('score', 0), infringement_result.get('score', 0),
                procedure_result.get('score', 0), correction_coeff
            )

            # ── 维度二：业务预期 ──
            # 2.1 财务回报
            fin_default = {"score": 50, "damages_estimate": {}, "cost_estimate": "-", "time_estimate": {}, "recovery_probability": "-", "analysis": "评估失败"}
            progress.progress(64, "5/7 财务回报评估...")

            # Phase 1: LLM 提取被告身份
            defend_info = None
            if case.case_description:
                with st.spinner("🔍 识别被告身份（LLM NER + 类型判断）..."):
                    try:
                        phase1 = extract_defendant_info(case.case_description)
                        defendants = phase1.get("defendants", [])
                        if defendants:
                            for d in defendants:
                                if isinstance(d, dict) and d.get("role") == "primary_defendant":
                                    defend_info = d
                                    break
                            if not defend_info:
                                defend_info = defendants[0]
                    except Exception:
                        defend_info = None

            # Phase 2: 企查查查询
            qcc_data = None
            if defend_info:
                dname = defend_info.get("name", "")
                dtype = defend_info.get("type", "enterprise")
                with st.spinner(f"🏢 企查查调取被告财务画像（{dname}，{'企业' if dtype != 'individual' else '自然人'}）..."):
                    try:
                        qcc_data = search_for_financial_qcc_full(defend_info)
                    except Exception:
                        qcc_data = {"_summary": "企查查调用失败", "stages": {}, "metrics": {}}
            else:
                qcc_data = {"_summary": "⚠️ 未识别到被告主体名称，无法调用企查查", "stages": {}, "metrics": {}}

            with st.spinner("📚 北大法宝检索判赔数据 → DeepSeek 预测..."):
                try: pkulaw_fin = search_for_financial()
                except: pkulaw_fin = {"laws": [], "cases": []}
                try:
                    financial_result = evaluate_financial_return(case.case_description,
                        infringement_severity=str(infringement_result.get('analysis', '')),
                        case_law_references="", pkulaw_data=pkulaw_fin, qcc_data=qcc_data)
                except Exception as exc:
                    financial_result = {"error": str(exc)[:200]}
            if financial_result.get("error"):
                st.warning("⚠️ 财务评估异常，使用默认分")
                financial_result = fin_default
            fin_score = financial_result.get('score', 50)
            de = financial_result.get('damages_estimate', {})
            te = financial_result.get('time_estimate', {})
            fin_extra = []
            if de: fin_extra.append(f"判赔预测: P10=¥{de.get('p10','-')} / P50=¥{de.get('p50','-')} / P90=¥{de.get('p90','-')}")
            fin_extra.append(f"预估成本: ¥{financial_result.get('cost_estimate','-')}")
            if te: fin_extra.append(f"时间: 一审{te.get('first_instance_months','-')}月 + 二审{te.get('second_instance_months','-')}月 + 执行{te.get('enforcement_months','-')}月")
            fin_extra.append(f"回款概率: {financial_result.get('recovery_probability','-')}%")
            dim_card("2.1 财务回报评估", fin_score, financial_result.get('analysis', ''), extra="\n".join(fin_extra))

            # ── 企查查 · 被告财务画像（评估流程中展示）──
            if qcc_data and qcc_data.get("stages"):
                with st.expander("🏢 企查查 · 被告财务画像（实测数据）", expanded=False):
                    st.caption(qcc_data.get("_summary", ""))
                    metrics = qcc_data.get("metrics", {})
                    if metrics:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("回款概率", f"{metrics.get('recovery_probability', '-')}%")
                        c2.metric("判赔方向", metrics.get('damages_adjustment', '-'))
                        c3.metric("时间延长", f"+{metrics.get('time_extra_months', 0)}月")
                        reds = metrics.get("red_flags", [])
                        greens = metrics.get("green_flags", [])
                        if reds: st.error("🚨 " + " | ".join(reds[:3]))
                        if greens: st.success("✅ " + " | ".join(greens[:3]))
                    # 风险明细
                    d_stage = qcc_data.get("stages", {}).get("D_风险下钻", {})
                    if d_stage:
                        lines = []
                        for k in ("失信信息","被执行人","终本案件","限高消费","经营异常","严重违法"):
                            v = d_stage.get(k, {})
                            if isinstance(v, dict) and v.get("_summary"):
                                lines.append(f"- {k}: {v['_summary']}")
                        if lines:
                            st.caption("**风险明细**"); st.text("\n".join(lines))
                    f_stage = qcc_data.get("stages", {}).get("F_经营规模", {})
                    if f_stage:
                        st.caption(f"**经营规模**: {f_stage.get('_summary','')}")
            elif qcc_data and qcc_data.get("_summary"):
                st.caption(f"🏢 {qcc_data['_summary']}")

            # 2.2 判例价值
            prec_default = {"score": 50, "first_case_index": "-", "influence_level": "-", "analysis": "评估失败"}
            progress.progress(78, "6/7 判例价值评估...")
            with st.spinner("📚 北大法宝首案检索 → DeepSeek 判例价值判断..."):
                try: pkulaw_prec = search_for_precedent(case.case_description)
                except: pkulaw_prec = {"laws": [], "cases": []}
                try:
                    precedent_result = evaluate_precedent_value(case.case_description,
                        case_law_references="", pkulaw_data=pkulaw_prec)
                except Exception as exc:
                    precedent_result = {"error": str(exc)[:200]}
            if precedent_result.get("error"):
                st.warning("⚠️ 判例价值异常，使用默认分")
                precedent_result = prec_default
            prec_score = precedent_result.get('score', 50)
            dim_card("2.2 判例价值评估", prec_score, precedent_result.get('analysis', ''),
                     extra=f"首案指数: {precedent_result.get('first_case_index','-')} | 影响力级别: {precedent_result.get('influence_level','-')}")

            business_score = calculate_business_expectation(
                financial_result.get('score', 50), precedent_result.get('score', 50), case.goal_type)

            # ── 维度三：证据就绪度 ──
            progress.progress(92, "7/7 证据就绪度评估...")
            with st.spinner("正在逐项核验证据完整性..."):
                evidence_result = evaluate_evidence_readiness(case.case_description,
                    uploaded_evidence_texts=evidence_texts, evidence_count=0)
            if evidence_result.get("error"):
                evidence_result = {"score": 60, "evidence_matrix": [], "analysis": "", "missing_items": [], "remediation_suggestions": [], "collection_advice": "", "error": evidence_result.get("error")}

            evidence_score = evidence_result.get('score', 60)

            # ── 综合评分 ──
            progress.progress(97, "计算综合评分...")
            final_score = calculate_overall_score(legal_score, business_score, evidence_score)
            rec = generate_recommendation(final_score, procedure_result.get('items', []))

            # ── 🔍 防幻觉验证阶段（progress 95，报告生成前）──
            with st.spinner("🔍 北大法宝防幻觉验证（adjust_provisions → law_recognition → anhao_recognition → 交叉验证）..."):
                # 先生成报告草稿用于验证扫描
                rule_results_for_verif = [
                    {"rule_name": it.get("name", "未知程序项"), "severity": "pass" if it.get("status") in ("pass","warning","block") else "warning",
                     "result": it.get("detail", ""), "reason": it.get("detail", "")}
                    for it in procedure_result.get('items', [])
                ]
                report_md_pre = generate_markdown_report(
                    {"name": case.name, "cause_type": case.cause_type, "goal_type": case.goal_type, "client_org": case.client_org},
                    {"legal_feasibility": legal_score, "business_expectation": business_score, "evidence_readiness": evidence_score,
                     "final_score": final_score, "recommendation": rec['recommendation'], "confidence_score": 70, "reason": rec['reason'], "action_items": []},
                    rule_results_for_verif,
                    {"elements": [
                        {"element":"权利基础","score":rights_result.get('score',0),"analysis":rights_result.get('analysis',''),"evidence_status":"-","risks":rights_result.get('risks',[])},
                        {"element":"侵权认定","score":infringement_result.get('score',0),"analysis":infringement_result.get('analysis',''),"evidence_status":"-","risks":infringement_result.get('risks',[])},
                        {"element":"诉讼程序","score":procedure_result.get('score',0),"analysis":procedure_result.get('analysis',''),"evidence_status":"-","risks":procedure_result.get('block_items',[])},
                    ]})
                vresult = run_verification_phase(report_md_pre)
                vs = vresult["summary"]

            st.markdown("---")
            with st.expander("🔍 北大法宝 · 防幻觉验证（全部通过）" if vs["laws_verified"] else "🔍 北大法宝 · 防幻觉验证", expanded=True):
                col_v1, col_v2, col_v3, col_v4 = st.columns(4)
                with col_v1:
                    st.metric("法条校验", "✅" if vs["laws_verified"] else "⚠️",
                              delta=f"识别{vs['laws_found']}条" if vs["laws_found"] else "未引用")
                with col_v2:
                    st.metric("案号校验", "✅" if vs["cases_verified"] else "⚠️",
                              delta=f"{vs['cases_found']}案号" if vs['cases_found'] else "0案号")
                with col_v3:
                    hall_count = len(vs["hallucinations"])
                    st.metric("幻觉排查", "✅" if not hall_count else "⚠️",
                              delta="无" if not hall_count else f"{hall_count}条")
                with col_v4:
                    st.metric("总体", "✅ 通过" if vs["laws_verified"] else "⚠️ 需复查")
                if vs["hallucinations"]:
                    for h in vs["hallucinations"]:
                        st.warning(h)

            # ── 存入 session state ──
            eval_data = {
                "rights": rights_result,
                "infringement": infringement_result,
                "procedure": procedure_result,
                "moot": moot_result,
                "financial": financial_result,
                "precedent": precedent_result,
                "evidence": evidence_result,
                "qcc_data": qcc_data or {},
                "legal_score": legal_score,
                "business_score": business_score,
                "evidence_score": evidence_score,
                "final_score": final_score,
                "recommendation": rec,
                "correction_coeff": correction_coeff,
            }
            st.session_state[eval_key] = eval_data
            for k, v in [("rights", rights_result), ("infringement", infringement_result), ("procedure", procedure_result),
                          ("moot", moot_result), ("financial", financial_result), ("precedent", precedent_result), ("evidence", evidence_result)]:
                st.session_state[f"{k}_{case_id}"] = v

            # ── 保存到数据库 ──
            db.add(ScoreSnapshot(case_id=case_id, legal_score=legal_score, business_score=business_score,
                evidence_score=evidence_score, confidence_score=70, final_score=final_score, recommendation=rec['recommendation']))
            db.commit()

            # ── 生成报告 ──
            rule_results_for_report = [
                {"rule_name": it.get("name", "未知程序项"),
                 "severity": (it.get("status", "warning") or "warning")
                     if it.get("status") in ("pass", "warning", "block")
                     else {"满足": "pass", "存疑": "warning", "不满足": "block"}.get(it.get("status", "存疑"), "warning"),
                 "result": it.get("detail", ""), "reason": it.get("detail", "")}
                for it in procedure_result.get('items', [])
            ]
            report_md = generate_markdown_report(
                {"name": case.name, "cause_type": case.cause_type, "goal_type": case.goal_type, "client_org": case.client_org},
                {"legal_feasibility": legal_score, "business_expectation": business_score, "evidence_readiness": evidence_score,
                 "final_score": final_score, "recommendation": rec['recommendation'], "confidence_score": 70, "reason": rec['reason'], "action_items": []},
                rule_results_for_report,
                {"elements": [
                    {"element":"权利基础","score":rights_result.get('score',0),"analysis":rights_result.get('analysis',''),"evidence_status":"-","risks":rights_result.get('risks',[])},
                    {"element":"侵权认定","score":infringement_result.get('score',0),"analysis":infringement_result.get('analysis',''),"evidence_status":"-","risks":infringement_result.get('risks',[])},
                    {"element":"诉讼程序","score":procedure_result.get('score',0),"analysis":procedure_result.get('analysis',''),"evidence_status":"-","risks":procedure_result.get('block_items',[])},
                ]})

            # 验证章节追加到报告
            hall_count = len(vs["hallucinations"])
            verification_section = f"""

## 七、北大法宝防幻觉验证

- ✅ 法条校验: 识别到 {vs['laws_found']} 条法规引用
- ✅ 案号校验: 识别到 {vs['cases_found']} 个案号引用
- {'✅' if not hall_count else '⚠️'} 幻觉排查: {'通过' if not hall_count else f'发现 {hall_count} 处可疑引用'}
"""
            report_md += verification_section

            # 报告增强：核心法律分析段落添加法宝超链接
            try:
                legal_analysis_text = (
                    f"权利基础：{rights_result.get('analysis', '')}。"
                    f"侵权认定：{infringement_result.get('analysis', '')}。"
                    f"诉讼程序：{procedure_result.get('analysis', '')}。"
                )
                enhance_resp = get_linked_content(legal_analysis_text[:3000])
                if enhance_resp and "result" in enhance_resp:
                    sc = enhance_resp["result"].get("structuredContent", enhance_resp["result"])
                    linked_text = sc.get("result", "") if isinstance(sc, dict) else str(sc)
                    if linked_text:
                        report_md += f"""

## 八、法律分析（法宝超链增强版）

{linked_text}
"""
            except Exception:
                pass

            report_dir = Path("data/reports")
            report_dir.mkdir(parents=True, exist_ok=True)
            md_path = report_dir / f"{case_id}_report.md"
            md_path.write_text(report_md, encoding="utf-8")
            db.add(Report(case_id=case_id, report_type="评估报告", markdown_content=report_md, pdf_uri=str(md_path)))
            case.status = "completed"
            db.commit()

            deepseek_results = {
                "rights": rights_result, "infringement": infringement_result,
                "procedure": procedure_result, "financial": financial_result,
                "precedent": precedent_result, "evidence": evidence_result
            }
            generate_all_queries(case_id, case.case_description, deepseek_results)

            progress.progress(100, "评估完成！")
            st.success("三维评估全部完成！请查看下方分页结果")
            st.info("评估报告已生成，前往「评估报告」页面可下载。")
            st.rerun()

        # ════════════════════════════════════════════════════
        # 评估结果展示 — Tab 分页
        # ════════════════════════════════════════════════════
        if eval_data:
            st.markdown("---")

            tab_rights, tab_infr, tab_proc, tab_moot, tab_biz, tab_evid, tab_final = st.tabs([
                "1.1 权利基础", "1.2 侵权认定", "1.3 诉讼程序",
                "1.4 模拟法庭", "2 业务预期", "3 证据就绪度", "综合评分"
            ])

            rights_r = eval_data["rights"]
            infr_r = eval_data["infringement"]
            proc_r = eval_data["procedure"]
            moot_r = eval_data["moot"]
            fin_r = eval_data["financial"]
            prec_r = eval_data["precedent"]
            evid_r = eval_data["evidence"]
            legal_s = eval_data["legal_score"]
            biz_s = eval_data["business_score"]
            evid_s = eval_data["evidence_score"]
            final_s = eval_data["final_score"]
            rec_data = eval_data["recommendation"]
            coeff = eval_data["correction_coeff"]

            # ── Tab 1: 权利基础 ──
            with tab_rights:
                sub_scores = []
                for k, v in rights_r.get('sub_scores', {}).items():
                    label = {"validity":"商标有效性","usage_continuity":"连续使用","coverage":"覆盖范围","well_known_status":"驰名地位","risk_of_invalidation":"无效风险"}.get(k, k)
                    sub_scores.append({"name": label, "score": v, "status": "pass" if v >= 60 else "warning"})
                dim_card("1.1 权利基础评估", rights_r.get('score', 0),
                         rights_r.get('analysis', ''), sub_items=sub_scores,
                         extra="优势: " + ", ".join(rights_r.get('strengths', ['-'])) + "\n\n风险: " + ", ".join(rights_r.get('risks', ['-'])))

                with st.expander("📚 北大法宝 · 法条检索（验证权利基础）", expanded=True):
                    with st.spinner("实时调用北大法宝..."):
                        try:
                            pkulaw_data = search_for_rights_foundation()
                            st.caption(f"**检索摘要**: {pkulaw_data.get('_summary','')}")
                            for law in pkulaw_data.get("laws", [])[:5]:
                                st.markdown(f"**{law.get('title','?')}**")
                                if law.get('content'): st.caption(law['content'][:300])
                                if law.get('timeliness'): st.caption(f"时效: {law['timeliness']}")
                        except Exception as e:
                            st.error(f"检索失败: {e}")

            # ── Tab 2: 侵权认定 ──
            with tab_infr:
                el_items = [{"name": el['name'], "score": el['score'], "status": el.get('status','pass'), "detail": el.get('analysis','')} for el in infr_r.get('elements', [])]
                dim_card("1.2 侵权认定评估", infr_r.get('score', 0),
                         infr_r.get('analysis', ''), sub_items=el_items)

                with st.expander("📚 北大法宝 · 类案检索（验证侵权认定标准）", expanded=True):
                    with st.spinner("实时调用北大法宝..."):
                        try:
                            pkulaw_data = search_for_infringement()
                            st.caption(f"**检索摘要**: {pkulaw_data.get('_summary','')}")
                            for law in pkulaw_data.get("laws", [])[:3]:
                                st.markdown(f"📖 **{law.get('title','?')}**")
                                if law.get('content'): st.caption(law['content'][:200])
                            for c in pkulaw_data.get("cases", [])[:5]:
                                st.markdown(f"⚖️ **{c.get('title','?')}**")
                                meta = " · ".join([x for x in [c.get('court',''), c.get('date','')] if x])
                                if meta: st.caption(meta)
                                if c.get('summary'): st.caption(c['summary'][:200])
                        except Exception as e:
                            st.error(f"检索失败: {e}")

            # ── Tab 3: 诉讼程序 ──
            with tab_proc:
                proc_items = [{"name": p['name'], "status": p.get('status','pass'), "detail": p.get('detail','')} for p in proc_r.get('items', [])]
                dim_card("1.3 诉讼程序审查", proc_r.get('score', 0),
                         proc_r.get('analysis', ''), sub_items=proc_items)

                with st.expander("📚 北大法宝 · 法条检索（验证诉讼程序依据）", expanded=True):
                    with st.spinner("实时调用北大法宝..."):
                        try:
                            pkulaw_data = search_for_procedure()
                            st.caption(f"**检索摘要**: {pkulaw_data.get('_summary','')}")
                            for law in pkulaw_data.get("laws", [])[:5]:
                                st.markdown(f"📖 **{law.get('title','?')}**")
                                if law.get('content'): st.caption(law['content'][:300])
                                if law.get('timeliness'): st.caption(f"时效: {law['timeliness']}")
                        except Exception as e:
                            st.error(f"检索失败: {e}")

            # ── Tab 4: 模拟法庭 ──
            with tab_moot:
                if moot_r.get("error") and not moot_r.get("rounds"):
                    st.warning(f"模拟法庭异常: {moot_r.get('error', '')[:200]}")
                else:
                    defense_strength = moot_r.get('defense_strength', 50)
                    coeff_color = COLORS["danger"] if coeff < 0.9 else COLORS["warning"] if coeff < 1.0 else COLORS["success"]

                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        metric_card("对抗修正系数", f"{coeff:.2f}",
                                    "被告抗辩有效削弱原告论证" if coeff < 1.0 else "原告论证在对抗中成立", coeff_color)
                    with col_c2:
                        metric_card("被告抗辩强度", f"{defense_strength}/100",
                                    "抗辩有力" if defense_strength >= 60 else "抗辩一般" if defense_strength >= 40 else "抗辩薄弱",
                                    COLORS["warning"])

                    # 争议焦点
                    focus_points = moot_r.get('focus_points', [])
                    if focus_points:
                        st.markdown(f"""
                        <div class="card" style="border-left:4px solid {COLORS['accent']};">
                            <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">争议焦点</div>
                            {"".join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">{i+1}. {fp}</div>' for i, fp in enumerate(focus_points))}
                        </div>
                        """, unsafe_allow_html=True)

                    # 庭审记录
                    rounds = moot_r.get('rounds', [])
                    if rounds:
                        st.markdown(f"""
                        <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">
                            庭审记录（共{len(rounds)}轮发言）
                        </div>
                        """, unsafe_allow_html=True)

                        for rnd in rounds:
                            role = rnd.get('role', rnd.get('speaker', ''))
                            role_name = rnd.get('role_name', role)
                            step_name = rnd.get('step_name', '')
                            content = rnd.get('content', '')

                            if 'plaintiff' in str(role) or '原告' in str(role_name):
                                role_type = "plaintiff"
                            elif 'defendant' in str(role) or '被告' in str(role_name):
                                role_type = "defendant"
                            else:
                                role_type = "judge"
                            chat_bubble(role_name, step_name, content, role_type)

                    # 法官评分
                    judge_scores = moot_r.get('judge_scores', {})
                    if judge_scores and judge_scores.get('plaintiff'):
                        st.markdown(f"""
                        <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin:16px 0 12px;letter-spacing:-0.02em;">
                            法官评分对比
                        </div>
                        """, unsafe_allow_html=True)

                        p_scores = judge_scores.get('plaintiff', {})
                        d_scores = judge_scores.get('defendant', {})

                        col_p, col_d = st.columns(2)
                        with col_p:
                            st.markdown(f"""
                            <div style="border:1px solid {COLORS['primary']};border-left:3px solid {COLORS['primary']};padding:10px 16px;margin-bottom:12px;">
                                <div style="font-weight:700;color:{COLORS['primary']};font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">原告论证强度</div>
                            </div>
                            """, unsafe_allow_html=True)
                            label_map = {"rights":"权利基础","infringement":"侵权认定","evidence":"证据体系","legal_application":"法律适用","claim_reasonableness":"诉求合理性"}
                            for k, v in p_scores.items():
                                score_bar(label_map.get(k, k), v, COLORS["primary"])

                        with col_d:
                            st.markdown(f"""
                            <div style="border:1px solid {COLORS['danger']};border-left:3px solid {COLORS['danger']};padding:10px 16px;margin-bottom:12px;">
                                <div style="font-weight:700;color:{COLORS['danger']};font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">被告抗辩强度</div>
                            </div>
                            """, unsafe_allow_html=True)
                            d_label_map = {"fact_defense":"事实抗辩","legal_defense":"法律抗辩","evidence_challenge":"证据质疑","alternative_explanation":"替代解释","procedural_defense":"程序抗辩"}
                            for k, v in d_scores.items():
                                score_bar(d_label_map.get(k, k), v, COLORS["danger"])

                        reasoning = judge_scores.get('coefficient_reasoning', '')
                        if reasoning:
                            st.info(f"**修正系数推理**: {reasoning}")

                    # 薄弱环节
                    weak_points = moot_r.get('weak_points', [])
                    if weak_points:
                        st.markdown(f"""
                        <div class="card" style="border-left:4px solid {COLORS['danger']};">
                            <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">对抗暴露的薄弱环节</div>
                            {"".join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">— {wp}</div>' for wp in weak_points)}
                        </div>
                        """, unsafe_allow_html=True)

                    st.caption(f"维度一 法律可行性综合得分: {legal_s} 分（权利 × 侵权 × 程序 × 对抗修正 {coeff:.2f}）")

                    # 北大法宝抗辩类案
                    with st.expander("📚 北大法宝 · 抗辩模式类案（被告常用抗辩）", expanded=True):
                        with st.spinner("实时调用北大法宝..."):
                            try:
                                pkulaw_data = search_for_moot_court()
                                st.caption(f"**检索摘要**: {pkulaw_data.get('_summary','')}")
                                for c in pkulaw_data.get("cases", [])[:5]:
                                    st.markdown(f"⚖️ **{c.get('title','?')}**")
                                    meta = " · ".join([x for x in [c.get('court',''), c.get('date','')] if x])
                                    if meta: st.caption(meta)
                                    if c.get('summary'): st.caption(c['summary'][:200])
                            except Exception as e:
                                st.error(f"检索失败: {e}")

            # ── Tab 5: 业务预期 ──
            with tab_biz:
                section_banner("维度二：业务预期", f"目标：{case.goal_type} · 回答「值不值得诉」", COLORS["warning"])

                fin_score = fin_r.get('score', 50)
                de = fin_r.get('damages_estimate', {})
                te = fin_r.get('time_estimate', {})
                fin_extra = []
                if de:
                    fin_extra.append(f"判赔预测: P10=¥{de.get('p10','-')} / P50=¥{de.get('p50','-')} / P90=¥{de.get('p90','-')}")
                fin_extra.append(f"预估成本: ¥{fin_r.get('cost_estimate','-')}")
                if te:
                    fin_extra.append(f"时间: 一审{te.get('first_instance_months','-')}月 + 二审{te.get('second_instance_months','-')}月 + 执行{te.get('enforcement_months','-')}月")
                fin_extra.append(f"回款概率: {fin_r.get('recovery_probability','-')}%")
                dim_card("2.1 财务回报评估", fin_score, fin_r.get('analysis', ''), extra="\n".join(fin_extra))

                # ── 企查查 · 被告财务画像 ──
                qcc_d = eval_data.get("qcc_data", {})
                if qcc_d and qcc_d.get("stages"):
                    with st.expander("🏢 企查查 · 被告财务画像（实测数据）", expanded=False):
                        st.caption(qcc_d.get("_summary", ""))
                        metrics = qcc_d.get("metrics", {})
                        if metrics:
                            cols = st.columns(3)
                            cols[0].metric("回款概率", f"{metrics.get('recovery_probability', '-')}%")
                            cols[1].metric("判赔方向", metrics.get('damages_adjustment', '-'))
                            cols[2].metric("时间延长", f"+{metrics.get('time_extra_months', 0)}月")
                            reds = metrics.get("red_flags", [])
                            greens = metrics.get("green_flags", [])
                            if reds:
                                st.error("🚨 " + " | ".join(reds[:5]))
                            if greens:
                                st.success("✅ " + " | ".join(greens[:5]))

                        # 阶段 D 风险明细
                        d_stage = qcc_d.get("stages", {}).get("D_风险下钻", {})
                        if d_stage:
                            risk_lines = []
                            for label in ("失信信息", "被执行人", "终本案件", "限高消费", "经营异常", "严重违法",
                                          "股权冻结", "动产抵押", "土地抵押", "司法拍卖", "欠税公告", "税收违法"):
                                row = d_stage.get(label, {})
                                if isinstance(row, dict) and row.get("_summary"):
                                    risk_lines.append(f"- {label}: {row['_summary']}")
                            if risk_lines:
                                st.caption("**风险明细**")
                                st.text("\n".join(risk_lines))

                        # 阶段 F 经营规模
                        f_stage = qcc_d.get("stages", {}).get("F_经营规模", {})
                        if f_stage:
                            ch_lines = []
                            for label in ("商标资产", "线上店铺", "APP信息", "小程序", "微信公众号", "抖音账号",
                                          "招投标", "融资记录", "荣誉信息", "榜单排名", "招聘信息"):
                                row = f_stage.get(label, {})
                                if isinstance(row, dict):
                                    ch_lines.append(f"- {label}: {row.get('_summary', '')}")
                            if ch_lines:
                                st.caption("**经营规模与侵权渠道**")
                                st.text("\n".join(ch_lines))

                # 北大法宝判赔数据
                with st.expander("📚 北大法宝 · 判赔数据类案（参考同案判赔区间）", expanded=True):
                    with st.spinner("实时调用北大法宝..."):
                        try:
                            pkulaw_data = search_for_financial()
                            st.caption(f"**检索摘要**: {pkulaw_data.get('_summary','')}")
                            for c in pkulaw_data.get("cases", [])[:5]:
                                st.markdown(f"💰 **{c.get('title','?')}**")
                                meta = " · ".join([x for x in [c.get('court',''), c.get('date','')] if x])
                                if meta: st.caption(meta)
                                if c.get('summary'): st.caption(c['summary'][:200])
                        except Exception as e:
                            st.error(f"检索失败: {e}")

                prec_score = prec_r.get('score', 50)
                dim_card("2.2 判例价值评估", prec_score, prec_r.get('analysis', ''),
                         extra=f"首案指数: {prec_r.get('first_case_index','-')} | 影响力级别: {prec_r.get('influence_level','-')}")

                with st.expander("📚 北大法宝 · 首案检索（判例价值主力引擎）", expanded=True):
                    with st.spinner("实时调用北大法宝..."):
                        try:
                            pkulaw_data = search_for_precedent(case.case_description)
                            st.caption(f"**检索摘要**: {pkulaw_data.get('_summary','')}")
                            for c in pkulaw_data.get("cases", [])[:8]:
                                st.markdown(f"⚖️ **{c.get('title','?')}**")
                                meta = " · ".join([x for x in [c.get('court',''), c.get('date','')] if x])
                                if meta: st.caption(meta)
                                if c.get('summary'): st.caption(c['summary'][:200])
                        except Exception as e:
                            st.error(f"检索失败: {e}")

                st.success(f"维度二 业务预期综合得分: {biz_s} 分")
                if case.goal_type == "要钱":
                    st.caption(f"公式: 0.9×财务({fin_score}) + 0.1×判例({prec_score}) = {biz_s}")
                else:
                    st.caption(f"公式: 0.1×财务({fin_score}) + 0.9×判例({prec_score}) = {biz_s}")

            # ── Tab 6: 证据就绪度 ──
            with tab_evid:
                section_banner("维度三：证据就绪度", "回答「现在能不能诉」", COLORS["success"])

                ev_items = [{"name": m['requirement'], "status": m.get('status','不足'), "detail": m.get('analysis','')} for m in evid_r.get('evidence_matrix', [])]
                dim_card("证据就绪度评估", evid_r.get('score', 60), evid_r.get('analysis', ''),
                         sub_items=ev_items,
                         extra="补证建议: " + ("; ".join(evid_r.get('remediation_suggestions', ['无']))) + "\n\n取证技术建议: " + evid_r.get('collection_advice', '根据证据类型自行判断'))

                st.success(f"维度三 证据就绪度得分: {evid_s} 分")

            # ── Tab 7: 综合评分 ──
            with tab_final:
                rec_color = {"green": COLORS["success"], "yellow": COLORS["warning"], "red": COLORS["danger"], "block": COLORS["danger"]}.get(rec_data['level'], COLORS["success"])
                final_score_card(final_s, rec_data['recommendation'], rec_data['reason'], rec_color)

                col_bars, col_radar = st.columns([1, 1])
                with col_bars:
                    st.markdown("##### 各维度得分")
                    score_bar("法律可行性", legal_s, COLORS["primary"], "权利 × 侵权 × 程序 × 对抗修正")
                    score_bar("业务预期", biz_s, COLORS["warning"], "要钱/要名自适应加权")
                    score_bar("证据就绪度", evid_s, COLORS["success"], "证据完整性与补证")
                    st.markdown(f"**乘法模型**: {legal_s} × {biz_s} × {evid_s} = **{final_s}**")
                    st.caption(f"对抗修正系数: {coeff:.2f} · 一票否决逻辑")

                with col_radar:
                    st.markdown("##### 三维雷达图")
                    radar_html = render_radar_html({
                        "法律可行性": legal_s,
                        "业务预期": biz_s,
                        "证据就绪度": evid_s
                    })
                    st.markdown(radar_html, unsafe_allow_html=True)

                # 北大法宝验证
                with st.expander("北大法宝 · 法条与案号验证"):
                    valid_status = get_validation_status(case_id)
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1:
                        metric_card("法条验证", "通过" if valid_status["provisions_validated"] else "待验证", "")
                    with col_v2:
                        metric_card("法规识别", "通过" if valid_status["laws_validated"] else "待验证", "")
                    with col_v3:
                        metric_card("案号识别", "通过" if valid_status["cases_validated"] else "待验证", "")
                    if not all([valid_status["provisions_validated"], valid_status["laws_validated"], valid_status["cases_validated"]]):
                        st.warning("评估完成后，请让 AI 助手运行北大法宝验证，确保法条和案号引用真实有效")

                st.info("评估报告已生成，前往「评估报告」页面查看和下载完整报告。")

    finally:
        db.close()


# ============================================================
# 页面 4: 模拟法庭
# ============================================================
elif page == "模拟法庭":
    page_header("模拟法庭", "多Agent对抗式庭审 · 原告Agent ↔ 被告Agent ↔ 法官Agent")

    if "current_case_id" not in st.session_state:
        st.warning("请先在「案件列表」中选择一个案件")
        st.stop()

    case_id = st.session_state["current_case_id"]
    case_name = st.session_state.get("current_case_name", "未知案件")

    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error("案件不存在")
            st.stop()

        # 案件信息
        st.markdown(f"""
        <div class="card" style="border-left:4px solid {COLORS['accent']};">
            <div style="font-size:1.05rem;font-weight:700;color:{COLORS['text_dark']};letter-spacing:-0.01em;">{case_name}</div>
            <div style="font-size:0.78rem;color:{COLORS['text_muted']};margin-top:4px;">
                ID: {case_id} | 案由: {case.cause_type} | 模式: {'Mock 模拟' if _mock else 'DeepSeek API'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        moot_key = f"moot_{case_id}"
        moot_result = st.session_state.get(moot_key)

        # 操作区
        col_run, col_info = st.columns([1, 2])
        with col_run:
            if st.button("开始模拟法庭", type="primary", use_container_width=True):
                rights_text = str(st.session_state.get(f"rights_{case_id}", {}).get('analysis', ''))
                inf_text = str(st.session_state.get(f"infringement_{case_id}", {}).get('analysis', ''))
                evidence_texts = st.session_state.get("evidence_text_extra", "")

                progress = st.progress(0, "正在启动模拟法庭...")
                with st.spinner("正在运行五步庭审模拟，预计需要 1-2 分钟..."):
                    moot_result = run_moot_court_simulation(
                        case.case_description,
                        rights_assessment=rights_text,
                        infringement_assessment=inf_text,
                        evidence_summary=evidence_texts[:1500] if evidence_texts else ""
                    )
                    st.session_state[moot_key] = moot_result
                progress.progress(100, "模拟法庭完成！")
                st.rerun()

        with col_info:
            if moot_result:
                coeff = moot_result.get('correction_coefficient', 1.0)
                ds = moot_result.get('defense_strength', 50)
                st.success(f"已完成 | 修正系数: **{coeff:.2f}** | 抗辩强度: **{ds}/100**")
            else:
                st.info("点击左侧按钮启动模拟法庭。需要先完成「评估分析」以获取权利基础和侵权认定结果。")

        st.markdown("")

        # ── 结果展示 ──
        if moot_result and moot_result.get('rounds'):
            rounds = moot_result.get('rounds', [])

            # 顶部摘要
            coeff = moot_result.get('correction_coefficient', 1.0)
            ds = moot_result.get('defense_strength', 50)
            coeff_color = COLORS["danger"] if coeff < 0.9 else COLORS["warning"] if coeff < 1.0 else COLORS["success"]

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                metric_card("对抗修正系数", f"{coeff:.2f}",
                            "抗辩有效削弱" if coeff < 1.0 else "原告论证成立", coeff_color)
            with col_s2:
                metric_card("被告抗辩强度", f"{ds}/100",
                            "有力" if ds >= 60 else "一般" if ds >= 40 else "薄弱", COLORS["warning"])
            with col_s3:
                wp_count = len(moot_result.get('weak_points', []))
                metric_card("暴露薄弱环节", f"{wp_count} 项", "需关注补强", COLORS["danger"])

            # 庭审步骤进度条
            step_names = ["开庭陈述", "被告答辩", "举证质证", "法庭辩论", "法官归纳"]
            step_nums = [1, 2, 3, 4, 5]
            st.markdown(f"""
            <div style="margin:20px 0;padding:16px 0;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    {"".join(f'''
                    <div style="flex:1;text-align:center;position:relative;">
                        <div style="width:32px;height:32px;border:2px solid {'#0d1429' if i < len(rounds) else '#e5e5e5'};border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700;color:{'#0d1429' if i < len(rounds) else '#ccc'};background:{'#0d1429' if i < len(rounds) else 'transparent'};">{f'<span style="color:#fff;">{i+1}</span>' if i < len(rounds) else i+1}</div>
                        <div style="font-size:0.72rem;color:{'#0d1429' if i < len(rounds) else '#ccc'};margin-top:6px;font-weight:{'600' if i < len(rounds) else '400'};">{s}</div>
                    </div>{'<div style="flex:0.3;height:2px;background:#0d1429;"></div>' if i < 4 else ''}
                    ''' for i, s in enumerate(step_names))}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 争议焦点
            focus_points = moot_result.get('focus_points', [])
            if focus_points:
                st.markdown(f"""
                <div class="card" style="border-left:4px solid {COLORS['accent']};">
                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">争议焦点</div>
                    {"".join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">{i+1}. {fp}</div>' for i, fp in enumerate(focus_points))}
                </div>
                """, unsafe_allow_html=True)

            # 庭审记录 — 按步骤分组显示
            st.markdown("")
            st.markdown(f"""
            <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">
                庭审记录（共{len(rounds)}轮发言）
            </div>
            """, unsafe_allow_html=True)

            current_step = None
            for rnd in rounds:
                role = rnd.get('role', rnd.get('speaker', ''))
                role_name = rnd.get('role_name', role)
                step_name = rnd.get('step_name', '')
                content = rnd.get('content', '')
                step_num = rnd.get('step', 0)

                # 步骤分隔线 + 步骤标题
                if step_num != current_step:
                    current_step = step_num
                    step_label_map = {1: "第一步 · 开庭陈述", 2: "第二步 · 被告答辩", 3: "第三步 · 举证质证", 4: "第四步 · 法庭辩论", 5: "第五步 · 法官归纳"}
                    st.markdown(f"""
                    <div style="margin:20px 0 8px 0;padding:8px 0;border-bottom:2px solid #0d1429;">
                        <span style="font-size:0.9rem;font-weight:700;color:#0d1429;letter-spacing:-0.01em;">{step_label_map.get(step_num, step_name)}</span>
                    </div>
                    """, unsafe_allow_html=True)

                if 'plaintiff' in str(role) or '原告' in str(role_name):
                    role_type = "plaintiff"
                elif 'defendant' in str(role) or '被告' in str(role_name):
                    role_type = "defendant"
                else:
                    role_type = "judge"
                chat_bubble(role_name, step_name, content, role_type)

            # 法官归纳摘要 — 高亮显示
            judge_summary = moot_result.get('judge_summary', '')
            if judge_summary:
                st.markdown(f"""
                <div class="card" style="border:2px solid {COLORS['accent']};margin-top:20px;">
                    <div style="font-size:0.72rem;color:{COLORS['accent']};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;font-weight:600;">法官最终归纳</div>
                    <div style="font-size:0.88rem;color:#333;line-height:1.8;">{judge_summary}</div>
                </div>
                """, unsafe_allow_html=True)

            # 法官评分对比
            judge_scores = moot_result.get('judge_scores', {})
            if judge_scores and judge_scores.get('plaintiff'):
                st.markdown("")
                st.markdown(f"""
                <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">
                    法官评分对比
                </div>
                """, unsafe_allow_html=True)

                p_scores = judge_scores.get('plaintiff', {})
                d_scores = judge_scores.get('defendant', {})
                p_detail = judge_scores.get('plaintiff_detail', {})
                d_detail = judge_scores.get('defendant_detail', {})

                col_p, col_d = st.columns(2)
                with col_p:
                    p_avg = sum(p_scores.values()) / len(p_scores) if p_scores else 0
                    st.markdown(f"""
                    <div style="border:1px solid {COLORS['primary']};border-left:3px solid {COLORS['primary']};padding:10px 16px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
                        <div style="font-weight:700;color:{COLORS['primary']};font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">原告论证强度</div>
                        <div style="font-size:1.4rem;font-weight:800;color:{COLORS['primary']};">{p_avg:.0f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    label_map = {"rights":"权利基础","infringement":"侵权认定","evidence":"证据体系","legal_application":"法律适用","claim_reasonableness":"诉求合理性"}
                    for k, v in p_scores.items():
                        detail = p_detail.get(k, "")
                        score_bar(label_map.get(k, k), v, COLORS["primary"], detail)

                with col_d:
                    d_avg = sum(d_scores.values()) / len(d_scores) if d_scores else 0
                    st.markdown(f"""
                    <div style="border:1px solid {COLORS['danger']};border-left:3px solid {COLORS['danger']};padding:10px 16px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
                        <div style="font-weight:700;color:{COLORS['danger']};font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">被告抗辩强度</div>
                        <div style="font-size:1.4rem;font-weight:800;color:{COLORS['danger']};">{d_avg:.0f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    d_label_map = {"fact_defense":"事实抗辩","legal_defense":"法律抗辩","evidence_challenge":"证据质疑","alternative_explanation":"替代解释","procedural_defense":"程序抗辩"}
                    for k, v in d_scores.items():
                        detail = d_detail.get(k, "")
                        score_bar(d_label_map.get(k, k), v, COLORS["danger"], detail)

                reasoning = judge_scores.get('coefficient_reasoning', '')
                if reasoning:
                    st.info(f"**修正系数推理**: {reasoning}")

            # 薄弱环节
            weak_points = moot_result.get('weak_points', [])
            if weak_points:
                st.markdown(f"""
                <div class="card" style="border-left:4px solid {COLORS['danger']};">
                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">对抗暴露的薄弱环节</div>
                    {"".join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">— {wp}</div>' for wp in weak_points)}
                </div>
                """, unsafe_allow_html=True)

        elif moot_result and moot_result.get('error'):
            st.error(f"模拟法庭出错: {moot_result['error']}")

    finally:
        db.close()


# ============================================================
# 页面 5: 评估报告
# ============================================================
elif page == "评估报告":
    page_header("评估报告", "三维评分总览 · 可下载总结文档")

    if "current_case_id" not in st.session_state:
        st.warning("请先在「案件列表」中选择一个已评估的案件")
        st.stop()

    case_id = st.session_state["current_case_id"]
    case_name = st.session_state.get("current_case_name", "未知案件")

    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error("案件不存在")
            st.stop()

        score = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
        report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()

        if not score:
            st.warning("该案件尚未评估，请先进行评估")
            st.stop()

        # 顶部摘要
        rec_color = {"建议起诉": COLORS["success"], "补证后再起诉": COLORS["warning"],
                     "暂不建议起诉": COLORS["danger"], "暂缓起诉": COLORS["danger"]}.get(score.recommendation, COLORS["primary"])

        st.markdown(f"""
        <div class="card" style="border-left:6px solid {rec_color};">
            <div style="font-size:0.72rem;color:{COLORS['text_muted']};margin-bottom:4px;text-transform:uppercase;letter-spacing:0.08em;">{case.cause_type} · 评估报告</div>
            <div style="font-size:1.5rem;font-weight:800;color:{COLORS['text_dark']};letter-spacing:-0.02em;">{case.name}</div>
            <div style="margin-top:16px;display:flex;gap:40px;flex-wrap:wrap;">
                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">综合评分</span><br>
                     <span style="font-size:3rem;font-weight:800;color:{rec_color};letter-spacing:-0.04em;">{score.final_score}</span>
                     <span style="color:{COLORS['text_muted']};font-size:0.9rem;">/100</span></div>
                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">建议</span><br>
                     <span style="font-size:1.2rem;font-weight:700;color:{rec_color};">{score.recommendation}</span></div>
                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">置信度</span><br>
                     <span style="font-size:1.2rem;font-weight:600;">{score.confidence_score}%</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 雷达图 + 评分条
        col_chart, col_bars = st.columns([1, 1])
        with col_chart:
            st.markdown("##### 三维评分雷达图")
            radar_html = render_radar_html({
                "法律可行性": int(score.legal_score),
                "业务预期": int(score.business_score),
                "证据就绪度": int(score.evidence_score)
            })
            st.markdown(radar_html, unsafe_allow_html=True)

        with col_bars:
            st.markdown("##### 各维度得分详情")
            score_bar("法律可行性", int(score.legal_score), COLORS["primary"], "权利 × 侵权 × 程序 × 对抗修正")
            score_bar("业务预期", int(score.business_score), COLORS["warning"], "要钱/要名自适应加权")
            score_bar("证据就绪度", int(score.evidence_score), COLORS["success"], "证据完整性与补证")
            st.divider()
            st.markdown(f"**乘法模型**: {int(score.legal_score)} × {int(score.business_score)} × {int(score.evidence_score)} = **{score.final_score}**")
            st.caption(f"置信度: {score.confidence_score}% · 一票否决逻辑")

        # 完整报告
        st.markdown("---")
        st.markdown("##### 完整评估报告")
        if report:
            st.markdown(report.markdown_content)
        else:
            st.info("报告内容未保存")

        # 下载区域
        st.markdown("---")
        st.markdown("##### 📥 下载总结文档")

        radar_svg_str = render_radar_svg({
            "法律可行性": int(score.legal_score),
            "业务预期": int(score.business_score),
            "证据就绪度": int(score.evidence_score)
        })

        summary_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>诉算评估报告 - {case.name}</title>
<style>
body{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;max-width:800px;margin:0 auto;padding:40px;color:#333}}
h1{{color:#0d1429;border-bottom:3px solid {rec_color};padding-bottom:12px}}
h2{{color:#0d1429;margin-top:28px}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:8px 12px;text-align:left}}
th{{background:#f8f9fa}}
.score-big{{font-size:3rem;font-weight:bold;color:{rec_color}}}
.rec{{font-size:1.3rem;font-weight:bold;color:{rec_color};margin:8px 0}}
</style></head>
<body>
<h1>诉算 · Soft IP 主诉评估报告</h1>
<p><strong>案件名称:</strong> {case.name} &nbsp;|&nbsp; <strong>案由:</strong> {case.cause_type} &nbsp;|&nbsp; <strong>评估日期:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>

<h2>一、结论摘要</h2>
<div class="score-big">{score.final_score} / 100</div>
<div class="rec">{score.recommendation}</div>

<h2>二、三维评分总览</h2>
<div style="text-align:center;margin:24px 0">{radar_svg_str}</div>
<table>
<tr><th>维度</th><th>得分</th><th>说明</th></tr>
<tr><td>法律可行性</td><td>{score.legal_score}/100</td><td>权利 × 侵权 × 程序 × 对抗修正</td></tr>
<tr><td>业务预期</td><td>{score.business_score}/100</td><td>要钱/要名自适应加权</td></tr>
<tr><td>证据就绪度</td><td>{score.evidence_score}/100</td><td>证据完整性与补证</td></tr>
<tr><td><strong>综合得分（乘法模型）</strong></td><td><strong>{score.final_score}/100</strong></td><td>一票否决逻辑</td></tr>
</table>

<h2>三、评估说明</h2>
<p>本评估基于用户提供的案情描述和证据材料，通过规则引擎和 AI 分析生成。评估覆盖法律可行性、业务预期、证据就绪度三个维度，采用乘法评分模型（一票否决逻辑）。</p>
<p><strong>置信度:</strong> {score.confidence_score}%</p>

<h2>四、后续建议</h2>
<ol>
<li>根据红线和警告项补充关键证据</li>
<li>与法律顾问或外部律师讨论诉讼策略</li>
<li>持续监控侵权行为并收集更多证据</li>
</ol>

<p style="margin-top:40px;color:#999;font-size:0.85rem;">
<em>Generated by 诉算 v{APP_VERSION} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</em>
</p>
<p style="color:#999;font-size:0.8rem;">免责声明: 本报告为 AI 辅助生成，仅供内部决策参考，不构成正式法律意见。</p>
</body></html>"""

        col_dl1, col_dl2, col_dl3 = st.columns(3)

        pdf_bytes = None
        try:
            pdf_bytes = generate_pdf_bytes(report.markdown_content if report else summary_html)
        except Exception as e:
            st.caption(f"PDF 生成失败: {e}")

        with col_dl1:
            if pdf_bytes:
                st.download_button("下载 PDF", data=pdf_bytes, file_name=f"{case_id}_评估报告.pdf",
                    mime="application/pdf", use_container_width=True, type="primary")
            else:
                st.download_button("下载 HTML", data=summary_html.encode('utf-8'),
                    file_name=f"{case_id}_评估报告.html", mime="text/html", use_container_width=True, type="primary")

        with col_dl2:
            if report:
                st.download_button("完整报告 (.md)", data=report.markdown_content,
                    file_name=f"{case_id}_完整报告.md", mime="text/markdown", use_container_width=True)

        with col_dl3:
            st.download_button("🌐 总结文档 (.html)", data=summary_html,
                file_name=f"{case_id}_总结报告.html", mime="text/html", use_container_width=True)

        if pdf_bytes:
            st.caption("PDF 已生成，点击上方按钮一键下载（含中文字体）")
        else:
            st.caption("PDF 生成失败，请使用 HTML 或 Markdown 格式下载")

    finally:
        db.close()


# ============================================================
# 页面 6: 关于
# ============================================================
elif page == "关于":
    page_header("关于诉算", "Soft IP 主诉评估智能工具")

    st.markdown(f"""
    <div class="card" style="border-left:4px solid {COLORS['accent']};">
        <div style="font-size:2rem;font-weight:800;color:{COLORS['primary']};letter-spacing:-0.03em;line-height:1;">诉算</div>
        <div style="font-size:0.75rem;color:{COLORS['text_muted']};margin-top:6px;text-transform:uppercase;letter-spacing:0.1em;">Soft IP 主诉评估智能工具 · v{APP_VERSION}</div>
    </div>

    <div class="card">
        <div class="form-section-title">已实现功能</div>
        <ul style="font-size:0.88rem;color:{COLORS['text_body']};line-height:2;list-style:none;padding-left:0;">
            <li>— 商标侵权案件创建与管理</li>
            <li>— 红线风险自动检查（6 条规则）</li>
            <li>— 法律要件分析（权利基础 / 侵权认定 / 诉讼程序）</li>
            <li>— 三维乘法评分（法律 × 业务 × 证据 · 一票否决）</li>
            <li>— 三维雷达可视化</li>
            <li>— 模拟法庭（多Agent对抗式庭审：原告 ↔ 被告 ↔ 法官，五步庭审流程）</li>
            <li>— 评估报告生成（Markdown + PDF + HTML 下载）</li>
            <li>— Mock 模式（无需 API Key 即可运行）</li>
        </ul>
    </div>

    <div class="card">
        <div class="form-section-title">后续规划</div>
        <ul style="font-size:0.88rem;color:{COLORS['text_body']};line-height:2;list-style:none;padding-left:0;">
            <li>— 接入法律数据库（法规、案例检索）自动化闭环</li>
            <li>— 著作权、不正当竞争案由扩展</li>
            <li>— 证据文件上传与自动解析增强</li>
            <li>— 模拟法庭用户介入功能（暂停修改论证）</li>
        </ul>
    </div>

    <div class="card">
        <div class="form-section-title">技术栈</div>
        <ul style="font-size:0.88rem;color:{COLORS['text_body']};line-height:2;list-style:none;padding-left:0;">
            <li>— 前端: Streamlit + 自定义CSS主题</li>
            <li>— 数据库: SQLite + SQLAlchemy</li>
            <li>— LLM: DeepSeek API（可切换 Mock 模式）</li>
            <li>— 模拟法庭: 多Agent架构（7次独立LLM调用）</li>
            <li>— 可视化: SVG 雷达图（无需额外依赖）</li>
        </ul>
    </div>

    <div style="font-size:0.78rem;color:{COLORS['text_muted']};text-align:center;margin-top:24px;padding:16px;border:1px solid #e5e5e5;">
        <strong>免责声明</strong> · 本系统为 AI 辅助决策工具，评估结果仅供内部参考，不构成正式法律意见。
    </div>
    """, unsafe_allow_html=True)
