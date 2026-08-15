"""
评分引擎 - 严格按 v1 产品方案的三维乘法模型
法律可行性 = 权利基础 × 侵权认定 × 诉讼程序 × 对抗修正系数
业务预期  = if 要钱: 0.9×财务+0.1×判例 / if 要名: 0.1×财务+0.9×判例
主诉决策总分 = 法律可行性 × 业务预期 × 证据就绪度
"""
from typing import Dict, Any, Iterable, Optional

def normalize(score, scale=100):
    """归一化到 0-1 范围"""
    return max(0, min(score, scale)) / scale

def calculate_legal_feasibility(rights_score: float, infringement_score: float, procedure_score: float, correction_coefficient: float=1.0) -> float:
    """
    法律可行性 = 权利基础 × 侵权认定 × 诉讼程序 × 对抗修正系数
    乘法模型，体现"一票否决"逻辑
    """
    r = normalize(rights_score)
    i = normalize(infringement_score)
    p = normalize(procedure_score)
    c = max(0.7, min(correction_coefficient, 1.3))
    return round(r * i * p * c * 100, 1)

def calculate_business_expectation(financial_score: float, precedent_score: float, goal_type: str) -> float:
    """
    业务预期 = 自适应权重（根据业务目标分流）
    要钱 → 0.9×财务 + 0.1×判例
    要名 → 0.1×财务 + 0.9×判例
    """
    f = normalize(financial_score)
    p = normalize(precedent_score)
    if goal_type == '要钱':
        return round((0.9 * f + 0.1 * p) * 100, 1)
    return round((0.1 * f + 0.9 * p) * 100, 1)

def calculate_overall_score(legal_feasibility: float, business_expectation: float, evidence_readiness: float) -> float:
    """
    主诉决策总分 = 法律可行性 × 业务预期 × 证据就绪度
    """
    l = normalize(legal_feasibility)
    b = normalize(business_expectation)
    e = normalize(evidence_readiness)
    return round(l * b * e * 100, 1)

def evaluate_data_integrity(dimension_results: Dict[str, Dict[str, Any]], critical_dimensions: Optional[Iterable[str]]=None) -> Dict[str, Any]:
    """按维度完成状态生成数据完整性摘要。"""
    critical = list(critical_dimensions or dimension_results.keys())
    failed = []
    missing = []
    completed = []
    for name in critical:
        result = dimension_results.get(name)
        if not result:
            missing.append(name)
            continue
        is_complete = result.get('is_complete')
        if is_complete is None:
            is_complete = not bool(result.get('error'))
            if result.get('status') == 'failed':
                is_complete = False
        status = result.get('status', 'completed')
        if status == 'failed' or not is_complete:
            failed.append(name)
        else:
            completed.append(name)
    optional_incomplete = []
    for name, result in dimension_results.items():
        if name in critical:
            continue
        if not result:
            optional_incomplete.append(name)
            continue
        is_complete = result.get('is_complete')
        if is_complete is None:
            is_complete = not bool(result.get('error'))
            if result.get('status') == 'failed':
                is_complete = False
        if result.get('status') == 'failed' or not is_complete:
            optional_incomplete.append(name)
    total = len(critical) or 1
    completed_ratio = len(completed) / total
    status = 'complete' if not failed and (not missing) else 'partial'
    return {'status': status, 'is_complete': status == 'complete', 'critical_missing': missing, 'critical_failed': failed, 'optional_incomplete': optional_incomplete, 'completed_ratio': round(completed_ratio, 3)}

def calculate_confidence_score(dimension_results: Dict[str, Dict[str, Any]], retrieval_status: Optional[Dict[str, Any]]=None, critical_dimensions: Optional[Iterable[str]]=None) -> float:
    """按维度完成率和外部检索完成率粗略估算置信度。"""
    integrity = evaluate_data_integrity(dimension_results, critical_dimensions)
    score = 40 + integrity['completed_ratio'] * 40
    if retrieval_status:
        total = max(retrieval_status.get('total', 0), 1)
        completed = retrieval_status.get('completed', 0)
        score += min(completed / total, 1) * 20
    if integrity['critical_missing'] or integrity['critical_failed']:
        score -= 15
    if integrity['optional_incomplete']:
        score -= min(len(integrity['optional_incomplete']) * 3, 10)
    return round(max(0, min(score, 100)), 1)

def generate_recommendation(final_score: Optional[float], red_flags: list, is_complete: bool=True, missing_dimensions: Optional[Iterable[str]]=None) -> Dict[str, Any]:
    """
    生成建议
    ≥75 → 建议启动诉讼
    60-74 → 补充后启动
    <60 → 暂缓
    硬性红线 → 直接制止
    数据不完整 → 不输出误导性综合建议
    """
    missing_dimensions = list(missing_dimensions or [])
    has_block = any((r.get('severity') == 'block' or r.get('status') == 'block' for r in red_flags))
    if not is_complete or final_score is None:
        dims_text = '、'.join(missing_dimensions) if missing_dimensions else '关键维度'
        return {'recommendation': '评估未完成', 'reason': f'{dims_text}尚未完成，当前不输出综合起诉建议。', 'level': 'yellow'}
    if has_block:
        return {'recommendation': '暂不建议起诉', 'reason': '存在程序性红线问题，需优先解决', 'level': 'block'}
    if final_score >= 75:
        return {'recommendation': '建议起诉', 'reason': f'综合评分 {final_score} 分，法律风险可控，建议启动诉讼', 'level': 'green'}
    if final_score >= 60:
        return {'recommendation': '补证后起诉', 'reason': f'综合评分 {final_score} 分，补充关键证据后可启动诉讼', 'level': 'yellow'}
    return {'recommendation': '暂缓起诉', 'reason': f'综合评分 {final_score} 分，建议暂缓诉讼，进一步收集证据', 'level': 'red'}