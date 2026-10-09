from __future__ import annotations

import argparse
from pathlib import Path

from .engine import run_scenario
from .capture.importer import import_jsonl
from .adapters import export_schematic_2d


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m operations")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="run a synthetic dispatch scenario")
    demo.add_argument("--scenario", type=Path, required=True)
    demo.add_argument("--db", type=Path, required=True)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--run-id")
    importer = commands.add_parser(
        "import-observations", help="import local observation JSONL"
    )
    importer.add_argument("--input", type=Path, required=True)
    importer.add_argument("--db", type=Path, required=True)
    importer.add_argument("--seal", action="store_true")
    visual = commands.add_parser(
        "visualize-2d", help="export a saved simulation as a 2D HTML playback"
    )
    visual.add_argument("--db", type=Path, required=True)
    visual.add_argument("--run-id", required=True)
    visual.add_argument("--layout", type=Path, required=True)
    visual.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        result = run_scenario(args.scenario, args.db, seed=args.seed, run_id=args.run_id)
        print(f"run_id={result.run_id}")
        print(f"database={result.database}")
        print(f"events={result.event_count}")
        print(f"status={result.status.value}")
        print(f"incomplete_activities={result.incomplete_activity_count}")
        return 0
    if args.command == "import-observations":
        result = import_jsonl(args.input, args.db, seal=args.seal)
        print(f"accepted_lines={result.accepted_lines}")
        print(f"event_lines={result.event_lines}")
        print(f"errors={len(result.errors)}")
        for error in result.errors:
            print(f"line {error.line_number}: {error.message}")
        return 1 if result.errors else 0
    if args.command == "visualize-2d":
        result = export_schematic_2d(args.db, args.run_id, args.layout, args.out)
        print(f"run_id={result.run_id}")
        print(f"events={result.event_count}")
        print(f"stop_time_s={result.stop_time_s:g}")
        print(f"output={result.output}")
        return 0
    return 2
