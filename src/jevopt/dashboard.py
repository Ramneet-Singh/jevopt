from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence


JEV_INPUT_USD_PER_BILLION = 42


def summarize_run(name: str, run_dir: Path) -> dict[str, object]:
    programs = []
    for result_path in sorted(run_dir.glob("*/result.json")):
        result = json.loads(result_path.read_text())
        decisions = result["decisions"]
        jevopt_binary = (
            result["jevopt_binary"]
            if "jevopt_binary" in result
            else result["jev_binary"]
        )
        clang_inline = sum(
            bool(item["llvm_observation"]["default"]) for item in decisions
        )
        jevopt_inline = sum(bool(item["sent_to_llvm"]) for item in decisions)
        clang_bytes = result["stock_binary"]["text_bytes"]
        jevopt_bytes = jevopt_binary["text_bytes"]
        jev_input_tokens = sum(
            int(item.get("usage", {}).get("input_tokens", 0)) for item in decisions
        )
        programs.append(
            {
                "id": result_path.parent.name,
                "translation_units": len(result["compile_commands"]),
                "decisions": len(decisions),
                "correct": result["program"].get("correct", False),
                "clang": {
                    "inline": clang_inline,
                    "do_not_inline": len(decisions) - clang_inline,
                    "text_bytes": clang_bytes,
                },
                "jevopt": {
                    "inline": jevopt_inline,
                    "do_not_inline": len(decisions) - jevopt_inline,
                    "text_bytes": jevopt_bytes,
                    "api_cost_usd": round(
                        jev_input_tokens * JEV_INPUT_USD_PER_BILLION / 1_000_000_000,
                        6,
                    ),
                },
                "delta_bytes": jevopt_bytes - clang_bytes,
                "delta_percent": round(100 * (jevopt_bytes / clang_bytes - 1), 4),
            }
        )

    if not programs:
        raise ValueError(f"no result.json files found below {run_dir}")

    ratios = [
        item["jevopt"]["text_bytes"] / item["clang"]["text_bytes"] for item in programs
    ]  # type: ignore[index,operator]
    return {
        "id": name,
        "label": name,
        "benchmark": "Embench 1.0",
        "featured_program": "statemate",
        "configuration": "Jev 1.13 · Clang 21 · x86-64",
        "aggregate": {
            "programs": len(programs),
            "correct": sum(bool(item["correct"]) for item in programs),
            "wins": sum(item["delta_bytes"] < 0 for item in programs),
            "ties": sum(item["delta_bytes"] == 0 for item in programs),
            "losses": sum(item["delta_bytes"] > 0 for item in programs),
            "geomean_delta_percent": round(
                100
                * (
                    math.exp(sum(math.log(ratio) for ratio in ratios) / len(ratios)) - 1
                ),
                4,
            ),
            "clang_text_bytes": sum(item["clang"]["text_bytes"] for item in programs),  # type: ignore[index]
            "jevopt_text_bytes": sum(item["jevopt"]["text_bytes"] for item in programs),  # type: ignore[index]
        },
        "programs": programs,
    }


def export_dashboard(runs: Sequence[tuple[str, Path]], output: Path) -> None:
    data = {"runs": [summarize_run(name, path) for name, path in runs]}
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, indent=2, sort_keys=True)
    output.write_text(serialized + "\n")
    output.with_suffix(".js").write_text(
        f"window.JEVOPT_DASHBOARD = {serialized};\n"
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Export jevopt run data for the dashboard"
    )
    parser.add_argument(
        "--run",
        action="append",
        metavar="NAME=PATH",
        required=True,
        help="Run name and directory containing PROGRAM/result.json files",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    runs = []
    for value in args.run:
        name, separator, path = value.partition("=")
        if not separator or not name or not path:
            parser.error("--run must have the form NAME=PATH")
        runs.append((name, Path(path)))
    export_dashboard(runs, args.output)


if __name__ == "__main__":
    main()
