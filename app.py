"""
Soft IP 主诉评估系统 - Streamlit 主程序
MVP 版本：商标侵权案件评估
"""

import streamlit as st
import sys
import os
import math
import base64
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.append(str(Path(__file__).parent))

from config import APP_TITLE, APP_VERSION, USE_MOCK
from database import init_db, SessionLocal, Case, RuleHit, ScoreSnapshot, Report
from evidence_parser import parse_pdf, ocr_image, is_pdf_file, is_image_file
from report_generator import generate_markdown_report, generate_pdf_bytes

# 评估引擎（按 v1 方案的选择）
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

# 页面配置
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化数据库
@st.cache_resource
def _init_db():
    init_db()
    return True

_init_db()

# ============================================================
# 工具函数：三维雷达图（纯SVG，无需额外依赖）
# ============================================================

def render_radar_svg(scores: dict, size: int = 340) -> str:
    """
    用 SVG 绘制三维评分雷达图
    scores: {"法律可行性": 0-100, "业务预期": 0-100, "证据就绪度": 0-100}
    """
    labels = ["法律可行性", "业务预期", "证据就绪度"]
    values = [scores.get(k, 0) for k in labels]

    cx, cy, r = size // 2, size // 2, size // 2 - 50
    angles = [math.radians(90), math.radians(210), math.radians(330)]

    # 计算点的坐标
    def point(angle, dist_ratio):
        x = cx + r * dist_ratio * math.cos(angle)
        y = cy - r * dist_ratio * math.sin(angle)
        return x, y

    # 背景网格（3层同心圈）
    grid_paths = ""
    for level in [0.33, 0.67, 1.0]:
        pts = [point(a, level) for a in angles]
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        grid_paths += f'<polygon points="{pts_str}" fill="none" stroke="#e0e0e0" stroke-width="1"/>\n'

    # 轴线
    axis_lines = ""
    for a in angles:
        x, y = point(a, 1.0)
        axis_lines += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e0e0e0" stroke-width="1"/>\n'

    # 标签
    label_texts = ""
    label_offsets = [(0, -15), (-10, 12), (10, 12)]
    for i, (a, lb) in enumerate(zip(angles, labels)):
        x, y = point(a, 1.15)
        ox, oy = label_offsets[i]
        label_texts += f'<text x="{x + ox:.1f}" y="{y + oy:.1f}" text-anchor="middle" font-size="13" fill="#333">{lb}</text>\n'

    # 得分多边形
    data_pts = [point(a, v / 100.0) for a, v in zip(angles, values)]
    data_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)

    # 得分点
    dots = ""
    for x, y in data_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2c7be5"/>\n'

    # 得分标签
    score_texts = ""
    for i, (a, v) in enumerate(zip(angles, values)):
        x, y = point(a, v / 100.0 + 0.08)
        score_texts += f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="16" font-weight="bold" fill="#2c7be5">{v}分</text>\n'

    svg = f'''<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
<rect width="{size}" height="{size}" fill="white" rx="12"/>
{grid_paths}
{axis_lines}
{label_texts}
<polygon points="{data_str}" fill="#2c7be5" fill-opacity="0.15" stroke="#2c7be5" stroke-width="2.5"/>
{dots}
{score_texts}
</svg>'''
    return svg

def render_radar_html(scores: dict, size: int = 340) -> str:
    """
    生成包含雷达图的 HTML（SVG → base64，确保 Streamlit 能渲染）
    """
    svg = render_radar_svg(scores, size)
    b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;max-width:{size}px;"/>'

def render_score_bar(label, score, color):
    """渲染单个评分条"""
    return f'''
    <div style="margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span style="font-size:14px;color:#444;">{label}</span>
        <span style="font-size:14px;font-weight:bold;color:{color};">{score} 分</span>
      </div>
      <div style="height:8px;background:#e8ecf1;border-radius:4px;overflow:hidden;">
        <div style="height:100%;width:{score}%;background:{color};border-radius:4px;transition:width 0.5s;"></div>
      </div>
    </div>
    '''
    """渲染单个评分条"""
    return f'''
    <div style="margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span style="font-size:14px;color:#444;">{label}</span>
        <span style="font-size:14px;font-weight:bold;color:{color};">{score} 分</span>
      </div>
      <div style="height:8px;background:#e8ecf1;border-radius:4px;overflow:hidden;">
        <div style="height:100%;width:{score}%;background:{color};border-radius:4px;transition:width 0.5s;"></div>
      </div>
    </div>
    '''

# ============================================================
# 侧边栏导航（使用 nav_target 间接跳转，避免修改 widget 绑定的 key）
# ============================================================

st.sidebar.title("⚖️ Soft IP 评估系统")
st.sidebar.caption(f"版本: {APP_VERSION}")

page_options = ["📝 新建案件", "📊 案件列表", "🔍 评估分析", "⚖️ 模拟法庭", "📄 评估报告", "ℹ️ 关于"]

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "📝 新建案件"

# 如果存在跳转目标，先更新 nav_page 再触发 rerun（必须在任何 widget 渲染前执行）
if st.session_state.get("nav_target"):
    target = st.session_state.pop("nav_target")
    if target in page_options:
        st.session_state.nav_page = target
    st.rerun()

st.sidebar.divider()
page = st.sidebar.radio("导航", page_options, key="nav_page")

st.sidebar.divider()
st.sidebar.caption(f"运行模式: {'Mock 模拟' if USE_MOCK else 'Production'}")
st.sidebar.caption("© 2026 Soft IP Evaluation")

# ============================================================
# 页面 1: 新建案件
# ============================================================
if page == "📝 新建案件":
    st.markdown("<h1 style='color:#1a1a1a;font-size:2rem;font-weight:bold;'>📝 新建商标侵权案件</h1>", unsafe_allow_html=True)
    st.caption("上传证据文件 + 填写案情描述，开始诉前评估")

    # ── 文件上传区（form 外部，自动解析）──
    st.markdown("### 📎 上传证据文件")
    uploaded_files = st.file_uploader(
        "支持 PDF（自动提取文本）和图片（OCR识别文字）",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="evidence_uploader",
        help="上传商标注册证、侵权截图、公证文书等证据文件"
    )

    parsed_evidences = []
    if uploaded_files:
        for f in uploaded_files:
            # 避免重复解析同一个文件
            cache_key = f"parsed_{f.name}_{f.size}"
            if cache_key not in st.session_state:
                with st.spinner(f"🔍 正在解析 {f.name} ..."):
                    file_bytes = f.getvalue()
                    if is_pdf_file(f.name):
                        result = parse_pdf(file_bytes, f.name)
                    elif is_image_file(f.name):
                        result = ocr_image(file_bytes, f.name)
                    else:
                        result = {"success": False, "text": "", "error": "不支持的文件格式"}

                    # 截取前 3000 字
                    if result["success"] and len(result["text"]) > 3000:
                        result["text"] = result["text"][:3000] + "\n\n... (文本过长，已截取)"

                    st.session_state[cache_key] = result

            parsed = st.session_state[cache_key]
            parsed_evidences.append((f.name, f.size, parsed))

    # 展示解析结果
    if parsed_evidences:
        st.markdown("**解析结果：**")
        for fname, fsize, result in parsed_evidences:
            icon = "✅" if result["success"] else "❌"
            if result["success"]:
                text_len = len(result["text"])
                with st.expander(f"{icon} {fname} ({text_len} 字)"):
                    st.text_area(
                        f"内容 - {fname}",
                        value=result["text"],
                        height=200,
                        key=f"preview_{fname}",
                        label_visibility="collapsed"
                    )
                    col_btn1, col_btn2 = st.columns([1, 3])
                    with col_btn1:
                        if st.button(f"📋 追加到案情", key=f"append_{hash(fname)}", use_container_width=True):
                            current_extra = st.session_state.get("evidence_text_extra", "")
                            st.session_state["evidence_text_extra"] = current_extra + f"\n\n【证据文件: {fname}】\n{result['text']}"
                            st.rerun()
            else:
                st.warning(f"{icon} {fname}: {result['error']}")

        st.divider()

    # 补充文本（来自追加按钮）
    evidence_extra = st.session_state.get("evidence_text_extra", "")
    if evidence_extra:
        st.success(f"📋 已追加 {len(evidence_extra)} 字证据文本到案情描述")
        if st.button("🗑️ 清除已追加的证据文本", type="secondary"):
            st.session_state["evidence_text_extra"] = ""
            st.rerun()

    # ── 表单 ──
    default_desc = st.session_state.get("last_case_desc", "")

    with st.form("new_case_form"):
        col1, col2 = st.columns(2)
        with col1:
            case_name = st.text_input("案件名称 *", placeholder="例如：某品牌诉某电商商标侵权案")
            cause_type = st.selectbox("案由", ["商标侵权", "著作权侵权", "不正当竞争"], disabled=True)
            goal_type = st.radio("业务目标", ["要钱", "要名"], horizontal=True)
        with col2:
            client_org = st.text_input("委托客户", placeholder="例如：某知名品牌公司")
            # 预设值为用户手动输入 + 追加的证据文本
            prefill = (evidence_extra + "\n\n" + default_desc).strip()
            case_description = st.text_area(
                "案情描述 *", height=300,
                value=prefill,
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
                    st.session_state["nav_target"] = "🔍 评估分析"
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")
                    db.rollback()
                finally:
                    db.close()

# ============================================================
# 页面 2: 案件列表
# ============================================================
elif page == "📊 案件列表":
    st.markdown("<h1 style='color:#1a1a1a;font-size:2rem;font-weight:bold;'>📊 案件列表</h1>", unsafe_allow_html=True)

    db = SessionLocal()
    try:
        cases = db.query(Case).order_by(Case.created_at.desc()).all()
        if not cases:
            st.info("暂无案件，请先创建案件")
        else:
            for c in cases:
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.markdown(f"**{c.name}**")
                    st.caption(f"ID: {c.id} | {c.cause_type} | {c.goal_type}")
                with c2:
                    sc = {"draft":"🟡 草稿","evaluating":"🔵 评估中","completed":"🟢 已完成"}.get(c.status, "⚪")
                    st.caption(sc)
                with c3:
                    if st.button("🔍 查看", key=f"v_{c.id}", use_container_width=True):
                        st.session_state["current_case_id"] = c.id
                        st.session_state["current_case_name"] = c.name
                        st.session_state["nav_target"] = "🔍 评估分析"
                        st.rerun()
                st.divider()
    finally:
        db.close()

# ============================================================
# 页面 3: 评估分析
# ============================================================
elif page == "🔍 评估分析":
    st.markdown("<h1 style='color:#1a1a1a;font-size:2rem;font-weight:bold;'>🔍 诉前评估分析</h1>", unsafe_allow_html=True)

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

        st.markdown(f"**当前案件:** {case_name}  &nbsp;|&nbsp;  ID: {case_id}  &nbsp;|&nbsp;  案由: {case.cause_type}")

        with st.expander("📋 案情描述", expanded=False):
            st.text_area("", case.case_description, height=200, disabled=True, label_visibility="collapsed")

        # 如果已完成 → 显示历史结果并允许重新评估
        if case.status == "completed":
            latest = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
            if latest:
                st.divider()
                st.markdown("### 📊 历史评估结果")
                c1, c2, c3 = st.columns(3)
                c1.metric("综合得分", f"{latest.final_score} 分")
                c2.metric("置信度", f"{latest.confidence_score}%")
                c3.metric("建议", latest.recommendation)
            st.divider()

        # 评估按钮
        eval_col1, eval_col2, eval_col3 = st.columns([1, 2, 1])
        with eval_col2:
            do_eval = st.button("🚀 开始评估", type="primary", use_container_width=True)

        if do_eval:
            progress = st.progress(0, "初始化...")
            status_area = st.container()

            with status_area:
                evidence_texts = st.session_state.get("evidence_text_extra", "")

                # ── UI Helper ──
                def dim_card(title, score, analysis, sub_items=None, extra=None, color="#2c7be5"):
                    """渲染一个子维度评估结果卡片"""
                    bar_color = "#2ecc71" if score >= 60 else "#f39c12" if score >= 40 else "#e74c3c"
                    st.markdown(f"""
                    <div style="border:1px solid #e0e0e0;border-radius:10px;padding:20px 24px;margin:8px 0 16px 0;
                                border-left:4px solid {bar_color};background:#fff;">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <span style="font-size:1.1rem;font-weight:600;color:#1a1a1a;">{title}</span>
                        <span style="font-size:1.8rem;font-weight:bold;color:{bar_color};">{score}<span style="font-size:0.9rem;color:#999;"> 分</span></span>
                      </div>
                      <div style="background:#f0f0f0;border-radius:6px;height:6px;overflow:hidden;margin-bottom:10px;">
                        <div style="height:100%;width:{score}%;background:{bar_color};border-radius:6px;"></div>
                      </div>
                      <div style="font-size:0.9rem;color:#555;line-height:1.6;">{analysis[:300]}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if sub_items or extra:
                        with st.expander("📋 详细分析", expanded=False):
                            if sub_items:
                                for si in sub_items:
                                    ic = {"pass":"✅","warning":"⚠️","block":"🚫","满足":"✅","存疑":"⚠️","不满足":"❌","充足":"✅","不足":"⚠️","缺失":"❌"}.get(si.get('status',''), '⚪')
                                    sub_s = si.get('score', None)
                                    score_str = f" **({sub_s}分)**" if sub_s is not None else ""
                                    st.markdown(f"{ic} **{si.get('name', si.get('requirement', ''))}**{score_str}: {si.get('detail', si.get('analysis', ''))}")
                            if extra:
                                st.caption(extra)

                # ============================================================================
                # 维度一：法律可行性
                # ============================================================================
                st.markdown("""<div style="background:linear-gradient(135deg,#eef2ff 0%,#f0f4ff 100%);
                            border-radius:12px;padding:18px 24px;margin:0 0 16px 0;">
                            <span style="font-size:1.4rem;font-weight:bold;color:#1e3a5f;">🔍 维度一：法律可行性</span>
                            <span style="color:#666;margin-left:12px;">回答“能不能诉”</span></div>""", unsafe_allow_html=True)

                # 1.1 权利基础
                progress.progress(8, "1/7 权利基础评估...")
                with st.spinner("DeepSeek 正在分析商标权利基础（有效性、撤三风险、覆盖范围、驰名地位）..."):
                    rights_result = evaluate_rights_foundation(case.case_description, uploaded_texts=evidence_texts if not _mock else "")
                if "error" in rights_result:
                    st.error(f"权利基础评估失败: {rights_result.get('error', rights_result.get('raw',''))}")
                else:
                    sub_scores = []
                    for k, v in rights_result.get('sub_scores', {}).items():
                        label = {"validity":"商标有效性","usage_continuity":"连续使用","coverage":"覆盖范围","well_known_status":"驰名地位","risk_of_invalidation":"无效风险"}.get(k, k)
                        sub_scores.append({"name": label, "score": v, "status": "pass" if v >= 60 else "warning"})
                    dim_card("1.1 权利基础评估", rights_result.get('score', 0),
                             rights_result.get('analysis', ''),
                             sub_items=sub_scores,
                             extra="优势: " + ", ".join(rights_result.get('strengths', ['-'])) + "\n\n风险: " + ", ".join(rights_result.get('risks', ['-'])))

                # ── 北大法宝：权利基础法条检索 ──
                with st.expander("📚 北大法宝 · 法条检索（验证权利基础）", expanded=False):
                    st.caption("检索商标法核心法条 + 驰名商标认定规定")
                    pkulaw_rights = get_dimension_results(case_id, "1.1_权利基础")
                    if pkulaw_rights:
                        for law in pkulaw_rights.get("laws", [])[:3]:
                            st.markdown(f"**{law.get('title', law.get('name',''))}**")
                            st.caption(law.get('content', law.get('text',''))[:300])
                    else:
                        st.info("⚠️ 尚未检索。评估完成后，让 AI 助手通过北大法宝检索验证。")

                # 1.2 侵权认定
                progress.progress(22, "2/7 侵权认定评估...")
                with st.spinner("DeepSeek 正在分析商标侵权五要件（商标性使用、商品类似性、近似性、混淆可能性、正当使用）..."):
                    infringement_result = evaluate_infringement(case.case_description,
                        rights_assessment=str(rights_result.get('analysis', '')),
                        uploaded_texts=evidence_texts if not _mock else "")
                if "error" in infringement_result:
                    st.error(f"侵权认定失败: {infringement_result.get('error', infringement_result.get('raw',''))}")
                else:
                    el_items = []
                    for el in infringement_result.get('elements', []):
                        el_items.append({"name": el['name'], "score": el['score'], "status": el.get('status','pass'), "detail": el.get('analysis','')})
                    dim_card("1.2 侵权认定评估", infringement_result.get('score', 0),
                             infringement_result.get('analysis', ''),
                             sub_items=el_items)

                # ── 北大法宝：侵权认定类案检索 ──
                with st.expander("📚 北大法宝 · 类案检索（验证侵权认定标准）", expanded=False):
                    st.caption("检索近似商标/混淆可能性类案判决")
                    pkulaw_inf = get_dimension_results(case_id, "1.2_侵权认定")
                    if pkulaw_inf:
                        for c in pkulaw_inf.get("cases", [])[:3]:
                            st.markdown(f"**{c.get('title', c.get('name',''))}**")
                            st.caption(f"{c.get('court','')} | {c.get('date','')}")
                    else:
                        st.info("⚠️ 尚未检索。评估完成后，让 AI 助手通过北大法宝检索验证。")

                # 1.3 诉讼程序
                progress.progress(36, "3/7 程序审查...")
                with st.spinner("DeepSeek 正在审查诉讼时效、管辖仲裁、主体适格、前置程序..."):
                    procedure_result = evaluate_procedure(case.case_description)
                if "error" in procedure_result:
                    st.error(f"程序审查失败: {procedure_result.get('error', procedure_result.get('raw',''))}")
                else:
                    proc_items = [{"name": p['name'], "status": p.get('status','pass'), "detail": p.get('detail','')} for p in procedure_result.get('items', [])]
                    dim_card("1.3 诉讼程序审查", procedure_result.get('score', 0),
                             procedure_result.get('analysis', ''),
                             sub_items=proc_items)

                # ── 北大法宝：程序法条检索 ──
                with st.expander("📚 北大法宝 · 法条检索（验证诉讼程序依据）", expanded=False):
                    st.caption("检索诉讼时效、管辖、主体适格相关法条")
                    pkulaw_proc = get_dimension_results(case_id, "1.3_诉讼程序")
                    if pkulaw_proc:
                        for law in pkulaw_proc.get("laws", [])[:3]:
                            st.markdown(f"**{law.get('title', law.get('name',''))}**")
                            st.caption(law.get('content', law.get('text',''))[:300])
                    else:
                        st.info("⚠️ 尚未检索。评估完成后，让 AI 助手通过北大法宝检索验证。")

                # 1.4 模拟法庭（多Agent五步庭审）
                progress.progress(50, "4/7 模拟法庭对抗检验...")
                st.markdown("""<div style="background:linear-gradient(135deg,#fdebd0 0%,#fdf2e9 100%);
                            border-radius:10px;padding:14px 20px;margin:16px 0 12px 0;border-left:4px solid #e67e22;">
                            <span style="font-size:1.1rem;font-weight:bold;color:#7e5109;">⚖️ 1.4 模拟法庭（多Agent对抗检验）</span>
                            <span style="color:#888;margin-left:8px;font-size:0.85rem;">原告Agent ↔ 被告Agent ↔ 法官Agent</span></div>""", unsafe_allow_html=True)

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

                    # 修正系数 + 抗辩强度概览
                    coeff_color = "#e74c3c" if correction_coeff < 0.9 else "#f39c12" if correction_coeff < 1.0 else "#2ecc71"
                    st.markdown(f"""<div style="display:flex;gap:16px;margin:12px 0;">
                        <div style="flex:1;background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px;text-align:center;">
                            <div style="font-size:0.8rem;color:#999;">对抗修正系数</div>
                            <div style="font-size:2rem;font-weight:bold;color:{coeff_color};">{correction_coeff:.2f}</div>
                            <div style="font-size:0.75rem;color:#999;">{'被告抗辩有效削弱原告论证' if correction_coeff < 1.0 else '原告论证在对抗中成立'}</div>
                        </div>
                        <div style="flex:1;background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px;text-align:center;">
                            <div style="font-size:0.8rem;color:#999;">被告抗辩强度</div>
                            <div style="font-size:2rem;font-weight:bold;color:#e67e22;">{defense_strength}<span style="font-size:1rem;color:#999;">/100</span></div>
                            <div style="font-size:0.75rem;color:#999;">{'抗辩有力' if defense_strength >= 60 else '抗辩一般' if defense_strength >= 40 else '抗辩薄弱'}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                    # 庭审对话记录（可展开）
                    rounds = moot_result.get('rounds', [])
                    if rounds:
                        with st.expander(f"📜 庭审记录（共{len(rounds)}轮发言）", expanded=False):
                            for rnd in rounds:
                                role = rnd.get('role', rnd.get('speaker', ''))
                                role_name = rnd.get('role_name', role)
                                step_name = rnd.get('step_name', '')
                                content = rnd.get('content', '')

                                # 角色颜色
                                if 'plaintiff' in str(role) or '原告' in str(role_name):
                                    color = "#2c7be5"
                                    icon = "🔵"
                                elif 'defendant' in str(role) or '被告' in str(role_name):
                                    color = "#e74c3c"
                                    icon = "🔴"
                                else:
                                    color = "#8e44ad"
                                    icon = "⚖️"

                                st.markdown(f"""<div style="border-left:3px solid {color};padding:8px 16px;margin:8px 0;background:#f8f9fa;border-radius:0 6px 6px 0;">
                                    <div style="font-weight:bold;color:{color};font-size:0.9rem;">{icon} {role_name}
                                    <span style="color:#999;font-weight:normal;font-size:0.8rem;margin-left:8px;">{step_name}</span></div>
                                    <div style="font-size:0.85rem;color:#444;margin-top:6px;line-height:1.6;white-space:pre-wrap;">{content[:800]}{'...' if len(content)>800 else ''}</div>
                                </div>""", unsafe_allow_html=True)

                    # 法官评分（如有）
                    judge_scores = moot_result.get('judge_scores', {})
                    if judge_scores and judge_scores.get('plaintiff'):
                        with st.expander("📊 法官评分明细", expanded=False):
                            p_scores = judge_scores.get('plaintiff', {})
                            d_scores = judge_scores.get('defendant', {})
                            p_detail = judge_scores.get('plaintiff_detail', {})
                            d_detail = judge_scores.get('defendant_detail', {})

                            col_p, col_d = st.columns(2)
                            with col_p:
                                st.markdown("**🔵 原告论证强度**")
                                label_map = {
                                    "rights": "权利基础", "infringement": "侵权认定",
                                    "evidence": "证据体系", "legal_application": "法律适用",
                                    "claim_reasonableness": "诉求合理性"
                                }
                                for k, v in p_scores.items():
                                    label = label_map.get(k, k)
                                    detail = p_detail.get(k, "")
                                    st.markdown(f"• **{label}**: {v} 分 — {detail}" if detail else f"• **{label}**: {v} 分")

                            with col_d:
                                st.markdown("**🔴 被告抗辩强度**")
                                d_label_map = {
                                    "fact_defense": "事实抗辩", "legal_defense": "法律抗辩",
                                    "evidence_challenge": "证据质疑", "alternative_explanation": "替代解释",
                                    "procedural_defense": "程序抗辩"
                                }
                                for k, v in d_scores.items():
                                    label = d_label_map.get(k, k)
                                    detail = d_detail.get(k, "")
                                    st.markdown(f"• **{label}**: {v} 分 — {detail}" if detail else f"• **{label}**: {v} 分")

                            reasoning = judge_scores.get('coefficient_reasoning', '')
                            if reasoning:
                                st.info(f"📝 **修正系数推理**: {reasoning}")

                    # 薄弱环节
                    weak_points = moot_result.get('weak_points', [])
                    if weak_points:
                        st.markdown("**⚠️ 对抗暴露的薄弱环节:**")
                        for wp in weak_points:
                            st.markdown(f"- {wp}")

                    # 提示可前往独立页面查看完整记录
                    st.caption("💡 前往「模拟法庭」页面可查看完整庭审记录和交互式回放")

                # ── 维度一小计 ──
                legal_score = calculate_legal_feasibility(
                    rights_result.get('score', 0), infringement_result.get('score', 0),
                    procedure_result.get('score', 0), correction_coeff
                )
                st.success(f"✅ **维度一法律可行性综合得分: {legal_score} 分**  ")
                st.caption(f"公式: 权利基础({rights_result.get('score',0)}) × 侵权认定({infringement_result.get('score',0)}) × 诉讼程序({procedure_result.get('score',0)}) × 对抗修正({correction_coeff:.2f}) = {legal_score}")

                # ============================================================================
                # 维度二：业务预期
                # ============================================================================
                st.markdown(f"""<div style="background:linear-gradient(135deg,#fef9e7 0%,#fef7e0 100%);
                            border-radius:12px;padding:18px 24px;margin:24px 0 16px 0;">
                            <span style="font-size:1.4rem;font-weight:bold;color:#7d6608;">💰 维度二：业务预期</span>
                            <span style="color:#666;margin-left:12px;">目标：{case.goal_type} &nbsp;|&nbsp; 回答“值不值得诉”</span></div>""", unsafe_allow_html=True)

                # 2.1 财务回报
                progress.progress(64, "5/7 财务回报评估...")
                with st.spinner("DeepSeek 正在预测判赔区间、诉讼成本和净收益..."):
                    financial_result = evaluate_financial_return(case.case_description)
                if "error" in financial_result:
                    st.warning(f"财务评估异常: {financial_result.get('error', financial_result.get('raw',''))[:200]}")
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
                    dim_card("2.1 财务回报评估", fin_score, financial_result.get('analysis', ''),
                             extra="\n".join(fin_extra))
                    st.caption("💡 评估完成后可让 AI 助手通过北大法宝检索同类判赔数据以校准预测")

                # 2.2 判例价值
                progress.progress(78, "6/7 判例价值评估...")
                with st.spinner("DeepSeek 正在评估首案潜力、指导性案例入选概率..."):
                    precedent_result = evaluate_precedent_value(case.case_description)
                if "error" in precedent_result:
                    st.warning(f"判例价值异常: {precedent_result.get('error', precedent_result.get('raw',''))[:200]}")
                    prec_score = 50
                else:
                    prec_score = precedent_result.get('score', 50)
                    dim_card("2.2 判例价值评估", prec_score, precedent_result.get('analysis', ''),
                             extra=f"首案指数: {precedent_result.get('first_case_index','-')} | 影响力级别: {precedent_result.get('influence_level','-')}")

                # ── 北大法宝：判例价值类案检索（主力引擎）──
                with st.expander("📚 北大法宝 · 首案检索（判例价值主力引擎）", expanded=True):
                    st.caption("检索同类在先判决，判断首案潜力 + 指导性案例入选概率")
                    pkulaw_prec = get_dimension_results(case_id, "2.2_判例价值")
                    if pkulaw_prec:
                        for c in pkulaw_prec.get("cases", [])[:5]:
                            st.markdown(f"**{c.get('title', c.get('name',''))}**")
                            st.caption(f"{c.get('court','')} | {c.get('date','')} | {c.get('summary','')[:150] if c.get('summary') else ''}")
                    else:
                        st.info("⚠️ 尚未检索。评估完成后，让 AI 助手通过北大法宝检索同类在先判决。")

                # ── 维度二小计 ──
                business_score = calculate_business_expectation(fin_score, prec_score, case.goal_type)
                st.success(f"✅ **维度二业务预期综合得分: {business_score} 分**  ")
                if case.goal_type == "要钱":
                    st.caption(f"公式: 0.9×财务({fin_score}) + 0.1×判例({prec_score}) = {business_score}")
                else:
                    st.caption(f"公式: 0.1×财务({fin_score}) + 0.9×判例({prec_score}) = {business_score}")

                # ============================================================================
                # 维度三：证据就绪度
                # ============================================================================
                st.markdown("""<div style="background:linear-gradient(135deg,#e8f8f5 0%,#e6f8f4 100%);
                            border-radius:12px;padding:18px 24px;margin:24px 0 16px 0;">
                            <span style="font-size:1.4rem;font-weight:bold;color:#0e6251;">📋 维度三：证据就绪度</span>
                            <span style="color:#666;margin-left:12px;">回答“现在能不能诉”</span></div>""", unsafe_allow_html=True)

                progress.progress(92, "7/7 证据就绪度评估...")
                with st.spinner("DeepSeek 正在逐项核验证据完整性..."):
                    evidence_result = evaluate_evidence_readiness(case.case_description,
                        uploaded_evidence_texts=evidence_texts, evidence_count=0)
                if "error" in evidence_result:
                    st.warning(f"证据评估异常: {evidence_result.get('error', evidence_result.get('raw',''))[:200]}")
                    evidence_score = 60
                else:
                    evidence_score = evidence_result.get('score', 60)
                    ev_items = [{"name": m['requirement'], "status": m.get('status','不足'), "detail": m.get('analysis','')} for m in evidence_result.get('evidence_matrix', [])]
                    dim_card("证据就绪度评估", evidence_score, evidence_result.get('analysis', ''),
                             sub_items=ev_items,
                             extra="补证建议: " + ("; ".join(evidence_result.get('remediation_suggestions', ['无']))) + "\n\n取证技术建议: " + evidence_result.get('collection_advice', '根据证据类型自行判断'))

                st.success(f"✅ **维度三证据就绪度得分: {evidence_score} 分**")

                # ============================================================================
                # 三维综合评分
                # ============================================================================
                st.markdown("---")
                progress.progress(97, "计算综合评分...")

                final_score = calculate_overall_score(legal_score, business_score, evidence_score)
                rec = generate_recommendation(final_score, procedure_result.get('items', []))
                rec_color = {"green":"#2ecc71","yellow":"#f39c12","red":"#e74c3c","block":"#e74c3c"}.get(rec['level'], "#2ecc71")

                st.markdown(f"""<div style="background:linear-gradient(135deg,{rec_color}15 0%,{rec_color}05 100%);
                            border:2px solid {rec_color}40;border-radius:16px;padding:28px 32px;margin:16px 0;text-align:center;">
                  <div style="font-size:0.9rem;color:#999;margin-bottom:4px;">三维综合评分</div>
                  <div style="font-size:4rem;font-weight:bold;color:{rec_color};">{final_score}<span style="font-size:1.2rem;color:#999;"> / 100</span></div>
                  <div style="font-size:1.3rem;font-weight:bold;color:{rec_color};margin-top:12px;">{rec['recommendation']}</div>
                  <div style="font-size:0.95rem;color:#555;margin-top:8px;">{rec['reason']}</div>
                </div>""", unsafe_allow_html=True)

                # 三维评分条 + 雷达图
                col_bars, col_radar = st.columns([1, 1])
                with col_bars:
                    st.markdown("##### 📊 各维度得分")
                    for label, val, w, c in [
                        ("法律可行性", legal_score, "权利×侵权×程序×对抗", "#2c7be5"),
                        ("业务预期", business_score, "要钱/要名自适应加权", "#f39c12"),
                        ("证据就绪度", evidence_score, "证据完整性与补证", "#0e6251"),
                    ]:
                        st.markdown(f"""
                        <div style="margin-bottom:16px;">
                          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <span style="font-size:0.95rem;color:#444;">{label}</span>
                            <span style="font-size:1.2rem;font-weight:bold;color:{c};">{val} 分</span>
                          </div>
                          <div style="height:10px;background:#e8ecf1;border-radius:5px;overflow:hidden;">
                            <div style="height:100%;width:{val}%;background:{c};border-radius:5px;"></div>
                          </div>
                          <div style="font-size:0.75rem;color:#999;margin-top:2px;">{w}</div>
                        </div>""", unsafe_allow_html=True)

                    st.markdown(f"**计算公式**: {legal_score} × {business_score} × {evidence_score} = **{final_score}**")
                    st.caption(f"评分方法: 乘法模型（一票否决逻辑），对抗修正系数: {correction_coeff:.2f}")

                with col_radar:
                    radar_html = render_radar_html({
                        "法律可行性": legal_score,
                        "业务预期": business_score,
                        "证据就绪度": evidence_score
                    })
                    st.markdown(radar_html, unsafe_allow_html=True)

                # ── 北大法宝：法条与案号验证 ──
                st.markdown("---")
                with st.expander("🔍 北大法宝 · 法条与案号验证（防止 AI 生成虚假法条/案件）", expanded=False):
                    st.caption("运行 adjust_provisions / law_recognition / anhao_recognition 三大验证")
                    valid_status = get_validation_status(case_id)
                    col_v1, col_v2, col_v3 = st.columns(3)
                    with col_v1:
                        st.metric("法条验证", "✅ 通过" if valid_status["provisions_validated"] else "⏳ 待验证")
                    with col_v2:
                        st.metric("法规识别", "✅ 通过" if valid_status["laws_validated"] else "⏳ 待验证")
                    with col_v3:
                        st.metric("案号识别", "✅ 通过" if valid_status["cases_validated"] else "⏳ 待验证")
                    if not all([valid_status["provisions_validated"], valid_status["laws_validated"], valid_status["cases_validated"]]):
                        st.warning("⚠️ 评估完成后，请让 AI 助手运行北大法宝验证，确保法条和案号引用真实有效")

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

                # 生成北大法宝检索计划
                deepseek_results = {
                    "rights": rights_result, "infringement": infringement_result,
                    "procedure": procedure_result, "financial": financial_result,
                    "precedent": precedent_result, "evidence": evidence_result
                }
                generate_all_queries(case_id, case.case_description, deepseek_results)

                progress.progress(100, "评估完成！")
                st.success("🎉 三维评估全部完成！请前往「评估报告」查看下载")
                st.info("📚 北大法宝检索计划已生成。回复'帮我检索案件 [ID]'让 AI 助手完成法律数据库查询。")
                st.balloons()

    finally:
        db.close()

# ============================================================
# 页面: 模拟法庭（多Agent对抗式庭审）
# ============================================================
elif page == "⚖️ 模拟法庭":
    st.markdown("<h1 style='color:#1a1a1a;font-size:2rem;font-weight:bold;'>⚖️ 模拟法庭</h1>", unsafe_allow_html=True)
    st.caption("多Agent对抗式庭审模拟 — 原告Agent ↔ 被告Agent ↔ 法官Agent")

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

        st.markdown(f"**当前案件:** {case_name}  |  ID: {case_id}  |  案由: {case.cause_type}")
        st.caption(f"运行模式: {'Mock 模拟' if _mock else 'DeepSeek API'}")

        # 检查是否已有模拟法庭结果
        moot_key = f"moot_{case_id}"
        moot_result = st.session_state.get(moot_key)

        # ── 操作区 ──
        col_run, col_info = st.columns([1, 2])
        with col_run:
            if st.button("🚀 开始模拟法庭", type="primary", use_container_width=True):
                # 获取评估结果作为原告Agent的输入
                rights_key = f"rights_{case_id}"
                inf_key = f"infringement_{case_id}"
                rights_text = str(st.session_state.get(rights_key, {}).get('analysis', ''))
                inf_text = str(st.session_state.get(inf_key, {}).get('analysis', ''))
                evidence_texts = st.session_state.get("evidence_text_extra", "")

                progress = st.progress(0, "正在启动模拟法庭...")
                steps_labels = [
                    "开庭陈述（原告）",
                    "被告答辩",
                    "举证质证（原告→被告）",
                    "法庭辩论（原告→被告）",
                    "法官归纳"
                ]

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
                st.success(f"✅ 已完成模拟法庭 | 对抗修正系数: **{coeff:.2f}** | 被告抗辩强度: **{moot_result.get('defense_strength', 50)}/100**")
            else:
                st.info("点击上方按钮启动模拟法庭。需要先完成「评估分析」以获取权利基础和侵权认定结果。")

        st.divider()

        # ── 庭审记录展示 ──
        if moot_result and moot_result.get('rounds'):
            rounds = moot_result.get('rounds', [])

            # 三栏布局：左侧步骤导航 | 中央对话面板 | 右侧评分摘要
            col_nav, col_dialog, col_scores = st.columns([1, 3, 1])

            # ── 左侧：步骤导航 ──
            with col_nav:
                st.markdown("#### 庭审流程")
                step_groups = {}
                for r in rounds:
                    s = r.get('step', 0)
                    if s not in step_groups:
                        step_groups[s] = []
                    step_groups[s].append(r)

                step_icons = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}
                step_names_full = {
                    1: "开庭陈述",
                    2: "被告答辩",
                    3: "举证质证",
                    4: "法庭辩论",
                    5: "法官归纳"
                }

                for step_num in sorted(step_groups.keys()):
                    icon = step_icons.get(step_num, "  ")
                    name = step_names_full.get(step_num, "")
                    count = len(step_groups[step_num])
                    st.markdown(f"**{icon} {name}**")
                    st.caption(f"  {count} 轮发言 ✅")
                    if step_num < 5:
                        st.markdown("  ↓")

                st.divider()
                coeff = moot_result.get('correction_coefficient', 1.0)
                coeff_color = "#e74c3c" if coeff < 0.9 else "#f39c12" if coeff < 1.0 else "#2ecc71"
                st.markdown(f"""<div style="text-align:center;padding:12px;background:{coeff_color}15;border-radius:8px;">
                    <div style="font-size:0.75rem;color:#999;">修正系数</div>
                    <div style="font-size:1.8rem;font-weight:bold;color:{coeff_color};">{coeff:.2f}</div>
                </div>""", unsafe_allow_html=True)

            # ── 中央：对话面板 ──
            with col_dialog:
                st.markdown("#### 庭审记录")
                for rnd in rounds:
                    role = rnd.get('role', rnd.get('speaker', ''))
                    role_name = rnd.get('role_name', role)
                    step_name = rnd.get('step_name', '')
                    content = rnd.get('content', '')

                    # 角色颜色和图标
                    if 'plaintiff' in str(role) or '原告' in str(role_name):
                        color = "#2c7be5"
                        bg = "#ebf3fc"
                        icon = "🔵"
                        align = "left"
                    elif 'defendant' in str(role) or '被告' in str(role_name):
                        color = "#e74c3c"
                        bg = "#fdf0ef"
                        icon = "🔴"
                        align = "right"
                    else:
                        color = "#8e44ad"
                        bg = "#f5eef8"
                        icon = "⚖️"
                        align = "center"

                    if align == "right":
                        margin = "margin-left:15%;"
                    elif align == "center":
                        margin = "margin:0 8%;"
                    else:
                        margin = "margin-right:15%;"

                    st.markdown(f"""<div style="background:{bg};border:1px solid {color}30;border-radius:12px;
                        padding:16px 20px;margin:10px 0;{margin}">
                        <div style="font-weight:bold;color:{color};font-size:0.9rem;margin-bottom:8px;">
                            {icon} {role_name}
                            <span style="color:#aaa;font-weight:normal;font-size:0.78rem;margin-left:8px;">{step_name}</span>
                        </div>
                        <div style="font-size:0.85rem;color:#333;line-height:1.7;white-space:pre-wrap;">{content}</div>
                    </div>""", unsafe_allow_html=True)

            # ── 右侧：评分摘要 ──
            with col_scores:
                st.markdown("#### 法官评分")

                judge_scores = moot_result.get('judge_scores', {})
                if judge_scores and judge_scores.get('plaintiff'):
                    p_scores = judge_scores.get('plaintiff', {})
                    d_scores = judge_scores.get('defendant', {})

                    st.markdown("**🔵 原告**")
                    p_labels = {"rights": "权利基础", "infringement": "侵权认定",
                                "evidence": "证据体系", "legal_application": "法律适用",
                                "claim_reasonableness": "诉求合理"}
                    for k, v in p_scores.items():
                        bar_c = "#2ecc71" if v >= 70 else "#f39c12" if v >= 50 else "#e74c3c"
                        st.markdown(f"""<div style="margin-bottom:6px;">
                            <div style="font-size:0.75rem;color:#666;">{p_labels.get(k, k)}</div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <div style="flex:1;height:6px;background:#eee;border-radius:3px;overflow:hidden;">
                                    <div style="height:100%;width:{v}%;background:{bar_c};border-radius:3px;"></div>
                                </div>
                                <span style="font-size:0.75rem;font-weight:bold;color:{bar_c};">{v}</span>
                            </div>
                        </div>""", unsafe_allow_html=True)

                    st.markdown("---")
                    st.markdown("**🔴 被告**")
                    d_labels = {"fact_defense": "事实抗辩", "legal_defense": "法律抗辩",
                                "evidence_challenge": "证据质疑", "alternative_explanation": "替代解释",
                                "procedural_defense": "程序抗辩"}
                    for k, v in d_scores.items():
                        bar_c = "#2ecc71" if v >= 70 else "#f39c12" if v >= 50 else "#e74c3c"
                        st.markdown(f"""<div style="margin-bottom:6px;">
                            <div style="font-size:0.75rem;color:#666;">{d_labels.get(k, k)}</div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <div style="flex:1;height:6px;background:#eee;border-radius:3px;overflow:hidden;">
                                    <div style="height:100%;width:{v}%;background:{bar_c};border-radius:3px;"></div>
                                </div>
                                <span style="font-size:0.75rem;font-weight:bold;color:{bar_c};">{v}</span>
                            </div>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.caption("（评分数据不可用）")

                st.divider()
                st.markdown(f"**被告抗辩强度**")
                ds = moot_result.get('defense_strength', 50)
                st.markdown(f"<div style='font-size:2rem;font-weight:bold;color:#e67e22;'>{ds}<span style='font-size:0.9rem;color:#999;'>/100</span></div>", unsafe_allow_html=True)

                # 薄弱环节
                weak_points = moot_result.get('weak_points', [])
                if weak_points:
                    st.divider()
                    st.markdown("**⚠️ 薄弱环节**")
                    for wp in weak_points:
                        st.markdown(f"<div style='font-size:0.78rem;color:#666;margin-bottom:4px;'>• {wp}</div>", unsafe_allow_html=True)

                # 争议焦点
                focus_points = moot_result.get('focus_points', [])
                if focus_points:
                    st.divider()
                    st.markdown("**🎯 争议焦点**")
                    for i, fp in enumerate(focus_points, 1):
                        st.markdown(f"<div style='font-size:0.78rem;color:#666;margin-bottom:4px;'>{i}. {fp}</div>", unsafe_allow_html=True)

        elif moot_result and moot_result.get('error'):
            st.error(f"模拟法庭出错: {moot_result['error']}")

    finally:
        db.close()

# ============================================================
# 页面: 评估报告（含三维可视化 + 可下载总结文档）
# ============================================================
elif page == "📄 评估报告":
    st.markdown("<h1 style='color:#1a1a1a;font-size:2rem;font-weight:bold;'>📄 评估报告</h1>", unsafe_allow_html=True)

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

        # 获取最新评分
        score = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
        report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()

        if not score:
            st.warning("该案件尚未评估，请先进行评估")
            st.stop()

        # ── 顶部摘要 ──
        rec_color = {"建议起诉": "#2ecc71", "补证后再起诉": "#f39c12", "暂不建议起诉": "#e74c3c", "暂缓起诉": "#e74c3c"}
        color = rec_color.get(score.recommendation, "#333")

        st.markdown(f"""
        <div style="background:linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    border-radius:16px; padding:28px 32px; margin-bottom:20px;
                    border-left:6px solid {color};">
          <div style="font-size:0.9rem;color:#666;margin-bottom:4px;">{case.cause_type} · 评估报告</div>
          <div style="font-size:1.5rem;font-weight:bold;color:#1a1a1a;">{case.name}</div>
          <div style="margin-top:16px;display:flex;gap:40px;flex-wrap:wrap;">
            <div><span style="color:#999;">综合评分</span><br>
                 <span style="font-size:2.5rem;font-weight:bold;color:{color};">{score.final_score}</span>
                 <span style="color:#999;">/100</span></div>
            <div><span style="color:#999;">建议</span><br>
                 <span style="font-size:1.2rem;font-weight:bold;color:{color};">{score.recommendation}</span></div>
            <div><span style="color:#999;">置信度</span><br>
                 <span style="font-size:1.2rem;">{score.confidence_score}%</span></div>
            <div><span style="color:#999;">评估时间</span><br>
                 <span style="font-size:0.95rem;">{score.id}</span></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 三维雷达图（左侧）+ 分数条（右侧）──
        col_chart, col_bars = st.columns([1, 1])

        with col_chart:
            st.markdown("#### 📊 三维评分雷达图")
            radar_html = render_radar_html({
                "法律可行性": int(score.legal_score),
                "业务预期": int(score.business_score),
                "证据就绪度": int(score.evidence_score)
            }, size=340)
            st.markdown(radar_html, unsafe_allow_html=True)

        with col_bars:
            st.markdown("#### 📈 各维度得分详情")
            st.markdown(render_score_bar("法律可行性 (权重 45%)", int(score.legal_score), "#2c7be5"), unsafe_allow_html=True)
            st.markdown(render_score_bar("业务预期 (权重 25%)", int(score.business_score), "#00a186"), unsafe_allow_html=True)
            st.markdown(render_score_bar("证据就绪度 (权重 30%)", int(score.evidence_score), "#e67e22"), unsafe_allow_html=True)

            st.divider()
            st.markdown(f"**加权公式**: `0.45×法律 + 0.25×业务 + 0.30×证据`")
            st.markdown(f"**最终得分**: `{score.final_score}`")
            st.markdown(f"**置信度**: `{score.confidence_score}%`")

        # ── 完整报告 ──
        st.divider()
        st.markdown("### 📝 完整评估报告")
        if report:
            st.markdown(report.markdown_content)
        else:
            st.info("报告内容未保存")

        # ── 下载区域 ──
        st.divider()
        st.markdown("### 📥 下载总结文档")

        # 生成 HTML 总结报告
        radar_svg_str = render_radar_svg({
            "法律可行性": int(score.legal_score),
            "业务预期": int(score.business_score),
            "证据就绪度": int(score.evidence_score)
        })

        summary_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Soft IP 评估报告 - {case.name}</title>
<style>
body{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;max-width:800px;margin:0 auto;padding:40px;color:#333}}
h1{{color:#1a1a1a;border-bottom:3px solid {color};padding-bottom:12px}}
h2{{color:#2c3e50;margin-top:28px}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:8px 12px;text-align:left}}
th{{background:#f8f9fa}}
.score-big{{font-size:3rem;font-weight:bold;color:{color}}}
.rec{{font-size:1.3rem;font-weight:bold;color:{color};margin:8px 0}}
</style></head>
<body>
<h1>Soft IP 主诉评估报告</h1>
<p><strong>案件名称:</strong> {case.name} &nbsp;|&nbsp; <strong>案由:</strong> {case.cause_type} &nbsp;|&nbsp; <strong>评估日期:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>

<h2>一、结论摘要</h2>
<div class="score-big">{score.final_score} / 100</div>
<div class="rec">{score.recommendation}</div>

<h2>二、三维评分总览</h2>
<div style="text-align:center;margin:24px 0">{radar_svg_str}</div>
<table>
<tr><th>维度</th><th>得分</th><th>权重</th></tr>
<tr><td>法律可行性</td><td>{score.legal_score}/100</td><td>45%</td></tr>
<tr><td>业务预期</td><td>{score.business_score}/100</td><td>25%</td></tr>
<tr><td>证据就绪度</td><td>{score.evidence_score}/100</td><td>30%</td></tr>
<tr><td><strong>综合得分</strong></td><td><strong>{score.final_score}/100</strong></td><td></td></tr>
</table>

<h2>三、评估说明</h2>
<p>本评估基于用户提供的案情描述和证据材料，通过规则引擎和 AI 分析生成。评估覆盖法律可行性、业务预期、证据就绪度三个维度，采用加权评分模型。</p>
<p><strong>置信度:</strong> {score.confidence_score}%</p>

<h2>四、后续建议</h2>
<ol>
<li>根据红线和警告项补充关键证据</li>
<li>与法律顾问或外部律师讨论诉讼策略</li>
<li>持续监控侵权行为并收集更多证据</li>
</ol>

<p style="margin-top:40px;color:#999;font-size:0.85rem;">
<em>Generated by Soft IP 主诉评估系统 v{APP_VERSION} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</em>
</p>
<p style="color:#999;font-size:0.8rem;">免责声明: 本报告为 AI 辅助生成，仅供内部决策参考，不构成正式法律意见。</p>
</body></html>"""

        col_dl1, col_dl2, col_dl3 = st.columns(3)

        # 生成 PDF bytes
        pdf_bytes = None
        try:
            pdf_bytes = generate_pdf_bytes(report.markdown_content if report else summary_html)
        except Exception as e:
            st.caption(f"PDF 生成失败: {e}")

        with col_dl1:
            if pdf_bytes:
                st.download_button(
                    "📄 一键下载 PDF",
                    data=pdf_bytes,
                    file_name=f"{case_id}_评估报告.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
            else:
                st.download_button(
                    "📄 下载 HTML (可转PDF)",
                    data=summary_html.encode('utf-8'),
                    file_name=f"{case_id}_评估报告.html",
                    mime="text/html",
                    use_container_width=True,
                    type="primary",
                    help="HTML 格式报告"
                )

        with col_dl2:
            if report:
                st.download_button(
                    "📝 完整报告 (.md)",
                    data=report.markdown_content,
                    file_name=f"{case_id}_完整报告.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="Markdown 格式，包含详细评估分析"
                )

        with col_dl3:
            st.download_button(
                "🌐 总结文档 (.html)",
                data=summary_html,
                file_name=f"{case_id}_总结报告.html",
                mime="text/html",
                use_container_width=True,
                help="精美格式 HTML 报告，可在 Word/WPS 中打开编辑"
            )

        if pdf_bytes:
            st.caption(f"📄 PDF 文件已生成，点击上方按钮即可一键下载（含中文字体）")
        else:
            st.caption("⚠️ PDF 生成失败，请使用 HTML 或 Markdown 格式下载")

    finally:
        db.close()

# ============================================================
# 页面 5: 关于
# ============================================================
elif page == "ℹ️ 关于":
    st.markdown("<h1 style='color:#1a1a1a;font-size:2rem;font-weight:bold;'>ℹ️ 关于本系统</h1>", unsafe_allow_html=True)
    st.markdown("""
    ### ⚖️ Soft IP 主诉评估系统

    **版本**: MVP v0.1.0

    **已实现功能**:
    - ✅ 商标侵权案件创建与管理
    - ✅ 红线风险自动检查（6 条规则）
    - ✅ 法律要件分析
    - ✅ 三维评分（法律 × 业务 × 证据）
    - ✅ 三维雷达可视化
    - ✅ 评估报告生成（Markdown + 总结文档下载）
    - ✅ Mock 模式（无需 API Key）
    - ✅ 模拟法庭（多Agent对抗式庭审：原告↔被告↔法官，五步庭审流程）

    **后续规划**:
    - 🔜 接入法律数据库（法规、案例检索）自动化闭环
    - 🔜 著作权、不正当竞争案由扩展
    - 🔜 证据文件上传与自动解析
    - 🔜 模拟法庭用户介入功能（暂停修改论证）

    **技术栈**:
    - 前端: Streamlit
    - 数据库: SQLite + SQLAlchemy
    - LLM: Mock 模式（可切换 DeepSeek）
    - 可视化: SVG 雷达图（无需额外依赖）

    ---
    **免责声明**: 本系统为 AI 辅助决策工具，评估结果仅供内部参考，不构成正式法律意见。
    """)
