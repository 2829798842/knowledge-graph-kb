"""统一配置项目日志格式并提供通用 logger 获取入口。"""

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
    """把文本日志级别解析成 `logging` 常量。"""

    normalized_level: str = str(log_level or "INFO").strip().upper()
    return getattr(logging, normalized_level, logging.INFO)


def configure_logging(log_level: str = "INFO") -> None:
    """按项目约定初始化根日志并压低三方库噪音。"""

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
    """返回纳入项目统一配置体系的模块 logger。"""

    return logging.getLogger(name)
