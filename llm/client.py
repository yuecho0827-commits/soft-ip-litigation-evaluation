"""
统一 LLM 调用客户端 — DeepSeek API
整个项目唯一的 HTTP 调用入口，消除 llm_client.py 和 moot_court/agents.py 的代码重复。

提供两个接口：
  - call_text:   返回纯文本（用于生成发言等自由文本场景）
  - call_json:   返回解析后的 JSON dict（用于结构化评估）
"""
import json
import urllib.request
import urllib.error
from typing import Dict
from config import get_runtime_settings

def _get_settings() -> dict:
    """获取运行时设置并验证 API Key"""
    settings = get_runtime_settings()
    api_key = settings['deepseek_api_key']
    if not api_key.strip():
        raise RuntimeError('未配置 DEEPSEEK_API_KEY，真实 Demo 模式无法调用 DeepSeek')
    return settings

def _strip_markdown_fences(raw: str) -> str:
    """清理 LLM 返回文本中的 markdown 代码块标记"""
    text = raw.strip()
    if text.startswith('```json'):
        text = text[len('```json'):].strip()
    elif text.startswith('```'):
        text = text[3:].strip()
    if text.endswith('```'):
        text = text[:-3].strip()
    return text

def _call_deepseek_api(system_prompt: str, user_prompt: str, temperature: float=0.2, max_tokens: int=4000) -> str:
    """
    调用 DeepSeek Chat API，返回原始文本。
    所有 LLM 调用的底层统一入口。
    """
    settings = _get_settings()
    base_url = settings['deepseek_base_url'].rstrip('/')
    url = f'{base_url}/v1/chat/completions'
    payload = json.dumps({'model': 'deepseek-chat', 'max_tokens': max_tokens, 'temperature': temperature, 'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}]}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Authorization', f"Bearer {settings['deepseek_api_key']}")
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result['choices'][0]['message']['content'].strip()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'API 错误 ({e.code})')
    except Exception as e:
        raise RuntimeError(f'API 调用失败: {e}')

def call_text(system_prompt: str, user_prompt: str, temperature: float=0.3, max_tokens: int=2000) -> str:
    """调用 LLM，返回纯文本。用于生成发言、分析等自由文本场景。"""
    return _call_deepseek_api(system_prompt, user_prompt, temperature, max_tokens)

def call_json(system_prompt: str, user_prompt: str, temperature: float=0.2, max_tokens: int=4000) -> Dict:
    """
    调用 LLM，返回解析后的 JSON dict。
    用于结构化评估、法官归纳等需要机器解析的场景。
    """
    raw = _call_deepseek_api(system_prompt, user_prompt, temperature, max_tokens)
    raw = _strip_markdown_fences(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {'error': 'JSON 解析失败', 'raw': raw[:500]}