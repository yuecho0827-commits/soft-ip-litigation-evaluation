"""
诉算系统全局样式系统
参考 ten.375.studio 设计语言：极简、高对比、编辑设计感
纯白背景 + 深藏青(#0d1429) + 焦橙(#d65938) + 噪点纹理
"""

import streamlit as st

# ============================================================
# 色彩系统
# ============================================================
COLORS = {
    "primary": "#0d1429",         # 深藏青 — 标题/主色
    "primary_light": "#1a2540",   # 浅藏青
    "primary_pale": "#f5f6f8",    # 极浅藏青
    "accent": "#d65938",          # 焦橙 — 点缀/关键数字
    "accent_light": "#fbe8e3",    # 浅橙
    "success": "#0d1429",         # 深藏青表示达标（沉稳）
    "success_light": "#f5f6f8",
    "warning": "#d65938",         # 焦橙表示待改善
    "warning_light": "#fbe8e3",
    "danger": "#b91c1c",          # 红色表示风险
    "danger_light": "#fde8e8",
    "neutral": "#666666",
    "neutral_light": "#f5f5f5",
    "text_dark": "#0d1429",
    "text_body": "#333333",
    "text_muted": "#666666",
    "border": "#000000",
    "bg_page": "#ffffff",
    "bg_card": "#ffffff",
    "teal": "#a5d8dd",
    "teal_light": "#e8f5f6",
    "teal_text": "#cce8eb",
}

# 模拟法庭角色色
ROLE_COLORS = {
    "plaintiff": {"color": "#0d1429", "bg": "#ffffff", "icon": "■", "label": "原告"},
    "defendant": {"color": "#b91c1c", "bg": "#ffffff", "icon": "■", "label": "被告"},
    "judge":     {"color": "#d65938", "bg": "#ffffff", "icon": "■", "label": "法官"},
}


# ============================================================
# 全局 CSS 注入
# ============================================================

def inject_global_css():
    """注入全局CSS — ten.375.studio 风格"""
    st.markdown("""
    <style>
    /* ════════════════════════════════════════════
       全局基础
       ════════════════════════════════════════════ */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;400;500;600;800&display=swap');

    .stApp {
        background-color: #ffffff;
        font-family: 'Inter', -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
        color: #0d1429;
    }

    /* ── 噪点纹理覆盖层 ── */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: 9998;
        opacity: 0.022;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }

    /* ── 隐藏 Streamlit 默认元素 ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}

    /* ── 隐藏滚动条 ── */
    ::-webkit-scrollbar {width: 0px; height: 0px;}
    * {scrollbar-width: none;}

    /* ════════════════════════════════════════════
       侧边栏 — 深藏青底（高对比度文字）
       ════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {
        background: #0d1429;
        border-right: 1px solid #0d1429;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }

    /* 侧边栏 radio 导航 — 强对比 */
    section[data-testid="stSidebar"] [data-testid="stRadio"] label {
        color: #ffffff !important;
        font-size: 0.9rem;
        font-weight: 400;
        padding: 10px 0;
        transition: all 0.2s ease;
        border-left: 3px solid transparent;
        padding-left: 14px;
        border-radius: 0 4px 4px 0;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        color: #ffffff !important;
        border-left-color: #d65938;
        background: rgba(255, 255, 255, 0.05);
    }
    /* 选中的 radio 项 — 高亮指示 */
    section[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] label,
    section[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] [aria-checked="true"] + label {
        color: #ffffff !important;
        font-weight: 600;
        border-left-color: #d65938;
        background: rgba(214, 89, 56, 0.12);
    }

    /* 侧边栏分隔线 */
    section[data-testid="stSidebar"] hr {
        border-color: rgba(204, 232, 235, 0.15);
        margin: 16px 0;
    }

    /* ════════════════════════════════════════════
       排版
       ════════════════════════════════════════════ */
    .page-title {
        font-size: 2rem;
        font-weight: 800;
        color: #0d1429;
        letter-spacing: -0.03em;
        line-height: 1.1;
        margin-bottom: 6px;
    }
    .page-subtitle {
        font-size: 0.85rem;
        color: #666666;
        font-weight: 400;
        margin-bottom: 28px;
        letter-spacing: 0.01em;
    }

    /* ════════════════════════════════════════════
       卡片 — 极简：细黑边框，无阴影，锐角
       ════════════════════════════════════════════ */
    .card {
        background: #ffffff;
        border: 1px solid #000000;
        border-radius: 2px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: none;
        transition: border-color 0.2s ease;
    }
    .card:hover {
        border-color: #d65938;
    }

    /* ── 维度卡片 — 左侧粗色条 ── */
    .dim-card {
        background: #ffffff;
        border: 1px solid #000000;
        border-left: 4px solid #0d1429;
        border-radius: 2px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: none;
    }
    .dim-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .dim-card-title {
        font-size: 1rem;
        font-weight: 600;
        color: #0d1429;
        letter-spacing: -0.01em;
    }
    .dim-card-score {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1;
    }
    .dim-card-score-unit {
        font-size: 0.8rem;
        color: #999999;
        font-weight: 400;
    }
    .dim-card-body {
        font-size: 0.85rem;
        color: #333333;
        line-height: 1.7;
    }

    /* ── 评分进度条 — 极细，锐角 ── */
    .score-bar-wrap {
        margin-bottom: 14px;
    }
    .score-bar-label {
        display: flex;
        justify-content: space-between;
        margin-bottom: 5px;
        font-size: 0.85rem;
    }
    .score-bar-track {
        height: 4px;
        background: #f0f0f0;
        border-radius: 0;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 0;
        transition: width 0.6s ease;
    }

    /* ════════════════════════════════════════════
       区块标题 — 大字+底线，无背景填充
       ════════════════════════════════════════════ */
    .section-banner {
        border-bottom: 2px solid #0d1429;
        border-radius: 0;
        padding: 0 0 10px 0;
        margin: 32px 0 16px 0;
        background: transparent;
    }
    .section-banner-title {
        font-size: 1.4rem;
        font-weight: 800;
        color: #0d1429;
        letter-spacing: -0.02em;
    }
    .section-banner-sub {
        color: #999999;
        font-size: 0.8rem;
        margin-left: 12px;
        font-weight: 400;
    }

    /* ════════════════════════════════════════════
       综合评分 — 超大数字
       ════════════════════════════════════════════ */
    .final-score-card {
        background: #ffffff;
        border: 2px solid #0d1429;
        border-radius: 2px;
        padding: 36px;
        text-align: center;
        margin: 20px 0;
        box-shadow: none;
    }
    .final-score-number {
        font-size: 5rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        line-height: 1;
    }
    .final-score-label {
        font-size: 0.75rem;
        color: #999999;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    /* ════════════════════════════════════════════
       聊天气泡（模拟法庭）— 极简：白底+左色条
       ════════════════════════════════════════════ */
    .chat-bubble {
        background: #ffffff;
        border: 1px solid #e5e5e5;
        border-left: 3px solid #0d1429;
        border-radius: 0;
        padding: 16px 20px;
        margin: 10px 0;
        font-size: 0.85rem;
        line-height: 1.75;
    }
    .chat-bubble-header {
        font-weight: 600;
        font-size: 0.8rem;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .chat-bubble-content {
        color: #333333;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .chat-role-tag {
        font-size: 0.68rem;
        font-weight: 500;
        padding: 2px 8px;
        border: 1px solid;
        border-radius: 0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ════════════════════════════════════════════
       案件卡片
       ════════════════════════════════════════════ */
    .case-card {
        background: #ffffff;
        border: 1px solid #000000;
        border-radius: 2px;
        padding: 20px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
        cursor: pointer;
        box-shadow: none;
    }
    .case-card:hover {
        border-color: #d65938;
        box-shadow: none;
    }
    .case-card-title {
        font-size: 1rem;
        font-weight: 700;
        color: #0d1429;
        margin-bottom: 6px;
        letter-spacing: -0.01em;
    }
    .case-card-meta {
        font-size: 0.78rem;
        color: #666666;
    }

    /* ── 状态徽章 — 方角 ── */
    .status-badge {
        display: inline-block;
        font-size: 0.68rem;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border: 1px solid;
    }

    /* ── 表单区域标题 ── */
    .form-section-title {
        font-size: 0.9rem;
        font-weight: 700;
        color: #0d1429;
        margin-bottom: 14px;
        padding-bottom: 8px;
        border-bottom: 1px solid #000000;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    /* ════════════════════════════════════════════
       Streamlit 组件覆盖
       ════════════════════════════════════════════ */

    /* ── Tab 样式 ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        border-bottom: 2px solid #0d1429;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 0;
        font-weight: 500;
        letter-spacing: 0.01em;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #d65938;
        color: #0d1429;
        font-weight: 700;
    }

    /* ── Spinner ── */
    .stSpinner > div > div {
        border-top-color: #d65938 !important;
    }

    /* ── 分隔线 ── */
    hr {
        border: none;
        border-top: 1px solid #e5e5e5;
        margin: 24px 0;
    }

    /* ── 按钮 — 黑底白字/白底黑边 ── */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        letter-spacing: 0.01em;
        transition: all 0.2s ease;
    }
    .stButton > button[kind="primary"] {
        background: #0d1429;
        color: #ffffff;
        border: 2px solid #0d1429;
    }
    .stButton > button[kind="primary"]:hover {
        background: #d65938;
        border-color: #d65938;
    }
    .stButton > button[kind="secondary"] {
        background: #ffffff;
        color: #0d1429;
        border: 2px solid #000000;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #d65938;
        color: #d65938;
    }

    /* ── Expander — 扁平化 ── */
    .stExpander {
        border: 1px solid #000000;
        border-radius: 2px;
        overflow: hidden;
        box-shadow: none;
    }
    details summary span {
        font-weight: 600;
        color: #0d1429;
    }

    /* ── Alert ── */
    .stAlert {
        border-radius: 2px;
    }

    /* ── 输入框 ── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 2px;
        border: 1px solid #000000;
        font-family: inherit;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #d65938;
        box-shadow: none;
    }

    /* ── Selectbox ── */
    .stSelectbox > div > div {
        border-radius: 2px;
        border: 1px solid #000000;
    }

    /* ── File uploader ── */
    .stFileUploader {
        border: 1px dashed #000000;
        border-radius: 2px;
    }

    /* ── 模拟法庭步骤导航 ── */
    .step-nav-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        border-radius: 0;
        margin-bottom: 2px;
        font-size: 0.85rem;
        color: #666666;
        border-left: 2px solid transparent;
        transition: all 0.2s ease;
    }
    .step-nav-item.active {
        background: transparent;
        color: #0d1429;
        font-weight: 700;
        border-left-color: #d65938;
    }
    .step-nav-number {
        width: 24px;
        height: 24px;
        border: 1px solid #000000;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.72rem;
        font-weight: 700;
        background: transparent;
        color: #0d1429;
    }
    .step-nav-item.active .step-nav-number {
        background: #0d1429;
        color: #ffffff;
        border-color: #0d1429;
    }

    /* ── 指标卡 — 极简 ── */
    .metric-card-wrap {
        background: #ffffff;
        border: 1px solid #000000;
        border-radius: 2px;
        padding: 16px 20px;
        text-align: center;
        margin-bottom: 12px;
        box-shadow: none;
    }
    .metric-card-label {
        font-size: 0.7rem;
        color: #999999;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .metric-card-value {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.1;
    }
    .metric-card-sub {
        font-size: 0.72rem;
        color: #999999;
        margin-top: 4px;
    }

    /* ── 链接 ── */
    a {
        color: #d65938;
        text-decoration: none;
        transition: color 0.15s ease;
    }
    a:hover {
        color: #0d1429;
    }

    /* ── 选中文本 ── */
    ::selection {
        background: #d65938;
        color: #ffffff;
    }

    /* ── 大标题描边效果（参考 ten.375.studio stroke text） ── */
    .stroke-title {
        -webkit-text-stroke: 2px #0d1429;
        color: transparent;
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: -0.03em;
    }

    /* ── Streamlit markdown h1-h3 ── */
    .stMarkdown h1 {
        font-size: 1.8rem;
        font-weight: 800;
        color: #0d1429;
        letter-spacing: -0.02em;
    }
    .stMarkdown h2 {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0d1429;
    }
    .stMarkdown h3 {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0d1429;
    }

    /* ── Progress bar ── */
    .stProgress > div > div > div {
        background-color: #0d1429;
    }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# 可复用 HTML 组件
# ============================================================

def page_header(title: str, subtitle: str = ""):
    """页面标题 — 大号加粗"""
    sub_html = f'<div class="page-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="page-title">{title}</div>{sub_html}', unsafe_allow_html=True)


def section_banner(title: str, subtitle: str = "", color: str = None):
    """区块标题 — 底线分隔，无背景填充"""
    st.markdown(f"""
    <div class="section-banner">
        <span class="section-banner-title">{title}</span>
        <span class="section-banner-sub">{subtitle}</span>
    </div>
    """, unsafe_allow_html=True)


def dim_card(title: str, score: int, analysis: str, sub_items=None, extra=None):
    """维度评估卡片"""
    if score >= 60:
        color = COLORS["primary"]
        status = "达标"
    elif score >= 40:
        color = COLORS["accent"]
        status = "待改善"
    else:
        color = COLORS["danger"]
        status = "风险"

    analysis_display = analysis[:400] if len(analysis) > 400 else analysis

    st.markdown(f"""
    <div class="dim-card" style="border-left-color:{color};">
        <div class="dim-card-header">
            <span class="dim-card-title">{title}</span>
            <span class="dim-card-score" style="color:{color};">
                {score}<span class="dim-card-score-unit"> 分</span>
            </span>
        </div>
        <div style="background:#f0f0f0;height:3px;overflow:hidden;margin-bottom:12px;">
            <div style="height:100%;width:{score}%;background:{color};transition:width 0.6s;"></div>
        </div>
        <div class="dim-card-body">{analysis_display}</div>
    </div>
    """, unsafe_allow_html=True)

    if sub_items or extra:
        with st.expander("详细分析", expanded=False):
            if sub_items:
                for si in sub_items:
                    ic = {"pass": "✅", "warning": "⚠️", "block": "🚫",
                          "满足": "✅", "存疑": "⚠️", "不满足": "❌",
                          "充足": "✅", "不足": "⚠️", "缺失": "❌"}.get(si.get('status', ''), '⚪')
                    sub_s = si.get('score', None)
                    score_str = f" **({sub_s}分)**" if sub_s is not None else ""
                    st.markdown(f"{ic} **{si.get('name', si.get('requirement', ''))}**{score_str}: {si.get('detail', si.get('analysis', ''))}")
            if extra:
                st.caption(extra)


def score_bar(label: str, score: int, color: str = None, description: str = ""):
    """评分进度条 — 极细"""
    if not color:
        if score >= 60:
            color = COLORS["primary"]
        elif score >= 40:
            color = COLORS["accent"]
        else:
            color = COLORS["danger"]

    st.markdown(f"""
    <div class="score-bar-wrap">
        <div class="score-bar-label">
            <span style="color:#0d1429;font-weight:500;">{label}</span>
            <span style="font-weight:800;color:{color};">{score}</span>
        </div>
        <div class="score-bar-track">
            <div class="score-bar-fill" style="width:{score}%;background:{color};"></div>
        </div>
        {f'<div style="font-size:0.7rem;color:#999;margin-top:3px;">{description}</div>' if description else ''}
    </div>
    """, unsafe_allow_html=True)


def final_score_card(final_score: int, recommendation: str, reason: str, color: str = None):
    """综合评分卡 — 超大数字"""
    if not color:
        if final_score >= 65:
            color = COLORS["primary"]
        elif final_score >= 40:
            color = COLORS["accent"]
        else:
            color = COLORS["danger"]

    st.markdown(f"""
    <div class="final-score-card" style="border-color:{color};">
        <div class="final-score-label">三维综合评分</div>
        <div class="final-score-number" style="color:{color};">{final_score}<span style="font-size:1.2rem;color:#999;font-weight:400;"> / 100</span></div>
        <div style="font-size:1.2rem;font-weight:800;color:{color};margin-top:16px;letter-spacing:-0.02em;">{recommendation}</div>
        <div style="font-size:0.85rem;color:#666;margin-top:8px;">{reason}</div>
    </div>
    """, unsafe_allow_html=True)


def case_card(case_id, name, cause_type, goal_type, status, score=None, recommendation=None):
    """案件卡片"""
    status_map = {
        "draft": ("草稿", "#ffffff", "#0d1429"),
        "evaluating": ("评估中", "#0d1429", "#ffffff"),
        "completed": ("已完成", "#d65938", "#ffffff"),
    }
    status_text, status_bg, status_color = status_map.get(status, ("未知", "#f5f5f5", "#666"))

    score_html = ""
    if score is not None:
        rec_color = COLORS["primary"] if score >= 65 else COLORS["accent"] if score >= 40 else COLORS["danger"]
        score_html = f"""
        <div style="display:flex;align-items:baseline;gap:6px;margin-top:10px;">
            <span style="font-size:2rem;font-weight:800;color:{rec_color};letter-spacing:-0.04em;">{score}</span>
            <span style="font-size:0.75rem;color:#999;">/ 100</span>
            {f'<span style="font-size:0.78rem;color:{rec_color};margin-left:8px;font-weight:600;">{recommendation}</span>' if recommendation else ''}
        </div>
        """

    st.markdown(f"""
    <div class="case-card">
        <div class="case-card-title">{name}</div>
        <div class="case-card-meta">
            {cause_type} · {goal_type} · ID: {case_id}
        </div>
        <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:flex-end;">
            <span class="status-badge" style="background:{status_bg};color:{status_color};border-color:{status_color};">{status_text}</span>
            {score_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def chat_bubble(role_name: str, step_name: str, content: str, role_type: str = "plaintiff"):
    """模拟法庭聊天气泡 — 白底+左色条"""
    rc = ROLE_COLORS.get(role_type, ROLE_COLORS["plaintiff"])
    color = rc["color"]

    if role_type == "defendant":
        margin = "margin-left:15%;"
    elif role_type == "judge":
        margin = "margin:0 8%;"
    else:
        margin = "margin-right:15%;"

    content_display = content if len(content) <= 1200 else content[:1200] + "\n\n...(内容过长，已截断)"

    st.markdown(f"""
    <div class="chat-bubble" style="border-left-color:{color};{margin}">
        <div class="chat-bubble-header">
            <span style="color:{color};">{role_name}</span>
            <span class="chat-role-tag" style="border-color:{color};color:{color};">{step_name}</span>
        </div>
        <div class="chat-bubble-content">{content_display}</div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label: str, value: str, sub: str = "", color: str = None):
    """指标卡 — 极简"""
    if not color:
        color = COLORS["primary"]

    st.markdown(f"""
    <div class="metric-card-wrap" style="border-color:{color};">
        <div class="metric-card-label">{label}</div>
        <div class="metric-card-value" style="color:{color};">{value}</div>
        {f'<div class="metric-card-sub">{sub}</div>' if sub else ''}
    </div>
    """, unsafe_allow_html=True)


def form_section_title(title: str):
    """表单分区标题"""
    st.markdown(f'<div class="form-section-title">{title}</div>', unsafe_allow_html=True)
