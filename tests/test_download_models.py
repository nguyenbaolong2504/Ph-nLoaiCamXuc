"""Verify bundled pretrained assets work offline and bad downloads stay unusable."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from scripts import download_models

ROOT = Path(__file__).resolve().parents[1]

class ModelAssetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="expression-models-")
        self.root = Path(self.temporary.name)
        self.models = self.root / "models"
        self.models.mkdir()
        for name in ("manifest.json", "expression.onnx", "face_detector.tflite"):
            shutil.copyfile(ROOT / "models" / name, self.models / name)
        self.root_patch = patch.object(download_models, "ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def test_valid_bundled_models_never_request_network(self):
        with patch.object(download_models.urllib.request, "urlopen", side_effect=AssertionError("Network must not be needed")) as network:
            download_models.download()
        network.assert_not_called()
        manifest = json.loads((self.models / "manifest.json").read_text())
        for name, record in manifest.items():
            self.assertEqual(hashlib.sha256((self.models / name).read_bytes()).hexdigest(), record["sha256"])

    def test_bad_download_does_not_replace_existing_file(self):
        target = self.models / "expression.onnx"
        target.write_bytes(b"damaged local asset")
        with patch.object(download_models.urllib.request, "urlopen", return_value=io.BytesIO(b"not a real model")):
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                download_models.download()
        self.assertEqual(target.read_bytes(), b"damaged local asset")
        self.assertFalse((self.models / "expression.download").exists())

    def test_dns_error_explains_git_recovery(self):
        (self.models / "expression.onnx").unlink()
        with patch.object(download_models.urllib.request, "urlopen", side_effect=urllib.error.URLError("getaddrinfo failed")):
            with self.assertRaisesRegex(RuntimeError, "git pull"):
                download_models.download()
        self.assertFalse((self.models / "expression.onnx").exists())
        self.assertFalse((self.models / "expression.download").exists())

if __name__ == "__main__":
    unittest.main()
