"""
模拟法庭 Agent 定义
三个独立 Agent：原告、被告、法官
每个 Agent 维护自己的角色设定和对话历史

LLM 调用封装：
  - call_llm_text: 返回纯文本（用于原告/被告发言）
  - call_llm_json: 返回 JSON dict（用于法官归纳）
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from config import get_runtime_settings

from . import prompts


# ============================================================
# LLM 调用封装
# ============================================================

def call_llm_text(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    """
    调用 DeepSeek API，返回纯文本（不解析 JSON）
    用于原告/被告 Agent 的发言生成
    """
    settings = get_runtime_settings()
    api_key = settings["deepseek_api_key"]
    base_url = settings["deepseek_base_url"].rstrip("/")
    if not api_key.strip():
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，真实 Demo 模式无法调用 DeepSeek")
    url = f"{base_url}/v1/chat/completions"
    payload = json.dumps({
        "model": "deepseek-chat",
        "max_tokens": 2000,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 错误 ({e.code})")
    except Exception as e:
        raise RuntimeError(f"API 调用失败: {e}")


def call_llm_json(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
    """
    调用 DeepSeek API，返回解析后的 JSON dict
    用于法官 Agent 的结构化归纳
    """
    settings = get_runtime_settings()
    api_key = settings["deepseek_api_key"]
    base_url = settings["deepseek_base_url"].rstrip("/")
    if not api_key.strip():
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，真实 Demo 模式无法调用 DeepSeek")
    url = f"{base_url}/v1/chat/completions"
    payload = json.dumps({
        "model": "deepseek-chat",
        "max_tokens": 4000,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 错误 ({e.code})")
    except Exception as e:
        raise RuntimeError(f"API 调用失败: {e}")

    # 清理 markdown 标记
    if raw.startswith("```json"):
        raw = raw.split("\n", 1)[1]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "JSON 解析失败", "raw": raw[:500]}


# ============================================================
# 原告 Agent
# ============================================================

class PlaintiffAgent:
    """原告代理律师 Agent - 拥有完整案件信息和单方评估结果"""

    def __init__(self):
        self.system_prompt = prompts.PLAINTIFF_SYSTEM
        self.role_name = "原告代理律师"
        self.history = []

    def opening_statement(
        self,
        case_description: str,
        rights_assessment: str,
        infringement_assessment: str
    ) -> str:
        """第一步：开庭陈述"""
        user_prompt = prompts.OPENING_STATEMENT_USER.format(
            case_description=case_description[:3000],
            rights_assessment=rights_assessment[:1500] if rights_assessment else "未提供",
            infringement_assessment=infringement_assessment[:1500] if infringement_assessment else "未提供"
        )
        response = call_llm_text(self.system_prompt, user_prompt, temperature=0.3)
        self.history.append({"step": "opening", "content": response})
        return response

    def evidence_presentation(
        self,
        defendant_response: str,
        case_description: str,
        evidence_summary: str,
        has_rights_proof: bool = True,
        has_infringement_proof: bool = True,
        has_damage_proof: bool = False
    ) -> str:
        """第三步：举证回应"""
        user_prompt = prompts.EVIDENCE_PLAINTIFF_USER.format(
            defendant_response=defendant_response[:2000],
            case_description=case_description[:2000],
            evidence_summary=evidence_summary[:1500] if evidence_summary else "未上传证据文件",
            has_rights_proof="是" if has_rights_proof else "否",
            has_infringement_proof="是" if has_infringement_proof else "否",
            has_damage_proof="是" if has_damage_proof else "否"
        )
        response = call_llm_text(self.system_prompt, user_prompt, temperature=0.3)
        self.history.append({"step": "evidence", "content": response})
        return response

    def closing_argument(self, full_transcript: str) -> str:
        """第四步：法庭辩论"""
        user_prompt = prompts.DEBATE_PLAINTIFF_USER.format(
            full_transcript=full_transcript[:4000]
        )
        response = call_llm_text(self.system_prompt, user_prompt, temperature=0.4)
        self.history.append({"step": "debate", "content": response})
        return response


# ============================================================
# 被告 Agent
# ============================================================

class DefendantAgent:
    """被告代理律师 Agent - 只知道公开案情，不知道原告内部评估"""

    def __init__(self):
        self.system_prompt = prompts.DEFENDANT_SYSTEM
        self.role_name = "被告代理律师"
        self.history = []

    def defense_response(
        self,
        plaintiff_opening: str,
        case_description: str
    ) -> str:
        """第二步：被告答辩"""
        user_prompt = prompts.DEFENSE_RESPONSE_USER.format(
            plaintiff_opening=plaintiff_opening[:2000],
            case_description=case_description[:2000]
        )
        response = call_llm_text(self.system_prompt, user_prompt, temperature=0.3)
        self.history.append({"step": "defense", "content": response})
        return response

    def cross_examination(self, plaintiff_evidence_response: str) -> str:
        """第三步：质证"""
        user_prompt = prompts.EVIDENCE_DEFENDANT_USER.format(
            plaintiff_evidence_response=plaintiff_evidence_response[:2000]
        )
        response = call_llm_text(self.system_prompt, user_prompt, temperature=0.3)
        self.history.append({"step": "cross_exam", "content": response})
        return response

    def closing_argument(self, full_transcript: str) -> str:
        """第四步：法庭辩论"""
        user_prompt = prompts.DEBATE_DEFENDANT_USER.format(
            full_transcript=full_transcript[:4000]
        )
        response = call_llm_text(self.system_prompt, user_prompt, temperature=0.4)
        self.history.append({"step": "debate", "content": response})
        return response


# ============================================================
# 法官 Agent
# ============================================================

class JudgeAgent:
    """法官 Agent - 中立评判，产出修正系数"""

    def __init__(self):
        self.system_prompt = prompts.JUDGE_SYSTEM
        self.role_name = "审判法官"
        self.history = []

    def final_summary(
        self,
        full_transcript: str,
        case_description: str
    ) -> Dict[str, Any]:
        """第五步：法官归纳，返回结构化 JSON"""
        user_prompt = prompts.JUDGE_SUMMARY_USER.format(
            full_transcript=full_transcript[:5000],
            case_description=case_description[:2000]
        )
        result = call_llm_json(self.system_prompt, user_prompt, temperature=0.2)
        self.history.append({"step": "summary", "content": result})
        return result
