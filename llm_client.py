"""
LLM 评估引擎 - 基于 DeepSeek API
严格按 v1 产品方案的三个维度 + 子维度设计
每一环节都是一个独立的 LLM 调用，返回结构化评估结果
"""
import json
from typing import Dict, Any, Optional
from config import get_runtime_settings
from llm import call_json

def _call_llm(system_prompt: str, user_prompt: str, temperature: float=0.2) -> dict:
    """调用 DeepSeek LLM，返回解析后的 JSON（委托给统一的 llm.client）"""
    return call_json(system_prompt, user_prompt, temperature=temperature)

def _has_pkulaw(d) -> bool:
    """判断 pkulaw_data 是否有有效数据"""
    if not d or not isinstance(d, dict):
        return False
    return bool(d.get('laws')) or bool(d.get('cases'))

def _fmt_laws(pkulaw_data: dict) -> str:
    """格式化法条上下文"""
    if not _has_pkulaw(pkulaw_data):
        return ''
    items = pkulaw_data.get('laws', [])[:5]
    if not items:
        return ''
    parts = ['\n## 北大法宝检索到的法条（主要分析依据）\n']
    for i, it in enumerate(items, 1):
        title = it.get('title', '')
        content = it.get('content', '')
        time = it.get('timeliness', '')
        parts.append(f'{i}. {title}（{time}）' if time else f'{i}. {title}')
        if content:
            parts.append(f'   {content[:300]}')
    return '\n'.join(parts)

def _fmt_cases(pkulaw_data: dict) -> str:
    """格式化类案上下文"""
    if not _has_pkulaw(pkulaw_data):
        return ''
    items = pkulaw_data.get('cases', [])[:5]
    if not items:
        return ''
    parts = ['\n## 北大法宝检索到的类案（参考判例）\n']
    for i, it in enumerate(items, 1):
        title = it.get('title', '')
        court = it.get('court', '')
        date = it.get('date', '')
        summary = it.get('summary', '')
        line = f'{i}. {title}'
        meta = ' · '.join([x for x in [court, date] if x])
        if meta:
            line += f'（{meta}）'
        parts.append(line)
        if summary:
            parts.append(f'   {summary[:200]}')
    return '\n'.join(parts)

def evaluate_rights_foundation(case_description: str, party_info: str='', uploaded_texts: str='', pkulaw_data: dict=None) -> Dict:
    """
    子维度 1.1：权利基础评估
    评估商标权的有效性、使用情况、撤三风险、跨类保护可能性
    """
    prompt = f"""你是资深知识产权律师。请基于以下信息，评估原告商标权利基础的稳固程度。\n\n## 案情描述\n{case_description[:3000]}\n\n## 当事人信息\n{(party_info[:1000] if party_info else '未提供')}\n\n## 证据材料文本\n{(uploaded_texts[:2000] if uploaded_texts else '未提供')}\n{_fmt_laws(pkulaw_data)}\n\n## 评估框架\n请从以下维度评估商标权利基础：\n1. 商标是否有效注册、当前状态（是否在有效期内）\n2. 是否连续三年使用（防止被撤三）\n3. 核定商品/服务范围是否覆盖侵权行为\n4. 是否为驰名商标（可跨类保护）\n5. 是否存在无效/撤销/异议风险\n\n## 返回格式（严格 JSON）\n{{\n  "score": 0-100,\n  "sub_scores": {{\n    "validity": {{"score": 0-100, "reason": "1句话理由"}},\n    "usage_continuity": {{"score": 0-100, "reason": "1句话理由"}},\n    "coverage": {{"score": 0-100, "reason": "1句话理由"}},\n    "well_known_status": {{"score": 0-100, "reason": "1句话理由"}},\n    "risk_of_invalidation": {{"score": 0-100(分数越低=风险越高), "reason": "1句话理由"}}\n  }},\n  "analysis": "整体分析（150字以内）",\n  "strengths": ["优势1", "优势2"],\n  "risks": ["风险1", "风险2"],\n  "red_flag": true/false (是否<60分)\n}}\n\n只返回 JSON，不要任何其他文字。"""
    return _call_llm('你是资深知识产权律师，专注于商标权利基础评估。请严格按 JSON 格式返回。', prompt, 0.2)

def evaluate_infringement(case_description: str, rights_assessment: str='', uploaded_texts: str='', pkulaw_data: dict=None) -> Dict:
    """
    子维度 1.2：侵权认定评估（单方视角）
    分析商标侵权构成要件：商标性使用、商品类似性、商标近似性、混淆可能性、正当使用
    """
    prompt = f"""你是资深知识产权法官。请基于以下信息，分析商标侵权构成要件的成立可能性。\n\n## 案情描述\n{case_description[:3000]}\n\n## 权利基础评估概要\n{(rights_assessment[:1500] if rights_assessment else '未提供')}\n\n## 证据材料\n{(uploaded_texts[:2000] if uploaded_texts else '未提供')}\n{_fmt_laws(pkulaw_data)}\n{_fmt_cases(pkulaw_data)}\n\n## 评估框架（商标侵权五要件）\n逐一分析以下要件是否满足：\n1. 被告是否构成"商标性使用"\n2. 商品/服务是否相同或类似\n3. 商标是否相同或近似\n4. 是否可能导致消费者混淆\n5. 是否为正当使用\n\n## 返回格式（严格 JSON）\n{{\n  "score": 0-100 (综合得分),\n  "elements": [\n    {{\n      "name": "商标性使用",\n      "score": 0-100,\n      "status": "满足/存疑/不满足",\n      "analysis": "分析理由"\n    }},\n    ...\n  ],\n  "analysis": "整体侵权认定分析（150字以内）",\n  "strengths": ["优势"],\n  "risks": ["风险"],\n  "red_flag": true/false\n}}\n\n只返回 JSON。"""
    return _call_llm('你是资深知识产权法官，擅长商标侵权构成要件分析。请严格按 JSON 格式返回。', prompt, 0.2)

def evaluate_procedure(case_description: str, party_info: str='', pkulaw_data: dict=None) -> Dict:
    """
    子维度 1.3：诉讼程序审查
    时效、管辖、主体适格、前置程序
    """
    prompt = f"""你是资深诉讼律师。请审查以下案件的程序可行性。\n\n## 案情描述\n{case_description[:3000]}\n\n## 当事人信息\n{(party_info[:1000] if party_info else '未提供')}\n{_fmt_laws(pkulaw_data)}\n\n## 评估框架\n1. 诉讼时效（3年，自知道权利受损+义务人之日起算）\n2. 管辖与仲裁（是否存在仲裁协议、管辖法院是否有利）\n3. 主体适格（原告是否为适格权利人、被告是否明确）\n4. 前置程序（行政前置、通知-删除等）\n\n## 返回格式（严格 JSON）\n{{\n  "score": 0-100,\n  "items": [\n    {{\n      "name": "诉讼时效",\n      "score": 0-100,\n      "status": "pass/warning/block",\n      "detail": "分析"\n    }},\n    ...\n  ],\n  "analysis": "整体程序评估",\n  "block_items": ["阻塞项"],\n  "red_flag": true/false\n}}\n\n只返回 JSON。"""
    return _call_llm('你是资深诉讼律师，擅长程序审查。请严格按 JSON 格式返回。', prompt, 0.2)

def run_moot_court_simulation(case_description: str, rights_assessment: str, infringement_assessment: str, evidence_summary: str, pkulaw_data: dict=None) -> Dict:
    """
    子维度 1.4：模拟法庭（对抗检验）
    五步庭审：原告陈述→被告答辩→举证质证→法庭辩论→法官归纳
    """
    prompt = f"""你是一个模拟法庭的协调者。请在原告视角的分析基础上，模拟完整的庭审过程。\n\n## 案情\n{case_description[:2000]}\n\n## 权利基础评估\n{rights_assessment[:1000]}\n\n## 侵权认定评估（原告视角）\n{infringement_assessment[:1000]}\n{_fmt_cases(pkulaw_data)}\n\n## 证据概要\n{(evidence_summary[:1000] if evidence_summary else '未提供')}\n\n## 模拟法庭五步\n请按照原告（Pl）、被告（Def）、法官（Judge）三个角色，完成以下五个环节的模拟：\n1. 原告陈述（诉讼请求+事实理由+法律依据）\n2. 被告答辩（逐项反驳+抗辩策略+可能的反诉）\n3. 举证质证（原告证据的"三性"审查+被告可能的反证）\n4. 法庭辩论（围绕争议焦点各两轮）\n5. 法官归纳（争议焦点总结+薄弱点+被告抗辩强度评估+对抗修正系数）\n\n## 返回格式（严格 JSON）\n{{\n  "rounds": [\n    {{"role": "原告", "content": "..."}},\n    {{"role": "被告", "content": "..."}},\n    {{"role": "法官", "content": "..."}}\n  ],\n  "judge_summary": "法官归纳摘要",\n  "weak_points": ["原告论证薄弱点"],\n  "defense_strength": 0-100 (被告抗辩强度),\n  "correction_coefficient": 0.7-1.3 (对抗检验修正系数, 默认1.0)\n}}\n\n只返回 JSON。"""
    return _call_llm('你是一个模拟法庭系统，负责协调原告、被告、法官三个角色完成庭审模拟。请严格按 JSON 格式返回。', prompt, 0.3)

def _has_qcc(d) -> bool:
    """判断 qcc_data 是否有有效数据"""
    if not d or not isinstance(d, dict):
        return False
    return bool(d.get('_summary')) or bool(d.get('metrics'))

def _fmt_qcc(qcc_data: dict) -> str:
    """格式化企查查关键发现为 prompt 文本"""
    if not _has_qcc(qcc_data):
        return ''
    parts = ['\n## 企查查 · 被告财务画像（实测数据，作为判赔预测依据）\n']
    summary = qcc_data.get('_summary', '')
    if summary:
        parts.append(f'**检索摘要**: {summary}')
    metrics = qcc_data.get('metrics', {})
    if metrics:
        prob = metrics.get('recovery_probability', '-')
        parts.append(f'- 回款概率(企查查测算): {prob}%')
        da = metrics.get('damages_adjustment', '')
        if da:
            parts.append(f'- 判赔调整方向: {da}')
        extra = metrics.get('time_extra_months', 0)
        parts.append(f'- 时间延长量: +{extra}月')
        reds = metrics.get('red_flags', [])
        if reds:
            parts.append(f"- 🚨 风险信号: {'; '.join(reds[:5])}")
        greens = metrics.get('green_flags', [])
        if greens:
            parts.append(f"- ✅ 利好信号: {'; '.join(greens[:5])}")
    stages = qcc_data.get('stages', {})
    d_stage = stages.get('D_风险下钻', {})
    if d_stage:
        parts.append('\n### 被告风险明细（企查查实测）')
        for label in ('失信信息', '被执行人', '终本案件', '限高消费', '经营异常', '严重违法'):
            row = d_stage.get(label, {})
            if isinstance(row, dict) and row.get('_summary'):
                parts.append(f"- {label}: {row['_summary']}")
    f_stage = stages.get('F_经营规模', {})
    if f_stage:
        fsum = f_stage.get('_summary', '')
        if fsum:
            parts.append(f'\n### 被告经营规模\n{fsum}')
    return '\n'.join(parts)

def evaluate_financial_return(case_description: str, infringement_severity: str='', case_law_references: str='', pkulaw_data: dict=None, qcc_data: dict=None) -> Dict:
    """
    子维度 2.1：财务回报评估
    判赔预测 + 成本估算 + 时间成本 + 执行回款概率
    企查查数据为判赔预测和回款概率提供实测先验参数
    """
    prompt = f"""你是知识产权诉讼财务分析师。请评估商标侵权案件的财务可行性。\n\n## 案情\n{case_description[:3000]}\n\n## 侵权严重程度\n{(infringement_severity[:1000] if infringement_severity else '待分析')}\n\n## 类案参考\n{(case_law_references[:2000] if case_law_references else '暂无（建议使用北大法宝检索同类案件')}\n{_fmt_cases(pkulaw_data)}\n{_fmt_qcc(qcc_data)}\n\n## 评估框架\n请基于以上信息（特别是企查查实测数据），分析以下5项：\n1. 预期判赔/和解金额（结合法定赔偿区间、类案数据、企查查提供的被告经营规模和风险画像，惩罚性赔偿概率）\n2. 诉讼成本估算（律师费、诉讼费、公证费等）\n3. 时间成本（一审+二审+执行周期，结合企查查提供的被告拖延倾向和执行风险）\n4. 执行回款概率（结合企查查实测被告偿付能力数据：失信/被执行/终本/限高等风险信号）\n5. 净收益预测 NPV = P50 × 回款概率 - 总成本 - 时间折现\n\n## 返回格式（严格 JSON）\n{{\n  "score": 0-100,\n  "damages_estimate": {{\n    "p10": 赔偿额10分位(元),\n    "p50": 赔偿额中位数(元),\n    "p90": 赔偿额90分位(元),\n    "basis": "估算依据"\n  }},\n  "cost_estimate": 预估总成本(元),\n  "time_estimate": {{\n    "first_instance_months": 一审月数,\n    "second_instance_months": 二审月数,\n    "enforcement_months": 执行月数\n  }},\n  "recovery_probability": 0-100 (回款概率百分比, 参考但不照搬企查查数据),\n  "net_present_value": "净收益估算",\n  "analysis": "财务分析总结（200字以内，必须引用企查查的风险/利好信号）"\n}}\n\n只返回 JSON。"""
    return _call_llm('你是知识产权诉讼财务分析师。请严格按 JSON 格式返回，必须参考企查查实测数据。', prompt, 0.2)

def evaluate_precedent_value(case_description: str, case_law_references: str='', pkulaw_data: dict=None) -> Dict:
    """
    子维度 2.2：判例价值评估
    首案潜力 + 指导性案例潜力 + 行业震慑效应 + 规则明晰价值
    """
    prompt = f"""你是知识产权领域专家。请评估该案件可能产生的判例价值。\n\n## 案情\n{case_description[:3000]}\n\n## 类案参考\n{(case_law_references[:2000] if case_law_references else '暂无（建议使用北大法宝检索确认是否存在同类在先判决')}\n{_fmt_cases(pkulaw_data)}\n\n## 评估框架\n1. 首案潜力（涉及的法律问题是否有在先判例）\n2. 指导性案例潜力（是否符合最高法指导性案例/典型案例遴选标准）\n3. 行业震慑效应（胜诉后对其他侵权者的威慑力）\n4. 规则明晰价值（能否推动模糊法律规则的明确化）\n\n## 返回格式（严格 JSON）\n{{\n  "score": 0-100,\n  "first_case_index": 0-100 (首案指数),\n  "influence_level": "行业级/区域级/个案级",\n  "analysis": "判例价值分析（150字以内）",\n  "key_points": ["价值点1", "价值点2"]\n}}\n\n只返回 JSON。"""
    return _call_llm('你是知识产权领域专家，擅长判例价值评估。请严格按 JSON 格式返回。', prompt, 0.2)

def evaluate_evidence_readiness(case_description: str, uploaded_evidence_texts: str='', evidence_count: int=0) -> Dict:
    """
    维度三：证据就绪度评估
    对照商标侵权标准取证清单，检查证据完整性
    """
    prompt = f"""你是知识产权证据审查专家。请评估案件证据的就绪程度。\n\n## 案情\n{case_description[:2000]}\n\n## 已上传证据材料\n{(uploaded_evidence_texts[:3000] if uploaded_evidence_texts else '未上传证据文件（仅凭案情描述分析）')}\n已上传文件数: {evidence_count}\n\n## 评估框架（商标侵权标准取证清单）\n逐项检查以下证据是否满足：\n1. 权利基础证据：商标注册证/续展证明/使用证据（防撤三）\n2. 侵权认定证据：侵权截图/购买取证/公证文书\n3. 损害赔偿证据：被告获利/原告损失/许可费/侵权规模\n4. 取证技术建议：可信时间戳/区块链存证/公证取证\n\n## 返回格式（严格 JSON）\n{{\n  "score": 0-100,\n  "evidence_matrix": [\n    {{\n      "requirement": "要件名",\n      "standard_evidence": "标准证据",\n      "status": "充足/不足/缺失",\n      "analysis": "分析"\n    }}\n  ],\n  "analysis": "整体证据评估",\n  "missing_items": ["缺失项1"],\n  "remediation_suggestions": ["补证建议1"],\n  "collection_advice": "取证技术建议"\n}}\n\n只返回 JSON。"""
    return _call_llm('你是知识产权证据审查专家。请严格按 JSON 格式返回。', prompt, 0.2)

def extract_defendant_info(case_description: str) -> dict:
    """
    从案情描述中提取被告结构化身份信息。
    返回: {defendants:[{name,type,aliases,location_hint,industry_hint,scale_hint,...}], ...}
    """
    prompt = f'你是一个法律信息提取引擎。你的任务是从 Soft IP 案件的案情描述中，精确提取被告的身份信息。\n\n## 提取规则\n\n1. **名称提取**：优先提取法定全称（如"北京字节跳动网络技术有限公司"），同时记录简称。只有简称时在 name 填简称，uncertainties 标注"仅获取简称，需外部消歧"。自然人提取姓名。\n\n2. **类型判断**：\n   - 含"公司/有限公司/股份有限公司" → enterprise\n   - 含"厂/店/工作室/经营部" + 自然人姓名 → self_employed\n   - 纯自然人姓名（无公司后缀）→ individual\n   - 含"协会/基金会/事业单位" → other_org\n\n3. **隐性信息**：从侵权规模描述提取 scale_hint，从侵权行为地提取 location_hint，从侵权商品类型推断 industry_hint，原文中的财务数据填入 known_financial_context。\n\n4. **多被告**：逐一提取，标注 role（primary_defendant / co_defendant）。\n\n## 内容\n{case_description[:4000]}\n\n## 返回格式（严格 JSON，不含其他内容）\n{{\n  "defendants": [\n    {{\n      "name": "法定全称或最佳近似",\n      "aliases": ["简称1"],\n      "type": "enterprise|individual|self_employed|other_org",\n      "role": "primary_defendant|co_defendant",\n      "location_hint": "",\n      "industry_hint": "",\n      "scale_hint": "",\n      "known_financial_context": "",\n      "extracted_from": "原文字句",\n      "confidence": 0.0-1.0\n    }}\n  ],\n  "uncertainties": [],\n  "total_defendants": 0\n}}\n\n只返回 JSON。'
    return _call_llm('你是一个法律信息提取引擎，专门从 Soft IP 案文中提取被告身份。严格按 JSON 返回，不要猜测，信息不足时标注 confidence 下降。', prompt, 0.1)

def check_api_connection() -> bool:
    """检查 DeepSeek API 连接"""
    try:
        _call_llm('回复 OK', '回复 OK')
        return True
    except Exception:
        return False