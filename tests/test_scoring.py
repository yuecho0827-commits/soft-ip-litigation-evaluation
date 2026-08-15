"""
scoring.py 单元测试
覆盖项目最核心的三维乘法评分引擎所有函数。
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scoring import normalize, calculate_legal_feasibility, calculate_business_expectation, calculate_overall_score, evaluate_data_integrity, calculate_confidence_score, generate_recommendation

class TestNormalize:
    """归一化函数测试"""

    def test_normal_score(self):
        """常规分数：50/100 → 0.5"""
        assert normalize(50) == 0.5

    def test_perfect_score(self):
        """满分：100/100 → 1.0"""
        assert normalize(100) == 1.0

    def test_zero_score(self):
        """零分：0/100 → 0.0"""
        assert normalize(0) == 0.0

    def test_negative_clamped_to_zero(self):
        """负数被截断为 0"""
        assert normalize(-10) == 0.0
        assert normalize(-100) == 0.0

    def test_overscore_clamped_to_scale(self):
        """超过满分的值被截断"""
        assert normalize(150) == 1.0
        assert normalize(200) == 1.0

    def test_custom_scale(self):
        """自定义满分值"""
        assert normalize(30, scale=60) == 0.5
        assert normalize(60, scale=60) == 1.0
        assert normalize(0, scale=60) == 0.0

    def test_edge_just_above_zero(self):
        """极小正值"""
        assert normalize(0.1) == 0.001

    def test_edge_just_below_scale(self):
        """略低于满分"""
        assert normalize(99.9) == pytest.approx(0.999)

    def test_float_precision(self):
        """浮点数精度"""
        result = normalize(33.333, scale=100)
        assert 0.333 < result < 0.334

class TestLegalFeasibility:
    """法律可行性评分测试"""

    def test_normal_case(self):
        """正常情况：三个维度都有分"""
        score = calculate_legal_feasibility(80, 75, 88, 1.0)
        assert score == 52.8

    def test_one_dimension_zero_vetos_all(self):
        """一票否决：任一维度0分，总分应为0"""
        assert calculate_legal_feasibility(0, 80, 80, 1.0) == 0.0
        assert calculate_legal_feasibility(80, 0, 80, 1.0) == 0.0
        assert calculate_legal_feasibility(80, 80, 0, 1.0) == 0.0

    def test_all_perfect(self):
        """全部满分 + 系数1.0"""
        score = calculate_legal_feasibility(100, 100, 100, 1.0)
        assert score == 100.0

    def test_all_perfect_boosted(self):
        """全部满分 + 正向修正系数"""
        score = calculate_legal_feasibility(100, 100, 100, 1.15)
        assert score == 115.0

    def test_adversarial_penalty(self):
        """对抗修正系数降低总分的场景"""
        score_no_penalty = calculate_legal_feasibility(80, 75, 88, 1.0)
        score_with_penalty = calculate_legal_feasibility(80, 75, 88, 0.75)
        assert score_with_penalty < score_no_penalty
        assert score_with_penalty == pytest.approx(39.6)

    def test_coefficient_below_range_clamped(self):
        """修正系数低于 0.7 被钳制到 0.7"""
        score = calculate_legal_feasibility(80, 75, 88, 0.5)
        assert score == 37.0

    def test_coefficient_above_range_clamped(self):
        """修正系数高于 1.3 被钳制到 1.3"""
        score = calculate_legal_feasibility(80, 75, 88, 2.0)
        expected_clamped = round(0.8 * 0.75 * 0.88 * 1.3 * 100, 1)
        assert score == expected_clamped

    def test_all_overscore(self):
        """输入超过100分，归一化后正常计算"""
        score = calculate_legal_feasibility(150, 150, 150, 1.0)
        assert score == 100.0

    def test_default_coefficient(self):
        """不传修正系数时默认为 1.0"""
        assert calculate_legal_feasibility(80, 75, 88) == 52.8

class TestBusinessExpectation:
    """业务预期评分测试"""

    def test_money_goal_weights_financial_more(self):
        """要钱：财务权重 0.9，判例 0.1"""
        score = calculate_business_expectation(80, 50, '要钱')
        assert score == 77.0

    def test_fame_goal_weights_precedent_more(self):
        """要名：判例权重 0.9，财务 0.1"""
        score = calculate_business_expectation(80, 50, '要名')
        assert score == 53.0

    def test_money_vs_fame_difference(self):
        """要钱和要名的结果应不同"""
        score_money = calculate_business_expectation(80, 50, '要钱')
        score_fame = calculate_business_expectation(80, 50, '要名')
        assert score_money != score_fame
        assert score_money > score_fame

    def test_money_vs_fame_reversed(self):
        """当判例分高时，要名分 > 要钱分"""
        score_money = calculate_business_expectation(30, 90, '要钱')
        score_fame = calculate_business_expectation(30, 90, '要名')
        assert score_fame > score_money

    def test_unknown_goal_defaults_to_fame_like(self):
        """未知目标类型走 else 分支（等同要名逻辑）"""
        score = calculate_business_expectation(80, 50, '其他')
        assert score == 53.0

    def test_empty_goal_defaults_to_fame_like(self):
        """空字符串走 else 分支"""
        score = calculate_business_expectation(80, 50, '')
        assert score == 53.0

    def test_zero_financial_score(self):
        """财务分为0"""
        score = calculate_business_expectation(0, 80, '要钱')
        assert score == 8.0

    def test_overscore_handled(self):
        """超过100分的输入被归一化"""
        score = calculate_business_expectation(200, 200, '要钱')
        assert score == 100.0

class TestOverallScore:
    """主诉决策总分测试（三维乘法）"""

    def test_normal_case(self):
        """常规三维分数"""
        score = calculate_overall_score(70, 80, 60)
        assert score == 33.6

    def test_one_veto_zero(self):
        """任一维度为0，总分归零（一票否决核心逻辑）"""
        assert calculate_overall_score(0, 80, 80) == 0.0
        assert calculate_overall_score(80, 0, 80) == 0.0
        assert calculate_overall_score(80, 80, 0) == 0.0

    def test_two_dimensions_zero(self):
        """两个维度为0，总分归零"""
        assert calculate_overall_score(0, 0, 80) == 0.0

    def test_all_three_zero(self):
        """全部为0"""
        assert calculate_overall_score(0, 0, 0) == 0.0

    def test_all_perfect(self):
        """全部满分"""
        assert calculate_overall_score(100, 100, 100) == 100.0

    def test_very_close_to_zero(self):
        """极小值趋近于零分"""
        score = calculate_overall_score(1, 100, 100)
        assert score == 1.0

    def test_overscore_scores(self):
        """超过满分的分数被归一化"""
        score = calculate_overall_score(150, 150, 150)
        assert score == 100.0

    def test_moderate_scores(self):
        """中等分数组合"""
        score = calculate_overall_score(80, 80, 80)
        assert score == 51.2

class TestDataIntegrity:
    """数据完整性评估测试"""

    def test_all_complete(self):
        """所有维度完成"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'completed', 'is_complete': True}, 'procedure': {'status': 'completed', 'is_complete': True}}
        integrity = evaluate_data_integrity(results)
        assert integrity['status'] == 'complete'
        assert integrity['is_complete'] is True
        assert integrity['critical_missing'] == []
        assert integrity['critical_failed'] == []
        assert integrity['completed_ratio'] == 1.0

    def test_some_missing(self):
        """部分维度缺失（未在 results 中出现）"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'procedure': {'status': 'completed', 'is_complete': True}}
        integrity = evaluate_data_integrity(results, critical_dimensions=['rights', 'infringement', 'procedure'])
        assert integrity['status'] == 'partial'
        assert integrity['is_complete'] is False
        assert 'infringement' in integrity['critical_missing']
        assert len(integrity['critical_missing']) == 1

    def test_some_failed(self):
        """部分维度状态为 failed"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'failed', 'is_complete': False, 'error': 'API超时'}, 'procedure': {'status': 'completed', 'is_complete': True}}
        integrity = evaluate_data_integrity(results)
        assert integrity['status'] == 'partial'
        assert 'infringement' in integrity['critical_failed']

    def test_is_complete_none_with_error(self):
        """is_complete 为 None 但有 error → 视为不完整"""
        results = {'rights': {'status': 'completed', 'is_complete': None, 'error': '部分失败'}}
        integrity = evaluate_data_integrity(results)
        assert integrity['status'] == 'partial'
        assert 'rights' in integrity['critical_failed']

    def test_is_complete_none_no_error(self):
        """is_complete 为 None 且无 error → 视为完整"""
        results = {'rights': {'status': 'completed', 'is_complete': None}}
        integrity = evaluate_data_integrity(results)
        assert integrity['status'] == 'complete'

    def test_critical_dimensions_subset(self):
        """只检查指定的关键维度"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'failed', 'is_complete': False}, 'optional_extra': {'status': 'completed', 'is_complete': True}}
        integrity = evaluate_data_integrity(results, critical_dimensions=['rights'])
        assert integrity['status'] == 'complete'

    def test_optional_incomplete(self):
        """非关键维度不完整被放入 optional_incomplete"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'moot': {'status': 'failed', 'is_complete': False}}
        integrity = evaluate_data_integrity(results, critical_dimensions=['rights'])
        assert 'moot' in integrity['optional_incomplete']

    def test_empty_results(self):
        """空字典 → 无 critical 维度 → 无缺失/失败 → 视为 complete"""
        integrity = evaluate_data_integrity({})
        assert integrity['is_complete'] is True
        assert integrity['completed_ratio'] == 0.0

    def test_empty_results_with_critical_dimensions(self):
        """指定了 critical 但 results 里全没有 → 全部 missing"""
        integrity = evaluate_data_integrity({}, critical_dimensions=['rights', 'infringement'])
        assert integrity['status'] == 'partial'
        assert len(integrity['critical_missing']) == 2
        assert integrity['completed_ratio'] == 0.0

    def test_completed_ratio_partial(self):
        """部分完成的 completed_ratio"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'completed', 'is_complete': True}, 'procedure': {'status': 'failed'}, 'financial': {'status': 'completed', 'is_complete': True}}
        integrity = evaluate_data_integrity(results)
        assert integrity['completed_ratio'] == 0.75
        assert integrity['status'] == 'partial'

class TestConfidenceScore:
    """置信度评分测试"""

    def test_all_complete_no_retrieval(self):
        """全部完成，无检索状态 → 基准 40 + 40 = 80"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'completed', 'is_complete': True}, 'procedure': {'status': 'completed', 'is_complete': True}}
        score = calculate_confidence_score(results)
        assert score == 80.0

    def test_half_complete(self):
        """一半完成 → 40 + 0.5*40 - 15(失败惩罚) = 45"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'failed'}}
        score = calculate_confidence_score(results)
        assert score == 45.0

    def test_none_complete_floor(self):
        """全未完成 → 40 + 0 - 15(惩罚) = 25"""
        results = {'rights': {'status': 'failed'}, 'infringement': {'status': 'failed'}}
        score = calculate_confidence_score(results)
        assert score == 25.0

    def test_with_retrieval_status(self):
        """有检索状态加分"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'completed', 'is_complete': True}}
        retrieval = {'total': 10, 'completed': 8}
        score = calculate_confidence_score(results, retrieval_status=retrieval)
        assert score == 96.0

    def test_with_retrieval_empty_total(self):
        """检索状态 total=0 时防除零"""
        results = {'rights': {'status': 'completed', 'is_complete': True}}
        retrieval = {'total': 0, 'completed': 0}
        score = calculate_confidence_score(results, retrieval_status=retrieval)
        assert score == 80.0

    def test_penalty_for_missing_dimensions(self):
        """缺失维度扣 15 分"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'infringement': {'status': 'completed', 'is_complete': True}}
        score = calculate_confidence_score(results, critical_dimensions=['rights', 'infringement', 'procedure'])
        assert pytest.approx(score) == 51.7

    def test_penalty_for_optional_incomplete(self):
        """非关键维度不完整扣分（每个扣3分，上限10）"""
        results = {'rights': {'status': 'completed', 'is_complete': True}, 'optional_a': {'status': 'failed'}, 'optional_b': {'status': 'failed'}, 'optional_c': {'status': 'failed'}, 'optional_d': {'status': 'failed'}}
        score = calculate_confidence_score(results, critical_dimensions=['rights'])
        assert score == 70.0

    def test_floor_zero(self):
        """置信度不低于 0"""
        results = {'rights': {'status': 'failed'}}
        score = calculate_confidence_score(results)
        assert score >= 0.0

    def test_ceiling_hundred(self):
        """置信度不超过 100"""
        results = {'rights': {'status': 'completed', 'is_complete': True}}
        retrieval = {'total': 1, 'completed': 999}
        score = calculate_confidence_score(results, retrieval_status=retrieval)
        assert score <= 100.0

class TestGenerateRecommendation:
    """建议生成测试"""

    def test_high_score_recommend_litigation(self):
        """≥75 分 → 建议起诉"""
        result = generate_recommendation(80.0, [])
        assert result['recommendation'] == '建议起诉'
        assert result['level'] == 'green'
        assert '80' in result['reason']

    def test_mid_score_recommend_supplement(self):
        """60-74 分 → 补证后起诉"""
        result = generate_recommendation(65.0, [])
        assert result['recommendation'] == '补证后起诉'
        assert result['level'] == 'yellow'

    def test_low_score_recommend_hold(self):
        """<60 分 → 暂缓起诉"""
        result = generate_recommendation(30.0, [])
        assert result['recommendation'] == '暂缓起诉'
        assert result['level'] == 'red'

    def test_boundary_75_exactly(self):
        """边界值 75.0 → 建议起诉"""
        result = generate_recommendation(75.0, [])
        assert result['recommendation'] == '建议起诉'

    def test_boundary_60_exactly(self):
        """边界值 60.0 → 补证后起诉"""
        result = generate_recommendation(60.0, [])
        assert result['recommendation'] == '补证后起诉'

    def test_boundary_59_9(self):
        """边界值 59.9 → 暂缓起诉"""
        result = generate_recommendation(59.9, [])
        assert result['recommendation'] == '暂缓起诉'

    def test_none_score_incomplete(self):
        """score 为 None 时 → 评估未完成"""
        result = generate_recommendation(None, [])
        assert result['recommendation'] == '评估未完成'
        assert result['level'] == 'yellow'

    def test_not_complete_flag(self):
        """is_complete=False → 评估未完成"""
        result = generate_recommendation(80.0, [], is_complete=False)
        assert result['recommendation'] == '评估未完成'

    def test_block_severity_trumps_score(self):
        """存在 block 级别的红线 → 暂不建议起诉，无视高分"""
        red_flags = [{'rule_code': 'statute', 'severity': 'block', 'result': '时效已过'}]
        result = generate_recommendation(85.0, red_flags)
        assert result['recommendation'] == '暂不建议起诉'
        assert result['level'] == 'block'

    def test_block_status_field(self):
        """status 字段为 block 也视为红线"""
        red_flags = [{'rule_code': 'subject', 'status': 'block', 'result': '主体不适格'}]
        result = generate_recommendation(85.0, red_flags)
        assert result['recommendation'] == '暂不建议起诉'

    def test_warning_only_does_not_block(self):
        """warning 级别不触发 block → 正常按分数建议"""
        red_flags = [{'rule_code': 'evidence', 'severity': 'warning', 'result': '证据不足'}]
        result = generate_recommendation(80.0, red_flags)
        assert result['recommendation'] == '建议起诉'

    def test_empty_red_flags(self):
        """空的红线列表"""
        result = generate_recommendation(80.0, [])
        assert result['recommendation'] == '建议起诉'

    def test_with_missing_dimensions(self):
        """有缺失维度名称 → 提示具体哪些维度未完成"""
        result = generate_recommendation(None, [], is_complete=False, missing_dimensions=['权利基础', '侵权认定'])
        assert '权利基础' in result['reason']
        assert '侵权认定' in result['reason']

    def test_incomplete_without_missing_names(self):
        """不完整但未提供缺失维度名 → 通用提示"""
        result = generate_recommendation(None, [], is_complete=False)
        assert '关键维度' in result['reason']

    def test_zero_score_but_valids(self):
        """0 分但无红线 → 暂缓起诉"""
        result = generate_recommendation(0.0, [])
        assert result['recommendation'] == '暂缓起诉'
        assert result['level'] == 'red'

class TestIntegrationScenarios:
    """集成场景测试：模拟产品手册中描述的真实评估流程"""

    def test_scenario_strong_case(self):
        """场景1：强案 — 全部维度90+，模拟法庭利好"""
        legal = calculate_legal_feasibility(rights_score=95, infringement_score=95, procedure_score=95, correction_coefficient=1.05)
        assert legal == 90.0
        business = calculate_business_expectation(financial_score=90, precedent_score=85, goal_type='要钱')
        final = calculate_overall_score(legal, business, evidence_readiness=90)
        recommendation = generate_recommendation(final, [])
        assert recommendation['recommendation'] == '补证后起诉'

    def test_scenario_weak_rights_veto(self):
        """场景2：权利基础薄弱，即使证据充分也应低分"""
        legal = calculate_legal_feasibility(rights_score=20, infringement_score=80, procedure_score=90, correction_coefficient=1.0)
        assert legal < 20
        final = calculate_overall_score(legal, business_expectation=80, evidence_readiness=90)
        assert final < 15
        recommendation = generate_recommendation(final, [])
        assert recommendation['recommendation'] == '暂缓起诉'

    def test_scenario_empty_shell_company(self):
        """场景3：被告是空壳公司 — 法律可行但回款概率低，要钱不应高分"""
        legal = calculate_legal_feasibility(85, 80, 90, 1.0)
        business_money = calculate_business_expectation(financial_score=10, precedent_score=40, goal_type='要钱')
        final = calculate_overall_score(legal, business_money, evidence_readiness=75)
        assert final < 50
        recommendation = generate_recommendation(final, [])
        assert recommendation['recommendation'] in ('补证后起诉', '暂缓起诉')

    def test_scenario_goal_switch_changes_outcome(self):
        """场景4：同一案件，要钱 vs 要名，结论可能不同"""
        legal = calculate_legal_feasibility(80, 75, 85, 1.0)
        biz_money = calculate_business_expectation(30, 85, '要钱')
        biz_fame = calculate_business_expectation(30, 85, '要名')
        assert biz_fame > biz_money
        final_money = calculate_overall_score(legal, biz_money, 80)
        final_fame = calculate_overall_score(legal, biz_fame, 80)
        assert final_fame > final_money

    def test_scenario_moot_court_penalty(self):
        """场景5：模拟法庭暴露弱点，修正系数降低"""
        score_before = calculate_legal_feasibility(80, 75, 88, 1.0)
        score_after = calculate_legal_feasibility(80, 75, 88, 0.75)
        assert score_after < score_before * 0.8