"""Command line entry point: `umd-events <command>`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import PROJECT_ROOT, get_settings


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("urllib3", "requests_cache", "snowflake.connector"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def cmd_ingest(args) -> int:
    from .pipeline import run_pipeline

    report = run_pipeline(get_settings(), sources=args.source or None, export=not args.no_export,
                          llm=True if args.llm_tags else None, reprocess=args.reprocess)
    print()
    print(f"{'source':<18}{'status':<9}{'fetched':>8}{'parsed':>8}{'rejected':>9}{'new':>6}{'changed':>8}{'secs':>7}")
    for s in report.sources:
        print(f"{s.source:<18}{s.status:<9}{s.fetched:>8}{s.parsed:>8}{s.rejected:>9}{s.inserted:>6}{s.updated:>8}"
              f"{s.duration_s:>7}" + (f"  {s.message}" if s.message else ""))
    print(f"\n{report.source_records} source records -> {report.events} events ({report.merges} merges)")
    if report.exports:
        print(f"exported to {get_settings().export_dir}")
    return 1 if all(s.status == "failed" for s in report.sources) else 0


def cmd_export(args) -> int:
    from .storage.export import export_all
    from .storage.local import LocalStore

    settings = get_settings()
    with LocalStore(settings.db_path) as store:
        export_all(store, Path(args.out) if args.out else settings.export_dir)
    return 0


def cmd_sources(args) -> int:
    from .collectors import REGISTRY

    for name, cls in REGISTRY.items():
        print(f"{name:<18} tier {cls.tier}  {cls.display_name}")
    return 0


def cmd_stats(args) -> int:
    from .storage.local import LocalStore

    with LocalStore(get_settings().db_path, read_only=True) as store:
        total = store.query("SELECT count(*) n, count(*) FILTER (WHERE len(sources) > 1) merged FROM EVENTS")[0]
        print(f"events: {total['n']} ({total['merged']} found on more than one source)")
        for r in store.query("SELECT s, count(*) n FROM (SELECT unnest(sources) s FROM EVENTS) GROUP BY s ORDER BY n DESC"):
            print(f"  {r['s']:<18}{r['n']:>6}")
        print("completeness:")
        for r in store.query("""SELECT round(100*avg((description IS NOT NULL)::INT)) description,
                                       round(100*avg((venue_name IS NOT NULL)::INT)) venue,
                                       round(100*avg((len(tags) > 0 AND tags <> ['other'])::INT)) tags,
                                       round(100*avg((latitude IS NOT NULL)::INT)) coordinates,
                                       round(100*avg((image_url IS NOT NULL)::INT)) image FROM EVENTS"""):
            print("  " + "  ".join(f"{k}={v:.0f}%" for k, v in r.items()))
        print("top tags:")
        for r in store.query("SELECT t, count(*) n FROM (SELECT unnest(tags) t FROM EVENTS) GROUP BY t ORDER BY n DESC LIMIT 15"):
            print(f"  {r['t']:<22}{r['n']:>6}")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("umd_events.api:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_embed(args) -> int:
    from .enrich.embeddings import MODEL_NAME, embed_events
    from .models import Event
    from .storage.local import LocalStore

    with LocalStore(get_settings().db_path) as store:
        done = store.embedded_hashes()
        rows = store.query("SELECT event_id, title, short_description AS summary, tags, venue_name, organizer_name, "
                           "content_hash, start_time, source, source_url FROM EVENTS")
        todo = [Event(**r) for r in rows if done.get(r["event_id"]) != r["content_hash"]]
        if not todo:
            print("all events already embedded")
            return 0
        vectors = embed_events(todo)
        store.write_embeddings(vectors, MODEL_NAME, {e.event_id: e.content_hash for e in todo})
        print(f"embedded {len(vectors)} events with {MODEL_NAME}")
    return 0


def cmd_snowflake_sql(args) -> int:
    from .storage.snowflake import write_sql_files

    out = Path(args.out) if args.out else PROJECT_ROOT / "sql"
    write_sql_files(out)
    print(f"wrote {out / 'snowflake_schema.sql'} and {out / 'snowflake_load.sql'}")
    return 0


def cmd_load_snowflake(args) -> int:
    from .storage import snowflake

    settings = get_settings()
    loaded = snowflake.load(Path(args.dir) if args.dir else settings.export_dir)
    for table, n in loaded.items():
        print(f"{table:<18}{n:>7} rows merged")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="umd-events", description="UMD event ingestion pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="collect, normalize, dedupe, store and export")
    p.add_argument("--source", action="append", help="only this source (repeatable); see `sources`")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--llm-tags", action="store_true", help="also tag with a local Ollama model")
    p.add_argument("--reprocess", action="store_true", help="re-parse stored RAW_EVENTS instead of scraping")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("export", help="rewrite export files from the local store")
    p.add_argument("--out")
    p.set_defaults(func=cmd_export)

    sub.add_parser("sources", help="list registered sources").set_defaults(func=cmd_sources)
    sub.add_parser("stats", help="summarize the local store").set_defaults(func=cmd_stats)
    sub.add_parser("embed", help="compute embeddings (needs the embeddings extra)").set_defaults(func=cmd_embed)

    p = sub.add_parser("serve", help="run the HTTP API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("snowflake-sql", help="write Snowflake DDL and load SQL to sql/")
    p.add_argument("--out")
    p.set_defaults(func=cmd_snowflake_sql)

    p = sub.add_parser("load-snowflake", help="merge exported files into Snowflake (needs credentials)")
    p.add_argument("--dir", help="export directory (default data/exports)")
    p.set_defaults(func=cmd_load_snowflake)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
