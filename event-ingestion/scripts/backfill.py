"""Re-parse every stored RAW_EVENTS payload with the current parsers (no scraping), then rebuild and export.

Use after fixing a parser or adding a field: `python scripts/backfill.py`.
"""

import sys

from umd_events.cli import main

if __name__ == "__main__":
    sys.exit(main(["ingest", "--reprocess", *sys.argv[1:]]))
