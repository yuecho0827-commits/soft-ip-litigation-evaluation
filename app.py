"""
Soft IP 主诉评估系统 - Streamlit 主程序
专业法律科技 UI · 三维乘法评分 · 多Agent模拟法庭
"""

import streamlit as st
import sys
import os
import math
import base64
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from config import APP_TITLE, APP_VERSION, USE_MOCK
from database import init_db, SessionLocal, Case, RuleHit, ScoreSnapshot, Report
from evidence_parser import parse_pdf, ocr_image, is_pdf_file, is_image_file
from report_generator import generate_markdown_report, generate_pdf_bytes
from styles import (
    inject_global_css, page_header, section_banner, dim_card,
    score_bar, final_score_card, case_card, chat_bubble,
    metric_card, form_section_title, COLORS, ROLE_COLORS
)

# 评估引擎
if USE_MOCK:
    from mock_llm import (
        extract_case_facts as evaluate_rights_foundation,
        analyze_legal_elements as evaluate_infringement,
        check_rules as evaluate_procedure,
        generate_score as evaluate_financial_return,
        generate_report as evaluate_precedent_value,
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
page = st.sidebar.radio("导航", page_options, key="nav_page", label_visibility="collapsed")

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
    page_header("新建商标侵权案件", "上传证据文件，填写案情描述，开始诉前评估")

    # ── 证据上传区 ──
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

    if parsed_evidences:
        for fname, fsize, result in parsed_evidences:
            if result["success"]:
                text_len = len(result["text"])
                with st.expander(f"{fname}（{text_len} 字）"):
                    st.text_area(f"内容 - {fname}", value=result["text"], height=160,
                                 key=f"preview_{fname}", label_visibility="collapsed")
                    if st.button(f"追加到案情描述", key=f"append_{hash(fname)}"):
                        current_extra = st.session_state.get("evidence_text_extra", "")
                        st.session_state["evidence_text_extra"] = current_extra + f"\n\n【证据文件: {fname}】\n{result['text']}"
                        st.rerun()
            else:
                st.warning(f"{fname}: {result['error']}")

    evidence_extra = st.session_state.get("evidence_text_extra", "")
    if evidence_extra:
        st.success(f"已追加 {len(evidence_extra)} 字证据文本到案情描述")
        if st.button("🗑️ 清除已追加的证据文本", type="secondary"):
            st.session_state["evidence_text_extra"] = ""
            st.rerun()

    st.markdown("")

    # ── 案件表单 ──
    form_section_title("案件信息")
    default_desc = st.session_state.get("last_case_desc", "")

    with st.form("new_case_form"):
        col1, col2 = st.columns(2)
        with col1:
            case_name = st.text_input("案件名称 *", placeholder="例如：某品牌诉某电商商标侵权案")
            cause_type = st.selectbox("案由", ["商标侵权", "著作权侵权", "不正当竞争"], disabled=True)
            goal_type = st.radio("业务目标", ["要钱", "要名"], horizontal=True)
        with col2:
            client_org = st.text_input("委托客户", placeholder="例如：某知名品牌公司")
            prefill = (evidence_extra + "\n\n" + default_desc).strip()
            case_description = st.text_area(
                "案情描述 *", height=300, value=prefill,
                placeholder="请详细描述案情，包括：\n- 原告商标信息（注册号、类别、有效期）\n- 被告侵权行为（何时发现、如何侵权）\n- 侵权商品销售情况\n- 已收集的证据"
            )

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
            for c in cases:
                # 获取最新评分
                score = db.query(ScoreSnapshot).filter(
                    ScoreSnapshot.case_id == c.id
                ).order_by(ScoreSnapshot.id.desc()).first()

                col_card, col_btn = st.columns([5, 1])
                with col_card:
                    case_card(c.id, c.name, c.cause_type, c.goal_type, c.status,
                             score.final_score if score else None,
                             score.recommendation if score else None)
                with col_btn:
                    st.write("")
                    st.write("")
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
        st.markdown(f"""
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
                    {{"draft":"草稿","evaluating":"评估中","completed":"已完成"}}.get(case.status, "未知")
                </div>
            </div>
        </div>
        """.replace('{{"draft"', '{"draft"').replace('}}.get', '}}.get'), unsafe_allow_html=True)

        with st.expander("查看案情描述", expanded=False):
            st.text_area("", case.case_description, height=200, disabled=True, label_visibility="collapsed")

        # 如果已完成 → 显示历史结果
        if case.status == "completed":
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

        # 评估按钮
        col_sp1, col_btn, col_sp2 = st.columns([1, 2, 1])
        with col_btn:
            do_eval = st.button("开始评估", type="primary", use_container_width=True)

        if do_eval:
            progress = st.progress(0, "初始化评估引擎...")
            evidence_texts = st.session_state.get("evidence_text_extra", "")

            # ════════════════════════════════════════════════════
            # 维度一：法律可行性
            # ════════════════════════════════════════════════════
            section_banner("维度一：法律可行性", "回答「能不能诉」", COLORS["primary"])

            # 1.1 权利基础
            progress.progress(8, "1/7 权利基础评估...")
            with st.spinner("正在分析商标权利基础（有效性、撤三风险、覆盖范围、驰名地位）..."):
                rights_result = evaluate_rights_foundation(case.case_description, uploaded_texts=evidence_texts if not _mock else "")
            if "error" in rights_result:
                st.error(f"权利基础评估失败: {rights_result.get('error', '')[:200]}")
            else:
                sub_scores = []
                for k, v in rights_result.get('sub_scores', {}).items():
                    label = {"validity":"商标有效性","usage_continuity":"连续使用","coverage":"覆盖范围","well_known_status":"驰名地位","risk_of_invalidation":"无效风险"}.get(k, k)
                    sub_scores.append({"name": label, "score": v, "status": "pass" if v >= 60 else "warning"})
                dim_card("1.1 权利基础评估", rights_result.get('score', 0),
                         rights_result.get('analysis', ''), sub_items=sub_scores,
                         extra="优势: " + ", ".join(rights_result.get('strengths', ['-'])) + "\n\n风险: " + ", ".join(rights_result.get('risks', ['-'])))

            with st.expander("北大法宝 · 法条检索（验证权利基础）"):
                pkulaw_rights = get_dimension_results(case_id, "1.1_权利基础")
                if pkulaw_rights:
                    for law in pkulaw_rights.get("laws", [])[:3]:
                        st.markdown(f"**{law.get('title', law.get('name',''))}**")
                        st.caption(law.get('content', law.get('text',''))[:300])
                else:
                    st.info("尚未检索。评估完成后，让 AI 助手通过北大法宝检索验证。")

            # 1.2 侵权认定
            progress.progress(22, "2/7 侵权认定评估...")
            with st.spinner("正在分析商标侵权五要件（商标性使用、商品类似性、近似性、混淆可能性、正当使用）..."):
                infringement_result = evaluate_infringement(case.case_description,
                    rights_assessment=str(rights_result.get('analysis', '')),
                    uploaded_texts=evidence_texts if not _mock else "")
            if "error" in infringement_result:
                st.error(f"侵权认定失败: {infringement_result.get('error', '')[:200]}")
            else:
                el_items = [{"name": el['name'], "score": el['score'], "status": el.get('status','pass'), "detail": el.get('analysis','')} for el in infringement_result.get('elements', [])]
                dim_card("1.2 侵权认定评估", infringement_result.get('score', 0),
                         infringement_result.get('analysis', ''), sub_items=el_items)

            with st.expander("北大法宝 · 类案检索（验证侵权认定标准）"):
                pkulaw_inf = get_dimension_results(case_id, "1.2_侵权认定")
                if pkulaw_inf:
                    for c in pkulaw_inf.get("cases", [])[:3]:
                        st.markdown(f"**{c.get('title', c.get('name',''))}**")
                        st.caption(f"{c.get('court','')} | {c.get('date','')}")
                else:
                    st.info("尚未检索。评估完成后，让 AI 助手通过北大法宝检索验证。")

            # 1.3 诉讼程序
            progress.progress(36, "3/7 程序审查...")
            with st.spinner("正在审查诉讼时效、管辖仲裁、主体适格、前置程序..."):
                procedure_result = evaluate_procedure(case.case_description)
            if "error" in procedure_result:
                st.error(f"程序审查失败: {procedure_result.get('error', '')[:200]}")
            else:
                proc_items = [{"name": p['name'], "status": p.get('status','pass'), "detail": p.get('detail','')} for p in procedure_result.get('items', [])]
                dim_card("1.3 诉讼程序审查", procedure_result.get('score', 0),
                         procedure_result.get('analysis', ''), sub_items=proc_items)

            with st.expander("北大法宝 · 法条检索（验证诉讼程序依据）"):
                pkulaw_proc = get_dimension_results(case_id, "1.3_诉讼程序")
                if pkulaw_proc:
                    for law in pkulaw_proc.get("laws", [])[:3]:
                        st.markdown(f"**{law.get('title', law.get('name',''))}**")
                        st.caption(law.get('content', law.get('text',''))[:300])
                else:
                    st.info("尚未检索。评估完成后，让 AI 助手通过北大法宝检索验证。")

            # 1.4 模拟法庭
            progress.progress(50, "4/7 模拟法庭对抗检验...")
            section_banner("1.4 模拟法庭（多Agent对抗检验）", "原告Agent ↔ 被告Agent ↔ 法官Agent", COLORS["accent"])

            mode_label = "Mock 模拟" if _mock else "DeepSeek API"
            with st.spinner(f"正在进行五步庭审模拟（{mode_label}）：开庭陈述 → 被告答辩 → 举证质证 → 法庭辩论 → 法官归纳..."):
                moot_result = run_moot_court_simulation(case.case_description,
                    rights_assessment=str(rights_result.get('analysis', '')),
                    infringement_assessment=str(infringement_result.get('analysis', '')),
                    evidence_summary=evidence_texts[:1500] if evidence_texts else "")

            if moot_result.get("error") and not moot_result.get("rounds"):
                st.warning(f"模拟法庭异常: {moot_result.get('error', '')[:200]}")
                correction_coeff = 1.0
            else:
                correction_coeff = moot_result.get('correction_coefficient', 1.0)
                defense_strength = moot_result.get('defense_strength', 50)

                # 修正系数 + 抗辩强度
                coeff_color = COLORS["danger"] if correction_coeff < 0.9 else COLORS["warning"] if correction_coeff < 1.0 else COLORS["success"]
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    metric_card("对抗修正系数", f"{correction_coeff:.2f}",
                                "被告抗辩有效削弱原告论证" if correction_coeff < 1.0 else "原告论证在对抗中成立", coeff_color)
                with col_c2:
                    metric_card("被告抗辩强度", f"{defense_strength}/100",
                                "抗辩有力" if defense_strength >= 60 else "抗辩一般" if defense_strength >= 40 else "抗辩薄弱",
                                COLORS["warning"])

                # 庭审记录
                rounds = moot_result.get('rounds', [])
                if rounds:
                    with st.expander(f"庭审记录（共{len(rounds)}轮发言）"):
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
                judge_scores = moot_result.get('judge_scores', {})
                if judge_scores and judge_scores.get('plaintiff'):
                    with st.expander("法官评分明细"):
                        p_scores = judge_scores.get('plaintiff', {})
                        d_scores = judge_scores.get('defendant', {})
                        p_detail = judge_scores.get('plaintiff_detail', {})
                        d_detail = judge_scores.get('defendant_detail', {})

                        col_p, col_d = st.columns(2)
                        with col_p:
                            st.markdown(f"**{ROLE_COLORS['plaintiff']['label']} 原告论证强度**")
                            label_map = {"rights":"权利基础","infringement":"侵权认定","evidence":"证据体系","legal_application":"法律适用","claim_reasonableness":"诉求合理性"}
                            for k, v in p_scores.items():
                                label = label_map.get(k, k)
                                detail = p_detail.get(k, "")
                                st.markdown(f"• **{label}**: {v} 分" + (f" — {detail}" if detail else ""))

                        with col_d:
                            st.markdown(f"**{ROLE_COLORS['defendant']['label']} 被告抗辩强度**")
                            d_label_map = {"fact_defense":"事实抗辩","legal_defense":"法律抗辩","evidence_challenge":"证据质疑","alternative_explanation":"替代解释","procedural_defense":"程序抗辩"}
                            for k, v in d_scores.items():
                                label = d_label_map.get(k, k)
                                detail = d_detail.get(k, "")
                                st.markdown(f"• **{label}**: {v} 分" + (f" — {detail}" if detail else ""))

                        reasoning = judge_scores.get('coefficient_reasoning', '')
                        if reasoning:
                            st.info(f"**修正系数推理**: {reasoning}")

                # 薄弱环节
                weak_points = moot_result.get('weak_points', [])
                if weak_points:
                    st.markdown("**对抗暴露的薄弱环节:**")
                    for wp in weak_points:
                        st.markdown(f"- {wp}")

                st.caption("前往「模拟法庭」页面可查看完整庭审记录和交互式回放")

            # 维度一小计
            legal_score = calculate_legal_feasibility(
                rights_result.get('score', 0), infringement_result.get('score', 0),
                procedure_result.get('score', 0), correction_coeff
            )
            st.success(f"**维度一 法律可行性综合得分: {legal_score} 分**")
            st.caption(f"公式: 权利基础({rights_result.get('score',0)}) × 侵权认定({infringement_result.get('score',0)}) × 诉讼程序({procedure_result.get('score',0)}) × 对抗修正({correction_coeff:.2f}) = {legal_score}")

            # ════════════════════════════════════════════════════
            # 维度二：业务预期
            # ════════════════════════════════════════════════════
            section_banner("维度二：业务预期", f"目标：{case.goal_type} · 回答「值不值得诉」", COLORS["warning"])

            progress.progress(64, "5/7 财务回报评估...")
            with st.spinner("正在预测判赔区间、诉讼成本和净收益..."):
                financial_result = evaluate_financial_return(case.case_description)
            if "error" in financial_result:
                st.warning(f"财务评估异常: {financial_result.get('error', '')[:200]}")
                fin_score = 50
            else:
                fin_score = financial_result.get('score', 50)
                de = financial_result.get('damages_estimate', {})
                te = financial_result.get('time_estimate', {})
                fin_extra = []
                if de: fin_extra.append(f"判赔预测: P10=¥{de.get('p10','-')} / P50=¥{de.get('p50','-')} / P90=¥{de.get('p90','-')}")
                fin_extra.append(f"预估成本: ¥{financial_result.get('cost_estimate','-')}")
                if te: fin_extra.append(f"时间: 一审{te.get('first_instance_months','-')}月 + 二审{te.get('second_instance_months','-')}月 + 执行{te.get('enforcement_months','-')}月")
                fin_extra.append(f"回款概率: {financial_result.get('recovery_probability','-')}%")
                dim_card("2.1 财务回报评估", fin_score, financial_result.get('analysis', ''), extra="\n".join(fin_extra))

            progress.progress(78, "6/7 判例价值评估...")
            with st.spinner("正在评估首案潜力、指导性案例入选概率..."):
                precedent_result = evaluate_precedent_value(case.case_description)
            if "error" in precedent_result:
                st.warning(f"判例价值异常: {precedent_result.get('error', '')[:200]}")
                prec_score = 50
            else:
                prec_score = precedent_result.get('score', 50)
                dim_card("2.2 判例价值评估", prec_score, precedent_result.get('analysis', ''),
                         extra=f"首案指数: {precedent_result.get('first_case_index','-')} | 影响力级别: {precedent_result.get('influence_level','-')}")

            with st.expander("北大法宝 · 首案检索（判例价值主力引擎）"):
                pkulaw_prec = get_dimension_results(case_id, "2.2_判例价值")
                if pkulaw_prec:
                    for c in pkulaw_prec.get("cases", [])[:5]:
                        st.markdown(f"**{c.get('title', c.get('name',''))}**")
                        st.caption(f"{c.get('court','')} | {c.get('date','')} | {c.get('summary','')[:150] if c.get('summary') else ''}")
                else:
                    st.info("尚未检索。评估完成后，让 AI 助手通过北大法宝检索同类在先判决。")

            business_score = calculate_business_expectation(fin_score, prec_score, case.goal_type)
            st.success(f"**维度二 业务预期综合得分: {business_score} 分**")
            if case.goal_type == "要钱":
                st.caption(f"公式: 0.9×财务({fin_score}) + 0.1×判例({prec_score}) = {business_score}")
            else:
                st.caption(f"公式: 0.1×财务({fin_score}) + 0.9×判例({prec_score}) = {business_score}")

            # ════════════════════════════════════════════════════
            # 维度三：证据就绪度
            # ════════════════════════════════════════════════════
            section_banner("维度三：证据就绪度", "回答「现在能不能诉」", COLORS["success"])

            progress.progress(92, "7/7 证据就绪度评估...")
            with st.spinner("正在逐项核验证据完整性..."):
                evidence_result = evaluate_evidence_readiness(case.case_description,
                    uploaded_evidence_texts=evidence_texts, evidence_count=0)
            if "error" in evidence_result:
                st.warning(f"证据评估异常: {evidence_result.get('error', '')[:200]}")
                evidence_score = 60
            else:
                evidence_score = evidence_result.get('score', 60)
                ev_items = [{"name": m['requirement'], "status": m.get('status','不足'), "detail": m.get('analysis','')} for m in evidence_result.get('evidence_matrix', [])]
                dim_card("证据就绪度评估", evidence_score, evidence_result.get('analysis', ''),
                         sub_items=ev_items,
                         extra="补证建议: " + ("; ".join(evidence_result.get('remediation_suggestions', ['无']))) + "\n\n取证技术建议: " + evidence_result.get('collection_advice', '根据证据类型自行判断'))

            st.success(f"**维度三 证据就绪度得分: {evidence_score} 分**")

            # ════════════════════════════════════════════════════
            # 综合评分
            # ════════════════════════════════════════════════════
            st.markdown("---")
            progress.progress(97, "计算综合评分...")

            final_score = calculate_overall_score(legal_score, business_score, evidence_score)
            rec = generate_recommendation(final_score, procedure_result.get('items', []))
            rec_color = {"green": COLORS["success"], "yellow": COLORS["warning"], "red": COLORS["danger"], "block": COLORS["danger"]}.get(rec['level'], COLORS["success"])

            final_score_card(final_score, rec['recommendation'], rec['reason'], rec_color)

            # 评分条 + 雷达图
            col_bars, col_radar = st.columns([1, 1])
            with col_bars:
                st.markdown("##### 各维度得分")
                score_bar("法律可行性", legal_score, COLORS["primary"], "权利 × 侵权 × 程序 × 对抗修正")
                score_bar("业务预期", business_score, COLORS["warning"], "要钱/要名自适应加权")
                score_bar("证据就绪度", evidence_score, COLORS["success"], "证据完整性与补证")
                st.markdown(f"**乘法模型**: {legal_score} × {business_score} × {evidence_score} = **{final_score}**")
                st.caption(f"对抗修正系数: {correction_coeff:.2f} · 一票否决逻辑")

            with col_radar:
                st.markdown("##### 三维雷达图")
                radar_html = render_radar_html({
                    "法律可行性": legal_score,
                    "业务预期": business_score,
                    "证据就绪度": evidence_score
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

            # 保存
            db.add(ScoreSnapshot(case_id=case_id, legal_score=legal_score, business_score=business_score,
                evidence_score=evidence_score, confidence_score=70, final_score=final_score, recommendation=rec['recommendation']))
            for k, v in [("rights", rights_result), ("infringement", infringement_result), ("procedure", procedure_result),
                          ("moot", moot_result), ("financial", financial_result), ("precedent", precedent_result), ("evidence", evidence_result)]:
                st.session_state[f"{k}_{case_id}"] = v
            db.commit()

            progress.progress(99, "生成报告...")
            report_md = generate_markdown_report(
                {"name": case.name, "cause_type": case.cause_type, "goal_type": case.goal_type, "client_org": case.client_org},
                {"legal_feasibility": legal_score, "business_expectation": business_score, "evidence_readiness": evidence_score,
                 "final_score": final_score, "recommendation": rec['recommendation'], "confidence_score": 70, "reason": rec['reason'], "action_items": []},
                procedure_result.get('items', []),
                {"elements": [
                    {"element":"权利基础","score":rights_result.get('score',0),"analysis":rights_result.get('analysis',''),"evidence_status":"-","risks":rights_result.get('risks',[])},
                    {"element":"侵权认定","score":infringement_result.get('score',0),"analysis":infringement_result.get('analysis',''),"evidence_status":"-","risks":infringement_result.get('risks',[])},
                    {"element":"诉讼程序","score":procedure_result.get('score',0),"analysis":procedure_result.get('analysis',''),"evidence_status":"-","risks":procedure_result.get('block_items',[])},
                ]})

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
            st.success("三维评估全部完成！请前往「评估报告」查看下载")
            st.info("北大法宝检索计划已生成。回复'帮我检索案件 [ID]'让 AI 助手完成法律数据库查询。")
            st.balloons()

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

            # 争议焦点
            focus_points = moot_result.get('focus_points', [])
            if focus_points:
                st.markdown(f"""
                <div class="card" style="border-left:4px solid {COLORS['accent']};">
                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">争议焦点</div>
                    {"".join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">{i+1}. {fp}</div>' for i, fp in enumerate(focus_points))}
                </div>
                """, unsafe_allow_html=True)

            # 庭审对话
            st.markdown("")
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
