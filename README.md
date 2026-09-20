# jevopt

**Making intelligent compiler optimisation decisions with Jev.** jevopt is a C/C++ compiler driver that combines Clang’s optimiser with [Jev](https://typesafe.ai/) for function-call inlining decisions. At every discretionary call site, Jev chooses whether to inline using the current LLVM IR, original source, build context, and a small set of structural facts.

![jevopt achieves 58.2% code-size reduction on Statemate from the [Embench benchmark](https://www.embench.org/)](dashboard/assets/jevopt-dashboard.png)

## Usage

jevopt currently targets Linux and a pinned LLVM 21 toolchain. You need:

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Clang, Clang++, LLVM Size, LLD, and LLVM development headers for LLVM 21
- CMake and Ninja
- A [TypeSafe](https://typesafe.ai/) API key

Install the Python environment and add your key:

```bash
uv sync
cp .env.example .env
# Add TYPESAFE_API_KEY to .env
```

Compile a directory of `.c`, `.cc`, `.cpp`, or `.cxx` files:

```bash
uv run jevopt compile \
  --source-dir <source_directory> \
  --output-dir <output_directory> \
  [--verify]
```

An example invocation is:

```bash
uv run jevopt compile \
  --source-dir examples/inline_probe \
  --output-dir build/demo \
  --verify
```

This produces:

- `build/demo/clang-oz`: the Clang `-Oz` reference binary
- `build/demo/jevopt`: the Jev-guided binary
- `build/demo/result.json`: both sizes and the complete decision trace

`--verify` is an optional argument that, when used, runs both binaries and compares their exit code and stdout. If the source directory contains `expected.stdout`, both outputs must also match it.

Forward project-specific options with repeatable flags:

```bash
uv run jevopt compile \
  --source-dir src \
  --output-dir build/jevopt \
  --compile-arg=-Iinclude \
  --compile-arg=-ffunction-sections \
  --link-arg=-Wl,--gc-sections \
  --link-arg=-lm
```

jevopt does not support LTO because LLVM's interactive ML inliner advisor support is only run while compiling one translation unit and not at link time. See the [LLVM docs on ML-Guided Optimisation](https://llvm.org/docs/MLGO.html) for more context.

### LLVM passthrough

The passthrough command exercises the same LLVM plugin and channel but returns LLVM’s own decisions. Its output must be byte-for-byte identical to regular Clang, making it a useful integration check:

```bash
uv run jevopt passthrough \
  --source-dir examples/cpp_probe \
  --output-dir build/passthrough \
  --verify
```

### Dashboard

The dashboard ships with the released `jevopt-embench` data and supports selecting a run and program. You can open `dashboard/index.html` directly, including from a downloaded copy. To serve it over local HTTP instead:

```bash
uv run python -m http.server 8000 --directory dashboard
```

Open [http://localhost:8000](http://localhost:8000). To export another compatible run:

```bash
uv run python -m jevopt.dashboard \
  --run my-run=runs/my-run \
  --output dashboard/data/runs.json
```

The exporter writes both `runs.json` and a matching `runs.js`, allowing the dashboard to work over HTTP or directly through `file://` without a CORS exception.

The included GitHub Actions workflow publishes `dashboard/` to GitHub Pages on pushes to `main`. The live dashboard is available at [ramneet-singh.github.io/jevopt](https://ramneet-singh.github.io/jevopt/).

### Rerun the Embench experiment

Clone Embench 1.0 into `third_party/embench-iot`, then run:

```bash
uv run benchmarks/run_embench.py \
  --output-dir runs/jevopt-embench-reproduction
```
> [!INFO]
> Please note that since Jev's outputs are stochastic, each run of the experiment can produce different results and may not match the results presented here. The logs from our run of the experiment are in `runs/jevopt-embench`.

The runner refuses to overwrite an existing result, verifies every output binary, and regenerates `dashboard/data/runs.json` when complete. This will make hundreds of live Jev calls using your `TYPESAFE_API_KEY`.

## Approach

```text
C / C++ source
      │
      ▼
 Clang 21 -Oz ──► JevInlineAdvisor LLVM plugin
                         │
                         ├─ current caller + callee LLVM IR
                         ├─ original translation-unit source
                         ├─ target and build context
                         └─ 7 direct structural facts
                                      │
                                      ▼
                         Jev Choice: inline / do_not_inline
                                      │
                                      ▼
                           LLVM optimisation + LLD
                                      │
                                      ▼
                              measured binary
```

In order to preserve correctness, the plugin replaces only discretionary inlining advice. LLVM takes care of legality, mandatory attributes, transformation, optimisation, object generation, and linking.

The prompt is kept deliberately small and fixed because the surrounding code context can sometimes get too large for Jev's context window. We also do not provide Jev with LLVM's suggested answer so as to not bias it. Prompt:

```text
Both actions are legal. Choose the action expected to produce the smaller final
native executable .text section after optimization and linking.
```

Each answer is a typed two-way `Choice`. Following the usual procedure (see [LLVM docs on ML-Guided Optimisation](https://llvm.org/docs/MLGO.html)), jevopt sends that choice back through a FIFO channel, and records the state, probabilities, decision, compiler commands, and binary hashes in `result.json`.

## Codebase layout

| Path | Purpose |
| --- | --- |
| `src/jevopt/cli.py` | The two-command compiler interface and fixed Jev decision path |
| `src/jevopt/interactive.py` | FIFO protocol between the Python driver and LLVM |
| `src/jevopt/dashboard.py` | Converts complete run traces into dashboard data |
| `llvm_plugin/` | LLVM pass plugin that exposes discretionary inline sites and IR |
| `dashboard/` | Dependency-free result explorer |
| `benchmarks/` | Reproducible full-suite Embench runner |
| `runs/jevopt-embench/` | Sanitized, complete decision traces from the released run |
| `examples/` | Small real C and C++ end-to-end probes |
| `tests/` | Interface-level compiler, Jev, C++, and dashboard tests |

## Embench experiment

The released `jevopt-embench` run compares the fixed Jevopt path with Clang `-Oz` on all 19 programs in [Embench 1.0](https://github.com/embench/embench-iot/tree/embench-1.0).

| Setting | Value |
| --- | --- |
| Compiler | Clang/LLVM 21.1.8 + LLD |
| Target | x86-64 |
| Optimisation | `-Oz` |
| Compilation | Separate translation units, no LTO |
| Linking | Function/data sections with linker section GC |
| Jev | `jev-1.13.0` |
| Context | Current caller/callee IR, original source, 7 direct structural facts |
| Metric | Final native executable `.text` bytes |
| Correctness | Checked by Embench: every compiled program produces correct output |

### Results

On the entire Embench benchmark suite, we see that aggregated with a geometric mean, the executable `.text` in a program compiled with jevopt is 7.87% larger than one compiled with clang `-Oz`. While this means jevopt cannot beat clang `-Oz` in aggregate, the exciting part is that intelligent model judgements can beat a mature compiler heuristic often! I will say more about why I find this exciting below. Here is a summary of the per-program comparison.

| Metric | Value |
| --- | ---: |
| Smaller than Clang `-Oz` | 7/19 |
| Equal to Clang `-Oz` | 2/19 |
| Larger than Clang `-Oz` | 10/19 |
| Geometric-mean size change | **+7.87%** |

As is evident, please note that jevopt is not meant to be production software, but rather a cool preliminary experiment to show all the exciting possibilities at the intersection of AI and compilers. Having said that, I believe a couple of things make this result more exciting than it may seem:

1. When optimising for code size in particular, it is quite reasonable to perform two compilations -- one with jevopt and one without -- and then choose whichever has the lower `.text` size. This is because, unlike when optimising for runtime, we do not need to choose workloads and carefully benchmark the runtime. So even if jevopt beats clang on *some* programs (which we have proven above), there are very real gains to be had at the cost of just 1 compilation (and a few cents in Jev API calls)!

2. As wonderfully intelligent as Jev is, I am fairly certain this is not a usecase that its author had in mind :) I believe that finetuning a Jev-like model specifically for making inlining decisions inside LLVM should improve jevopt's performance even more and might even get us an aggregate win over clang `-Oz`.

For reference, here are the results for individual programs.

| Program | Clang `-Oz` | Jevopt | Change |
| --- | ---: | ---: | ---: |
| aha-mont64 | 913 B | 1,017 B | +11.39% |
| crc32 | 456 B | 463 B | +1.54% |
| cubic | 1,724 B | 2,202 B | +27.73% |
| edn | 1,810 B | 1,799 B | −0.61% |
| huffbench | 1,792 B | 1,995 B | +11.33% |
| matmult-int | 708 B | 687 B | −2.97% |
| minver | 1,461 B | 1,342 B | −8.15% |
| nbody | 937 B | 937 B | 0.00% |
| nettle-aes | 2,932 B | 3,029 B | +3.31% |
| nettle-sha256 | 5,279 B | 5,113 B | −3.14% |
| nsichneu | 17,670 B | 17,670 B | 0.00% |
| picojpeg | 10,507 B | 28,455 B | +170.82% |
| qrduino | 7,701 B | 10,623 B | +37.94% |
| sglib-combined | 3,455 B | 3,286 B | −4.89% |
| slre | 3,651 B | 4,838 B | +32.51% |
| st | 1,013 B | 1,062 B | +4.84% |
| statemate | 5,698 B | 2,382 B | −58.20% |
| ud | 1,096 B | 1,038 B | −5.29% |
| wikisort | 6,306 B | 9,549 B | +51.43% |

If you made it here, thanks for reading! Like I said, I intend to keep doing cool stuff applying AI to compilers, so please reach out if you're interested!

## License

Copyright © 2026 Ramneet Singh. This project is licensed under the [GNU General Public License v3.0](LICENSE).
