"""Run every source, then export. Same as `umd-events ingest`; handy for cron / Task Scheduler."""

import sys

from umd_events.cli import main

if __name__ == "__main__":
    sys.exit(main(["ingest", *sys.argv[1:]]))
