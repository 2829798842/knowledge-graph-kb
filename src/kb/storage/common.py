"""SQLite 仓储共享辅助函数。"""

from src.kb.common import utc_now_iso

DEFAULT_MODEL_CONFIG_ID = "default"


def normalize_entity_name(value: str) -> str:
    return " ".join(str(value).split()).strip().lower()


def placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def resolve_progress(completed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(completed / total, 1.0)) * 100.0, 2)


__all__ = [
    "DEFAULT_MODEL_CONFIG_ID",
    "normalize_entity_name",
    "placeholders",
    "resolve_progress",
    "utc_now_iso",
]
