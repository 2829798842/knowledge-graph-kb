"""包名称：kb_graph.config

功能说明：提供应用配置读取、路径解析与运行时目录初始化能力。
"""

from kb_graph.config.settings import Settings, ensure_app_dirs, get_settings

__all__ = ["Settings", "ensure_app_dirs", "get_settings"]
