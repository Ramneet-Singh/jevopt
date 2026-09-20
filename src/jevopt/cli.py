from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Sequence

from jevopt.interactive import run_json_interactive

CLANG = "/usr/bin/clang-21"
CLANGXX = "/usr/bin/clang++-21"
LLVM_SIZE = "/usr/bin/llvm-size-21"
COMPILE_FLAGS = ("-Oz", "-march=x86-64")
LINK_FLAGS = ("-fuse-ld=lld", "-march=x86-64", "-Wl,--build-id=none")
SOURCE_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx"})
CXX_SUFFIXES = frozenset({".cc", ".cpp", ".cxx"})
JEV_MODEL = "jev-1.13.0"
PROMPT_VERSION = "inline-size-v3-minimal-ir-full-budget-structure-features-source-blind"
MAX_IR_CHARS = 48_000
MAX_SOURCE_CHARS = 16_000
DIRECT_FEATURES = frozenset(
    {
        "caller_basic_block_count",
        "caller_instruction_count",
        "caller_users",
        "callee_basic_block_count",
        "callee_instruction_count",
        "callee_users",
        "constant_args",
    }
)
ROOT = Path(__file__).parents[2]
PLUGIN_SOURCE_DIR = ROOT / "llvm_plugin"
PLUGIN_BUILD_DIR = ROOT / "build" / "llvm_plugin"


@dataclass(frozen=True)
class BuildOptions:
    source_dir: Path
    output_dir: Path
    run_args: tuple[str, ...] = ()
    link_args: tuple[str, ...] = ()
    extra_sources: tuple[Path, ...] = ()
    compile_args: tuple[str, ...] = ()
    verify: bool = False

    @property
    def sources(self) -> list[Path]:
        sources = [
            path
            for path in sorted(self.source_dir.iterdir())
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        ]
        sources.extend(self.extra_sources)
        if not sources:
            raise ValueError(f"no C or C++ sources found in {self.source_dir}")
        return sources

    def validate(self) -> None:
        flags = (*self.compile_args, *self.link_args)
        if any(flag == "-flto" or flag.startswith("-flto=") for flag in flags):
            raise ValueError("jevopt does not support LTO")


def _compiler_for(source: Path) -> str:
    return CLANGXX if source.suffix.lower() in CXX_SUFFIXES else CLANG


def _linker_for(sources: Sequence[Path]) -> str:
    if any(source.suffix.lower() in CXX_SUFFIXES for source in sources):
        return CLANGXX
    return CLANG


def _text_size(binary: Path) -> int:
    output = subprocess.run(
        [LLVM_SIZE, "--format=sysv", str(binary)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for line in output.splitlines():
        columns = line.split()
        if columns and columns[0] == ".text":
            return int(columns[1])
    raise RuntimeError(f"llvm-size did not report .text for {binary}")


def _binary_info(binary: Path) -> dict[str, object]:
    return {
        "path": str(binary),
        "text_bytes": _text_size(binary),
        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }


def _build_plugin() -> Path:
    subprocess.run(
        [
            "/usr/bin/cmake",
            "-S",
            str(PLUGIN_SOURCE_DIR),
            "-B",
            str(PLUGIN_BUILD_DIR),
            "-G",
            "Ninja",
            f"-DCMAKE_CXX_COMPILER={CLANGXX}",
            "-DLLVM_DIR=/usr/lib/llvm-21/lib/cmake/llvm",
        ],
        check=True,
    )
    subprocess.run(["/usr/bin/cmake", "--build", str(PLUGIN_BUILD_DIR)], check=True)
    return PLUGIN_BUILD_DIR / "JevInlineAdvisor.so"


def _link(
    sources: Sequence[Path],
    objects: Sequence[Path],
    binary: Path,
    link_args: Sequence[str],
) -> list[str]:
    command = [
        _linker_for(sources),
        *LINK_FLAGS,
        *(str(path) for path in objects),
        *link_args,
        "-o",
        str(binary),
    ]
    subprocess.run(command, check=True)
    return command


def _compile_stock(options: BuildOptions) -> dict[str, object]:
    sources = options.sources
    objects_dir = options.output_dir / "stock-objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    objects = []
    commands = []
    for index, source in enumerate(sources):
        object_path = objects_dir / f"{index}-{source.stem}.o"
        command = [
            _compiler_for(source),
            *COMPILE_FLAGS,
            *options.compile_args,
            "-c",
            str(source),
            "-o",
            str(object_path),
        ]
        subprocess.run(command, check=True)
        objects.append(object_path)
        commands.append(command)
    binary = options.output_dir / "clang-oz"
    link_command = _link(sources, objects, binary, options.link_args)
    return {
        "binary": _binary_info(binary),
        "compile_commands": commands,
        "link_command": link_command,
    }


def _compile_with_advisor(
    options: BuildOptions,
    binary_name: str,
    should_inline: Callable[[dict[str, Any]], bool],
) -> dict[str, object]:
    sources = options.sources
    objects_dir = options.output_dir / f"{binary_name}-objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    plugin = _build_plugin()
    objects = []
    commands = []
    observations: list[dict[str, Any]] = []

    for index, source in enumerate(sources):
        object_path = objects_dir / f"{index}-{source.stem}.o"
        channel_base = options.output_dir / f"inliner-channel-{index}"
        command = [
            _compiler_for(source),
            *COMPILE_FLAGS,
            *options.compile_args,
            f"-fpass-plugin={plugin}",
            "-c",
            str(source),
            "-o",
            str(object_path),
        ]

        def decide(observation: dict[str, Any]) -> bool:
            observation["source"] = str(source)
            observation["build_context"] = {
                "optimization": "-Oz",
                "separate_translation_units": True,
                "preprocessor_definitions": [
                    flag[2:] for flag in options.compile_args if flag.startswith("-D")
                ],
                "lto": False,
                "function_sections": "-ffunction-sections" in options.compile_args,
                "data_sections": "-fdata-sections" in options.compile_args,
                "linker_gc_sections": "-Wl,--gc-sections" in options.link_args,
            }
            return should_inline(observation)

        observations.extend(run_json_interactive(channel_base, command, decide))
        objects.append(object_path)
        commands.append(command)

    binary = options.output_dir / binary_name
    link_command = _link(sources, objects, binary, options.link_args)
    return {
        "binary": _binary_info(binary),
        "observations": observations,
        "compile_commands": commands,
        "link_command": link_command,
    }


def _verify_binaries(
    options: BuildOptions, stock_binary: Path, candidate_binary: Path
) -> dict[str, object]:
    if not options.verify:
        return {"verified": False}
    stock = subprocess.run(
        [str(stock_binary), *options.run_args],
        check=False,
        capture_output=True,
        text=True,
    )
    candidate = subprocess.run(
        [str(candidate_binary), *options.run_args],
        check=False,
        capture_output=True,
        text=True,
    )
    expected_path = options.source_dir / "expected.stdout"
    expected = expected_path.read_text() if expected_path.exists() else stock.stdout
    correct = (
        stock.returncode == 0
        and candidate.returncode == 0
        and stock.stdout == expected
        and candidate.stdout == expected
    )
    return {
        "verified": True,
        "correct": correct,
        "stock_returncode": stock.returncode,
        "candidate_returncode": candidate.returncode,
        "stock_stdout": stock.stdout,
        "candidate_stdout": candidate.stdout,
        "stock_stderr": stock.stderr,
        "candidate_stderr": candidate.stderr,
    }


def _clip_code(text: str, budget: int, kind: str, focus: str = "") -> str:
    if len(text) <= budget:
        return text
    marker = f"\n/* ... {kind} clipped to fit Jev's context window ... */\n"
    available = budget - len(marker)
    if focus and (position := text.find(focus)) >= 0:
        head = min(2_000, available // 4)
        nearby = available - head
        start = max(head, min(position - nearby // 2, len(text) - nearby))
        return text[:head] + marker + text[start : start + nearby]
    head = available * 2 // 3
    return text[:head] + marker + text[-(available - head) :]


def _clip_source(text: str, focuses: Sequence[str]) -> str:
    if len(text) <= MAX_SOURCE_CHARS:
        return text
    marker = "\n/* ... source clipped to fit Jev's context window ... */\n"
    head = 2_000
    segment = (MAX_SOURCE_CHARS - head - 2 * len(marker)) // 2
    ranges = [(0, head)]
    for focus in focuses:
        position = text.find(focus)
        if position >= 0:
            start = max(head, min(position - segment // 3, len(text) - segment))
            ranges.append((start, start + segment))
    ranges.sort()
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return marker.join(text[start:end] for start, end in merged)[:MAX_SOURCE_CHARS]


def _new_jev_client():
    os.environ.setdefault("TYPESAFE_LOG_LEVEL", "warning")
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from typesafe_sdk import TypeSafeClient

    return TypeSafeClient(api_key=os.environ.get("TYPESAFE_API_KEY"), model=JEV_MODEL)


def _ask_jev(observation: dict[str, Any], client: Any) -> dict[str, object]:
    features = {
        name: value
        for name, value in observation["numeric_features"].items()
        if name in DIRECT_FEATURES
    }
    ir = observation["ir"]
    caller_ir = str(ir["caller"])
    callee_ir = str(ir["callee"])
    callsite_ir = str(ir["callsite"])
    ir_limit = MAX_IR_CHARS - MAX_SOURCE_CHARS
    caller_budget = min(len(caller_ir), ir_limit // 2)
    callee_budget = min(len(callee_ir), ir_limit - caller_budget)
    caller_budget = min(len(caller_ir), ir_limit - callee_budget)
    clipped_caller = _clip_code(caller_ir, caller_budget, "LLVM IR", callsite_ir)
    clipped_callee = _clip_code(callee_ir, callee_budget, "LLVM IR")
    source_text = Path(observation["source"]).read_text()
    clipped_source = _clip_source(
        source_text,
        (str(observation["caller"]), str(observation["callee"])),
    )
    state: dict[str, object] = {
        "objective": "Minimize final native executable .text size after all LLVM optimizations.",
        "target": "x86-64, Clang 21.1.8",
        "build_context": observation["build_context"],
        "callsite": {
            "source": observation["source"],
            "module": observation["module"],
            "caller": observation["caller"],
            "callee": observation["callee"],
            "instruction": callsite_ir,
        },
        "caller_ir": clipped_caller,
        "callee_ir": clipped_callee,
        "numeric_facts": features,
        "c_translation_unit": clipped_source,
    }
    if len(clipped_source) < len(source_text):
        state["source_clipping"] = {
            "limit_chars": MAX_SOURCE_CHARS,
            "original_chars": len(source_text),
            "included_chars": len(clipped_source),
        }
    if len(clipped_caller) < len(caller_ir) or len(clipped_callee) < len(callee_ir):
        state["ir_clipping"] = {
            "limit_chars": ir_limit,
            "caller_original_chars": len(caller_ir),
            "caller_included_chars": len(clipped_caller),
            "callee_original_chars": len(callee_ir),
            "callee_included_chars": len(clipped_callee),
        }
    question = {
        "instructions": {
            "decision": "Both actions are legal. Choose the action expected to produce the smaller final native executable .text section after optimization and linking."
        },
        "criteria": {
            "inline": {"meaning": "Inline this call site."},
            "do_not_inline": {"meaning": "Keep this call out of line."},
        },
    }

    from typesafe_sdk import Choice

    started = time.monotonic()
    response = client.system_one(
        state=state,
        questions={"inline_decision": Choice(**question)},
    )
    latency_ms = round((time.monotonic() - started) * 1000, 3)
    answer = response.choices["inline_decision"]
    return {
        "model": response.model,
        "prompt_version": PROMPT_VERSION,
        "state": state,
        "question": question,
        "llvm_observation": observation,
        "answer": {
            "choice": answer.choice,
            "probabilities": answer.probabilities,
            "confidence": answer.confidence,
        },
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "latency_ms": latency_ms,
    }


def passthrough(options: BuildOptions) -> dict[str, object]:
    options.validate()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    stock = _compile_stock(options)
    interactive = _compile_with_advisor(
        options,
        "passthrough",
        lambda observation: bool(observation["default"]),
    )
    stock_binary = stock["binary"]
    candidate_binary = interactive["binary"]
    program = _verify_binaries(
        options,
        Path(stock_binary["path"]),  # type: ignore[arg-type,index]
        Path(candidate_binary["path"]),  # type: ignore[arg-type,index]
    )
    identical = stock_binary["sha256"] == candidate_binary["sha256"]  # type: ignore[index]
    result = {
        "mode": "passthrough",
        "program": program,
        "source_count": len(options.sources),
        "identical_to_clang": identical,
        "stock_binary": stock_binary,
        "passthrough_binary": candidate_binary,
        "observations": interactive["observations"],
        "stock_compile_commands": stock["compile_commands"],
        "stock_link_command": stock["link_command"],
        "compile_commands": interactive["compile_commands"],
        "link_command": interactive["link_command"],
    }
    (options.output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def compile_with_jev(options: BuildOptions) -> dict[str, object]:
    options.validate()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    stock = _compile_stock(options)
    decisions: list[dict[str, Any]] = []

    with _new_jev_client() as client:

        def should_inline(observation: dict[str, Any]) -> bool:
            decision = _ask_jev(observation, client)
            inline = decision["answer"]["choice"] == "inline"
            decision["sent_to_llvm"] = int(inline)
            decisions.append(decision)
            if len(decisions) % 25 == 0:
                print(f"Jev decisions: {len(decisions)}", file=sys.stderr, flush=True)
            return inline

        jevopt = _compile_with_advisor(options, "jevopt", should_inline)

    stock_binary = stock["binary"]
    jevopt_binary = jevopt["binary"]
    program = _verify_binaries(
        options,
        Path(stock_binary["path"]),  # type: ignore[arg-type,index]
        Path(jevopt_binary["path"]),  # type: ignore[arg-type,index]
    )
    text_delta = jevopt_binary["text_bytes"] - stock_binary["text_bytes"]  # type: ignore[index,operator]
    inline_count = sum(item["sent_to_llvm"] for item in decisions)
    llvm_inline = sum(bool(item["llvm_observation"]["default"]) for item in decisions)
    result = {
        "mode": "jevopt",
        "model": JEV_MODEL,
        "prompt_version": PROMPT_VERSION,
        "program": program,
        "source_count": len(options.sources),
        "stock_binary": stock_binary,
        "jevopt_binary": jevopt_binary,
        "summary": {
            "decisions": len(decisions),
            "clang_inline": llvm_inline,
            "clang_do_not_inline": len(decisions) - llvm_inline,
            "jevopt_inline": inline_count,
            "jevopt_do_not_inline": len(decisions) - inline_count,
            "text_delta_bytes": text_delta,
            "text_delta_percent": round(
                100 * text_delta / stock_binary["text_bytes"],  # type: ignore[operator]
                4,
            ),
            "input_tokens": sum(item["usage"]["input_tokens"] for item in decisions),
            "output_tokens": sum(item["usage"]["output_tokens"] for item in decisions),
            "jev_latency_ms": round(sum(item["latency_ms"] for item in decisions), 3),
        },
        "decisions": decisions,
        "stock_compile_commands": stock["compile_commands"],
        "stock_link_command": stock["link_command"],
        "compile_commands": jevopt["compile_commands"],
        "link_command": jevopt["link_command"],
    }
    (options.output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def _add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--extra-source", type=Path, action="append", default=[])
    parser.add_argument("--compile-arg", action="append", default=[])
    parser.add_argument("--link-arg", action="append", default=[])
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--run-arg", action="append", default=[])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jevopt",
        description="Compile C and C++ for size with Clang and Jev-guided inlining.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    _add_build_arguments(commands.add_parser("compile", help="compile with Jevopt"))
    _add_build_arguments(
        commands.add_parser(
            "passthrough",
            help="replay LLVM's own decisions through the Jevopt advisor",
        )
    )
    return parser


def _options(args: argparse.Namespace) -> BuildOptions:
    return BuildOptions(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        run_args=tuple(args.run_arg),
        link_args=tuple(args.link_arg),
        extra_sources=tuple(args.extra_source),
        compile_args=tuple(args.compile_arg),
        verify=args.verify,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    options = _options(args)
    result = (
        compile_with_jev(options) if args.command == "compile" else passthrough(options)
    )
    summary = (
        result["summary"]
        if "summary" in result
        else {"identical_to_clang": result["identical_to_clang"]}
    )
    print(json.dumps(summary, sort_keys=True))
    program = result["program"]
    correct = not program["verified"] or program["correct"]  # type: ignore[index]
    if args.command == "passthrough":
        correct = correct and result["identical_to_clang"]
    return 0 if correct else 1
