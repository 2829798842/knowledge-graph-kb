"""CLI entrypoint for the local-first knowledge-graph knowledge base."""
import argparse
import json
from pathlib import Path
from typing import Any

import uvicorn

from src import create_app
from src.config import Settings, get_settings
from src.kb import build_knowledge_base_container
from src.kb.application.services import restore_backup
from src.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


def cli() -> None:
    """Run the command-line interface."""

    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    args = _build_parser().parse_args()

    if args.command in {None, "serve"}:
        _serve(settings)
        return

    if args.command == "restore":
        result = restore_backup(
            settings=settings,
            backup_dir=Path(args.backup_dir),
            force=bool(args.force),
        )
        _print_json(result)
        return

    container = build_knowledge_base_container(settings)
    maintenance = container.maintenance_service

    if args.command == "doctor":
        _print_json(maintenance.doctor())
        return
    if args.command == "backup":
        output_dir = Path(args.output_dir).resolve() if args.output_dir else None
        _print_json(maintenance.backup(output_dir=output_dir))
        return
    if args.command == "rebuild-vectors":
        _print_json(maintenance.rebuild_vectors())
        return
    if args.command == "rebuild-graph":
        _print_json(maintenance.rebuild_graph())
        return

    raise SystemExit(f"Unsupported command: {args.command}")


def main() -> None:
    cli()


def _serve(settings: Settings) -> None:
    logger.info(
        "Starting server. host=%s port=%s log_level=%s",
        settings.server_host,
        settings.server_port,
        settings.log_level,
    )
    uvicorn.run(
        "main:create_app",
        factory=True,
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_config=None,
        access_log=False,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Knowledge Graph KB CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Start the FastAPI server.")
    subparsers.add_parser("doctor", help="Run local readiness and integrity checks.")

    backup_parser = subparsers.add_parser("backup", help="Create a local backup.")
    backup_parser.add_argument("--output-dir", help="Optional output directory for the backup.")

    restore_parser = subparsers.add_parser("restore", help="Restore a backup into the local data directory.")
    restore_parser.add_argument("backup_dir", help="Backup directory to restore from.")
    restore_parser.add_argument("--force", action="store_true", help="Overwrite a non-empty target data directory.")

    subparsers.add_parser("rebuild-vectors", help="Rebuild the FAISS vector index from stored paragraphs.")
    subparsers.add_parser("rebuild-graph", help="Repair graph integrity and clean orphan graph records.")
    return parser


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
