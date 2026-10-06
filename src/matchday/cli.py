"""Command line entry point: `matchday sync` is what the Kubernetes CronJob runs."""

import argparse
import json
import logging

from sqlalchemy.orm import sessionmaker

from matchday.config import get_settings
from matchday.db import get_engine
from matchday.sync import provider_from_settings, sync_matches


def main() -> None:
    parser = argparse.ArgumentParser(prog="matchday")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync", help="fetch fixtures and results from the configured provider")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "sync":
        settings = get_settings()
        with sessionmaker(get_engine())() as session:
            result = sync_matches(session, provider_from_settings(settings))
        logging.info("sync finished %s", json.dumps(result))
