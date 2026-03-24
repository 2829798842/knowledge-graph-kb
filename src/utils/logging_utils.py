"""统一配置后端日志格式、收敛高噪音第三方日志，并提供项目内通用 logger 获取入口。
"""

import logging
from typing import Final

DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
NOISY_LOGGER_LEVELS: Final[dict[str, int]] = {
    "uvicorn.access": logging.WARNING,
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "openai": logging.WARNING,
    "multipart": logging.WARNING,
    "faiss.loader": logging.WARNING,
}

_LOGGING_CONFIGURED: bool = False


def _resolve_log_level(log_level: str) -> int:
    """将文本形式的日志级别解析为 logging 常量。

    Args:
        log_level: 配置或环境变量中的日志级别字符串。

    Returns:
        int: logging 可识别的日志级别值。
    """

    normalized_level: str = str(log_level or "INFO").strip().upper()
    return getattr(logging, normalized_level, logging.INFO)


def configure_logging(log_level: str = "INFO") -> None:
    """配置项目统一日志输出。

    Args:
        log_level: 根日志与业务日志默认使用的级别。
    """

    global _LOGGING_CONFIGURED

    resolved_level: int = _resolve_log_level(log_level)
    if not _LOGGING_CONFIGURED:
        logging.basicConfig(
            level=resolved_level,
            format=DEFAULT_LOG_FORMAT,
            datefmt=DEFAULT_LOG_DATE_FORMAT,
            force=True,
        )
        _LOGGING_CONFIGURED = True

    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    for handler in root_logger.handlers:
        handler.setLevel(resolved_level)

    logging.getLogger("src").setLevel(resolved_level)
    logging.getLogger("uvicorn").setLevel(resolved_level)
    logging.getLogger("uvicorn.error").setLevel(resolved_level)
    for logger_name, noisy_level in NOISY_LOGGER_LEVELS.items():
        logging.getLogger(logger_name).setLevel(noisy_level)


def get_logger(name: str) -> logging.Logger:
    """返回项目内统一配置的 logger。

    Args:
        name: 当前模块的 logger 名称，通常直接传入 `__name__`。

    Returns:
        logging.Logger: 已纳入统一日志配置体系的 logger 实例。
    """

    return logging.getLogger(name)
