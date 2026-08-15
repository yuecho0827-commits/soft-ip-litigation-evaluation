"""
统一日志模块 — 所有模块共用的日志入口。

用法:
    from services.logger import log
    log.info("开始评估")
    log.error("API 调用失败", exc_info=True)
"""

import logging
import sys

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger("soft_ip")
        _logger.setLevel(logging.INFO)
        if not _logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            ))
            _logger.addHandler(handler)
    return _logger


def info(msg: str, *args, **kwargs):
    _get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    _get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    _get_logger().error(msg, *args, **kwargs)


def debug(msg: str, *args, **kwargs):
    _get_logger().debug(msg, *args, **kwargs)
