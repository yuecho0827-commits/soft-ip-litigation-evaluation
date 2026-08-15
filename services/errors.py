"""
应用级异常和错误处理。

提供统一的 AppError 基类，所有业务异常继承于此，方便上层统一捕获和展示。
"""


class AppError(RuntimeError):
    """应用基类异常 — 标记业务错误（区别于系统级异常）"""

    def __init__(self, message: str, error_code: str = "APP_ERROR"):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = message


class ConfigError(AppError):
    """配置错误"""
    pass


class APIError(AppError):
    """外部 API 调用错误"""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message, error_code="API_ERROR")
        self.status_code = status_code


class EvaluationError(AppError):
    """评估流程错误"""
    pass
