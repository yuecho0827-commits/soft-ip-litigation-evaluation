"""
外部服务调用编排 — 北大法宝、企查查的检索和验证流程。

所有函数通过参数注入依赖，不直接依赖 Streamlit 或 app.py 全局变量。
"""
from datetime import datetime
from typing import Callable

def build_external_call_dict(retrieval_labels: dict[str, str], search_rights: Callable, search_infringement: Callable, search_procedure: Callable, search_moot_court: Callable, search_financial: Callable, search_precedent: Callable, safe_external_call: Callable) -> dict:
    """构建六项北大法宝检索的初始结果字典"""
    return {'rights_retrieval': safe_external_call(retrieval_labels['rights_retrieval'], search_rights), 'infringement_retrieval': safe_external_call(retrieval_labels['infringement_retrieval'], search_infringement), 'procedure_retrieval': safe_external_call(retrieval_labels['procedure_retrieval'], search_procedure), 'moot_retrieval': safe_external_call(retrieval_labels['moot_retrieval'], search_moot_court), 'financial_retrieval': safe_external_call(retrieval_labels['financial_retrieval'], search_financial), 'precedent_retrieval': safe_external_call(retrieval_labels['precedent_retrieval'], lambda: search_precedent(case_description or ''))}

def extract_defendant_info_result(case_description: str, extract_defendant_info_fn: Callable, use_mock: bool) -> dict:
    """
    从案情描述中提取主被告信息。
    返回格式：{name, type, status: "completed"/"failed", error?}
    """
    if use_mock:
        result = extract_defendant_info_fn(case_description)
        defendant = (result.get('defendants') or [{}])[0]
        defendant['status'] = 'completed'
        return defendant
    try:
        phase1 = extract_defendant_info_fn(case_description)
        defendants = phase1.get('defendants', [])
        if not defendants:
            return {'status': 'failed', 'error': '未识别到被告主体'}
        for item in defendants:
            if isinstance(item, dict) and item.get('role') == 'primary_defendant':
                item['status'] = 'completed'
                return item
        first = defendants[0]
        first['status'] = 'completed'
        return first
    except Exception as exc:
        return {'status': 'failed', 'error': str(exc)[:200]}

def build_external_results(search_rights: Callable, search_infringement: Callable, search_procedure: Callable, search_moot_court: Callable, search_financial: Callable, search_precedent: Callable, safe_external_call: Callable, build_external_failure: Callable, extract_defendant_info_fn: Callable, search_financial_qcc: Callable, run_verification_phase: Callable, retrieval_labels: dict[str, str], mode_label: str, use_mock: bool, case_description: str, report_markdown: str='') -> dict:
    """
    编排完整的外部服务调用流程：北大法宝检索 → 被告提取 → 企查查画像 → 防幻觉验证。

    所有外部依赖通过参数注入，使函数本身可测试。
    """
    external = {'generated_at': datetime.now().isoformat(), 'mode': mode_label, 'rights_retrieval': safe_external_call(retrieval_labels['rights_retrieval'], search_rights), 'infringement_retrieval': safe_external_call(retrieval_labels['infringement_retrieval'], search_infringement), 'procedure_retrieval': safe_external_call(retrieval_labels['procedure_retrieval'], search_procedure), 'moot_retrieval': safe_external_call(retrieval_labels['moot_retrieval'], search_moot_court), 'financial_retrieval': safe_external_call(retrieval_labels['financial_retrieval'], search_financial), 'precedent_retrieval': safe_external_call(retrieval_labels['precedent_retrieval'], lambda: search_precedent(case_description))}
    defendant = extract_defendant_info_result(case_description, extract_defendant_info_fn, use_mock)
    external['defendant_info'] = defendant
    if use_mock:
        external['qcc_data'] = build_external_failure('企查查被告财务画像', 'Mock 模式未调用企查查', status='skipped', include_collections=False)
        external['verification'] = build_external_failure('北大法宝防幻觉验证', 'Mock 模式未执行防幻觉验证', status='skipped', include_collections=False)
        return external
    if defendant.get('status') == 'completed' and defendant.get('name'):
        qcc_data = safe_external_call('企查查被告财务画像', lambda: search_financial_qcc(defendant), include_collections=False)
    else:
        qcc_data = {'status': 'not_applicable', 'error': defendant.get('error', '未识别到被告主体名称'), '_summary': '未识别到被告主体名称，未执行企查查检索', 'metrics': {}, 'stages': {}}
    external['qcc_data'] = qcc_data
    if report_markdown:
        external['verification'] = safe_external_call('北大法宝防幻觉验证', lambda: run_verification_phase(report_markdown), include_collections=False)
        verification = external.get('verification', {})
        for key in ('adjust_provisions', 'law_recognition', 'anhao_recognition'):
            if key in verification:
                external[key] = verification.get(key)
    else:
        external['verification'] = {'status': 'not_run', 'error': None, '_summary': '尚未执行防幻觉验证', 'summary': {}}
    return external