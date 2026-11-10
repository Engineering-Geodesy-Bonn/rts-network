"""Command line: `rtsapi serve` (default) and `rtsapi import-legacy <v1 database>`."""

import argparse
import json
import logging
import sys

from rtsapi.config import settings


def setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")


def serve(args: argparse.Namespace) -> None:
    import uvicorn

    from rtsapi.app import create_app

    if args.db:
        settings.db_path = args.db
    uvicorn.run(
        create_app(settings),
        host=args.host,
        port=args.port,
        access_log=args.access_log,
        log_level=settings.log_level.lower(),
        ws_ping_interval=10,
        ws_ping_timeout=20,
        root_path=args.root_path,  # the dashboard proxies /api to this server
    )


def import_legacy(args: argparse.Namespace) -> None:
    from rtsapi import repo
    from rtsapi.db import Database
    from rtsapi.legacy import import_legacy as run_import

    db = Database(args.db or settings.db_path)
    try:
        report = run_import(args.source, db)
        repo.set_meta(db, "legacy_import", json.dumps(report))
    finally:
        db.close()
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rtsapi", description="RTS Network API")
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="Run the API server (default)")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--db", help=f"Database file (default {settings.db_path})")
    p_serve.add_argument("--root-path", default="/api", help="Path prefix of the reverse proxy")
    p_serve.add_argument("--access-log", action="store_true", help="Log every request")
    p_serve.set_defaults(func=serve)

    p_import = sub.add_parser("import-legacy", help="Import a v1 database (read-only, idempotent)")
    p_import.add_argument("source", help="Path of the v1 database.db")
    p_import.add_argument("--db", help=f"Target database (default {settings.db_path})")
    p_import.set_defaults(func=import_legacy)

    args = parser.parse_args(argv)
    setup_logging(settings.log_level)
    if args.command is None:
        args = parser.parse_args(["serve", *(argv or sys.argv[1:])])
    args.func(args)


if __name__ == "__main__":
    main()
