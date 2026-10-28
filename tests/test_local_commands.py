"""Exercise npm's Python bridge with real subprocesses, without MongoDB/network."""
import csv
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv

SOURCE = Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which("node") and sys.version_info[:2] == (3, 11), "Needs Node and Python 3.11")
class LocalCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="expression local ")
        cls.root = Path(cls.temporary.name)
        (cls.root / "scripts").mkdir()
        (cls.root / "backend").mkdir()
        for name in ("local.mjs", "setup.py"):
            shutil.copyfile(SOURCE / "scripts" / name, cls.root / "scripts" / name)
        shutil.copytree(SOURCE / "ai", cls.root / "ai", ignore=shutil.ignore_patterns("__pycache__", "runs"))
        venv.EnvBuilder(with_pip=False, system_site_packages=True).create(cls.root / ".venv")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def invoke(self, *args):
        return subprocess.run([shutil.which("node"), str(self.root / "scripts/local.mjs"), *args],
                              cwd=self.root / "backend", capture_output=True, text=True, timeout=45)

    def test_dataset_paths_with_spaces_resolve_from_repo_root(self):
        raw = self.root / "data" / "raw file.csv"
        raw.parent.mkdir(exist_ok=True)
        with raw.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["emotion", "pixels", "Usage"])
            writer.writerow([3, " ".join(["128"] * 2304), "Training"])
        result = self.invoke("prepare", "data/raw file.csv", "--output", "data/output with spaces")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "data/output with spaces/train/happy/fer-00000.png").is_file())
        self.assertFalse((self.root / "backend/data").exists())

    def test_python_failure_is_not_reported_as_success(self):
        result = self.invoke("prepare", "missing.csv")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing.csv", result.stderr)

    @unittest.skipUnless(importlib.util.find_spec("torch") and importlib.util.find_spec("sklearn"), "Research dependencies not installed")
    def test_training_help_is_forwarded_to_actual_cli(self):
        result = self.invoke("train", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--batch-size", result.stdout)
        self.assertIn("mobilenet_v3_small", result.stdout)

    def test_setup_preserves_existing_configuration(self):
        config = self.root / ".env"
        existing = "MONGO_URI=mongodb://127.0.0.1:27099\nAPP_PORT=8099\n"
        config.write_text(existing, encoding="utf-8")
        subprocess.run([sys.executable, str(self.root / "scripts/setup.py")], check=True, capture_output=True)
        self.assertEqual(config.read_text(encoding="utf-8"), existing)

if __name__ == "__main__":
    unittest.main()
