import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]


class PassthroughCliTest(unittest.TestCase):
    def run_passthrough(self, example: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as output_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "jevopt",
                    "passthrough",
                    "--source-dir",
                    str(ROOT / "examples" / example),
                    "--output-dir",
                    output_dir,
                    "--verify",
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads((Path(output_dir) / "result.json").read_text())

    def test_real_llvm_decisions_reproduce_c_binary(self) -> None:
        result = self.run_passthrough("inline_probe")

        self.assertEqual(result["mode"], "passthrough")
        self.assertTrue(result["program"]["verified"])
        self.assertTrue(result["program"]["correct"])
        self.assertTrue(result["identical_to_clang"])
        self.assertGreater(len(result["observations"]), 0)
        observation = result["observations"][0]
        self.assertIn("numeric_features", observation)
        self.assertEqual({"caller", "callee", "callsite"}, set(observation["ir"]))

    def test_compiles_and_links_cpp(self) -> None:
        result = self.run_passthrough("cpp_probe")

        self.assertTrue(result["program"]["correct"])
        self.assertTrue(result["identical_to_clang"])
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["stock_link_command"][0], "/usr/bin/clang++-21")


if __name__ == "__main__":
    unittest.main()
