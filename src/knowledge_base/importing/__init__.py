"""Legacy compatibility exports for importing modules."""

from src.kb.importing.parser import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_EXTENSION_DISPLAY,
    SUPPORTED_EXTENSION_SET,
    UnsupportedFileTypeError,
    detect_file_type,
    extract_text,
)

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_EXTENSION_DISPLAY",
    "SUPPORTED_EXTENSION_SET",
    "UnsupportedFileTypeError",
    "detect_file_type",
    "extract_text",
]
