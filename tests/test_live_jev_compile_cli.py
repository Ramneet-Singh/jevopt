import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from dotenv import load_dotenv


ROOT = Path(__file__).parents[1]


class LiveJevCompileCliTest(unittest.TestCase):
    @unittest.skipUnless(
        load_dotenv(ROOT / ".env") and os.getenv("TYPESAFE_API_KEY"),
        "live TypeSafe credentials are unavailable",
    )
    def test_fixed_jevopt_path_controls_real_llvm_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "jevopt",
                    "compile",
                    "--source-dir",
                    str(ROOT / "examples" / "inline_probe"),
                    "--output-dir",
                    output_dir,
                    "--verify",
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads((Path(output_dir) / "result.json").read_text())
            self.assertEqual(result["mode"], "jevopt")
            self.assertTrue(result["program"]["correct"])
            self.assertEqual(
                result["prompt_version"],
                "inline-size-v3-minimal-ir-full-budget-structure-features-source-blind",
            )
            self.assertGreater(result["jevopt_binary"]["text_bytes"], 0)
            self.assertEqual(len(result["decisions"]), 1)
            decision = result["decisions"][0]
            self.assertEqual(decision["model"], "jev-1.13.0")
            self.assertIn(decision["answer"]["choice"], {"inline", "do_not_inline"})
            self.assertEqual(
                set(decision["question"]["criteria"]),
                {"inline", "do_not_inline"},
            )
            self.assertNotIn("llvm_default_advice", decision["state"])
            self.assertIn("c_translation_unit", decision["state"])
            self.assertIn("caller_ir", decision["state"])
            self.assertIn("callee_ir", decision["state"])
            self.assertEqual(
                set(decision["state"]["numeric_facts"]),
                {
                    "callee_basic_block_count",
                    "callee_instruction_count",
                    "callee_users",
                    "caller_basic_block_count",
                    "caller_instruction_count",
                    "caller_users",
                    "constant_args",
                },
            )
            self.assertEqual(
                decision["sent_to_llvm"],
                int(decision["answer"]["choice"] == "inline"),
            )


if __name__ == "__main__":
    unittest.main()
