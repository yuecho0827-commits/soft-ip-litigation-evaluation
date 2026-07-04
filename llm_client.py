"""
真实 LLM 客户端 - DeepSeek API
使用标准库 urllib，零额外依赖
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, List
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


def _call_deepseek(messages: list, temperature: float = 0.3) -> str:
    """调用 DeepSeek API，返回文本"""
    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {DEEPSEEK_API_KEY}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"API 调用失败 ({e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"API 调用异常: {e}")


def _call_deepseek_json(messages: list) -> dict:
    """调用 DeepSeek API，要求返回 JSON，自动解析"""
    # 在 system prompt 末尾追加 JSON 格式要求
    if messages[0]["role"] == "system":
        messages[0]["content"] += "\n\n请严格按照 JSON 格式返回，不要包含任何 markdown 标记或额外解释文字，只输出纯 JSON。"
    else:
        messages.insert(0, {
            "role": "system",
            "content": "请严格按照 JSON 格式返回，不要包含任何 markdown 标记或额外解释文字，只输出纯 JSON。"
        })

    raw = _call_deepseek(messages, temperature=0.2)

    # 清理可能的 markdown 代码块标记
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    return json.loads(raw)


# ============================================================
# 案情事实提取
# ============================================================

EXTRACT_FACTS_PROMPT = """你是一位资深的知识产权律师，请从以下案件描述中提取关键信息，以 JSON 格式返回。

案件描述：
{description}

请提取以下内容，返回严格 JSON：

{{
  "parties": [
    {{"role": "plaintiff/defendant", "name": "当事人名称", "type": "company/individual"}}
  ],
  "timeline": [
    {{"date": "YYYY-MM-DD", "event": "事件描述"}}
  ],
  "key_facts": [
    "关键事实1", "关键事实2"
  ],
  "trademark_info": {{
    "owner": "权利人",
    "registration_number": "注册号（如有）",
    "category": "商品/服务类别（如有）",
    "status": "有效/争议中"
  }},
  "infringement_summary": "侵权行为概述（一句话）",
  "evidence_checklist": {{
    "has_rights_proof": true/false,
    "has_infringement_proof": true/false,
    "has_damage_proof": true/false
  }}
}}

注意：
- 如果某信息在描述中未提及，用空字符串 "" 或空数组 []
- evidence_checklist 根据描述中是否提到相关证据判断
- key_facts 只列出与案件法律评估直接相关的事实"""


def extract_case_facts_real(case_description: str) -> Dict[str, Any]:
    """真实 API：从案情描述提取事实"""
    prompt = EXTRACT_FACTS_PROMPT.format(description=case_description)
    result = _call_deepseek_json([
        {"role": "system", "content": "你是一位资深知识产权律师，擅长从案件描述中提取结构化信息。"},
        {"role": "user", "content": prompt}
    ])
    return result


# ============================================================
# 法律要件分析（商标侵权）
# ============================================================

LEGAL_ANALYSIS_PROMPT = """你是一位资深知识产权法官，请基于以下案件事实，对商标侵权的构成要件进行逐项分析，以 JSON 格式返回。

## 案件事实
- 权利人: {rights_holder}
- 被告: {defendant}
- 关键事实:
{key_facts}
- 商标状态: {trademark_status}

## 分析框架（商标侵权五要件）

1. **权利基础**：原告是否为注册商标权利人？商标是否有效？
2. **商标使用行为**：被告是否在商业活动中使用了被诉标识？
3. **商品/服务相同或类似**：被诉商品与原告商标核定使用的商品/服务是否相同或类似？
4. **商标相同或近似**：被诉标识与原告注册商标是否相同或近似，是否容易导致混淆？
5. **无正当理由**：被告是否有权使用该标识（如获得授权、正当使用等）？

请返回严格 JSON：
{{
  "elements": [
    {{
      "element": "权利基础",
      "score": 0-100,
      "analysis": "分析理由",
      "evidence_status": "充足/部分充足/不足",
      "risks": ["风险点1", "风险点2"]
    }},
    {{
      "element": "商标使用行为",
      "score": 0-100,
      "analysis": "分析理由",
      "evidence_status": "充足/部分充足/不足/无法判断",
      "risks": []
    }},
    {{
      "element": "商品类似性",
      "score": 0-100,
      "analysis": "分析理由",
      "evidence_status": "充足/部分充足/不足/无法判断",
      "risks": []
    }},
    {{
      "element": "商标近似性",
      "score": 0-100,
      "analysis": "分析理由",
      "evidence_status": "充足/部分充足/不足/无法判断",
      "risks": []
    }},
    {{
      "element": "无正当理由",
      "score": 0-100,
      "analysis": "分析理由",
      "evidence_status": "充足/部分充足/不足/无法判断",
      "risks": []
    }}
  ],
  "overall_legal_feasibility": 0-100,
  "key_risks": ["整体风险点"],
  "key_strengths": ["整体优势"]
}}

评分标准：
- 81-100：要件成立可能性极高，证据充分
- 61-80：要件可能成立，有一定证据支持
- 41-60：要件成立存在争议，证据不足
- 21-40：要件成立难度较大
- 0-20：要件难以成立

如果信息不足，请基于现有信息做合理推断，并在 analysis 中说明推断依据和不确定性。"""


def analyze_legal_elements_real(case_facts: Dict) -> Dict[str, Any]:
    """真实 API：分析法律要件"""
    parties = case_facts.get("parties", [])
    plaintiff = next((p["name"] for p in parties if p["role"] == "plaintiff"), "原告")
    defendant = next((p["name"] for p in parties if p["role"] == "defendant"), "被告")

    key_facts = "\n".join(f"- {f}" for f in case_facts.get("key_facts", []))

    tm_info = case_facts.get("trademark_info", {})
    trademark_status = tm_info.get("status", "未知")

    prompt = LEGAL_ANALYSIS_PROMPT.format(
        rights_holder=plaintiff,
        defendant=defendant,
        key_facts=key_facts,
        trademark_status=trademark_status
    )

    return _call_deepseek_json([
        {"role": "system", "content": "你是一位资深知识产权法官，擅长对商标侵权案件进行要件分析和评估。请严格返回 JSON。"},
        {"role": "user", "content": prompt}
    ])


# ============================================================
# 健康检查
# ============================================================

def check_api_connection() -> bool:
    """检查 DeepSeek API 连接"""
    try:
        _call_deepseek([
            {"role": "user", "content": "回复 OK"}
        ], temperature=0)
        return True
    except Exception as e:
        print(f"API 连接失败: {e}")
        return False
