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

# 后续扩展点：模拟法庭 Mock
def run_moot_court(case_facts: Dict) -> List[Dict[str, Any]]:
    """
    运行模拟法庭（Mock 模式）
    后续可接入真实 LLM 多 Agent 框架
    """
    mock_delay()

    return [
        {
            "round": 1,
            "speaker": "plaintiff",
            "role_name": "原告代理律师",
            "content": "我方主张：被告在同类商品上使用与原告注册商标近似的标识，容易导致混淆，构成商标侵权。提交证据证明：1) 原告注册商标证；2) 被告侵权商品截图..."
        },
        {
            "round": 2,
            "speaker": "defendant",
            "role_name": "被告代理律师",
            "content": "我方抗辩：1) 被诉标识与原告注册商标不构成近似；2) 商品类别不同，不会导致混淆；3) 我方使用系正当使用..."
        },
        {
            "round": 3,
            "speaker": "judge",
            "role_name": "合议庭",
            "content": "争议焦点归纳：1) 商标近似性认定；2) 商品类似性认定；3) 赔偿额计算标准。请双方围绕上述争点进一步举证。"
        }
    ]
