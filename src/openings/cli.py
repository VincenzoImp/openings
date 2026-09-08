"""The ``openings`` command."""

from __future__ import annotations

import argparse
import sys

from openings.project_meta import get_project_version


def _cmd_run() -> int:
    from openings.pipeline import prepare_runtime, run_collection
    from openings.scheduler import create_scheduler

    config, _db = prepare_runtime(scheduled=False)
    scheduler = create_scheduler(config, run_collection)
    return 0 if scheduler.run_once() else 1


def _cmd_scheduler() -> int:
    from openings.logger import get_logger
    from openings.pipeline import make_vector_maintenance, prepare_runtime, run_collection
    from openings.scheduler import create_scheduler

    logger = get_logger("main")
    config, db = prepare_runtime(scheduled=True)
    scheduler = create_scheduler(
        config,
        run_collection,
        vector_sync_function=make_vector_maintenance(config, db),
        vector_sync_interval_minutes=config.vector_search.sync_interval_minutes,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Interrupted")
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Fatal error: %s", exc)
        return 1
    return 0


def _cmd_web() -> int:
    from openings.web.app import main as web_main

    web_main()
    return 0


def _cmd_healthcheck() -> int:
    from openings.healthcheck import main as healthcheck_main

    return healthcheck_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openings",
        description="Openings: a configurable job crawler, archive and application tracker.",
    )
    parser.add_argument("--version", action="version", version=f"openings {get_project_version()}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("run", help="Collect once and exit.")
    subcommands.add_parser("scheduler", help="Collect on the configured interval (default).")
    subcommands.add_parser("web", help="Serve the dashboard, REST API and MCP endpoint.")
    subcommands.add_parser("healthcheck", help="Verify config, database and directories.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "scheduler"
    handlers = {
        "run": _cmd_run,
        "scheduler": _cmd_scheduler,
        "web": _cmd_web,
        "healthcheck": _cmd_healthcheck,
    }
    return handlers[command]()


if __name__ == "__main__":
    sys.exit(main())
