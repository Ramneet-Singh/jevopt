from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from jevopt.dashboard import export_dashboard


ROOT = Path(__file__).parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jevopt on all Embench programs")
    parser.add_argument(
        "--embench-dir",
        type=Path,
        default=ROOT / "third_party" / "embench-iot",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "runs" / "jevopt-embench",
    )
    parser.add_argument(
        "--dashboard-data",
        type=Path,
        default=ROOT / "dashboard" / "data" / "runs.json",
    )
    args = parser.parse_args()

    support = args.embench_dir / "support"
    chip = args.embench_dir / "config" / "native" / "chips" / "speed-test-gcc"
    board = args.embench_dir / "config" / "native" / "boards" / "default"
    arch = args.embench_dir / "config" / "native"
    programs = sorted(
        path for path in (args.embench_dir / "src").iterdir() if path.is_dir()
    )

    for source_dir in programs:
        output_dir = args.output_dir / source_dir.name
        if output_dir.exists():
            raise SystemExit(f"refusing to overwrite existing run: {output_dir}")
        command = [
            sys.executable,
            "-m",
            "jevopt",
            "compile",
            "--source-dir",
            str(source_dir),
            "--output-dir",
            str(output_dir),
            "--verify",
            f"--extra-source={support / 'main.c'}",
            f"--extra-source={support / 'beebsc.c'}",
            f"--extra-source={chip / 'chipsupport.c'}",
            f"--extra-source={board / 'boardsupport.c'}",
            f"--compile-arg=-I{support}",
            f"--compile-arg=-I{chip}",
            f"--compile-arg=-I{board}",
            f"--compile-arg=-I{arch}",
            "--compile-arg=-DCPU_MHZ=1",
            "--compile-arg=-DWARMUP_HEAT=1",
            "--compile-arg=-fdata-sections",
            "--compile-arg=-ffunction-sections",
            "--link-arg=-Wl,--gc-sections",
            "--link-arg=-lm",
        ]
        print(f"[{source_dir.name}] compiling", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
        result = json.loads((output_dir / "result.json").read_text())
        delta = result["summary"]["text_delta_percent"]
        print(f"[{source_dir.name}] {delta:+.2f}%", flush=True)

    export_dashboard([("jevopt-embench", args.output_dir)], args.dashboard_data)


if __name__ == "__main__":
    main()
