"""
API 客户端公共基础设施 — Bearer token、配置检查、跳过结果。

供 qcc_api.py 和 pkulaw_api.py 共用，消除重复模式。
"""

from typing import Dict, Tuple

from config import get_runtime_settings


def require_token(env_key: str) -> Tuple[str, str, bool]:
    """
    获取 API token。
    返回 (token, error_message, is_configured)
    """
    token = get_runtime_settings().get(env_key, "").strip()
    if not token:
        return "", "未配置 {}".format(env_key), False
    return token, "", True


def bearer_headers(token: str) -> Dict[str, str]:
    """构建 Bearer 认证 + JSON 请求头"""
    auth_value = token if token.lower().startswith("bearer ") else "Bearer {}".format(token)
    return {
        "Authorization": auth_value,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def skipped_result(message: str, defaults: Dict = None) -> Dict:
    """构建 token 未配置时的跳过结果"""
    result = {
        "status": "skipped",
        "error": message,
        "_summary": message,
    }
    if defaults:
        result.update(defaults)
    return result
