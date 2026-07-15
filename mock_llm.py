"""
Mock LLM 模块 - MVP 阶段使用模拟数据
后续可无缝切换到真实 DeepSeek API
"""

import time
from typing import Dict, List, Any
from datetime import datetime

def mock_delay():
    """模拟 LLM 响应延迟"""
    time.sleep(1)

def extract_case_facts(case_description: str) -> Dict[str, Any]:
    """
    从案情描述中提取关键事实
    Mock 模式：返回模拟数据
    """
    mock_delay()

    return {
        "parties": [
            {"role": "plaintiff", "name": "某知名品牌公司", "type": "company"},
            {"role": "defendant", "name": "某电商平台商家", "type": "company"}
        ],
        "timeline": [
            {"date": "2020-01-01", "event": "原告注册商标"},
            {"date": "2023-01-01", "event": "发现被告侵权行为"},
            {"date": "2023-06-01", "event": "发送律师函"}
        ],
        "key_facts": [
            "被告在电商平台上销售假冒原告注册商标的商品",
            "侵权商品销售额约为 50 万元",
            "原告商标为驰名商标，具有较高知名度"
        ],
        "evidence_checklist": {
            "has_rights_proof": True,
            "has_infringement_proof": True,
            "has_damage_proof": False
        }
    }

def analyze_legal_elements(case_facts: Dict) -> Dict[str, Any]:
    """
    分析法律构成要件
    Mock 模式：返回模拟评分
    """
    mock_delay()

    return {
        "elements": [
            {
                "element": "权利基础",
                "score": 85,
                "analysis": "原告持有有效注册商标，权利基础牢固",
                "evidence_status": "充足",
                "risks": []
            },
            {
                "element": "侵权认定",
                "score": 75,
                "analysis": "被告行为构成商标侵权，但相似度认定存在一定争议",
                "evidence_status": "部分充足",
                "risks": ["商品类似程度认定可能有争议"]
            },
            {
                "element": "赔偿依据",
                "score": 60,
                "analysis": "缺乏明确的损害赔偿计算依据",
                "evidence_status": "不足",
                "risks": ["赔偿额难以获得法院全额支持"]
            }
        ],
        "overall_legal_feasibility": 73
    }

def check_rules(case_facts: Dict) -> List[Dict[str, Any]]:
    """
    规则检查（红线检查）
    Mock 模式：返回模拟结果
    """
    mock_delay()

    return [
        {
            "rule_code": " statute_of_limitations",
            "rule_name": "诉讼时效检查",
            "severity": "pass",
            "result": "未发现时效问题",
            "reason": "侵权行为在诉讼时效内"
        },
        {
            "rule_code": "subject_qualification",
            "rule_name": "主体资格检查",
            "severity": "pass",
            "result": "原告主体资格完整",
            "reason": "原告为注册商标持有人"
        },
        {
            "rule_code": "arbitration_clause",
            "rule_name": "仲裁协议检查",
            "severity": "pass",
            "result": "未发现仲裁协议",
            "reason": "原被告之间无仲裁协议"
        },
        {
            "rule_code": "missing_rights_proof",
            "rule_name": "权利证明缺失检查",
            "severity": "pass",
            "result": "权利证明文件齐全",
            "reason": "已上传商标注册证"
        },
        {
            "rule_code": "missing_infringement_proof",
            "rule_name": "侵权固定证据缺失检查",
            "severity": "warning",
            "result": "侵权证据需要进一步固定",
            "reason": "公证证据较为简单，建议补充购买记录公证"
        },
        {
            "rule_code": "missing_damage_proof",
            "rule_name": "损害赔偿证据缺失检查",
            "severity": "warning",
            "result": "损害赔偿计算依据不足",
            "reason": "缺乏被告获利证据或原告损失证据"
        }
    ]

def generate_score(case_facts: Dict, legal_analysis: Dict, rule_results: List) -> Dict[str, Any]:
    """
    生成三维评分
    Mock 模式：返回模拟评分
    """
    mock_delay()

    # 检查是否有 block 级规则命中
    has_block = any(r["severity"] == "block" for r in rule_results)

    if has_block:
        return {
            "legal_feasibility": legal_analysis["overall_legal_feasibility"],
            "business_expectation": 50,
            "evidence_readiness": 60,
            "confidence_score": 40,
            "final_score": None,
            "recommendation": "暂不建议起诉",
            "reason": "存在程序性红线问题"
        }

    # 计算三维评分
    legal_score = legal_analysis["overall_legal_feasibility"]
    business_score = 65  # Mock: 赔偿预期中等
    evidence_score = 70  # Mock: 证据基本就绪

    # 加权计算
    final_score = int(legal_score * 0.45 + business_score * 0.25 + evidence_score * 0.30)

    # 置信度
    confidence_score = 65

    # 建议
    if final_score >= 70:
        recommendation = "建议起诉"
    elif final_score >= 50:
        recommendation = "补证后再起诉"
    else:
        recommendation = "暂缓起诉"

    return {
        "legal_feasibility": legal_score,
        "business_expectation": business_score,
        "evidence_readiness": evidence_score,
        "confidence_score": confidence_score,
        "final_score": final_score,
        "recommendation": recommendation,
        "reason": f"综合评分 {final_score} 分，{recommendation}。需注意：证据仍需补充，赔偿依据不足。"
    }

def generate_report(case_info: Dict, score_result: Dict, rule_results: List) -> str:
    """
    生成评估报告（Markdown 格式）
    Mock 模式：返回模拟报告
    """
    mock_delay()

    report = f"""
# Soft IP 主诉评估报告

**案件名称**: {case_info.get('name', '未命名案件')}
**评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**案由**: 商标侵权
**业务目标**: {case_info.get('goal_type', '未指定')}

---

## 一、结论摘要

**总体建议**: {score_result['recommendation']}
**综合评分**: {score_result['final_score']} 分（满分100分）
**置信度**: {score_result['confidence_score']}%

{score_result['reason']}

---

## 二、三维评分总览

| 维度 | 得分 | 权重 | 加权得分 |
|------|------|------|---------|
| 法律可行性 | {score_result['legal_feasibility']} | 45% | {score_result['legal_feasibility'] * 0.45:.1f} |
| 业务预期 | {score_result['business_expectation']} | 25% | {score_result['business_expectation'] * 0.25:.1f} |
| 证据就绪度 | {score_result['evidence_readiness']} | 30% | {score_result['evidence_readiness'] * 0.30:.1f} |

---

## 三、红线风险检查

"""

    for rule in rule_results:
        status_icon = "✅" if rule["severity"] == "pass" else ("⚠️" if rule["severity"] == "warning" else "🚫")
        report += f"\n### {status_icon} {rule['rule_name']}\n"
        report += f"**结果**: {rule['result']}\n"
        report += f"**说明**: {rule['reason']}\n"

    report += """
---

## 四、证据矩阵诊断

### 权利基础证据
- ✅ 商标注册证（已上传）
- ✅ 续展证明（有效期内）

### 侵权认定证据
- ✅ 侵权商品截图（已公证）
- ⚠️ 购买记录公证（建议补充）
- ⚠️ 侵权商品实物（建议补充）

### 损害赔偿证据
- ❌ 被告获利证据（缺失）
- ❌ 原告损失证据（缺失）
- ⚠️ 许可费证据（可补充）

---

## 五、建议行动方案

1. **立即补充证据**:
   - 对侵权商品进行购买公证
   - 收集被告销售数据（可申请法院调取）
   - 准备商标知名度证据（获奖记录、广告投入等）

2. **法律策略建议**:
   - 重点论证商标近似性和商品类似性
   - 准备驰名商标认定材料（如需要）
   - 考虑申请行为保全（禁令）

3. **风险提示**:
   - 赔偿额可能低于预期，建议调整预期
   - 被告可能提出商标不侵权抗辩，需提前准备反驳证据

---

## 六、附录

**评估模型版本**: v0.1.0 MVP
**Disclaimer**: 本报告为 AI 辅助生成，仅供内部决策参考，不构成法律意见。
"""

    return report

def evaluate_evidence_readiness(
    case_description: str,
    uploaded_evidence_texts: str = "",
    evidence_count: int = 0
) -> Dict[str, Any]:
    """
    证据就绪度评估（Mock 模式）
    返回与 llm_client.evaluate_evidence_readiness 相同的结构
    """
    mock_delay()

    return {
        "score": 68,
        "evidence_matrix": [
            {
                "requirement": "权利基础证据",
                "standard_evidence": "商标注册证/续展证明/使用证据",
                "status": "充足",
                "analysis": "原告已上传商标注册证，权利基础证据完整"
            },
            {
                "requirement": "侵权认定证据",
                "standard_evidence": "侵权截图/购买取证/公证文书",
                "status": "不足",
                "analysis": "已有公证购买和页面截图，但缺少侵权商品实物比对"
            },
            {
                "requirement": "损害赔偿证据",
                "standard_evidence": "被告获利/原告损失/许可费",
                "status": "缺失",
                "analysis": "缺乏被告获利直接证据，原告损失计算依据不足"
            },
            {
                "requirement": "取证技术规范",
                "standard_evidence": "可信时间戳/区块链存证/公证",
                "status": "充足",
                "analysis": "已采用公证取证方式，符合电子证据规范"
            }
        ],
        "analysis": "证据体系框架基本建立，但损害赔偿证据明显缺失，建议在起诉前补充被告获利证据或申请法院调取销售数据",
        "missing_items": [
            "被告实际获利数据",
            "消费者混淆调查报告",
            "商标知名度证据（广告投入、获奖记录等）"
        ],
        "remediation_suggestions": [
            "申请法院调取被告电商平台销售记录",
            "委托第三方机构进行消费者混淆调查",
            "收集商标宣传推广证据以证明知名度"
        ],
        "collection_advice": "建议采用区块链存证固定后续发现的侵权证据，同时考虑申请法院证据保全"
    }


# ============================================================
# 模拟法庭 Mock - 多Agent五步庭审
# 返回结构与 moot_court.procedure.run_moot_court 一致
# ============================================================

def run_moot_court_simulation(
    case_description: str,
    rights_assessment: str = "",
    infringement_assessment: str = "",
    evidence_summary: str = ""
) -> Dict[str, Any]:
    """
    运行模拟法庭（Mock 模式）
    模拟完整的五步庭审流程，返回与真实 moot_court 模块相同的结构
    """
    mock_delay()

    rounds = [
        {
            "step": 1,
            "step_name": "开庭陈述",
            "role": "plaintiff",
            "role_name": "原告代理律师",
            "content": (
                "尊敬的审判长、审判员：\n\n"
                "我方受原告委托，就商标侵权一案发表开庭陈述。\n\n"
                "一、诉讼请求\n"
                "1. 请求判令被告立即停止侵犯原告第XXXX号注册商标专用权的行为；\n"
                "2. 请求判令被告赔偿经济损失人民币 80 万元；\n"
                "3. 请求判令被告在《中国知识产权报》刊登声明，消除影响。\n\n"
                "二、事实与理由\n"
                "原告系第XXXX号注册商标的专用权人，核定使用商品为第25类服装等，"
                "该商标经多年使用和宣传，已具有较高知名度。2023年1月，原告发现被告在"
                "电商平台上销售标有与原告注册商标近似标识的服装商品，销售规模较大，"
                "严重侵害了原告的商标专用权。\n\n"
                "三、法律依据\n"
                "依据《商标法》第57条第（二）项，未经商标注册人许可，在同一种商品上"
                "使用与其注册商标近似的商标，容易导致混淆的，属于侵犯注册商标专用权。"
                "依据《商标法》第63条，侵犯商标专用权的赔偿数额，按照权利人因被侵权"
                "所受到的实际损失确定。\n\n"
                "四、证据概要\n"
                "我方已固定以下证据：商标注册证及续展证明、被告侵权商品页面截图（已公证）、"
                "购买侵权商品实物（已公证）、被告店铺销售数据截图。"
            )
        },
        {
            "step": 2,
            "step_name": "被告答辩",
            "role": "defendant",
            "role_name": "被告代理律师",
            "content": (
                "尊敬的审判长、审判员：\n\n"
                "我方作为被告代理人，针对原告的诉讼请求发表如下答辩意见：\n\n"
                "一、对诉讼请求的总体回应\n"
                "我方请求驳回原告全部诉讼请求。我方不存在商标侵权行为，"
                "原告的诉讼请求缺乏事实和法律依据。\n\n"
                "二、对原告事实主张的逐项反驳\n"
                "1. 关于商标近似性：被诉标识与原告注册商标在字形、读音、含义上均存在"
                "明显差异，不构成近似商标。原告仅凭主观感受主张近似，缺乏客观对比分析。\n"
                "2. 关于商品类似性：我方销售的商品与原告核定使用的商品在功能、用途、"
                "销售渠道等方面存在差异，不构成类似商品。\n"
                "3. 关于混淆可能性：原告未提交任何消费者混淆的实际证据，"
                "仅凭推测主张混淆，不具有说服力。\n\n"
                "三、法律抗辩事由\n"
                "1. 依据《商标法》第59条，我方使用系描述性使用，属于正当使用。\n"
                "2. 即使认定标识近似，原告主张的赔偿金额明显过高，缺乏计算依据。\n\n"
                "四、证据质疑\n"
                "原告提及的公证证据，公证程序是否存在瑕疵需要审查。"
                "原告声称的销售数据截图，其真实性和关联性存在疑问。"
                "原告需进一步举证证明实际损失或被告获利。"
            )
        },
        {
            "step": 3,
            "step_name": "举证质证-原告举证",
            "role": "plaintiff",
            "role_name": "原告代理律师",
            "content": (
                "针对被告的答辩，我方作如下举证回应：\n\n"
                "一、对被告抗辩的回应\n"
                "1. 关于商标不近似：被诉标识\"XX服饰\"与原告注册商标\"XX\"在核心"
                "识别部分高度一致，一般公众施以普通注意力难以区分。我方将提交"
                "商标对比分析报告。\n"
                "2. 关于商品不类似：双方均从事服装销售，销售渠道均为电商平台，"
                "目标消费群体高度重合，构成类似商品。\n"
                "3. 关于正当使用：被告将标识用作商标性使用，而非描述性使用，"
                "不属于《商标法》第59条规定的正当使用情形。\n\n"
                "二、证据体系展示\n"
                "1. 权利基础证据：商标注册证（第XXXX号）、续展证明、商标使用证据\n"
                "2. 侵权固定证据：公证购买的侵权商品实物、侵权页面公证书\n"
                "3. 损害赔偿证据：被告店铺销量数据截图（部分）、原告许可费参考\n\n"
                "三、证据证明力\n"
                "公证购买证据具有完整的公证程序，真实性和合法性有保障。"
                "侵权页面截图经公证保全，能够证明被告的侵权行为持续状态。"
                "关于损害赔偿，虽目前缺乏被告完整获利数据，但我方将申请法院"
                "调取被告电商平台销售记录。"
            )
        },
        {
            "step": 3,
            "step_name": "举证质证-被告质证",
            "role": "defendant",
            "role_name": "被告代理律师",
            "content": (
                "针对原告举证，我方发表如下质证意见：\n\n"
                "一、真实性质疑\n"
                "1. 原告提交的公证购买证据，公证书中记载的购买时间与我方店铺"
                "上架时间存在矛盾，需核实公证程序的合法性。\n"
                "2. 侵权页面截图的截取时间、方式未在公证书中详细记载，"
                "电子证据的原始性无法确认。\n\n"
                "二、合法性质疑\n"
                "原告通过\"钓鱼式\"购买获取证据，购买行为本身可能诱导了"
                "侵权行为的发生，取证方式的合法性存疑。\n\n"
                "三、关联性质疑\n"
                "原告提交的商标使用证据，部分使用场景与本案核定商品无关，"
                "不能直接证明本案商标在涉案商品上的知名度。\n\n"
                "四、举证缺口\n"
                "1. 原告未提交消费者混淆调查报告，混淆可能性的主张缺乏证据支撑。\n"
                "2. 原告未提交被告实际获利的直接证据，赔偿请求缺乏计算基础。\n"
                "3. 原告未证明其商标在被告经营区域内的知名度，"
                "跨地域保护的主张依据不足。"
            )
        },
        {
            "step": 4,
            "step_name": "法庭辩论-原告",
            "role": "plaintiff",
            "role_name": "原告代理律师",
            "content": (
                "审判长，经过庭审调查，本案核心争议焦点已清晰显现：\n\n"
                "争议焦点一：被诉标识与原告注册商标是否构成近似\n"
                "我方认为，从字形结构、呼叫读音、整体视觉效果三个维度比较，"
                "被诉标识与原告商标构成近似。一般消费者在购物时施以普通注意力，"
                "极易产生混淆。被告虽主张差异，但未能提供任何客观对比依据。\n\n"
                "争议焦点二：被告使用行为是否属于正当使用\n"
                "被告将标识突出使用在商品标签和店铺名称中，起到了识别商品来源"
                "的功能，属于商标性使用，不适用《商标法》第59条的正当使用抗辩。\n\n"
                "争议焦点三：赔偿金额的合理确定\n"
                "综合考虑被告侵权持续时间、销售规模、原告商标知名度等因素，"
                "我方主张80万元赔偿具有合理性。即使部分获利数据尚未获取，"
                "依据《商标法》第63条法定赔偿条款，法院亦可在50万元以下"
                "酌情确定赔偿数额。\n\n"
                "综上所述，被告的侵权行为事实清楚、法律依据充分，"
                "请法庭支持我方全部诉讼请求。"
            )
        },
        {
            "step": 4,
            "step_name": "法庭辩论-被告",
            "role": "defendant",
            "role_name": "被告代理律师",
            "content": (
                "审判长，我方作最终辩论发言：\n\n"
                "一、关于商标近似性\n"
                "原告始终未能提交专业的商标近似性对比分析，仅凭主观判断主张近似。"
                "事实上，被诉标识在字体设计、排列方式、整体风格上与原告商标存在"
                "显著差异。原告将商标的核心识别部分片面提取进行比较，"
                "有违整体比对原则。\n\n"
                "二、关于混淆可能性\n"
                "原告未提交任何消费者混淆实际发生的证据。在电商平台环境下，"
                "消费者可以通过店铺名称、商品描述、价格等多重信息区分商品来源，"
                "混淆可能性远低于原告主张的程度。\n\n"
                "三、关于赔偿金额\n"
                "原告主张80万元赔偿，但未提交任何直接损失或被告获利的证据。"
                "原告引用的销量数据来源不明，不能作为赔偿计算依据。"
                "即使认定侵权成立，赔偿金额也应大幅降低。\n\n"
                "综上所述，原告的诉讼请求缺乏充分的事实和法律依据，"
                "请法庭依法驳回。支持原告诉请将对诚信经营的商家造成不当负担，"
                "不利于市场公平竞争环境的维护。"
            )
        },
        {
            "step": 5,
            "step_name": "法官归纳",
            "role": "judge",
            "role_name": "审判法官",
            "content": (
                "经审理，本庭对全案归纳如下：\n\n"
                "本案核心争议焦点为：1) 商标近似性认定；2) 商品类似性及混淆可能性；"
                "3) 赔偿金额的合理确定。\n\n"
                "原告在权利基础和侵权认定方面的论证总体成立，但在证据完整性上存在不足。"
                "被告提出的商标不近似抗辩有一定道理，但缺乏有力的反向证据支撑。"
                "被告对原告证据的三性质疑较为专业，特别是消费者混淆证据缺失"
                "和赔偿计算依据不足的问题，对原告论证构成实质性削弱。\n\n"
                "综合评估，原告单方评估结论在对抗检验后需适度修正，"
                "对抗修正系数为 0.90。"
            )
        }
    ]

    return {
        "rounds": rounds,
        "correction_coefficient": 0.90,
        "defense_strength": 65,
        "judge_summary": (
            "本案核心争议焦点为：1) 商标近似性认定；2) 商品类似性及混淆可能性；"
            "3) 赔偿金额的合理确定。原告在权利基础和侵权认定方面的论证总体成立，"
            "但在证据完整性上存在不足。被告提出的商标不近似抗辩有一定道理，"
            "但缺乏有力的反向证据支撑。被告对原告证据的三性质疑较为专业，"
            "特别是消费者混淆证据缺失和赔偿计算依据不足的问题，"
            "对原告论证构成实质性削弱。综合评估，对抗修正系数为 0.90。"
        ),
        "weak_points": [
            "缺乏消费者混淆实际发生的直接证据",
            "损害赔偿计算依据不足，被告获利数据未获取",
            "商标在被告经营区域内的知名度证据不充分",
            "部分公证取证程序的合法性可能受到质疑"
        ],
        "focus_points": [
            "商标近似性认定：原告主张近似，被告主张存在显著差异",
            "商品类似性及混淆可能性：原告未提交消费者混淆证据",
            "赔偿金额确定：原告主张80万但缺乏直接损失或获利证据"
        ],
        "judge_scores": {
            "plaintiff": {
                "rights": 82,
                "infringement": 70,
                "evidence": 60,
                "legal_application": 78,
                "claim_reasonableness": 55
            },
            "plaintiff_detail": {
                "rights": "原告商标权利基础论证充分，注册证和续展证明齐全",
                "infringement": "侵权认定论证基本成立，但混淆可能性缺乏实证",
                "evidence": "证据体系有框架但存在缺口，混淆和赔偿证据不足",
                "legal_application": "法条引用准确，但部分主张的法律适用需进一步论证",
                "claim_reasonableness": "80万赔偿请求偏高，缺乏充分计算依据"
            },
            "defendant": {
                "fact_defense": 60,
                "legal_defense": 65,
                "evidence_challenge": 75,
                "alternative_explanation": 50,
                "procedural_defense": 40
            },
            "defendant_detail": {
                "fact_defense": "对商标不近似的反驳有一定道理但缺乏反向证据",
                "legal_defense": "正当使用抗辩的法律适用较为勉强",
                "evidence_challenge": "对原告证据三性的质疑专业且有效",
                "alternative_explanation": "未能提供合理的非侵权行为解释",
                "procedural_defense": "程序性抗辩较为薄弱"
            },
            "coefficient_reasoning": (
                "被告抗辩在证据质疑维度表现突出，暴露了原告在消费者混淆证据和"
                "赔偿计算依据方面的明显缺口，对原告论证构成实质性削弱，"
                "故修正系数定为0.90。"
            )
        },
        "error": None
    }


# 向后兼容别名
def run_moot_court(case_facts: Dict = None, **kwargs) -> Dict[str, Any]:
    """向后兼容：旧接口调用转发到新函数"""
    if isinstance(case_facts, str):
        return run_moot_court_simulation(case_description=case_facts)
    return run_moot_court_simulation(
        case_description=kwargs.get("case_description", ""),
        rights_assessment=kwargs.get("rights_assessment", ""),
        infringement_assessment=kwargs.get("infringement_assessment", ""),
        evidence_summary=kwargs.get("evidence_summary", "")
    )
