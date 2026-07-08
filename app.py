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
        run_moot_court as run_moot_court_simulation,
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
        run_moot_court_simulation,
    )
    _mock = False

from legal_rules import run_rule_engine
from scoring import (
    calculate_legal_feasibility,
    calculate_business_expectation,
    calculate_overall_score,
    generate_recommendation,
)
from legal_database import format_laws_for_report, format_cases_for_report

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

page_options = ["📝 新建案件", "📊 案件列表", "🔍 评估分析", "📄 评估报告", "ℹ️ 关于"]

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
                # 聚合证据文本（如果有上传的文件解析结果）
                evidence_texts = st.session_state.get("evidence_text_extra", "")

                # ====================================================
                # 维度一：法律可行性
                # ====================================================
                st.markdown("---")
                st.markdown("## 🔍 维度一：法律可行性")

                # 1.1 权利基础
                progress.progress(10, "1/7 权利基础评估...")
                st.markdown("### 1.1 权利基础")
                with st.spinner("DeepSeek 正在分析商标权利基础..."):
                    rights_result = evaluate_rights_foundation(
                        case.case_description,
                        uploaded_texts=evidence_texts if not _mock else ""
                    )
                if "error" in rights_result:
                    st.error(f"权利基础评估失败: {rights_result.get('error', rights_result.get('raw',''))}")
                else:
                    st.metric("权利基础得分", f"{rights_result.get('score', 'N/A')} 分")
                    st.write(rights_result.get('analysis', ''))
                    with st.expander("详细分析"):
                        st.json(rights_result)

                # 1.2 侵权认定
                progress.progress(25, "2/7 侵权认定评估...")
                st.markdown("### 1.2 侵权认定")
                with st.spinner("DeepSeek 正在分析商标侵权构成要件..."):
                    infringement_result = evaluate_infringement(
                        case.case_description,
                        rights_assessment=str(rights_result.get('analysis', '')),
                        uploaded_texts=evidence_texts if not _mock else ""
                    )
                if "error" in infringement_result:
                    st.error(f"侵权认定评估失败: {infringement_result.get('error', infringement_result.get('raw',''))}")
                else:
                    st.metric("侵权认定得分", f"{infringement_result.get('score', 'N/A')} 分")
                    st.write(infringement_result.get('analysis', ''))
                    with st.expander("要件逐项分析"):
                        for el in infringement_result.get('elements', []):
                            icon = {"满足":"✅","存疑":"⚠️","不满足":"❌"}.get(el.get('status',''), '⚪')
                            st.markdown(f"{icon} **{el['name']}** ({el['score']}分): {el['analysis']}")

                # 1.3 诉讼程序
                progress.progress(40, "3/7 程序审查...")
                st.markdown("### 1.3 诉讼程序")
                with st.spinner("DeepSeek 正在审查程序可行性..."):
                    procedure_result = evaluate_procedure(case.case_description)
                if "error" in procedure_result:
                    st.error(f"程序审查失败: {procedure_result.get('error', procedure_result.get('raw',''))}")
                else:
                    st.metric("程序审查得分", f"{procedure_result.get('score', 'N/A')} 分")
                    for item in procedure_result.get('items', []):
                        icon = {"pass":"✅","warning":"⚠️","block":"🚫"}.get(item.get('status',''), '⚪')
                        st.markdown(f"{icon} **{item['name']}**: {item['detail']}")

                # 1.4 模拟法庭（对抗检验）
                progress.progress(55, "4/7 模拟法庭...")
                st.markdown("### 1.4 模拟法庭（对抗检验）")
                with st.spinner("DeepSeek 正在进行多角色庭审模拟..."):
                    moot_result = run_moot_court_simulation(
                        case.case_description,
                        rights_assessment=str(rights_result.get('analysis', '')),
                        infringement_assessment=str(infringement_result.get('analysis', '')),
                        evidence_summary=evidence_texts[:1500] if evidence_texts else ""
                    )
                if "error" in moot_result:
                    st.warning(f"模拟法庭异常: {moot_result.get('error', moot_result.get('raw',''))[:200]}")
                    correction_coeff = 1.0
                else:
                    correction_coeff = moot_result.get('correction_coefficient', 1.0)
                    st.metric("对抗修正系数", f"{correction_coeff:.2f}")
                    st.write(f"法官归纳: {moot_result.get('judge_summary', '')[:300]}")
                    with st.expander("完整庭审记录"):
                        for rnd in moot_result.get('rounds', []):
                            st.markdown(f"**{rnd['role']}**: {rnd['content'][:500]}")

                # 计算法律可行性
                legal_score = calculate_legal_feasibility(
                    rights_result.get('score', 0),
                    infringement_result.get('score', 0),
                    procedure_result.get('score', 0),
                    correction_coeff
                )
                st.success(f"✅ 法律可行性综合得分: **{legal_score} 分**")
                st.caption(f"公式: 权利基础 × 侵权认定 × 诉讼程序 × 对抗修正系数 = {rights_result.get('score',0)} × {infringement_result.get('score',0)} × {procedure_result.get('score',0)} × {correction_coeff:.2f}")

                # ====================================================
                # 维度二：业务预期
                # ====================================================
                st.markdown("---")
                st.markdown("## 💰 维度二：业务预期")

                # 2.1 财务回报
                progress.progress(70, "5/7 财务回报评估...")
                st.markdown("### 2.1 财务回报")
                st.caption("💡 如需类案检索辅助评估，可在评估完成后让 AI 助手通过北大法宝查询")
                with st.spinner("DeepSeek 正在评估判赔预测和成本..."):
                    financial_result = evaluate_financial_return(case.case_description)
                if "error" in financial_result:
                    st.warning(f"财务评估异常: {financial_result.get('error', financial_result.get('raw',''))[:200]}")
                    fin_score = 50
                else:
                    fin_score = financial_result.get('score', 50)
                    st.metric("财务回报得分", f"{fin_score} 分")
                    de = financial_result.get('damages_estimate', {})
                    if de:
                        st.markdown(f"判赔预测: P10=¥{de.get('p10','-')} / P50=¥{de.get('p50','-')} / P90=¥{de.get('p90','-')}")
                    st.write(financial_result.get('analysis', ''))

                # 2.2 判例价值
                progress.progress(80, "6/7 判例价值评估...")
                st.markdown("### 2.2 判例价值")
                st.caption("💡 如需首案检索（北大法宝），可在评估完成后让 AI 助手查询")
                with st.spinner("DeepSeek 正在评估判例价值..."):
                    precedent_result = evaluate_precedent_value(case.case_description)
                if "error" in precedent_result:
                    st.warning(f"判例价值异常: {precedent_result.get('error', precedent_result.get('raw',''))[:200]}")
                    prec_score = 50
                else:
                    prec_score = precedent_result.get('score', 50)
                    st.metric("判例价值得分", f"{prec_score} 分")
                    st.write(precedent_result.get('analysis', ''))
                    st.caption(f"首案指数: {precedent_result.get('first_case_index', '-')} | 影响力: {precedent_result.get('influence_level', '-')}")

                # 计算业务预期
                business_score = calculate_business_expectation(
                    fin_score, prec_score, case.goal_type
                )
                st.success(f"✅ 业务预期综合得分: **{business_score} 分**")
                goal_label = "要钱" if case.goal_type == "要钱" else "要名"
                st.caption(f"公式({'要钱' if case.goal_type == '要钱' else '要名'}): {case.goal_type == '要钱' and '0.9×财务+0.1×判例' or '0.1×财务+0.9×判例'}")

                # ====================================================
                # 维度三：证据就绪度
                # ====================================================
                st.markdown("---")
                st.markdown("## 📋 维度三：证据就绪度")
                progress.progress(90, "7/7 证据就绪度评估...")
                with st.spinner("DeepSeek 正在评估证据完整性..."):
                    evidence_result = evaluate_evidence_readiness(
                        case.case_description,
                        uploaded_evidence_texts=evidence_texts,
                        evidence_count=0
                    )
                if "error" in evidence_result:
                    st.warning(f"证据评估异常: {evidence_result.get('error', evidence_result.get('raw',''))[:200]}")
                    evidence_score = 60
                else:
                    evidence_score = evidence_result.get('score', 60)
                    st.metric("证据就绪度得分", f"{evidence_score} 分")
                    st.write(evidence_result.get('analysis', ''))
                    with st.expander("证据矩阵诊断"):
                        for item in evidence_result.get('evidence_matrix', []):
                            icon = {"充足":"✅","不足":"⚠️","缺失":"❌"}.get(item.get('status',''), '⚪')
                            st.markdown(f"{icon} **{item['requirement']}**: {item['analysis']}")
                    if evidence_result.get('remediation_suggestions'):
                        st.warning("补证建议: " + "; ".join(evidence_result['remediation_suggestions']))

                # ====================================================
                # 综合评分
                # ====================================================
                st.markdown("---")
                progress.progress(95, "计算综合评分...")
                st.markdown("## 🏆 综合评分")

                final_score = calculate_overall_score(
                    legal_score, business_score, evidence_score
                )
                rec = generate_recommendation(final_score, procedure_result.get('items', []))

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("法律可行性", f"{legal_score} 分")
                c2.metric("业务预期", f"{business_score} 分")
                c3.metric("证据就绪度", f"{evidence_score} 分")
                c4.metric("综合得分", f"{final_score} 分", delta=rec['recommendation'])

                st.caption(f"公式: 法律可行性 × 业务预期 × 证据就绪度 = {legal_score} × {business_score} × {evidence_score}")
                st.caption(f"💡 {rec['reason']}")

                # 保存评分
                db.add(ScoreSnapshot(
                    case_id=case_id,
                    legal_score=legal_score, business_score=business_score,
                    evidence_score=evidence_score, confidence_score=70,
                    final_score=final_score, recommendation=rec['recommendation']
                ))

                # 保存附加数据供报告使用
                st.session_state[f"rights_{case_id}"] = rights_result
                st.session_state[f"infringement_{case_id}"] = infringement_result
                st.session_state[f"procedure_{case_id}"] = procedure_result
                st.session_state[f"moot_{case_id}"] = moot_result
                st.session_state[f"financial_{case_id}"] = financial_result
                st.session_state[f"precedent_{case_id}"] = precedent_result
                st.session_state[f"evidence_{case_id}"] = evidence_result

                db.commit()

                # 生成报告
                progress.progress(98, "生成报告...")
                report_md = generate_markdown_report(
                    {"name": case.name, "cause_type": case.cause_type, "goal_type": case.goal_type, "client_org": case.client_org},
                    {
                        "legal_feasibility": legal_score,
                        "business_expectation": business_score,
                        "evidence_readiness": evidence_score,
                        "final_score": final_score,
                        "recommendation": rec['recommendation'],
                        "confidence_score": 70,
                        "reason": rec['reason'],
                        "action_items": []
                    },
                    procedure_result.get('items', []),
                    {"elements": [
                        {"element": "权利基础", "score": rights_result.get('score', 0), "analysis": rights_result.get('analysis', ''), "evidence_status": "已评估", "risks": rights_result.get('risks', [])},
                        {"element": "侵权认定", "score": infringement_result.get('score', 0), "analysis": infringement_result.get('analysis', ''), "evidence_status": "已评估", "risks": infringement_result.get('risks', [])},
                        {"element": "诉讼程序", "score": procedure_result.get('score', 0), "analysis": procedure_result.get('analysis', ''), "evidence_status": "已评估", "risks": procedure_result.get('block_items', [])},
                    ]}
                )

                report_dir = Path("data/reports")
                report_dir.mkdir(parents=True, exist_ok=True)
                md_path = report_dir / f"{case_id}_report.md"
                md_path.write_text(report_md, encoding="utf-8")

                db.add(Report(case_id=case_id, report_type="评估报告", markdown_content=report_md, pdf_uri=str(md_path)))
                case.status = "completed"
                db.commit()

                progress.progress(100, "评估完成！")
                st.success("🎉 三维评估完成！")
                st.balloons()

    finally:
        db.close()

# ============================================================
# 页面 4: 评估报告（含三维可视化 + 可下载总结文档）
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

    **后续规划**:
    - 🔜 接入 DeepSeek API，替换 Mock 模式
    - 🔜 接入法律数据库（法规、案例检索）
    - 🔜 模拟法庭（多 Agent 对抗推演）
    - 🔜 著作权、不正当竞争案由扩展
    - 🔜 证据文件上传与自动解析

    **技术栈**:
    - 前端: Streamlit
    - 数据库: SQLite + SQLAlchemy
    - LLM: Mock 模式（可切换 DeepSeek）
    - 可视化: SVG 雷达图（无需额外依赖）

    ---
    **免责声明**: 本系统为 AI 辅助决策工具，评估结果仅供内部参考，不构成正式法律意见。
    """)
