"""
评分引擎 - 三维评分逻辑
法律可行性 × 业务预期 × 证据就绪度
"""

from typing import Dict, Any, List
from config import SCORING_WEIGHTS, CONFIDENCE_WEIGHTS, ADVERSARIAL_COEFF_MIN, ADVERSARIAL_COEFF_MAX

def calculate_legal_feasibility(legal_elements: List[Dict]) -> float:
    """
    计算法律可行性得分
    基于商标侵权构成要件逐项评分
    """
    if not legal_elements:
        return 0.0

    # 要件权重（可调整）
    element_weights = {
        "权利基础": 0.25,
        "侵权认定": 0.45,
        "程序合规": 0.15,
        "赔偿依据": 0.15
    }

    weighted_score = 0.0
    total_weight = 0.0

    for element in legal_elements:
        element_name = element.get("element", "")
        score = element.get("score", 0)
        weight = element_weights.get(element_name, 0.1)

        weighted_score += score * weight
        total_weight += weight

    # 归一化
    if total_weight > 0:
        return round(weighted_score / total_weight, 1)
    else:
        return 0.0

def calculate_business_expectation(case_info: Dict, case_facts: Dict) -> float:
    """
    计算业务预期得分
    要钱路径：赔偿预期 vs 成本
    要名路径：传播影响评估
    """
    goal_type = case_info.get("goal_type", "要钱")

    if goal_type == "要钱":
        # 简化版：基于案情描述中的关键词估算
        case_description = case_facts.get("case_description", "")
        key_facts = case_facts.get("key_facts", [])

        # 赔偿预期指标
        damage_indicators = {
            "高": ["销售额高", "利润高", "驰名商标", "恶意侵权"],
            "中": ["有一定销售", "知名品牌"],
            "低": ["销售少", "影响小"]
        }

        # 简易评分逻辑（后续可接外部数据）
        score = 60  # 基准分

        for fact in key_facts:
            if any(kw in fact for kw in damage_indicators["高"]):
                score += 10
            elif any(kw in fact for kw in damage_indicators["中"]):
                score += 5

        return min(score, 100)

    elif goal_type == "要名":
        # 传播影响评估（简化版）
        # 后续可接舆情分析
        score = 70  # 基准分
        return score

    else:
        return 50

def calculate_evidence_readiness(evidence_mapping: List[Dict]) -> float:
    """
    计算证据就绪度得分
    基于证据矩阵：每个要件是否有对应证据
    """
    if not evidence_mapping:
        return 0.0

    # 统计证据支持情况
    support_counts = {
        "strong": 0,
        "partial": 0,
        "weak": 0,
        "none": 0
    }

    for mapping in evidence_mapping:
        support_level = mapping.get("support_level", "none")
        support_counts[support_level] = support_counts.get(support_level, 0) + 1

    total = len(evidence_mapping)
    if total == 0:
        return 0.0

    # 加权计算
    score = (
        support_counts["strong"] * 100 +
        support_counts["partial"] * 60 +
        support_counts["weak"] * 30 +
        support_counts["none"] * 0
    ) / total

    return round(score, 1)

def calculate_confidence_score(case_facts: Dict, retrieval_quality: float = 0.5) -> float:
    """
    计算置信度得分
    评估结果的可靠性
    """
    # 证据完整度
    evidence_completeness = 0.5  # 基准
    evidence_checklist = case_facts.get("evidence_checklist", {})
    if evidence_checklist.get("has_rights_proof"):
        evidence_completeness += 0.2
    if evidence_checklist.get("has_infringement_proof"):
        evidence_completeness += 0.2
    if evidence_checklist.get("has_damage_proof"):
        evidence_completeness += 0.1

    # 数据新鲜度（简化：假设为0.5）
    data_freshness = 0.5

    # 加权
    confidence = (
        evidence_completeness * CONFIDENCE_WEIGHTS["evidence_completeness"] +
        retrieval_quality * CONFIDENCE_WEIGHTS["retrieval_quality"] +
        data_freshness * CONFIDENCE_WEIGHTS["data_freshness"]
    )

    return round(confidence * 100, 1)

def generate_recommendation(final_score: float, rule_results: List[Dict]) -> Dict[str, Any]:
    """
    生成最终建议
    """
    # 检查是否有 block 级规则命中
    has_block = any(r["severity"] == "block" for r in rule_results)
    has_warning = any(r["severity"] == "warning" for r in rule_results)

    if has_block:
        return {
            "recommendation": "暂不建议起诉",
            "reason": "存在程序性红线问题，需先解决",
            "action_items": [r["reason"] for r in rule_results if r["severity"] == "block"]
        }

    # 基于评分给出建议
    if final_score >= 70:
        recommendation = "建议起诉"
        reason = f"综合评分 {final_score} 分，法律风险可控，证据基本就绪"
    elif final_score >= 50:
        recommendation = "补证后再起诉"
        reason = f"综合评分 {final_score} 分，需补充关键证据后再启动诉讼"
    else:
        recommendation = "暂缓起诉"
        reason = f"综合评分 {final_score} 分，当前证据和法律基础不足"

    # 生成行动建议
    action_items = []
    if has_warning:
        action_items = [r["reason"] for r in rule_results if r["severity"] == "warning"]

    return {
        "recommendation": recommendation,
        "reason": reason,
        "action_items": action_items,
        "final_score": final_score
    }

def run_scoring(case_info: Dict, case_facts: Dict, legal_analysis: Dict, rule_results: List[Dict], evidence_mapping: List[Dict] = None) -> Dict[str, Any]:
    """
    运行完整评分流程
    """
    # 1. 法律可行性
    legal_score = calculate_legal_feasibility(legal_analysis.get("elements", []))

    # 2. 业务预期
    business_score = calculate_business_expectation(case_info, case_facts)

    # 3. 证据就绪度
    evidence_score = calculate_evidence_readiness(evidence_mapping or [])

    # 4. 置信度
    confidence_score = calculate_confidence_score(case_facts)

    # 5. 加权计算最终得分
    final_score = int(
        legal_score * SCORING_WEIGHTS["legal_feasibility"] +
        business_score * SCORING_WEIGHTS["business_expectation"] +
        evidence_score * SCORING_WEIGHTS["evidence_readiness"]
    )

    # 6. 生成建议
    recommendation_result = generate_recommendation(final_score, rule_results)

    return {
        "legal_feasibility": legal_score,
        "business_expectation": business_score,
        "evidence_readiness": evidence_score,
        "confidence_score": confidence_score,
        "final_score": final_score,
        "recommendation": recommendation_result["recommendation"],
        "reason": recommendation_result["reason"],
        "action_items": recommendation_result["action_items"]
    }
