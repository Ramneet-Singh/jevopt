import json
from pathlib import Path
import tempfile
import unittest

from jevopt.dashboard import export_dashboard, summarize_run


class DashboardTest(unittest.TestCase):
    def test_summarizes_real_run_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            program = run / "demo"
            program.mkdir(parents=True)
            (program / "result.json").write_text(
                json.dumps(
                    {
                        "program": {"correct": True},
                        "compile_commands": [[], []],
                        "stock_binary": {"text_bytes": 100},
                        "jevopt_binary": {"text_bytes": 75},
                        "decisions": [
                            {
                                "llvm_observation": {"default": False},
                                "sent_to_llvm": 1,
                                "usage": {"input_tokens": 1000},
                            },
                            {
                                "llvm_observation": {"default": True},
                                "sent_to_llvm": 0,
                                "usage": {"input_tokens": 2000},
                            },
                        ],
                    }
                )
            )

            summary = summarize_run("test-run", run)
            item = summary["programs"][0]
            self.assertEqual(item["translation_units"], 2)
            self.assertEqual(
                item["clang"], {"inline": 1, "do_not_inline": 1, "text_bytes": 100}
            )
            self.assertEqual(
                item["jevopt"],
                {
                    "inline": 1,
                    "do_not_inline": 1,
                    "text_bytes": 75,
                    "api_cost_usd": 0.000126,
                },
            )
            self.assertEqual(item["delta_percent"], -25.0)

            output = Path(directory) / "runs.json"
            export_dashboard([("test-run", run)], output)
            self.assertEqual(json.loads(output.read_text())["runs"][0], summary)
            self.assertEqual(
                output.with_suffix(".js").read_text(),
                f"window.JEVOPT_DASHBOARD = {output.read_text().rstrip()};\n",
            )


if __name__ == "__main__":
    unittest.main()
