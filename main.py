import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent
SRC_DIR: Path = PROJECT_ROOT / "src"


def bootstrap_src_path() -> None:
    """将 `src` 目录加入模块搜索路径。

    Returns:
        None
    """

    src_path: str = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


bootstrap_src_path()

from kb_graph.main import cli  # noqa: E402


def main() -> None:
    """启动知识库一体化服务。

    Returns:
        None
    """

    cli()


if __name__ == "__main__":
    main()
