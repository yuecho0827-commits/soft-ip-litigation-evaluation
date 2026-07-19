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

from sqlalchemy.exc import OperationalError

sys.path.append(str(Path(__file__).parent))

from config import APP_TITLE, APP_VERSION, get_runtime_configuration_status, get_runtime_settings, save_runtime_settings
from database import init_db, SessionLocal, Case, Party, RuleHit, RetrievalRecord, ScoreSnapshot, Report
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
    metric_card, form_section_title, empty_state_notice, accent_notice, COLORS, ROLE_COLORS
)

# 评估引擎
import llm_client
import mock_llm
from moot_court import MootCourtProcedure, MootCourtResult, run_moot_court as run_moot_court_real


def _use_mock_mode() -> bool:
    return bool(RUNTIME_CONFIG.get("use_mock", False))


def _call_runtime_eval(name: str, *args, **kwargs):
    module = mock_llm if _use_mock_mode() else llm_client
    return getattr(module, name)(*args, **kwargs)


def evaluate_rights_foundation(*args, **kwargs):
    return _call_runtime_eval("evaluate_rights_foundation", *args, **kwargs)


def evaluate_infringement(*args, **kwargs):
    return _call_runtime_eval("evaluate_infringement", *args, **kwargs)


def evaluate_procedure(*args, **kwargs):
    return _call_runtime_eval("evaluate_procedure", *args, **kwargs)


def evaluate_financial_return(*args, **kwargs):
    return _call_runtime_eval("evaluate_financial_return", *args, **kwargs)


def evaluate_precedent_value(*args, **kwargs):
    return _call_runtime_eval("evaluate_precedent_value", *args, **kwargs)


def evaluate_evidence_readiness(*args, **kwargs):
    return _call_runtime_eval("evaluate_evidence_readiness", *args, **kwargs)


def extract_defendant_info(*args, **kwargs):
    return _call_runtime_eval("extract_defendant_info", *args, **kwargs)


def run_moot_court_simulation(*args, **kwargs):
    if _use_mock_mode():
        return mock_llm.run_moot_court_simulation(*args, **kwargs)
    return run_moot_court_real(*args, **kwargs)

from legal_rules import run_rule_engine
from scoring import (
    calculate_legal_feasibility,
    calculate_business_expectation,
    calculate_overall_score,
    calculate_confidence_score,
    evaluate_data_integrity,
    generate_recommendation,
)
from legal_database import format_laws_for_report, format_cases_for_report
from pkulaw_integration import (
    generate_all_queries, save_results, get_validation_status
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

RUNTIME_CONFIG = get_runtime_configuration_status()
RUNTIME_DIR = Path(RUNTIME_CONFIG.get("runtime_dir") or (Path(__file__).parent / "runtime"))
EVAL_CACHE_DIR = RUNTIME_DIR
CRITICAL_DIMENSIONS = ["rights", "infringement", "procedure", "financial", "precedent", "evidence"]
DIMENSION_LABELS = {
    "rights": "权利基础",
    "infringement": "侵权认定",
    "procedure": "诉讼程序",
    "moot": "模拟法庭",
    "financial": "财务回报",
    "precedent": "判例价值",
    "evidence": "证据就绪度",
}
RETRIEVAL_LABELS = {
    "rights_retrieval": "权利基础法条检索",
    "infringement_retrieval": "侵权认定类案检索",
    "procedure_retrieval": "程序法条检索",
    "moot_retrieval": "抗辩模式检索",
    "financial_retrieval": "判赔数据检索",
    "precedent_retrieval": "首案检索",
}
EVAL_FLOW_STEPS = [
    {"id": "rights", "full_title": "1.1 权利基础", "source": "来源：模型分析 + 北大法宝法条缓存"},
    {"id": "infringement", "full_title": "1.2 侵权认定", "source": "来源：模型分析 + 北大法宝类案缓存"},
    {"id": "procedure", "full_title": "1.3 诉讼程序", "source": "来源：模型分析 + 北大法宝程序法条缓存"},
    {"id": "moot", "full_title": "1.4 模拟法庭", "source": "来源：多 Agent 对抗检验 + 北大法宝抗辩模式缓存"},
    {"id": "financial", "full_title": "2.1 财务回报", "source": "来源：模型分析 + 北大法宝判赔缓存 + 企查查画像"},
    {"id": "precedent", "full_title": "2.2 判例价值", "source": "来源：模型分析 + 北大法宝首案检索缓存"},
    {"id": "evidence", "full_title": "3 证据就绪度", "source": "来源：模型分析 + 已上传证据文本"},
]
EVAL_FLOW_GROUPS = [
    ("法律可行性", ["rights", "infringement", "procedure", "moot"]),
    ("业务预期", ["financial", "precedent"]),
    ("证据就绪度", ["evidence"]),
]
EVAL_FLOW_MAP = {step["id"]: step for step in EVAL_FLOW_STEPS}


def _eval_cache_path(case_id: str) -> Path:
    EVAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return EVAL_CACHE_DIR / f"eval_results_{case_id}.json"


def _load_eval_cache(case_id: str):
    path = _eval_cache_path(case_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_eval_cache(case_id: str, payload: dict) -> None:
    _eval_cache_path(case_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _case_status_label(status: str) -> str:
    return {
        "draft": "待评估",
        "pending": "待评估",
        "evaluating": "评估中",
        "partial": "部分完成",
        "completed": "已完成",
    }.get(status or "pending", "未知")


def _case_status_text_color(status: str) -> str:
    return {
        "draft": COLORS["text_muted"],
        "pending": COLORS["text_muted"],
        "evaluating": COLORS["warning"],
        "partial": COLORS["warning"],
        "completed": COLORS["accent"],
    }.get(status or "pending", COLORS["text_muted"])


def _pkulaw_cache_path(case_id: str) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / f"pkulaw_results_{case_id}.json"


def _clear_case_runtime_state(case_id: str) -> None:
    for path in (_eval_cache_path(case_id), _pkulaw_cache_path(case_id), RUNTIME_DIR / "reports" / f"{case_id}_report.md"):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass

    for key in [
        f"eval_results_{case_id}",
        f"rights_{case_id}",
        f"infringement_{case_id}",
        f"procedure_{case_id}",
        f"moot_{case_id}",
        f"financial_{case_id}",
        f"precedent_{case_id}",
        f"evidence_{case_id}",
    ]:
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
    if st.session_state.get("current_case_id") == case_id:
        st.session_state.pop("current_case_id", None)
        st.session_state.pop("current_case_name", None)
        st.session_state.pop("nav_target", None)
        if st.session_state.get("workbench_tab") in ("评估分析", "模拟法庭", "评估报告"):
            st.session_state["workbench_tab"] = "案件列表"


def _build_dimension_result(result: dict, fallback: dict, label: str) -> dict:
    merged = dict(fallback)
    merged.update(result or {})
    error = merged.get("error")
    if error:
        merged["status"] = "failed"
        merged["is_complete"] = False
        merged["analysis"] = f"{label}未完成：{error}"
    else:
        merged["status"] = merged.get("status", "completed")
        merged["is_complete"] = merged.get("status") != "failed"
    return merged


def _build_external_failure(label: str, error: str, status: str = "failed", include_collections: bool = True) -> dict:
    payload = {
        "label": label,
        "status": status,
        "error": error,
        "_summary": error,
    }
    if include_collections:
        payload.setdefault("laws", [])
        payload.setdefault("cases", [])
    return payload


def _safe_external_call(label: str, func, include_collections: bool = True):
    if _use_mock_mode():
        return _build_external_failure(label, f"Mock 模式未调用{label}", status="skipped", include_collections=include_collections)
    try:
        result = func() or {}
        if not isinstance(result, dict):
            raise RuntimeError("返回结果不是字典")
        result.setdefault("label", label)
        result.setdefault("status", "completed")
        result.setdefault("error", None)
        if include_collections:
            result.setdefault("laws", [])
            result.setdefault("cases", [])
            result.setdefault("_summary", f"{label}已完成")
        return result
    except Exception as exc:
        return _build_external_failure(label, f"{label}失败: {str(exc)[:200]}", include_collections=include_collections)


def _collect_retrieval_status(external_results: dict) -> dict:
    completed = 0
    total = 0
    for key in RETRIEVAL_LABELS:
        total += 1
        if external_results.get(key, {}).get("status") == "completed":
            completed += 1
    if external_results.get("qcc_data", {}).get("status") in ("completed", "not_applicable"):
        completed += 1
    total += 1
    return {"completed": completed, "total": total}


def _label_dimension_names(names):
    return [DIMENSION_LABELS.get(name, name) for name in names]


def _build_integrity_payload(integrity: dict) -> dict:
    critical_issues = _label_dimension_names(integrity.get("critical_missing", [])) + _label_dimension_names(integrity.get("critical_failed", []))
    optional_issues = _label_dimension_names(integrity.get("optional_incomplete", []))
    return {
        "is_complete": integrity.get("is_complete", False),
        "label": "完整" if integrity.get("is_complete") else "部分完成",
        "critical_issues": critical_issues,
        "optional_issues": optional_issues,
    }


def _persist_external_cache(case_id: str, external_results: dict) -> None:
    save_results(case_id, external_results)


def _render_dimension_alert(result: dict, fallback_message: str = ""):
    status = result.get("status")
    if status == "failed":
        accent_notice(result.get("error") or fallback_message or "当前维度未完成")
    elif status == "skipped":
        accent_notice(result.get("_summary") or fallback_message)


def _render_cached_retrieval(title: str, retrieval: dict, item_kind: str = "mixed", expanded: bool = False):
    with st.expander(title, expanded=expanded):
        if not retrieval:
            accent_notice("暂无缓存检索结果")
            return
        status = retrieval.get("status")
        if status == "failed":
            accent_notice(retrieval.get("error") or retrieval.get("_summary") or "检索失败")
            return
        if status == "skipped":
            accent_notice(retrieval.get("_summary") or "当前模式未执行外部检索")
            return

        st.caption(retrieval.get("_summary", "已读取缓存检索结果"))
        if item_kind in ("mixed", "laws"):
            for law in retrieval.get("laws", [])[:5]:
                st.markdown(f"**{law.get('title', '?')}**")
                if law.get("content"):
                    st.caption(str(law.get("content"))[:300])
                if law.get("timeliness"):
                    st.caption(f"时效: {law.get('timeliness')}")
        if item_kind in ("mixed", "cases"):
            for case_item in retrieval.get("cases", [])[:8]:
                st.markdown(f"**{case_item.get('title', '?')}**")
                meta = " · ".join([x for x in [case_item.get("court", ""), case_item.get("date", "")] if x])
                if meta:
                    st.caption(meta)
                if case_item.get("summary"):
                    st.caption(str(case_item.get("summary"))[:200])


def _extract_primary_defendant(case_description: str) -> dict:
    if _use_mock_mode():
        result = extract_defendant_info(case_description)
        defendant = (result.get("defendants") or [{}])[0]
        defendant["status"] = "completed"
        return defendant
    try:
        phase1 = extract_defendant_info(case_description)
        defendants = phase1.get("defendants", [])
        if not defendants:
            return {"status": "failed", "error": "未识别到被告主体"}
        for item in defendants:
            if isinstance(item, dict) and item.get("role") == "primary_defendant":
                item["status"] = "completed"
                return item
        first = defendants[0]
        first["status"] = "completed"
        return first
    except Exception as exc:
        return {"status": "failed", "error": str(exc)[:200]}


def _refresh_external_results(case, report_markdown: str = "") -> dict:
    external_results = {
        "generated_at": datetime.now().isoformat(),
        "mode": RUNTIME_CONFIG["mode_label"],
        "rights_retrieval": _safe_external_call(RETRIEVAL_LABELS["rights_retrieval"], search_for_rights_foundation),
        "infringement_retrieval": _safe_external_call(RETRIEVAL_LABELS["infringement_retrieval"], search_for_infringement),
        "procedure_retrieval": _safe_external_call(RETRIEVAL_LABELS["procedure_retrieval"], search_for_procedure),
        "moot_retrieval": _safe_external_call(RETRIEVAL_LABELS["moot_retrieval"], search_for_moot_court),
        "financial_retrieval": _safe_external_call(RETRIEVAL_LABELS["financial_retrieval"], search_for_financial),
        "precedent_retrieval": _safe_external_call(RETRIEVAL_LABELS["precedent_retrieval"], lambda: search_for_precedent(case.case_description)),
    }

    defendant_info = _extract_primary_defendant(case.case_description)
    external_results["defendant_info"] = defendant_info

    if _use_mock_mode():
        external_results["qcc_data"] = _build_external_failure("企查查被告财务画像", "Mock 模式未调用企查查", status="skipped", include_collections=False)
        external_results["verification"] = _build_external_failure("北大法宝防幻觉验证", "Mock 模式未执行防幻觉验证", status="skipped", include_collections=False)
        return external_results

    if defendant_info.get("status") == "completed" and defendant_info.get("name"):
        qcc_data = _safe_external_call(
            "企查查被告财务画像",
            lambda: search_for_financial_qcc_full(defendant_info),
            include_collections=False,
        )
    else:
        qcc_data = {
            "status": "not_applicable",
            "error": defendant_info.get("error", "未识别到被告主体名称"),
            "_summary": "未识别到被告主体名称，未执行企查查检索",
            "metrics": {},
            "stages": {},
        }
    external_results["qcc_data"] = qcc_data

    if report_markdown:
        external_results["verification"] = _safe_external_call(
            "北大法宝防幻觉验证",
            lambda: run_verification_phase(report_markdown),
            include_collections=False,
        )
        verification = external_results.get("verification", {})
        for key in ("adjust_provisions", "law_recognition", "anhao_recognition"):
            if key in verification:
                external_results[key] = verification.get(key)
    else:
        external_results["verification"] = {
            "status": "not_run",
            "error": None,
            "_summary": "尚未执行防幻觉验证",
            "summary": {},
        }

    return external_results


def _eval_flow_state_key(case_id: str) -> str:
    return f"eval_flow_state_{case_id}"


def _default_eval_flow_state(selected_step: str | None = None) -> dict:
    return {
        "running": False,
        "current_step": None,
        "completed_steps": [],
        "selected_step": selected_step,
    }


def _completed_eval_steps(eval_data: dict | None) -> list[str]:
    if not eval_data:
        return []
    completed = []
    for step in EVAL_FLOW_STEPS:
        if eval_data.get(step["id"]):
            completed.append(step["id"])
    return completed


def _ensure_eval_flow_state(case_id: str, eval_data: dict | None = None) -> dict:
    key = _eval_flow_state_key(case_id)
    existing = st.session_state.get(key)
    if existing and existing.get("running"):
        return existing

    completed = _completed_eval_steps(eval_data)
    default_selected = completed[-1] if completed else EVAL_FLOW_STEPS[0]["id"]
    valid_choices = set(completed) or {default_selected}
    selected = existing.get("selected_step") if existing and existing.get("selected_step") in valid_choices else default_selected
    state = {
        "running": False,
        "current_step": None,
        "completed_steps": completed,
        "selected_step": selected,
    }
    st.session_state[key] = state
    return state


def _set_eval_flow_state(case_id: str, *, running=None, current_step=None, completed_steps=None, selected_step=None) -> dict:
    key = _eval_flow_state_key(case_id)
    state = dict(st.session_state.get(key) or _default_eval_flow_state())
    if running is not None:
        state["running"] = running
    if current_step is not None or running is False:
        state["current_step"] = current_step
    if completed_steps is not None:
        state["completed_steps"] = list(completed_steps)
    if selected_step is not None:
        state["selected_step"] = selected_step
    st.session_state[key] = state
    return state


def _eval_flow_visual_state(step_id: str, flow_state: dict) -> str:
    completed = set(flow_state.get("completed_steps", []))
    if flow_state.get("running") and step_id == flow_state.get("current_step"):
        return "current"
    if step_id in completed:
        if step_id == flow_state.get("selected_step"):
            return "selected"
        return "complete"
    return "upcoming"


def _eval_flow_group_widths(step_count: int) -> list[float]:
    grid = [0.76, 0.08, 0.76, 0.08, 0.76, 0.08, 0.76]
    if step_count == 4:
        return grid + [2.18]
    if step_count == 2:
        return grid + [2.18]
    if step_count == 1:
        return grid + [2.18]
    widths = []
    for idx in range(step_count):
        widths.append(0.76)
        if idx < step_count - 1:
            widths.append(0.08)
    widths.append(2.18)
    return widths






def _render_eval_flow_card(case_id: str, flow_state: dict, interactive: bool = True, render_token: str = "base") -> None:
    if flow_state.get("running") and flow_state.get("current_step"):
        status_text = f"当前进行：{EVAL_FLOW_MAP[flow_state['current_step']]['full_title']}"
    elif flow_state.get("completed_steps"):
        status_text = f"已完成 {len(flow_state.get('completed_steps', []))}/{len(EVAL_FLOW_STEPS)} 个环节"
    else:
        status_text = "尚未开始评估"

    with st.container(key=f"eval_flow_card_shell_{render_token}"):
        st.markdown(
            f"""
            <div class="eval-flow-header">
                <div>
                    <div class="eval-flow-title">评估主流程</div>
                    <div class="eval-flow-subtitle">点击已完成节点可回看对应评估内容。进行中的节点会以淡橙色呼吸高亮显示。</div>
                </div>
                <div class="eval-flow-status">{status_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        completed = set(flow_state.get("completed_steps", []))
        for group_name, step_ids in EVAL_FLOW_GROUPS:
            st.markdown(f'<div class="eval-flow-group-title">{group_name}</div>', unsafe_allow_html=True)
            widths = _eval_flow_group_widths(len(step_ids))
            cols = st.columns(widths)
            col_idx = 0
            for idx, step_id in enumerate(step_ids):
                step_meta = EVAL_FLOW_MAP[step_id]
                visual_state = _eval_flow_visual_state(step_id, flow_state)
                with cols[col_idx]:
                    with st.container(key=f"eval_flow_step_{visual_state}_{case_id}_{step_id}_{render_token}"):
                        can_click = interactive and step_id in completed
                        disabled = (not interactive) or visual_state == "upcoming"
                        if st.button(
                            step_meta["full_title"],
                            key=f"eval_flow_btn_{case_id}_{step_id}_{render_token}",
                            use_container_width=True,
                            type="primary" if visual_state == "current" else "secondary",
                            disabled=disabled,
                        ):
                            if can_click:
                                _set_eval_flow_state(
                                    case_id,
                                    running=flow_state.get("running"),
                                    current_step=flow_state.get("current_step"),
                                    completed_steps=flow_state.get("completed_steps", []),
                                    selected_step=step_id,
                                )
                                st.rerun()
                col_idx += 1
                if idx < len(step_ids) - 1:
                    with cols[col_idx]:
                        st.markdown('<div class="eval-flow-arrow">→</div>', unsafe_allow_html=True)
                    col_idx += 1


MOOT_ROLE_META = {
    "judge": {"label": "法官", "role_name": "审判法官"},
    "plaintiff": {"label": "原告", "role_name": "原告代理律师"},
    "defendant": {"label": "被告", "role_name": "被告代理律师"},
}


def _moot_round_to_dict(round_result) -> dict:
    return {
        "step": round_result.step,
        "step_name": round_result.step_name,
        "role": round_result.speaker,
        "role_name": round_result.role_name,
        "content": round_result.content,
    }


def _moot_role_type(round_item: dict | None) -> str | None:
    if not round_item:
        return None
    role = str(round_item.get("role", round_item.get("speaker", ""))).lower()
    role_name = str(round_item.get("role_name", ""))
    if "judge" in role or "法官" in role_name:
        return "judge"
    if "defendant" in role or "被告" in role_name:
        return "defendant"
    if "plaintiff" in role or "原告" in role_name:
        return "plaintiff"
    return None


def _build_moot_round_stub(rounds: list[dict], error: str | None = None) -> dict:
    return {
        "rounds": list(rounds),
        "correction_coefficient": 1.0,
        "defense_strength": 50,
        "judge_summary": "",
        "weak_points": [],
        "focus_points": [],
        "judge_scores": {},
        "error": error,
    }


def _build_moot_status_snapshot(eval_data: dict | None, flow_state: dict) -> dict:
    moot_r = (eval_data or {}).get("moot") or {}
    rounds = list(moot_r.get("rounds", []) or [])
    running_moot = bool(flow_state.get("running") and flow_state.get("current_step") == "moot")
    active_round = rounds[-1] if rounds else None
    active_role = _moot_role_type(active_round)
    all_roles = {_moot_role_type(r) for r in rounds if _moot_role_type(r)}
    completed_roles = {_moot_role_type(r) for r in (rounds[:-1] if running_moot and rounds else rounds) if _moot_role_type(r)}

    role_states = {}
    for role_key in ("judge", "plaintiff", "defendant"):
        if running_moot and role_key == active_role:
            role_states[role_key] = "current"
        elif role_key in completed_roles or (not running_moot and role_key in all_roles):
            role_states[role_key] = "complete"
        else:
            role_states[role_key] = "upcoming"

    total_rounds = max(7, len(rounds)) if rounds else 7
    if running_moot and active_round:
        status_label = f"进行中 · {len(rounds)}/{total_rounds} 段"
    elif rounds:
        status_label = f"已完成 · {len(rounds)}/{total_rounds} 段"
    elif flow_state.get("running"):
        status_label = "等待进入 1.4 模拟法庭"
    else:
        status_label = "尚未启动"

    stage_name = active_round.get("step_name", "") if active_round else ""
    speaker_name = active_round.get("role_name", "") if active_round else ""
    if not stage_name:
        stage_name = "模拟法庭态势"
    if not speaker_name:
        speaker_name = "待启动"

    return {
        "has_rounds": bool(rounds),
        "running_moot": running_moot,
        "status_label": status_label,
        "stage_name": stage_name,
        "speaker_name": speaker_name,
        "completed_count": len(rounds),
        "total_rounds": total_rounds,
        "role_states": role_states,
        "active_round": active_round,
    }


def _render_moot_status_card(case_id: str, eval_data: dict | None, flow_state: dict, render_token: str = "base") -> None:
    snapshot = _build_moot_status_snapshot(eval_data, flow_state)

    def _role_node_html(role_key: str) -> str:
        meta = MOOT_ROLE_META[role_key]
        state = snapshot["role_states"][role_key]
        note = "当前发言" if state == "current" else "已入场" if state == "complete" else "待发言"
        return (
            f'<div class="moot-role-node moot-role-{role_key} moot-state-{state}">'
            f'<div class="moot-role-name">{meta["label"]}</div>'
            f'<div class="moot-role-note">{note}</div>'
            f'</div>'
        )

    with st.container(key=f"moot_status_card_shell_{render_token}"):
        st.markdown(
            f"""
            <div class="moot-status-header">
                <div>
                    <div class="moot-status-title">模拟法庭态势</div>
                    <div class="moot-status-subtitle">固定脚本式三角色庭审编排。这里展示当前是谁在发言，以及已推进到哪一段。</div>
                </div>
                <div class="moot-status-badge">{snapshot["status_label"]}</div>
            </div>
            <div class="moot-status-summary">
                <div class="moot-status-metric"><span class="moot-status-metric-label">当前阶段</span><span class="moot-status-metric-value">{snapshot["stage_name"]}</span></div>
                <div class="moot-status-metric"><span class="moot-status-metric-label">当前发言</span><span class="moot-status-metric-value">{snapshot["speaker_name"]}</span></div>
                <div class="moot-status-metric"><span class="moot-status-metric-label">已完成轮次</span><span class="moot-status-metric-value">{snapshot["completed_count"]}/{snapshot["total_rounds"]}</span></div>
            </div>
            <div class="moot-triangle-shell">
                <div class="moot-link moot-link-left"></div>
                <div class="moot-link moot-link-right"></div>
                <div class="moot-link moot-link-base"></div>
                {_role_node_html("judge")}
                {_role_node_html("plaintiff")}
                {_role_node_html("defendant")}
            </div>
            """
            ,unsafe_allow_html=True,
        )
        st.caption("进入 1.4 模拟法庭后，右侧态势卡会跟随当前轮次更新；完整庭审全文仍保留在独立的「模拟法庭」页中。")
        if st.button("查看完整模拟法庭 →", key=f"goto_moot_full_{case_id}_{render_token}", use_container_width=True, disabled=not snapshot["has_rounds"]):
            st.session_state["nav_target"] = "模拟法庭"
            st.rerun()


def _render_eval_moot_live_content(eval_data: dict) -> None:
    moot_r = eval_data.get("moot") or {}
    rounds = list(moot_r.get("rounds", []) or [])
    if not rounds:
        empty_state_notice("模拟法庭开始后，这里会展示当前轮次的发言内容。")
        return

    current_round = rounds[-1]
    role_key = _moot_role_type(current_round) or "plaintiff"
    role_color = ROLE_COLORS.get(role_key, COLORS["accent"])
    total_rounds = max(7, len(rounds))

    cols = st.columns(3)
    cols[0].metric("当前发言", current_round.get("role_name", MOOT_ROLE_META[role_key]["role_name"]))
    cols[1].metric("当前阶段", current_round.get("step_name", "模拟法庭"))
    cols[2].metric("已完成轮次", f"{len(rounds)}/{total_rounds}")

    st.markdown(
        f"""
        <div style="margin:14px 0 10px 0;padding:12px 14px;border:1px solid {role_color};border-left:4px solid {role_color};background:#fffaf8;">
            <div style="font-size:0.72rem;color:{role_color};text-transform:uppercase;letter-spacing:0.08em;font-weight:700;margin-bottom:4px;">当前发言内容</div>
            <div style="font-size:0.85rem;color:#666;">本轮由 {current_round.get("role_name", MOOT_ROLE_META[role_key]["role_name"])} 发言，内容已同步展示在下方。</div>
        </div>
        """
        ,unsafe_allow_html=True,
    )
    chat_bubble(
        current_round.get("role_name", MOOT_ROLE_META[role_key]["role_name"]),
        current_round.get("step_name", "模拟法庭"),
        current_round.get("content", ""),
        role_key,
        truncate=400,
    )
    if len(rounds) > 1:
        previous_round = rounds[-2]
        st.caption(f"上一轮：{previous_round.get('role_name', '')} · {previous_round.get('step_name', '')}")


def _run_moot_court_with_updates(case_description: str, rights_assessment: str, infringement_assessment: str, evidence_summary: str, on_round=None) -> dict:
    total_rounds = 7
    if _use_mock_mode():
        final_result = mock_llm.run_moot_court_simulation(
            case_description,
            rights_assessment=rights_assessment,
            infringement_assessment=infringement_assessment,
            evidence_summary=evidence_summary,
        )
        rounds = list(final_result.get("rounds", []) or [])
        if not rounds:
            return final_result
        total_rounds = max(total_rounds, len(rounds))
        for idx in range(len(rounds)):
            partial = _build_moot_round_stub(rounds[: idx + 1], error=final_result.get("error"))
            if idx == len(rounds) - 1:
                partial = dict(final_result)
                partial["rounds"] = rounds[: idx + 1]
            if on_round:
                on_round(partial, idx, total_rounds)
            time.sleep(0.16)
        return final_result

    procedure = MootCourtProcedure(
        case_description=case_description,
        rights_assessment=rights_assessment,
        infringement_assessment=infringement_assessment,
        evidence_summary=evidence_summary,
    )
    try:
        for idx, _ in enumerate(procedure._run_steps()):
            partial_rounds = [_moot_round_to_dict(r) for r in procedure.rounds]
            partial = _build_moot_round_stub(partial_rounds)
            if idx == total_rounds - 1:
                final_state = MootCourtResult(rounds=list(procedure.rounds))
                procedure._parse_judge_result(final_state)
                partial = final_state.to_dict()
            if on_round:
                on_round(partial, idx, total_rounds)
    except RuntimeError as exc:
        return _build_moot_round_stub([_moot_round_to_dict(r) for r in procedure.rounds], error=str(exc))

    final_state = MootCourtResult(rounds=list(procedure.rounds))
    procedure._parse_judge_result(final_state)
    return final_state.to_dict()


def _render_eval_rights_content(eval_data: dict) -> None:
    external_cache = eval_data.get("external_results", {})
    rights_r = eval_data.get("rights") or {}
    sub_scores = []
    for key, value in rights_r.get("sub_scores", {}).items():
        label = {"validity": "商标有效性", "usage_continuity": "连续使用", "coverage": "覆盖范围", "well_known_status": "驰名地位", "risk_of_invalidation": "无效风险"}.get(key, key)
        if isinstance(value, dict):
            sub_scores.append({"name": label, "score": value.get("score", 0), "detail": value.get("reason", ""), "status": "pass" if value.get("score", 0) >= 60 else "warning"})
        else:
            sub_scores.append({"name": label, "score": value, "status": "pass" if value >= 60 else "warning"})
    dim_card(
        "1.1 权利基础评估",
        rights_r.get("score", 0),
        rights_r.get("analysis", ""),
        sub_items=sub_scores,
        extra="优势: " + ", ".join(rights_r.get("strengths", ["-"])) + "\n\n风险: " + ", ".join(rights_r.get("risks", ["-"])),
    )
    _render_dimension_alert(rights_r)
    _render_cached_retrieval("北大法宝 · 法条检索", external_cache.get("rights_retrieval", {}), "laws", True)


def _render_eval_infringement_content(eval_data: dict) -> None:
    external_cache = eval_data.get("external_results", {})
    infr_r = eval_data.get("infringement") or {}
    el_items = [{"name": el.get("name", "未知要素"), "score": el.get("score", 0), "status": el.get("status", "pass"), "detail": el.get("analysis", "")} for el in infr_r.get("elements", [])]
    dim_card("1.2 侵权认定评估", infr_r.get("score", 0), infr_r.get("analysis", ""), sub_items=el_items)
    _render_dimension_alert(infr_r)
    _render_cached_retrieval("北大法宝 · 类案检索", external_cache.get("infringement_retrieval", {}), "mixed", True)


def _render_eval_procedure_content(eval_data: dict) -> None:
    external_cache = eval_data.get("external_results", {})
    proc_r = eval_data.get("procedure") or {}
    proc_items = [{"name": item.get("name", "未知程序项"), "status": item.get("status", "pass"), "detail": item.get("detail", "")} for item in proc_r.get("items", [])]
    dim_card("1.3 诉讼程序审查", proc_r.get("score", 0), proc_r.get("analysis", ""), sub_items=proc_items)
    _render_dimension_alert(proc_r)
    _render_cached_retrieval("北大法宝 · 法条检索", external_cache.get("procedure_retrieval", {}), "laws", True)


def _render_eval_moot_content(eval_data: dict) -> None:
    external_cache = eval_data.get("external_results", {})
    moot_r = eval_data.get("moot") or {}
    coeff = eval_data.get("correction_coeff", 1.0)
    if moot_r.get("status") == "failed" and not moot_r.get("rounds"):
        accent_notice(moot_r.get("error", "模拟法庭未完成"))
    else:
        defense_strength = moot_r.get("defense_strength", 50)
        coeff_color = COLORS["danger"] if coeff < 0.9 else COLORS["warning"] if coeff < 1.0 else COLORS["success"]
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            metric_card("对抗修正系数", f"{coeff:.2f}", "中性=1.0", coeff_color)
        with col_c2:
            metric_card("被告抗辩强度", f"{defense_strength}/100", "用于理解对抗压力", COLORS["warning"])

        focus_points = moot_r.get("focus_points", [])
        if focus_points:
            st.markdown(
                f"""
                <div class="card" style="border-left:4px solid {COLORS['accent']};">
                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">争议焦点</div>
                    {''.join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">{i+1}. {fp}</div>' for i, fp in enumerate(focus_points))}
                </div>
                """,
                unsafe_allow_html=True,
            )

        rounds = moot_r.get("rounds", [])
        if rounds:
            st.markdown(
                f"""
                <div style="font-size:1.1rem;font-weight:800;color:{COLORS['text_dark']};margin-bottom:12px;letter-spacing:-0.02em;">
                    庭审记录（共{len(rounds)}轮发言）
                </div>
                """,
                unsafe_allow_html=True,
            )
            for rnd in rounds:
                role_name = rnd.get("role_name", rnd.get("role", rnd.get("speaker", "")))
                step_name = rnd.get("step_name", "")
                content = rnd.get("content", "")
                role_type = _moot_role_type(rnd) or "plaintiff"
                chat_bubble(role_name, step_name, content, role_type)

        weak_points = moot_r.get("weak_points", [])
        if weak_points:
            st.markdown(
                f"""
                <div class="card" style="border-left:4px solid {COLORS['danger']};">
                    <div style="font-weight:700;color:{COLORS['text_dark']};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;font-size:0.85rem;">对抗暴露的薄弱环节</div>
                    {''.join(f'<div style="font-size:0.85rem;color:#333;margin-bottom:6px;">- {wp}</div>' for wp in weak_points)}
                </div>
                """,
                unsafe_allow_html=True,
            )
    _render_cached_retrieval("北大法宝 · 抗辩模式类案", external_cache.get("moot_retrieval", {}), "cases", True)


def _render_eval_financial_content(eval_data: dict) -> None:
    external_cache = eval_data.get("external_results", {})
    fin_r = eval_data.get("financial") or {}
    qcc_d = eval_data.get("qcc_data", {})
    fin_score = fin_r.get("score", 0)
    de = fin_r.get("damages_estimate", {})
    te = fin_r.get("time_estimate", {})
    fin_extra = []
    if de:
        fin_extra.append(f"判赔预测: P10=¥{de.get('p10', '-')} / P50=¥{de.get('p50', '-')} / P90=¥{de.get('p90', '-')}" )
    fin_extra.append(f"预估成本: ¥{fin_r.get('cost_estimate', '-')}" )
    if te:
        fin_extra.append(f"时间: 一审{te.get('first_instance_months', '-')}月 + 二审{te.get('second_instance_months', '-')}月 + 执行{te.get('enforcement_months', '-')}月")
    fin_extra.append(f"回款概率: {fin_r.get('recovery_probability', '-')}%")
    dim_card("2.1 财务回报评估", fin_score, fin_r.get("analysis", ""), extra="\n".join(fin_extra))
    _render_dimension_alert(fin_r)

    if qcc_d.get("status") == "completed" and qcc_d.get("stages"):
        stages = qcc_d.get("stages", {})
        metrics = qcc_d.get("metrics", {})
        defend_info = external_cache.get("defendant_info", {})
        b_stage = stages.get("B_基本盘", {})
        d_stage = stages.get("D_风险下钻", {})

        with st.expander("🏢 企查查 · 被告财务画像（实时查询）", expanded=True):
            # ── Phase 1: 被告识别 ──
            if defend_info.get("name"):
                dtype_label = {"enterprise": "企业", "individual": "自然人", "self_employed": "个体户"}.get(
                    defend_info.get("type", ""), defend_info.get("type", ""))
                hints = []
                if defend_info.get("industry_hint"): hints.append(defend_info["industry_hint"])
                if defend_info.get("scale_hint"): hints.append(defend_info["scale_hint"])
                hint_text = f"（{' · '.join(hints)}）" if hints else ""
                st.markdown(f"### 🔍 被告识别\n**{defend_info['name']}** · {dtype_label} {hint_text}")

            # ── 关键项：注册资本 + 被执行 ──
            reg_items = b_stage.get("工商登记", {}).get("_items", [])
            reg_info = reg_items[0] if isinstance(reg_items, list) and reg_items else None
            jdebt_count = d_stage.get("被执行人", {}).get("_count", 0) if d_stage else 0

            if reg_info or jdebt_count is not None:
                st.markdown("### 🔑 关键项")
                k1, k2, k3, k4 = st.columns(4)
                if isinstance(reg_info, dict):
                    capital = reg_info.get("注册资本", reg_info.get("注册资金", "-"))
                    paid = reg_info.get("实缴资本", reg_info.get("实缴资金", "-"))
                    status = reg_info.get("登记状态", reg_info.get("企业状态", "-"))
                    insured = reg_info.get("参保人数", "-")
                    k1.metric("注册资本", f"{capital}", f"实缴{paid}" if paid and paid != capital else "")
                else:
                    k1.metric("注册资本", "-")
                k2.metric("经营状态", status if reg_info else "-")
                k3.metric("参保人数", f"{insured}人" if insured else "-")
                if jdebt_count > 0:
                    k4.metric("被执行", f"{jdebt_count}条", delta_color="inverse")
                else:
                    k4.metric("被执行", "无记录 ✅")

            # ── 摘要 ──
            st.caption(qcc_d.get("_summary", ""))

            # ── QCC 实测指标 ──
            st.markdown("### 📊 QCC 实测指标")
            c1, c2, c3 = st.columns(3)
            c1.metric("回款概率（QCC测算）", f"{metrics.get('recovery_probability', '-')}%")
            c2.metric("判赔方向", metrics.get('damages_adjustment', '-'))
            c3.metric("时间延长", f"+{metrics.get('time_extra_months', 0)}月")

            reds = metrics.get("red_flags", [])
            greens = metrics.get("green_flags", [])
            if reds:
                st.error("🚨 风险信号: " + " | ".join(reds))
            if greens:
                st.success("✅ 利好信号: " + " | ".join(greens))

            # ── 主体锁定 ──
            a = stages.get("A_主体锁定", {})
            if a.get("locked_name"):
                st.markdown("### 🎯 主体锁定")
                st.markdown(f"**{a.get('locked_name')}**（信用代码: {a.get('credit_code', '-')}）")
                candidates = a.get("candidates", [])
                if len(candidates) > 1:
                    with st.expander(f"查看更多候选（{len(candidates)}个）", expanded=False):
                        for c in candidates:
                            st.caption(f"- {c.get('name', '?')}")

            # ── 基本盘 ──
            if b_stage:
                st.markdown("### 📋 基本盘（工商 / 财务 / 人员）")
                b_lines = []
                for label in ("企业简介", "财务数据", "上市信息", "分支机构", "对外投资", "年报", "核心人员", "实际控制人"):
                    v = b_stage.get(label, {})
                    if isinstance(v, dict) and v.get("_count", 0) > 0:
                        b_lines.append(f"- **{label}**: {v.get('_summary', '-')}")
                if b_lines:
                    st.markdown("\n".join(b_lines))

            # ── 风险明细 ──
            c_stage = stages.get("C_风险分诊", {})
            if d_stage:
                st.markdown("### ⚠️ 风险明细")
                risk_hit = []
                for label in ("失信信息", "被执行人", "终本案件", "限高消费", "经营异常", "严重违法",
                              "股权冻结", "动产抵押", "土地抵押", "股权出质", "司法拍卖",
                              "欠税公告", "税收违法", "税务异常", "行政处罚", "惩戒名单", "违约信息",
                              "裁判文书", "法院立案", "限制出境"):
                    v = d_stage.get(label, {})
                    if isinstance(v, dict) and v.get("_count", 0) > 0:
                        risk_hit.append(f"- 🚨 **{label}**: {v.get('_summary', '-')}")
                if risk_hit:
                    st.markdown("\n".join(risk_hit))
                else:
                    st.success("✅ 无命中风险项")
                if c_stage.get("_summary"):
                    st.caption(f"风险分诊: {c_stage['_summary']}")

            # ── 经营规模 ──
            f_stage = stages.get("F_经营规模", {})
            if f_stage:
                st.markdown("### 🏭 经营规模与侵权渠道")
                ch_lines = []
                for label in ("商标资产", "线上店铺", "APP信息", "小程序", "微信公众号", "抖音账号",
                              "招投标", "融资记录", "荣誉信息", "榜单排名", "招聘信息"):
                    v = f_stage.get(label, {})
                    if isinstance(v, dict):
                        ch_lines.append(f"- **{label}**: {v.get('_summary', '-')}")
                if ch_lines:
                    st.markdown("\n".join(ch_lines))
                if f_stage.get("_summary"):
                    st.caption(f"汇总: {f_stage['_summary']}")

            # ── 数据链说明 ──
            st.markdown("---")
            st.caption(
                "📐 **数据链**: 案文 → DeepSeek NER 识别被告 → 企查查 MCP 实时查询 → 回款概率指标 → 注入 DeepSeek 财务分析\n\n"
                "💡 上方「2.1 财务回报评估」卡片中的评分由 DeepSeek 综合北大法宝判赔数据 + 以上企查查实测指标后给出。"
            )

    elif qcc_d.get("_summary"):
        accent_notice(qcc_d.get("_summary"))

    _render_cached_retrieval("北大法宝 · 判赔数据类案", external_cache.get("financial_retrieval", {}), "cases", True)


def _render_eval_precedent_content(eval_data: dict, goal_type: str) -> None:
    external_cache = eval_data.get("external_results", {})
    prec_r = eval_data.get("precedent") or {}
    fin_r = eval_data.get("financial") or {}
    biz_s = eval_data.get("business_score", 0)
    dim_card("2.2 判例价值评估", prec_r.get("score", 0), prec_r.get("analysis", ""), extra=f"首案指数: {prec_r.get('first_case_index', '-')} | 影响力级别: {prec_r.get('influence_level', '-')}")
    _render_dimension_alert(prec_r)
    _render_cached_retrieval("北大法宝 · 首案检索", external_cache.get("precedent_retrieval", {}), "cases", True)
    accent_notice(f"维度二 业务预期综合得分: {biz_s} 分")
    if goal_type == "要钱":
        st.caption(f"公式: 0.9×财务({fin_r.get('score', 0)}) + 0.1×判例({prec_r.get('score', 0)}) = {biz_s}")
    else:
        st.caption(f"公式: 0.1×财务({fin_r.get('score', 0)}) + 0.9×判例({prec_r.get('score', 0)}) = {biz_s}")


def _render_eval_evidence_content(eval_data: dict) -> None:
    evid_r = eval_data.get("evidence") or {}
    evid_s = eval_data.get("evidence_score", 0)
    ev_items = [{"name": item.get("requirement", "未知证据项"), "status": item.get("status", "不足"), "detail": item.get("analysis", "")} for item in evid_r.get("evidence_matrix", [])]
    dim_card(
        "证据就绪度评估",
        evid_r.get("score", 0),
        evid_r.get("analysis", ""),
        sub_items=ev_items,
        extra="补证建议: " + ("; ".join(evid_r.get("remediation_suggestions", ["无"]))) + "\n\n取证技术建议: " + evid_r.get("collection_advice", "根据证据类型自行判断"),
    )
    _render_dimension_alert(evid_r)
    if evid_r.get("status") == "failed":
        accent_notice("证据维度未完成，系统不会输出完整综合建议。")
    else:
        accent_notice(f"维度三 证据就绪度得分: {evid_s} 分")

def _render_eval_compact_summary(eval_data: dict, case_id: str, render_token: str = "base") -> None:
    integrity_info = eval_data.get("integrity", {"is_complete": True, "label": "完整", "critical_issues": []})
    rec_data = eval_data.get("recommendation", {})
    final_s = eval_data.get("final_score")

    with st.container(key=f"eval_result_card_shell_{render_token}"):
        st.markdown(
            """
            <div class="eval-result-header">
                <div>
                    <div class="eval-result-title">最终结果</div>
                    <div class="eval-result-subtitle">展示当前案件的三维得分、综合建议与结果校验状态。</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(4)
        cols[0].metric("法律可行性", eval_data.get("legal_score", 0))
        cols[1].metric("业务预期", eval_data.get("business_score", 0))
        cols[2].metric("证据就绪度", eval_data.get("evidence_score", 0))
        cols[3].metric("综合分", "未生成" if final_s is None else final_s)
        st.caption(f"综合建议：{rec_data.get('recommendation', '待评估')} · 数据完整性：{integrity_info.get('label', '未知')} · 置信度：{eval_data.get('confidence_score', 0)}%")
        if integrity_info.get("critical_issues"):
            accent_notice("关键未完成项：" + "、".join(integrity_info.get("critical_issues", [])))
        if eval_data.get("external_results", {}).get("generated_at"):
            st.caption(f"结果页默认展示缓存数据，最近缓存时间：{eval_data['external_results']['generated_at']}")
        if not _use_mock_mode():
            valid_status = get_validation_status(case_id)
            st.caption(
                f"法条验证：{'通过' if valid_status.get('provisions_validated') else '待验证'} · "
                f"法规识别：{'通过' if valid_status.get('laws_validated') else '待验证'} · "
                f"案号识别：{'通过' if valid_status.get('cases_validated') else '待验证'}"
            )


def _render_eval_detail_card(case_id: str, case, eval_data: dict | None, flow_state: dict, pending_message: str | None = None, render_token: str = "base") -> None:
    selected_step = flow_state.get("current_step") if flow_state.get("running") and flow_state.get("current_step") else flow_state.get("selected_step")
    selected_step = selected_step or EVAL_FLOW_STEPS[0]["id"]
    step_meta = EVAL_FLOW_MAP[selected_step]
    tag_label = "当前进行" if flow_state.get("running") and selected_step == flow_state.get("current_step") else "当前展示"

    with st.container(key=f"eval_detail_card_shell_{render_token}"):
        st.markdown(
            f"""
            <div class="eval-detail-header">
                <div>
                    <div class="eval-detail-title">{step_meta['full_title']}</div>
                    <div class="eval-detail-subtitle">{step_meta['source']}</div>
                </div>
                <div class="eval-detail-tag">{tag_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if pending_message:
            accent_notice(pending_message)

        if not eval_data or not eval_data.get(selected_step):
            empty_state_notice("开始评估后，这里会展示当前环节的详细分析内容。评估完成后，可点击上方已完成节点回看。")
            return

        if selected_step == "rights":
            _render_eval_rights_content(eval_data)
        elif selected_step == "infringement":
            _render_eval_infringement_content(eval_data)
        elif selected_step == "procedure":
            _render_eval_procedure_content(eval_data)
        elif selected_step == "moot":
            if flow_state.get("running") and selected_step == flow_state.get("current_step"):
                _render_eval_moot_live_content(eval_data)
            else:
                _render_eval_moot_content(eval_data)
        elif selected_step == "financial":
            _render_eval_financial_content(eval_data)
        elif selected_step == "precedent":
            _render_eval_precedent_content(eval_data, case.goal_type if case else "要钱")
        elif selected_step == "evidence":
            _render_eval_evidence_content(eval_data)


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

TOP_LEVEL_PAGES = ["工作台", "系统配置", "关于"]
WORKBENCH_PAGES = ["案件列表", "新建案件", "评估分析", "模拟法庭", "评估报告"]
WORKBENCH_PROGRESS = {"新建案件": 1, "案件列表": 2, "评估分析": 3, "模拟法庭": 4, "评估报告": 5}


def _build_workbench_summary() -> dict:
    active_tab = st.session_state.get("workbench_tab", WORKBENCH_PAGES[0])
    current_case_name = st.session_state.get("current_case_name", "尚未选择案件")
    if "current_case_id" in st.session_state:
        case_hint = f"当前案件 ID: {st.session_state['current_case_id']}"
    else:
        case_hint = "先新建案件，或从案件列表中选择一个继续。"

    progress_value = WORKBENCH_PROGRESS.get(active_tab, 1)
    progress_hint = f"工作台当前停留在「{active_tab}」"
    if active_tab == "评估分析":
        progress_hint = "工作台当前聚焦核心评估结果"
    elif active_tab == "模拟法庭":
        progress_hint = "工作台当前聚焦对抗检验"
    elif active_tab == "评估报告":
        progress_hint = "工作台当前聚焦结论与下载输出"

    return {
        "active_tab": active_tab,
        "current_case_name": current_case_name,
        "case_hint": case_hint,
        "progress_text": f"{progress_value}/{len(WORKBENCH_PAGES)}",
        "progress_hint": progress_hint,
    }


def _activate_workbench_tab(target: str) -> None:
    st.session_state["page"] = "工作台"
    st.session_state["workbench_tab"] = target


def render_workbench_tab_row() -> None:
    active_tab = st.session_state.get("workbench_tab", WORKBENCH_PAGES[0])
    container_key = "workbench_tabs_main"
    with st.container(
        key=container_key,
        horizontal=True,
        horizontal_alignment="distribute",
        gap=None,
    ):
        for tab_name in WORKBENCH_PAGES:
            if st.button(
                tab_name,
                key=f"{container_key}_{tab_name}",
                type="primary" if tab_name == active_tab else "secondary",
                use_container_width=True,
            ):
                _activate_workbench_tab(tab_name)
                st.rerun()


def render_workbench_shell() -> None:
    summary = _build_workbench_summary()
    st.markdown(f"""
    <div class="workbench-hero workbench-hero-compact">
        <div class="workbench-stat-card compact">
            <div class="workbench-stat-label">当前案件</div>
            <div class="workbench-stat-value current-case">{summary['current_case_name']}</div>
            <div class="workbench-stat-sub">{summary['case_hint']}</div>
        </div>
        <div class="workbench-stat-card compact">
            <div class="workbench-stat-label">流程位置</div>
            <div class="workbench-stat-value progress-value">{summary['progress_text']}</div>
            <div class="workbench-stat-sub">当前停留在「{summary['active_tab']}」 · {summary['progress_hint']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    render_workbench_tab_row()
    st.markdown("<div class='workbench-shell-gap'></div>", unsafe_allow_html=True)


if "page" not in st.session_state:
    st.session_state["page"] = "工作台"
if "workbench_tab" not in st.session_state:
    st.session_state["workbench_tab"] = "新建案件"
if st.session_state.get("nav_target"):
    target = st.session_state.pop("nav_target")
    if target in WORKBENCH_PAGES:
        _activate_workbench_tab(target)
    elif target in TOP_LEVEL_PAGES:
        st.session_state["page"] = target
    st.rerun()

# 侧边栏品牌区
st.sidebar.markdown("""
<div style="padding:12px 8px 18px 8px;">
    <div style="font-size:1.8rem;font-weight:800;color:#ffffff;letter-spacing:-0.04em;line-height:1;">
        诉算
    </div>
    <div style="font-size:0.72rem;color:rgba(255,255,255,0.68);margin-top:6px;letter-spacing:0.12em;text-transform:uppercase;">
        Soft IP Litigation Eval
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()

for opt in TOP_LEVEL_PAGES:
    is_active = st.session_state["page"] == opt
    if st.sidebar.button(
        opt,
        key=f"nav_{opt}",
        use_container_width=True,
        disabled=is_active,
    ):
        st.session_state["page"] = opt
        st.rerun()

# 侧边栏导航按钮样式：仅保留两级入口，强化当前选中项
st.sidebar.markdown("""
<style>
section[data-testid="stSidebar"] div[data-testid="stButton"] {
    margin: 0 !important;
    padding: 0 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    align-items: center !important;
    padding: 14px 16px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: rgba(255,255,255,0.76) !important;
    border-radius: 14px !important;
    transition: all 0.18s ease !important;
    width: 100% !important;
    min-height: 46px !important;
    line-height: 1.2 !important;
    box-sizing: border-box !important;
}
section[data-testid="stSidebar"] button[kind="secondary"] p,
section[data-testid="stSidebar"] button[kind="secondary"] div {
    text-align: left !important;
    justify-content: flex-start !important;
    width: 100% !important;
    line-height: 1.2 !important;
    color: inherit !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:not(:disabled):hover {
    background: rgba(255,255,255,0.08) !important;
    color: #ffffff !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:disabled {
    background: rgba(214,89,56,0.12) !important;
    color: #ffffff !important;
    cursor: default !important;
    opacity: 1 !important;
    box-shadow: inset 3px 0 0 #d65938 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:disabled p,
section[data-testid="stSidebar"] button[kind="secondary"]:disabled div {
    color: #ffffff !important;
    opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)

top_level_page = st.session_state["page"]
if top_level_page == "工作台":
    render_workbench_shell()
page = st.session_state.get("workbench_tab", WORKBENCH_PAGES[0]) if top_level_page == "工作台" else top_level_page

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
mode_label = RUNTIME_CONFIG["mode_label"]
mode_color = "#d65938" if RUNTIME_CONFIG["use_mock"] else "#a5d8dd"
st.sidebar.markdown(f"""
<div style="font-size:0.72rem;color:#cce8eb;opacity:0.7;">
    <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{mode_color};margin-right:6px;"></span>
    {mode_label}
</div>
<div style="font-size:0.65rem;color:#cce8eb;opacity:0.4;margin-top:4px;">
    v{APP_VERSION} · © 2026 诉算
</div>
""", unsafe_allow_html=True)

if RUNTIME_CONFIG["missing_required"]:
    st.sidebar.markdown(
        f'<div style="margin:10px 0;padding:10px 12px;border:1px solid #d65938;background:#fbe8e3;color:#0d1429;font-size:0.82rem;line-height:1.6;">真实 Demo 模式缺少配置：{"、".join(RUNTIME_CONFIG["missing_required"])}。</div>',
        unsafe_allow_html=True,
    )
for warning in RUNTIME_CONFIG["optional_warnings"]:
    st.sidebar.markdown(
        f'<div style="margin:10px 0;padding:10px 12px;border:1px solid #d65938;background:#fbe8e3;color:#0d1429;font-size:0.82rem;line-height:1.6;">{warning}</div>',
        unsafe_allow_html=True,
    )
if RUNTIME_CONFIG.get("storage_notice"):
    st.sidebar.markdown(
        f'<div style="margin:10px 0;padding:10px 12px;border:1px solid #d65938;background:#fbe8e3;color:#0d1429;font-size:0.82rem;line-height:1.6;">{RUNTIME_CONFIG["storage_notice"]}</div>',
        unsafe_allow_html=True,
    )


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

            submitted = st.form_submit_button("创建案件并进入评估", type="primary", use_container_width=True)

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
                            case_description=full_desc, status="pending"
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
                accent_notice(f"{fname}: {result['error']}")

        evidence_extra_show = st.session_state.get("evidence_text_extra", "")
        if evidence_extra_show:
            accent_notice(f"已追加 {len(evidence_extra_show)} 字证据文本到案情描述")
            if st.button("清除已追加的证据文本", type="secondary"):
                st.session_state["evidence_text_extra"] = ""
                st.rerun()


# ============================================================
# 页面 2: 案件列表
# ============================================================
elif page == "案件列表":
    page_header("案件列表", "查看和管理所有评估案件")

    def _load_case_list():
        db = SessionLocal()
        try:
            cases = db.query(Case).order_by(Case.created_at.desc()).all()
            case_data = []
            for c in cases:
                score = db.query(ScoreSnapshot).filter(
                    ScoreSnapshot.case_id == c.id
                ).order_by(ScoreSnapshot.id.desc()).first()
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
            st.error("案件数据库暂未就绪，请稍后刷新页面重试。")
            accent_notice("如果问题持续存在，我可以继续帮你检查本地数据库连接。")
            st.stop()

    delete_notice = st.session_state.pop("case_delete_notice", None)
    if delete_notice:
        accent_notice(delete_notice)

    if not case_data:
        empty_state_notice("暂无案件，请先创建案件")
    else:
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
                        action_cols = st.columns(2, gap="small")
                        if action_cols[0].button("删除", key=f"d_{c.id}", use_container_width=True, help="删除后会同时清空该案件的评估结果与报告"):
                            db = SessionLocal()
                            try:
                                target_case = db.query(Case).filter(Case.id == c.id).first()
                                if not target_case:
                                    st.error("案件不存在或已删除")
                                else:
                                    _reset_case_outputs(db, c.id)
                                    db.delete(target_case)
                                    db.commit()
                                    _clear_current_case_selection(c.id)
                                    st.session_state["case_delete_notice"] = f"案件“{c.name}”已删除。"
                                    st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"删除失败: {e}")
                            finally:
                                db.close()
                        if action_cols[1].button("查看 →", key=f"v_{c.id}", use_container_width=True):
                            st.session_state["current_case_id"] = c.id
                            st.session_state["current_case_name"] = c.name
                            st.session_state["nav_target"] = "评估分析"
                            st.rerun()


# ============================================================
# 页面 3: 评估分析
# ============================================================
elif page == "评估分析":
    page_header("诉前评估分析", "三维乘法评分模型 · 法律可行性 × 业务预期 × 证据就绪度")

    if "current_case_id" not in st.session_state:
        preview_state = _default_eval_flow_state(selected_step=EVAL_FLOW_STEPS[0]["id"])
        preview_cols = st.columns([1.7, 1.0], gap="medium")
        with preview_cols[0]:
            _render_eval_flow_card("preview", preview_state, interactive=False, render_token="preview")
        with preview_cols[1]:
            _render_moot_status_card("preview", None, preview_state, render_token="preview")
        _render_eval_detail_card("preview", None, None, preview_state, render_token="preview")
        st.stop()

    case_id = st.session_state["current_case_id"]
    case_name = st.session_state.get("current_case_name", "未知案件")

    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            st.error("案件不存在")
            st.stop()

        eval_key = f"eval_results_{case_id}"
        eval_data = st.session_state.get(eval_key) or _load_eval_cache(case_id)
        if eval_data and eval_key not in st.session_state:
            st.session_state[eval_key] = eval_data


        # ���� ������Ϣ������Ƭ ����
        status_text = _case_status_label(case.status)
        st_color = _case_status_text_color(case.status)
        notice_key = f"case_update_notice_{case_id}"
        edit_toggle_key = f"editing_case_{case_id}"

        with st.container(key=f"eval_case_panel_{case_id}"):
            st.html(
                f"""
                <div class="eval-case-summary">
                    <div class="eval-case-summary-main">
                        <div class="eval-case-summary-title">{case_name}</div>
                        <div class="eval-case-summary-meta">
                            ID: {case_id} &nbsp;|&nbsp; 案由: {case.cause_type} &nbsp;|&nbsp; 目标: {case.goal_type}
                            {f' &nbsp;|&nbsp; 客户: {case.client_org}' if case.client_org else ''}
                        </div>
                    </div>
                    <div class="eval-case-summary-status">
                        <span class="status-badge" style="background:{'#ffffff'};color:{st_color};border-color:{st_color};">{status_text}</span>
                    </div>
                </div>
                """
            )

            notice_message = st.session_state.pop(notice_key, None)
            if notice_message:
                accent_notice(notice_message)

            col_edit_action, col_edit_note = st.columns([0.9, 2.1], vertical_alignment="center")
            with col_edit_action:
                edit_label = "关闭编辑" if st.session_state.get(edit_toggle_key, False) else "编辑案件信息"
                if st.button(edit_label, key=f"toggle_edit_case_{case_id}", use_container_width=True):
                    st.session_state[edit_toggle_key] = not st.session_state.get(edit_toggle_key, False)
                    st.rerun()
            with col_edit_note:
                st.markdown(
                    '<div class="eval-case-edit-note">修改案件名称、业务目标或案情描述后，系统会自动清空旧评估结果并将案件状态重置为待评估。</div>',
                    unsafe_allow_html=True,
                )

            if st.session_state.get(edit_toggle_key, False):
                with st.form(f"edit_case_form_{case_id}"):
                    edited_name = st.text_input("案件名称 *", value=case.name or "")
                    edited_client_org = st.text_input("委托客户", value=case.client_org or "")
                    goal_options = ["要钱", "要名"]
                    goal_index = goal_options.index(case.goal_type) if case.goal_type in goal_options else 0
                    edited_goal_type = st.radio("业务目标", goal_options, index=goal_index, horizontal=True)
                    edited_description = st.text_area("案情描述 *", value=case.case_description or "", height=180)

                    col_save, col_cancel = st.columns(2)
                    save_edit = col_save.form_submit_button("保存修改", type="primary", use_container_width=True)
                    cancel_edit = col_cancel.form_submit_button("取消", use_container_width=True)

                    if cancel_edit:
                        st.session_state[edit_toggle_key] = False
                        st.rerun()

                    if save_edit:
                        normalized_name = edited_name.strip()
                        normalized_desc = edited_description.strip()
                        normalized_client = edited_client_org.strip()

                        if not normalized_name or not normalized_desc:
                            st.error("请填写必填项：案件名称、案情描述。")
                        else:
                            requires_reanalysis = any([
                                normalized_name != (case.name or "").strip(),
                                edited_goal_type != (case.goal_type or ""),
                                normalized_desc != (case.case_description or "").strip(),
                            ])

                            try:
                                case.name = normalized_name
                                case.client_org = normalized_client
                                case.goal_type = edited_goal_type
                                case.case_description = normalized_desc
                                if requires_reanalysis:
                                    _reset_case_outputs(db, case_id)
                                    case.status = "pending"
                                db.commit()
                                st.session_state["current_case_name"] = normalized_name
                                st.session_state[edit_toggle_key] = False
                                st.session_state[notice_key] = "案件信息已更新。" + (" 如涉及关键字段变更，系统已清空旧评估结果。" if requires_reanalysis else "")
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error(f"更新失败: {e}")

            with st.expander("查看案情描述", expanded=True):
                st.markdown(case.case_description)

            if case.status in ("completed", "partial") and not eval_data:
                latest = db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case_id).order_by(ScoreSnapshot.id.desc()).first()
                if latest:
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        metric_card("综合得分", "未生成" if latest.final_score is None else f"{latest.final_score}", "分" if latest.final_score is not None else "")
                    with col_m2:
                        metric_card("置信度", f"{latest.confidence_score}%", "")
                    with col_m3:
                        metric_card("建议", latest.recommendation, "", COLORS["primary"])
                    st.markdown("")

            if not RUNTIME_CONFIG["ready"] and not _use_mock_mode():
                st.error("真实 Demo 模式缺少必要配置：" + "、".join(RUNTIME_CONFIG["missing_required"]) + "。当前不允许发起真实评估或刷新外部检索。")

            disable_real_actions = (not RUNTIME_CONFIG["ready"] and not _use_mock_mode())

            # 评估按钮：开始评估 / 刷新外部检索
            col_sp1, col_btn, col_refresh, col_sp2 = st.columns([1, 1.4, 1.4, 1])
            with col_btn:
                btn_label = "重新评估" if eval_data else "开始评估"
                do_eval = st.button(btn_label, type="primary", use_container_width=True, disabled=disable_real_actions)
            with col_refresh:
                do_refresh = st.button(
                    "刷新外部检索",
                    use_container_width=True,
                    disabled=disable_real_actions or not eval_data or _use_mock_mode(),
                    help="会刷新北大法宝/企查查缓存，并更新结果展示。" if not _use_mock_mode() else "Mock 模式下不执行真实外部检索。",
                )

        overview_placeholder = st.empty()
        detail_placeholder = st.empty()
        result_placeholder = st.empty()
        render_counter = {"value": 0}

        def render_eval_workspace(view_data=None, pending_message=None, interactive=True):
            data = view_data if view_data is not None else eval_data
            render_counter["value"] += 1
            render_token = f"{case_id}_{render_counter['value']}"
            flow_state = _ensure_eval_flow_state(case_id, data)
            with overview_placeholder.container():
                top_cols = st.columns([1.7, 1.0], gap="medium")
                with top_cols[0]:
                    _render_eval_flow_card(case_id, flow_state, interactive=interactive and not flow_state.get("running"), render_token=render_token)
                with top_cols[1]:
                    _render_moot_status_card(case_id, data, flow_state, render_token=render_token)
            with detail_placeholder.container():
                _render_eval_detail_card(case_id, case, data, flow_state, pending_message=pending_message, render_token=render_token)
            result_placeholder.empty()
            if data and not flow_state.get("running"):
                with result_placeholder.container():
                    _render_eval_compact_summary(data, case_id, render_token=render_token)
            return flow_state

        render_eval_workspace(eval_data, interactive=bool(eval_data))

        if do_refresh and eval_data:
            latest_report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()
            refreshed_external = _refresh_external_results(case, latest_report.markdown_content if latest_report else "")
            eval_data["external_results"] = refreshed_external
            eval_data["retrieval_status"] = _collect_retrieval_status(refreshed_external)
            eval_data["confidence_score"] = calculate_confidence_score(
                {name: eval_data.get(name, {}) for name in ["rights", "infringement", "procedure", "moot", "financial", "precedent", "evidence"]},
                eval_data["retrieval_status"],
                CRITICAL_DIMENSIONS,
            )
            st.session_state[eval_key] = eval_data
            _save_eval_cache(case_id, eval_data)
            _persist_external_cache(case_id, refreshed_external)
            accent_notice("外部检索缓存已刷新，结果页将继续展示缓存版本。")
            st.rerun()

        # ════════════════════════════════════════════════════
        # 评估执行流水线
        # ════════════════════════════════════════════════════
        if do_eval:
            progress = st.progress(0, "初始化评估引擎...")
            evidence_texts = st.session_state.get("evidence_text_extra", "")
            completed_steps = []
            live_eval_data = {
                "external_results": {},
                "qcc_data": {},
            }

            def sync_eval_step(step_id: str, pending_message: str | None = None):
                _set_eval_flow_state(
                    case_id,
                    running=True,
                    current_step=step_id,
                    completed_steps=completed_steps,
                    selected_step=step_id,
                )
                render_eval_workspace(live_eval_data, pending_message=pending_message, interactive=False)

            # ── 维度一：法律可行性 ──
            sync_eval_step("rights", "正在进行权利基础分析：北大法宝检索法条，并结合案情与证据文本生成判断。")

            # 1.1 权利基础
            external_results = {
                "generated_at": datetime.now().isoformat(),
                "mode": RUNTIME_CONFIG["mode_label"],
            }
            live_eval_data["external_results"] = external_results
            rights_default = {"score": 0, "sub_scores": {}, "analysis": "", "strengths": [], "risks": [], "red_flag": False}
            progress.progress(8, "1/7 权利基础评估...")
            with st.spinner("北大法宝检索法条 -> 模型分析..."):
                pkulaw_rights = _safe_external_call(RETRIEVAL_LABELS["rights_retrieval"], search_for_rights_foundation)
                external_results["rights_retrieval"] = pkulaw_rights
                try:
                    rights_raw = evaluate_rights_foundation(
                        case.case_description,
                        uploaded_texts=evidence_texts,
                        pkulaw_data=pkulaw_rights if pkulaw_rights.get("status") == "completed" else None,
                    )
                except Exception as exc:
                    rights_raw = {"error": str(exc)[:200]}
            rights_result = _build_dimension_result(rights_raw, rights_default, "权利基础")
            live_eval_data["rights"] = rights_result
            live_eval_data["external_results"] = external_results
            completed_steps.append("rights")
            sync_eval_step("rights")

            # 1.2 侵权认定
            sync_eval_step("infringement", "正在进行侵权认定分析：检索类案并校验侵权构成要素。")
            inf_default = {"score": 0, "elements": [], "analysis": "", "strengths": [], "risks": [], "red_flag": False}
            progress.progress(22, "2/7 侵权认定评估...")
            with st.spinner("北大法宝检索类案 -> 五要件分析..."):
                pkulaw_inf = _safe_external_call(RETRIEVAL_LABELS["infringement_retrieval"], search_for_infringement)
                external_results["infringement_retrieval"] = pkulaw_inf
                try:
                    infringement_raw = evaluate_infringement(
                        case.case_description,
                        rights_assessment=str(rights_result.get("analysis", "")),
                        uploaded_texts=evidence_texts,
                        pkulaw_data=pkulaw_inf if pkulaw_inf.get("status") == "completed" else None,
                    )
                except Exception as exc:
                    infringement_raw = {"error": str(exc)[:200]}
            infringement_result = _build_dimension_result(infringement_raw, inf_default, "侵权认定")
            live_eval_data["infringement"] = infringement_result
            live_eval_data["external_results"] = external_results
            completed_steps.append("infringement")
            sync_eval_step("infringement")

            # 1.3 诉讼程序
            sync_eval_step("procedure", "正在进行诉讼程序审查：校验时效、管辖与主体适格等程序条件。")
            proc_default = {"score": 0, "items": [], "analysis": "", "block_items": [], "red_flag": False}
            progress.progress(36, "3/7 程序审查...")
            with st.spinner("北大法宝检索程序法条 -> 程序审查..."):
                pkulaw_proc = _safe_external_call(RETRIEVAL_LABELS["procedure_retrieval"], search_for_procedure)
                external_results["procedure_retrieval"] = pkulaw_proc
                try:
                    procedure_raw = evaluate_procedure(
                        case.case_description,
                        party_info=case.client_org or "",
                        pkulaw_data=pkulaw_proc if pkulaw_proc.get("status") == "completed" else None,
                    )
                except Exception as exc:
                    procedure_raw = {"error": str(exc)[:200]}
            procedure_result = _build_dimension_result(procedure_raw, proc_default, "诉讼程序")
            live_eval_data["procedure"] = procedure_result
            live_eval_data["external_results"] = external_results
            completed_steps.append("procedure")
            sync_eval_step("procedure")

            # 1.4 模拟法庭
            sync_eval_step("moot", "正在进行模拟法庭对抗检验：模拟原告、被告与法官多轮交锋。")
            moot_default = {"correction_coefficient": 1.0, "rounds": [], "judge_summary": "", "defense_strength": 0, "focus_points": [], "weak_points": [], "judge_scores": {}}
            progress.progress(50, "4/7 模拟法庭对抗检验...")
            with st.spinner("北大法宝检索抗辩模式 -> 五步庭审..."):
                pkulaw_moot = _safe_external_call(RETRIEVAL_LABELS["moot_retrieval"], search_for_moot_court)
                external_results["moot_retrieval"] = pkulaw_moot
                try:
                    def on_moot_round(partial_moot: dict, round_index: int, total_rounds: int) -> None:
                        live_eval_data["moot"] = partial_moot
                        live_eval_data["external_results"] = external_results
                        current_round = (partial_moot.get("rounds") or [{}])[-1]
                        current_role = current_round.get("role_name", "角色")
                        current_stage = current_round.get("step_name", "模拟法庭")
                        stage_progress = 50 + int(((round_index + 1) / max(total_rounds, 1)) * 12)
                        progress.progress(min(stage_progress, 62), f"4/7 模拟法庭进行中：{current_stage} · {current_role}")
                        sync_eval_step("moot", f"模拟法庭进行中：{current_stage} · {current_role}")

                    moot_raw = _run_moot_court_with_updates(
                        case.case_description,
                        rights_assessment=str(rights_result.get("analysis", "")),
                        infringement_assessment=str(infringement_result.get("analysis", "")),
                        evidence_summary=evidence_texts[:1500] if evidence_texts else "",
                        on_round=on_moot_round,
                    )
                except Exception as exc:
                    moot_raw = {"error": str(exc)[:200]}
            moot_result = _build_dimension_result(moot_raw, moot_default, "模拟法庭")
            live_eval_data["moot"] = moot_result
            live_eval_data["external_results"] = external_results
            completed_steps.append("moot")
            correction_coeff = moot_result.get("correction_coefficient", 1.0) if moot_result.get("status") != "failed" else 1.0
            live_eval_data["correction_coeff"] = correction_coeff
            sync_eval_step("moot", "模拟法庭已完成，正在汇总对抗结果。")

            legal_score = calculate_legal_feasibility(
                rights_result.get("score", 0),
                infringement_result.get("score", 0),
                procedure_result.get("score", 0),
                correction_coeff,
            )

            live_eval_data["legal_score"] = legal_score
            # 2.1 财务回报
            sync_eval_step("financial", "正在进行财务回报评估：结合企查查画像与判赔类案估算回款空间。")
            fin_default = {"score": 0, "damages_estimate": {}, "cost_estimate": "-", "time_estimate": {}, "recovery_probability": "-", "analysis": ""}
            progress.progress(64, "5/7 财务回报评估...")
            defend_info = _extract_primary_defendant(case.case_description)
            external_results["defendant_info"] = defend_info
            if _use_mock_mode():
                qcc_data = _build_external_failure("企查查被告财务画像", "Mock 模式未调用企查查", status="skipped", include_collections=False)
            elif defend_info.get("status") == "completed" and defend_info.get("name"):
                dname = defend_info.get("name", "")
                dtype = defend_info.get("type", "enterprise")
                with st.spinner(f"企查查调取被告财务画像（{dname}，{'企业' if dtype != 'individual' else '自然人'}）..."):
                    qcc_data = _safe_external_call(
                        "企查查被告财务画像",
                        lambda: search_for_financial_qcc_full(defend_info),
                        include_collections=False,
                    )
            else:
                qcc_data = {
                    "status": "not_applicable",
                    "error": defend_info.get("error", "未识别到被告主体名称"),
                    "_summary": "未识别到被告主体名称，未执行企查查检索",
                    "stages": {},
                    "metrics": {},
                }
            external_results["qcc_data"] = qcc_data

            with st.spinner("北大法宝检索判赔数据 -> 财务预测..."):
                pkulaw_fin = _safe_external_call(RETRIEVAL_LABELS["financial_retrieval"], search_for_financial)
                external_results["financial_retrieval"] = pkulaw_fin
                try:
                    financial_raw = evaluate_financial_return(
                        case.case_description,
                        infringement_severity=str(infringement_result.get("analysis", "")),
                        case_law_references="",
                        pkulaw_data=pkulaw_fin if pkulaw_fin.get("status") == "completed" else None,
                        qcc_data=qcc_data,
                    )
                except Exception as exc:
                    financial_raw = {"error": str(exc)[:200]}
            financial_result = _build_dimension_result(financial_raw, fin_default, "财务回报")
            live_eval_data["financial"] = financial_result
            live_eval_data["qcc_data"] = qcc_data or {}
            live_eval_data["external_results"] = external_results
            completed_steps.append("financial")
            sync_eval_step("financial")

            # 2.2 判例价值
            sync_eval_step("precedent", "正在进行判例价值评估：检索首案价值并判断影响力空间。")
            prec_default = {"score": 0, "first_case_index": "-", "influence_level": "-", "analysis": ""}
            progress.progress(78, "6/7 判例价值评估...")
            with st.spinner("北大法宝首案检索 -> 判例价值判断..."):
                pkulaw_prec = _safe_external_call(RETRIEVAL_LABELS["precedent_retrieval"], lambda: search_for_precedent(case.case_description))
                external_results["precedent_retrieval"] = pkulaw_prec
                try:
                    precedent_raw = evaluate_precedent_value(
                        case.case_description,
                        case_law_references="",
                        pkulaw_data=pkulaw_prec if pkulaw_prec.get("status") == "completed" else None,
                    )
                except Exception as exc:
                    precedent_raw = {"error": str(exc)[:200]}
            precedent_result = _build_dimension_result(precedent_raw, prec_default, "判例价值")
            live_eval_data["precedent"] = precedent_result
            live_eval_data["business_score"] = calculate_business_expectation(financial_result.get("score", 0), precedent_result.get("score", 0), case.goal_type)
            live_eval_data["external_results"] = external_results
            completed_steps.append("precedent")
            sync_eval_step("precedent")

            business_score = calculate_business_expectation(financial_result.get("score", 0), precedent_result.get("score", 0), case.goal_type)

            # 维度三：证据就绪度
            sync_eval_step("evidence", "正在进行证据就绪度评估：逐项检查关键证据是否充足，并生成补证建议。")
            progress.progress(92, "7/7 证据就绪度评估...")
            evid_default = {"score": 0, "evidence_matrix": [], "analysis": "", "missing_items": [], "remediation_suggestions": [], "collection_advice": ""}
            with st.spinner("正在逐项核验证据完整性..."):
                try:
                    evidence_raw = evaluate_evidence_readiness(
                        case.case_description,
                        uploaded_evidence_texts=evidence_texts,
                        evidence_count=0,
                    )
                except Exception as exc:
                    evidence_raw = {"error": str(exc)[:200]}
            evidence_result = _build_dimension_result(evidence_raw, evid_default, "证据就绪度")
            live_eval_data["evidence"] = evidence_result
            live_eval_data["external_results"] = external_results
            completed_steps.append("evidence")
            evidence_score = evidence_result.get("score", 0)
            live_eval_data["evidence_score"] = evidence_score
            sync_eval_step("evidence")

            dimension_results = {
                "rights": rights_result,
                "infringement": infringement_result,
                "procedure": procedure_result,
                "moot": moot_result,
                "financial": financial_result,
                "precedent": precedent_result,
                "evidence": evidence_result,
            }
            integrity = evaluate_data_integrity(dimension_results, CRITICAL_DIMENSIONS)
            retrieval_status = _collect_retrieval_status(external_results)
            confidence_score = calculate_confidence_score(dimension_results, retrieval_status, CRITICAL_DIMENSIONS)
            integrity_payload = _build_integrity_payload(integrity)

            progress.progress(97, "计算综合评分...")
            final_score = calculate_overall_score(legal_score, business_score, evidence_score) if integrity.get("is_complete") else None
            missing_dimensions = integrity_payload.get("critical_issues", [])
            rec = generate_recommendation(final_score, procedure_result.get("items", []), integrity.get("is_complete"), missing_dimensions)

            action_items = []
            if integrity_payload.get("critical_issues"):
                action_items.append("优先完成以下关键维度：" + "、".join(integrity_payload["critical_issues"]))
            for suggestion in evidence_result.get("remediation_suggestions", [])[:2]:
                action_items.append(suggestion)

            rule_results_for_verif = [
                {
                    "rule_name": it.get("name", "未知程序项"),
                    "severity": it.get("status", "warning") if it.get("status") in ("pass", "warning", "block") else "warning",
                    "result": it.get("detail", ""),
                    "reason": it.get("detail", ""),
                }
                for it in procedure_result.get("items", [])
            ]
            report_score_payload = {
                "legal_feasibility": legal_score,
                "business_expectation": business_score,
                "evidence_readiness": evidence_score,
                "final_score": final_score,
                "recommendation": rec["recommendation"],
                "confidence_score": confidence_score,
                "reason": rec["reason"],
                "action_items": action_items,
                "data_integrity": integrity_payload,
            }
            legal_analysis_payload = {
                "elements": [
                    {"element": "权利基础", "score": rights_result.get("score", 0), "analysis": rights_result.get("analysis", ""), "evidence_status": "-", "risks": rights_result.get("risks", [])},
                    {"element": "侵权认定", "score": infringement_result.get("score", 0), "analysis": infringement_result.get("analysis", ""), "evidence_status": "-", "risks": infringement_result.get("risks", [])},
                    {"element": "诉讼程序", "score": procedure_result.get("score", 0), "analysis": procedure_result.get("analysis", ""), "evidence_status": "-", "risks": procedure_result.get("block_items", [])},
                ]
            }
            report_md_pre = generate_markdown_report(
                {"name": case.name, "cause_type": case.cause_type, "goal_type": case.goal_type, "client_org": case.client_org},
                report_score_payload,
                rule_results_for_verif,
                legal_analysis_payload,
            )

            if _use_mock_mode():
                vresult = _build_external_failure("北大法宝防幻觉验证", "Mock 模式未执行防幻觉验证", status="skipped", include_collections=False)
                vresult["summary"] = {"laws_verified": False, "cases_verified": False, "laws_found": 0, "cases_found": 0, "hallucinations": []}
            else:
                with st.spinner("北大法宝防幻觉验证（adjust_provisions -> law_recognition -> anhao_recognition）..."):
                    vresult = _safe_external_call("北大法宝防幻觉验证", lambda: run_verification_phase(report_md_pre), include_collections=False)
            vs = vresult.get("summary", {"laws_verified": False, "cases_verified": False, "laws_found": 0, "cases_found": 0, "hallucinations": []})
            external_results["verification"] = vresult
            if isinstance(vresult, dict):
                for key in ("adjust_provisions", "law_recognition", "anhao_recognition"):
                    if key in vresult:
                        external_results[key] = vresult.get(key)

            st.markdown("---")
            if vresult.get("status") == "skipped":
                accent_notice(vresult.get("_summary", "当前模式未执行防幻觉验证。"))
            else:
                with st.expander("北大法宝 · 防幻觉验证", expanded=True):
                    col_v1, col_v2, col_v3, col_v4 = st.columns(4)
                    with col_v1:
                        st.metric("法条校验", "通过" if vs.get("laws_verified") else "待复查", delta=f"识别{vs.get('laws_found', 0)}条" if vs.get("laws_found") else "未引用")
                    with col_v2:
                        st.metric("案号校验", "通过" if vs.get("cases_verified") else "待复查", delta=f"{vs.get('cases_found', 0)}案号" if vs.get("cases_found") else "0案号")
                    with col_v3:
                        hall_count = len(vs.get("hallucinations", []))
                        st.metric("幻觉排查", "通过" if not hall_count else "待复查", delta="无" if not hall_count else f"{hall_count}条")
                    with col_v4:
                        st.metric("总体", "完整" if integrity.get("is_complete") else "部分完成")
                    for hallucination in vs.get("hallucinations", []):
                        accent_notice(hallucination)

            rule_results_for_report = [
                {
                    "rule_name": it.get("name", "未知程序项"),
                    "severity": it.get("status", "warning") if it.get("status") in ("pass", "warning", "block") else {"满足": "pass", "存疑": "warning", "不满足": "block"}.get(it.get("status", "存疑"), "warning"),
                    "result": it.get("detail", ""),
                    "reason": it.get("detail", ""),
                }
                for it in procedure_result.get("items", [])
            ]
            report_md = generate_markdown_report(
                {"name": case.name, "cause_type": case.cause_type, "goal_type": case.goal_type, "client_org": case.client_org},
                report_score_payload,
                rule_results_for_report,
                legal_analysis_payload,
            )

            hall_count = len(vs.get("hallucinations", []))
            verification_section = f"""

## 七、北大法宝防幻觉验证

- 法条校验: {vs.get('laws_found', 0)} 条
- 案号校验: {vs.get('cases_found', 0)} 个
- 幻觉排查: {'通过' if not hall_count else f'发现 {hall_count} 处可疑引用'}
"""
            report_md += verification_section

            if not _use_mock_mode():
                try:
                    legal_analysis_text = (
                        f"权利基础：{rights_result.get('analysis', '')}。"
                        f"侵权认定：{infringement_result.get('analysis', '')}。"
                        f"诉讼程序：{procedure_result.get('analysis', '')}。"
                    )
                    enhance_resp = get_linked_content(legal_analysis_text[:3000])
                    if enhance_resp and "result" in enhance_resp:
                        structured = enhance_resp["result"].get("structuredContent", enhance_resp["result"])
                        linked_text = structured.get("result", "") if isinstance(structured, dict) else str(structured)
                        if linked_text:
                            report_md += f"""

## 八、法律分析（法宝超链增强版）

{linked_text}
"""
                except Exception:
                    pass

            eval_data = {
                "rights": rights_result,
                "infringement": infringement_result,
                "procedure": procedure_result,
                "moot": moot_result,
                "financial": financial_result,
                "precedent": precedent_result,
                "evidence": evidence_result,
                "qcc_data": qcc_data or {},
                "external_results": external_results,
                "retrieval_status": retrieval_status,
                "integrity": integrity_payload,
                "legal_score": legal_score,
                "business_score": business_score,
                "evidence_score": evidence_score,
                "confidence_score": confidence_score,
                "final_score": final_score,
                "recommendation": rec,
                "correction_coeff": correction_coeff,
                "report_markdown": report_md,
            }
            live_eval_data = eval_data
            st.session_state[eval_key] = eval_data
            _save_eval_cache(case_id, eval_data)
            _persist_external_cache(case_id, external_results)
            for key, value in [("rights", rights_result), ("infringement", infringement_result), ("procedure", procedure_result), ("moot", moot_result), ("financial", financial_result), ("precedent", precedent_result), ("evidence", evidence_result)]:
                st.session_state[f"{key}_{case_id}"] = value

            db.add(
                ScoreSnapshot(
                    case_id=case_id,
                    legal_score=legal_score,
                    business_score=business_score,
                    evidence_score=evidence_score,
                    confidence_score=confidence_score,
                    final_score=final_score,
                    recommendation=rec["recommendation"],
                )
            )
            db.commit()

            report_dir = RUNTIME_DIR / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            md_path = report_dir / f"{case_id}_report.md"
            md_path.write_text(report_md, encoding="utf-8")
            db.add(Report(case_id=case_id, report_type="评估报告", markdown_content=report_md, pdf_uri=str(md_path)))
            case.status = "completed" if integrity.get("is_complete") else "partial"
            db.commit()

            if not _use_mock_mode():
                deepseek_results = {
                    "rights": rights_result,
                    "infringement": infringement_result,
                    "procedure": procedure_result,
                    "financial": financial_result,
                    "precedent": precedent_result,
                    "evidence": evidence_result,
                }
                generate_all_queries(case_id, case.case_description, deepseek_results)

            _set_eval_flow_state(
                case_id,
                running=False,
                current_step=None,
                completed_steps=completed_steps,
                selected_step=completed_steps[-1] if completed_steps else EVAL_FLOW_STEPS[0]["id"],
            )
            render_eval_workspace(eval_data, interactive=True)

            progress.progress(100, "评估完成")
            if integrity.get("is_complete"):
                accent_notice("评估完成，结果页将继续展示本次缓存结果。")
            else:
                accent_notice("评估已结束，但存在未完成关键维度；系统未输出完整综合结论。")
            accent_notice("评估报告已生成，请切换到「评估报告」标签页查看完整报告。")
            st.rerun()        # ════════════════════════════════════════════════════
    finally:
        db.close()

# ============================================================
elif page == "模拟法庭":
    page_header("模拟法庭", "固定脚本庭审复现 · 查看已完成评估案件的庭审记录与法官归纳")

    if "current_case_id" not in st.session_state:
        empty_state_notice("请先在「案件列表」中选择一个案件")
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
                ID: {case_id} | 案由: {case.cause_type} | 模式: {'Mock 模拟' if _use_mock_mode() else 'DeepSeek API'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        eval_key = f"eval_results_{case_id}"
        eval_data = st.session_state.get(eval_key) or _load_eval_cache(case_id) or {}
        if eval_data and eval_key not in st.session_state:
            st.session_state[eval_key] = eval_data

        moot_key = f"moot_{case_id}"
        moot_result = (eval_data.get("moot") if isinstance(eval_data, dict) else None) or st.session_state.get(moot_key)

        if moot_result and moot_result.get("rounds"):
            coeff = moot_result.get("correction_coefficient", 1.0)
            ds = moot_result.get("defense_strength", 50)
            accent_notice(f"已生成庭审复现报告 | 修正系数: {coeff:.2f} | 抗辩强度: {ds}/100")
            st.caption("本页仅复现已完成评估案件的模拟法庭结果，不再单独启动一次模拟法庭。")
        elif moot_result and moot_result.get("error"):
            accent_notice(f"当前案件的模拟法庭结果未完整生成：{moot_result.get('error', '未知错误')}")
        else:
            empty_state_notice("当前案件尚未生成模拟法庭复现结果。请先在「评估分析」中完成整案评估，系统会自动生成并缓存模拟法庭报告。")

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
            progress_segments = []
            for i, step_name in enumerate(step_names):
                completed = i < len(rounds)
                border_color = "#0d1429" if completed else "#e5e5e5"
                text_color = "#0d1429" if completed else "#cccccc"
                fill_color = "#0d1429" if completed else "transparent"
                step_weight = "600" if completed else "400"
                step_index_html = f'<span style="color:#fff;">{i + 1}</span>' if completed else str(i + 1)
                progress_segments.append(
                    f'<div style="flex:1;text-align:center;position:relative;">'
                    f'<div style="width:32px;height:32px;border:2px solid {border_color};border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700;color:{text_color};background:{fill_color};">{step_index_html}</div>'
                    f'<div style="font-size:0.72rem;color:{text_color};margin-top:6px;font-weight:{step_weight};">{step_name}</div>'
                    "</div>"
                )
                if i < len(step_names) - 1:
                    connector_color = "#0d1429" if completed else "#e5e5e5"
                    progress_segments.append(f'<div style="flex:0.3;height:2px;background:{connector_color};"></div>')
            st.markdown(
                f'<div style="margin:20px 0;padding:16px 0;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;"><div style="display:flex;justify-content:space-between;align-items:center;">{"".join(progress_segments)}</div></div>',
                unsafe_allow_html=True,
            )
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
                    chat_bubble(role_name, step_name, content, role_type, truncate=200)
                elif 'defendant' in str(role) or '被告' in str(role_name):
                    role_type = "defendant"
                    chat_bubble(role_name, step_name, content, role_type, truncate=200)
                else:
                    role_type = "judge"
                    chat_bubble(role_name, step_name, content, role_type)

            # 法官归纳摘要 — 高亮显示（焦点章节）
            judge_summary = moot_result.get('judge_summary', '')
            if judge_summary:
                st.markdown("")
                st.markdown(f"""
                <div class="card" style="border:3px solid {COLORS['accent']};background:linear-gradient(135deg, #fffaf0 0%, #ffffff 100%);margin-top:24px;padding:18px 22px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
                        <span style="font-size:1.4rem;">⚖️</span>
                        <span style="font-size:1.1rem;font-weight:800;color:{COLORS['accent']};letter-spacing:-0.01em;">法官最终判决</span>
                    </div>
                    <div style="font-size:0.95rem;color:#222;line-height:1.9;white-space:pre-wrap;">{judge_summary}</div>
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
                    accent_notice(f"<strong>修正系数推理：</strong>{reasoning}")

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
        empty_state_notice("请先在「案件列表」中选择一个已评估的案件")
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
            empty_state_notice("该案件尚未评估，请先进行评估")
            st.stop()

        report_eval_data = st.session_state.get(f"eval_results_{case_id}") or _load_eval_cache(case_id) or {}
        integrity_info = report_eval_data.get("integrity", {
            "is_complete": score.final_score is not None,
            "label": "完整" if score.final_score is not None else "部分完成",
            "critical_issues": [],
            "optional_issues": [],
        })
        report_content = report.markdown_content if report else report_eval_data.get("report_markdown", "")
        legal_score_value = int(score.legal_score or 0)
        business_score_value = int(score.business_score or 0)
        evidence_score_value = int(score.evidence_score or 0)
        final_score_display = "未生成" if score.final_score is None else str(score.final_score)
        final_score_suffix = "" if score.final_score is None else "/100"

        # 顶部摘要
        rec_color = {"建议起诉": COLORS["success"], "补证后起诉": COLORS["warning"], "评估未完成": COLORS["warning"], "暂不建议起诉": COLORS["danger"], "暂缓起诉": COLORS["danger"]}.get(score.recommendation, COLORS["primary"])

        st.markdown(f"""
        <div class="card" style="border-left:6px solid {rec_color};">
            <div style="font-size:0.72rem;color:{COLORS['text_muted']};margin-bottom:4px;text-transform:uppercase;letter-spacing:0.08em;">{case.cause_type} · 评估报告</div>
            <div style="font-size:1.5rem;font-weight:800;color:{COLORS['text_dark']};letter-spacing:-0.02em;">{case.name}</div>
            <div style="margin-top:16px;display:flex;gap:40px;flex-wrap:wrap;">
                <div><span style="font-size:0.7rem;color:{COLORS['text_muted']};text-transform:uppercase;letter-spacing:0.05em;">综合评分</span><br>
                     <span style="font-size:3rem;font-weight:800;color:{rec_color};letter-spacing:-0.04em;">{final_score_display}</span>
                     <span style="color:{COLORS['text_muted']};font-size:0.9rem;">{final_score_suffix}</span></div>
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
                "法律可行性": legal_score_value,
                "业务预期": business_score_value,
                "证据就绪度": evidence_score_value
            })
            st.markdown(radar_html, unsafe_allow_html=True)

        with col_bars:
            st.markdown("##### 各维度得分详情")
            score_bar("法律可行性", legal_score_value, COLORS["primary"], "权利 × 侵权 × 程序 × 对抗修正")
            score_bar("业务预期", business_score_value, COLORS["warning"], "要钱/要名自适应加权")
            score_bar("证据就绪度", evidence_score_value, COLORS["success"], "证据完整性与补证")
            st.divider()
            st.markdown(f"**乘法模型**: {legal_score_value} × {business_score_value} × {evidence_score_value} = **{final_score_display}**")
            st.caption(f"置信度: {score.confidence_score}% · 一票否决逻辑")

        # 完整报告
        st.markdown("---")
        st.markdown("##### 完整评估报告")
        if report_content:
            st.markdown(report_content)
        else:
            accent_notice("报告内容未保存")

        # 下载区域
        st.markdown("---")
        st.markdown("##### 📥 下载总结文档")

        radar_svg_str = render_radar_svg({
            "法律可行性": legal_score_value,
            "业务预期": business_score_value,
            "证据就绪度": evidence_score_value
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
<div class="score-big">{final_score_display}{" / 100" if final_score_suffix else ""}</div>
<div class="rec">{score.recommendation}</div>

<h2>二、三维评分总览</h2>
<div style="text-align:center;margin:24px 0">{radar_svg_str}</div>
<table>
<tr><th>维度</th><th>得分</th><th>说明</th></tr>
<tr><td>法律可行性</td><td>{score.legal_score}/100</td><td>权利 × 侵权 × 程序 × 对抗修正</td></tr>
<tr><td>业务预期</td><td>{score.business_score}/100</td><td>要钱/要名自适应加权</td></tr>
<tr><td>证据就绪度</td><td>{score.evidence_score}/100</td><td>证据完整性与补证</td></tr>
<tr><td><strong>综合得分（乘法模型）</strong></td><td><strong>{final_score_display}{final_score_suffix}</strong></td><td>一票否决逻辑</td></tr>
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
            pdf_bytes = generate_pdf_bytes(report_content if report_content else summary_html)
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
# 页面 6: 系统配置
# ============================================================
elif page == "系统配置":
    page_header("系统配置", "运行模式与外部服务参数管理")

    current_settings = get_runtime_settings()
    current_status = get_runtime_configuration_status()
    saved_mode_label = "Mock 模拟模式" if current_settings["use_mock"] else "真实 Demo 模式"
    mode_options = ["Mock 模拟模式", "真实 Demo 模式"]
    if st.session_state.get("system_config_mode_saved") != saved_mode_label:
        st.session_state["system_config_mode_preview"] = saved_mode_label
        st.session_state["system_config_mode_saved"] = saved_mode_label
    preview_mode_label = st.session_state.get("system_config_mode_preview", saved_mode_label)
    is_mock_mode = preview_mode_label == "Mock 模拟模式"

    st.markdown(f"""
    <div class="card" style="border-left:4px solid {COLORS['accent']};">
        <div style="font-size:1.05rem;font-weight:700;color:{COLORS['primary']};">本地配置中心</div>
        <div style="font-size:0.88rem;color:{COLORS['text_body']};margin-top:10px;line-height:1.8;">
            系统配置页用于维护当前机器上的运行参数。配置会写入本地 <code>.env</code> 文件，不会提交到仓库，也不会在页面中回显凭证明文。
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_form, col_status = st.columns([1.2, 0.8], gap="large")

    with col_form:
        form_section_title("运行配置")
        st.radio(
            "运行模式",
            mode_options,
            key="system_config_mode_preview",
            horizontal=True,
        )
        preview_mode_label = st.session_state.get("system_config_mode_preview", saved_mode_label)
        is_mock_mode = preview_mode_label == "Mock 模拟模式"

        with st.form("system_config_form"):
            st.markdown("**模型提供方**")
            st.caption("DeepSeek（固定，不可更换）")
            base_url = st.text_input(
                "DeepSeek Base URL",
                value=current_settings["deepseek_base_url"],
                placeholder="https://api.deepseek.com",
                disabled=is_mock_mode,
            )
            if is_mock_mode:
                st.caption("当前为 Mock 模式，真实服务配置已锁定。")
            else:
                st.caption("DeepSeek API Key：已配置。留空保存会保留现有 Key。" if current_status["api_key_configured"] else "DeepSeek API Key：未配置。")
            api_key_input = st.text_input(
                "DeepSeek API Key",
                value="",
                type="password",
                placeholder="留空则保留现有 API Key" if not is_mock_mode else "Mock 模式下无需填写",
                disabled=is_mock_mode,
            )
            clear_api_key = st.checkbox("保存时清空当前 DeepSeek API Key", disabled=is_mock_mode)

            st.markdown("**外部检索服务**")
            st.caption("企查查 Token：已配置。留空保存会保留现有 Token。" if current_status["qcc_api_token_configured"] else "企查查 Token：未配置。")
            qcc_api_token_input = st.text_input(
                "企查查 Token",
                value="",
                type="password",
                placeholder="留空则保留现有企查查 Token" if not is_mock_mode else "Mock 模式下无需填写",
                disabled=is_mock_mode,
            )
            clear_qcc_api_token = st.checkbox("保存时清空当前企查查 Token", disabled=is_mock_mode)

            st.caption("北大法宝 Token：已配置。留空保存会保留现有 Token。" if current_status["pkulaw_api_token_configured"] else "北大法宝 Token：未配置。")
            pkulaw_api_token_input = st.text_input(
                "北大法宝 Token",
                value="",
                type="password",
                placeholder="留空则保留现有北大法宝 Token" if not is_mock_mode else "Mock 模式下无需填写",
                disabled=is_mock_mode,
            )
            clear_pkulaw_api_token = st.checkbox("保存时清空当前北大法宝 Token", disabled=is_mock_mode)
            submitted = st.form_submit_button("保存配置", type="primary", use_container_width=True)

        if submitted:
            validation_errors = []
            if clear_api_key and api_key_input.strip():
                validation_errors.append("已勾选清空 DeepSeek API Key 时，请不要同时输入新的 Key。")
            if clear_qcc_api_token and qcc_api_token_input.strip():
                validation_errors.append("已勾选清空企查查 Token 时，请不要同时输入新的 Token。")
            if clear_pkulaw_api_token and pkulaw_api_token_input.strip():
                validation_errors.append("已勾选清空北大法宝 Token 时，请不要同时输入新的 Token。")

            if validation_errors:
                for message in validation_errors:
                    st.error(message)
            else:
                final_api_key = "" if clear_api_key else (api_key_input.strip() or current_settings["deepseek_api_key"])
                final_qcc_api_token = "" if clear_qcc_api_token else (qcc_api_token_input.strip() or current_settings["qcc_api_token"])
                final_pkulaw_api_token = "" if clear_pkulaw_api_token else (pkulaw_api_token_input.strip() or current_settings["pkulaw_api_token"])
                save_runtime_settings(
                    use_mock=(preview_mode_label == "Mock 模拟模式"),
                    llm_provider="deepseek",
                    deepseek_api_key=final_api_key,
                    deepseek_base_url=base_url.strip() or "https://api.deepseek.com",
                    qcc_api_token=final_qcc_api_token,
                    pkulaw_api_token=final_pkulaw_api_token,
                )
                accent_notice("系统配置已保存。当前页面会立即按新配置重新加载。")
                st.rerun()

    with col_status:
        form_section_title("当前状态")
        metric_cols = st.columns(2)
        with metric_cols[0]:
            metric_card("运行模式", current_status["mode_label"], "")
        with metric_cols[1]:
            metric_card("配置状态", "就绪" if current_status["ready"] else "待补充", "")

        service_cols_top = st.columns(2)
        with service_cols_top[0]:
            metric_card("DeepSeek", "已配置" if current_status["api_key_configured"] else "未配置", "")
        with service_cols_top[1]:
            metric_card("企查查", "已配置" if current_status["qcc_api_token_configured"] else "未配置", "")
        service_cols_bottom = st.columns(2)
        with service_cols_bottom[0]:
            metric_card("北大法宝", "已配置" if current_status["pkulaw_api_token_configured"] else "未配置", "")

        if not current_status["ready"]:
            empty_state_notice("真实 Demo 模式下需要先配置 DeepSeek API Key，保存后即可发起真实评估。")

        if current_status.get("storage_notice"):
            accent_notice(current_status["storage_notice"])

        for warning in current_status["optional_warnings"]:
            accent_notice(warning)

        st.caption(f"用户数据目录：{current_status['preferred_user_data_dir']}")
        st.caption(f"安装目录：{current_status['install_dir']}")
        st.caption(f"当前实际生效目录：{current_status['user_data_dir']}")
        st.caption("配置文件、数据库、缓存都会写入当前实际生效目录。")

        test_disabled = current_settings["use_mock"] or not current_status["api_key_configured"]
        if current_settings["use_mock"]:
            test_help = "Mock 模式下不调用真实 DeepSeek，无法测试连接。"
        elif not current_status["api_key_configured"]:
            test_help = "请先保存 DeepSeek API Key，再测试连接。"
        else:
            test_help = "测试当前已保存的 DeepSeek 配置是否可用。"
        with st.container(key="system_config_status_actions"):
            if st.button("测试 DeepSeek 连接", use_container_width=True, disabled=test_disabled, help=test_help):
                with st.spinner("正在测试 DeepSeek API 连接..."):
                    if llm_client.check_api_connection():
                        accent_notice("连接成功，真实 Demo 模式已可用。")
                    else:
                        st.error("连接失败。请检查 API Key、Base URL 或网络环境。")


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





