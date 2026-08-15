from typing import Optional
"""
缓存管理模块 — 案件评估结果和外部检索数据的文件缓存。

所有缓存文件均存储在 RUNTIME_DIR 下，纯文件 I/O，无 Streamlit 依赖。
"""
import json
from pathlib import Path
from config import RUNTIME_DIR

def eval_cache_path(case_id: str) -> Path:
    """评估结果缓存文件路径"""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / f'eval_results_{case_id}.json'

def load_eval_cache(case_id: str) -> Optional[dict]:
    """加载评估结果缓存，文件不存在或解析失败返回 None"""
    path = eval_cache_path(case_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None

def save_eval_cache(case_id: str, payload: dict) -> None:
    """保存评估结果到缓存文件"""
    eval_cache_path(case_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

def pkulaw_cache_path(case_id: str) -> Path:
    """北大法宝检索结果缓存文件路径"""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / f'pkulaw_results_{case_id}.json'

def clear_case_cache_files(case_id: str) -> None:
    """
    清理案件相关的所有缓存文件（评估缓存、PKULaw 缓存、报告）。
    仅删除文件，不涉及 session_state。
    """
    paths = (eval_cache_path(case_id), pkulaw_cache_path(case_id), RUNTIME_DIR / 'reports' / f'{case_id}_report.md')
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass