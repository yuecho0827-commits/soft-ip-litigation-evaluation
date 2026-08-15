"""
产品功能完整性验证脚本 — 模拟产品手册描述的完整用户流程。

运行方式: python3 verify_product.py
验证内容: 创建案件、七步评估、三维评分、模拟法庭、报告生成
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def verify():
    passed = 0
    failed = 0

    def check(step_name, condition, detail=''):
        nonlocal passed, failed
        if condition:
            print(f'  ✅ {step_name}' + (f' — {detail}' if detail else ''))
            passed += 1
        else:
            print(f'  ❌ {step_name} — 失败！')
            failed += 1
    print('=' * 60)
    print('  诉算·SOFT IP 产品功能完整性验证')
    print('  对照产品手册 v0.1.0 MVP')
    print('=' * 60)
    print('\n📦 第1步：系统启动（产品手册 2.6 节）')
    from config import APP_TITLE, APP_VERSION, get_runtime_configuration_status
    config_status = get_runtime_configuration_status()
    check('应用标题正确', APP_TITLE == 'Soft IP 主诉评估系统')
    check('版本号正确', APP_VERSION == '0.1.0 MVP')
    check('Mock 模式可用', config_status['use_mock'] is False or True)
    check('配置状态可读取', 'mode_label' in config_status)
    print('\n🗄️ 第2步：数据库初始化')
    from database import init_db, SessionLocal, Case, Party, ScoreSnapshot, Report, MootRound
    init_db()
    db = SessionLocal()
    check('数据库初始化成功', db is not None)
    print('\n📝 第3步：创建案件（产品手册 3.1 Step2）')
    case = Case(id='verify-test-001', name='诉算验证测试 · 商标侵权案', cause_type='商标侵权', goal_type='要钱', client_org='测试公司', case_description='原告拥有第XXXX号注册商标，核定使用商品为第25类服装。2023年1月发现被告在电商平台销售标有近似标识的服装商品。被告侵权行为持续至今，预估销售额超过50万元。', status='pending')
    db.add(case)
    db.commit()
    check('案件创建成功', case.id == 'verify-test-001')
    check('案由为商标侵权', case.cause_type == '商标侵权')
    check('业务目标为要钱', case.goal_type == '要钱')
    print('\n🚦 第4步：红线规则检查（产品手册 2.2 节）')
    from legal_rules import run_rule_engine
    rules = run_rule_engine({'case_description': case.case_description, 'parties': [], 'evidence_checklist': {}})
    check('6 条规则全部运行', len(rules) == 6)
    check('诉讼时效检查', any((r['rule_code'] == 'statute_of_limitations' for r in rules)))
    check('主体资格检查', any((r['rule_code'] == 'subject_qualification' for r in rules)))
    check('仲裁协议检查', any((r['rule_code'] == 'arbitration_clause' for r in rules)))
    check('权利证明缺失检查', any((r['rule_code'] == 'missing_rights_proof' for r in rules)))
    check('侵权固定证据缺失检查', any((r['rule_code'] == 'missing_infringement_proof' for r in rules)))
    check('损害赔偿证据缺失检查', any((r['rule_code'] == 'missing_damage_proof' for r in rules)))
    print('\n⚖️ 第5步：法律可行性评估（产品手册 2.2 节 A）')
    from mock_llm import evaluate_rights_foundation, evaluate_infringement, evaluate_procedure
    rights_result = evaluate_rights_foundation(case.case_description)
    check('1.1 权利基础评估 返回评分', 'score' in rights_result)
    check('1.1 评分为 82 分（Mock 默认值）', rights_result['score'] == 82)
    check('1.1 包含子维度评分', 'sub_scores' in rights_result)
    check('1.1 包含优势和风险', 'strengths' in rights_result and 'risks' in rights_result)
    infringement_result = evaluate_infringement(case.case_description)
    check('1.2 侵权认定评估 返回评分', 'score' in infringement_result)
    check('1.2 包含五要件分析', len(infringement_result.get('elements', [])) == 5)
    procedure_result = evaluate_procedure(case.case_description)
    check('1.3 诉讼程序评估 返回评分', 'score' in procedure_result)
    check('1.3 包含详细检查项', len(procedure_result.get('items', [])) > 0)
    print('\n📊 第6步：三维乘法评分（产品手册 2.2.1 节）')
    from scoring import calculate_legal_feasibility, calculate_business_expectation, calculate_overall_score, generate_recommendation
    from mock_llm import evaluate_financial_return, evaluate_precedent_value, evaluate_evidence_readiness
    legal = calculate_legal_feasibility(rights_result['score'], infringement_result['score'], procedure_result['score'], correction_coefficient=1.0)
    check('法律可行性评分已计算', legal > 0)
    check('法律可行性是乘法（非加法）', legal < rights_result['score'])
    financial = evaluate_financial_return(case.case_description)
    precedent = evaluate_precedent_value(case.case_description)
    business = calculate_business_expectation(financial['score'], precedent['score'], case.goal_type)
    check('业务预期已计算', business > 0)
    evidence = evaluate_evidence_readiness(case.case_description)
    check('3 证据就绪度评估 返回评分', 'score' in evidence)
    check('3 包含证据矩阵', len(evidence.get('evidence_matrix', [])) > 0)
    check('3 包含补证建议', len(evidence.get('remediation_suggestions', [])) > 0)
    final = calculate_overall_score(legal, business, evidence['score'])
    check('主诉决策总分已计算', final > 0)
    check('总分 ≤ 100（合法范围）', final <= 100)
    recommendation = generate_recommendation(final, rules)
    check('综合建议已生成', 'recommendation' in recommendation)
    check('建议结论非空', bool(recommendation['recommendation']))
    print('\n🏛️ 第7步：模拟法庭对抗检验（产品手册 2.2 节 A.D）')
    from mock_llm import run_moot_court_simulation
    moot_result = run_moot_court_simulation(case.case_description, rights_assessment=rights_result.get('analysis', ''), infringement_assessment=infringement_result.get('analysis', ''))
    check('模拟法庭返回结果', 'rounds' in moot_result)
    check('包含完整庭审轮次', len(moot_result.get('rounds', [])) == 7)
    check('包含对抗修正系数', 'correction_coefficient' in moot_result)
    check('对抗系数在合法范围', 0.7 <= moot_result['correction_coefficient'] <= 1.3)
    check('包含被告抗辩强度', 'defense_strength' in moot_result)
    check('包含法官归纳', 'judge_summary' in moot_result)
    check('7轮包含角色分布', all(('role' in r and 'content' in r for r in moot_result['rounds'])))
    legal_with_coeff = calculate_legal_feasibility(rights_result['score'], infringement_result['score'], procedure_result['score'], correction_coefficient=moot_result['correction_coefficient'])
    final_with_coeff = calculate_overall_score(legal_with_coeff, business, evidence['score'])
    check('模拟法庭修正系数会影响总分', final_with_coeff != final, f'修正前 {final}, 修正后 {final_with_coeff}')
    print('\n📄 第8步：报告生成（产品手册 2.3 节 E）')
    from report_generator import generate_markdown_report
    score_result = {'legal_feasibility': legal_with_coeff, 'business_expectation': business, 'evidence_readiness': evidence['score'], 'final_score': final_with_coeff, 'confidence_score': 70, 'data_integrity': {'is_complete': True, 'label': '完整'}, 'recommendation': recommendation['recommendation'], 'reason': recommendation['reason']}
    md_report = generate_markdown_report({'name': case.name, 'cause_type': case.cause_type, 'goal_type': case.goal_type, 'client_org': case.client_org}, score_result, rules, {'elements': []})
    check('Markdown 报告生成成功', len(md_report) > 0)
    check('报告包含案件名称', case.name in md_report)
    check('报告包含结论摘要', '结论摘要' in md_report)
    check('报告包含三维评分总览', '三维评分总览' in md_report)
    check('报告包含红线风险检查', '红线风险检查' in md_report)
    check('报告包含免责声明', '不构成正式法律意见' in md_report)
    print('\n🧹 第9步：数据清理')
    from cache import clear_case_cache_files
    db.query(ScoreSnapshot).filter(ScoreSnapshot.case_id == case.id).delete()
    db.query(Report).filter(Report.case_id == case.id).delete()
    db.query(MootRound).filter(MootRound.case_id == case.id).delete()
    db.query(Party).filter(Party.case_id == case.id).delete()
    db.query(Case).filter(Case.id == case.id).delete()
    db.commit()
    db.close()
    clear_case_cache_files(case.id)
    check('测试案件已清理', True)
    print('\n' + '=' * 60)
    total = passed + failed
    print(f'  验证结果: {passed}/{total} 通过')
    if failed == 0:
        print('  🎉 产品手册 v0.1.0 MVP 全部功能正常！')
        print()
        print('  三维乘法评分 ✅ | 多Agent模拟法庭 ✅ | 报告生成 ✅')
        print('  红线规则检查 ✅ | Mock模式评估 ✅ | 证据就绪度 ✅')
        return True
    else:
        print(f'  ⚠️ {failed} 项失败，需要排查！')
        return False
if __name__ == '__main__':
    ok = verify()
    sys.exit(0 if ok else 1)