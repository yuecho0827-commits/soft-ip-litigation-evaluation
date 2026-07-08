"""
评分引擎 - 严格按 v1 产品方案的三维乘法模型
法律可行性 = 权利基础 × 侵权认定 × 诉讼程序 × 对抗修正系数
业务预期  = if 要钱: 0.9×财务+0.1×判例 / if 要名: 0.1×财务+0.9×判例
主诉决策总分 = 法律可行性 × 业务预期 × 证据就绪度
"""

from typing import Dict, Any


def normalize(score, scale=100):
    """归一化到 0-1 范围"""
    return max(0, min(score, scale)) / scale


def calculate_legal_feasibility(
    rights_score: float,
    infringement_score: float,
    procedure_score: float,
    correction_coefficient: float = 1.0
) -> float:
    """
    法律可行性 = 权利基础 × 侵权认定 × 诉讼程序 × 对抗修正系数
    乘法模型，体现"一票否决"逻辑
    """
    r = normalize(rights_score)
    i = normalize(infringement_score)
    p = normalize(procedure_score)
    c = max(0.7, min(correction_coefficient, 1.3))  # 修正系数裁剪

    return round(r * i * p * c * 100, 1)


def calculate_business_expectation(
    financial_score: float,
    precedent_score: float,
    goal_type: str
) -> float:
    """
    业务预期 = 自适应权重（根据业务目标分流）
    要钱 → 0.9×财务 + 0.1×判例
    要名 → 0.1×财务 + 0.9×判例
    """
    f = normalize(financial_score)
    p = normalize(precedent_score)

    if goal_type == "要钱":
        return round((0.9 * f + 0.1 * p) * 100, 1)
    else:  # 要名
        return round((0.1 * f + 0.9 * p) * 100, 1)


def calculate_overall_score(
    legal_feasibility: float,
    business_expectation: float,
    evidence_readiness: float
) -> float:
    """
    主诉决策总分 = 法律可行性 × 业务预期 × 证据就绪度
    """
    l = normalize(legal_feasibility)
    b = normalize(business_expectation)
    e = normalize(evidence_readiness)

    return round(l * b * e * 100, 1)


def generate_recommendation(final_score: float, red_flags: list) -> Dict:
    """
    生成建议
    ≥75 → 建议启动诉讼
    60-74 → 补充后启动
    <60 → 暂缓
    硬性红线 → 直接制止
    """
    has_block = any(r.get("severity") == "block" for r in red_flags)

    if has_block:
        return {
            "recommendation": "暂不建议起诉",
            "reason": "存在程序性红线问题，需优先解决",
            "level": "block"
        }

    if final_score >= 75:
        return {
            "recommendation": "建议起诉",
            "reason": f"综合评分 {final_score} 分，法律风险可控，建议启动诉讼",
            "level": "green"
        }
    elif final_score >= 60:
        return {
            "recommendation": "补证后起诉",
            "reason": f"综合评分 {final_score} 分，补充关键证据后可启动诉讼",
            "level": "yellow"
        }
    else:
        return {
            "recommendation": "暂缓起诉",
            "reason": f"综合评分 {final_score} 分，建议暂缓诉讼，进一步收集证据",
            "level": "red"
        }
