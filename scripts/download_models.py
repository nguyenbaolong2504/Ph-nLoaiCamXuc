"""Download real pretrained assets. No fake/random inference fallback."""
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "48b10fa505aeb51fbd127fc60a5c660040e823b7"
ASSETS = {
    "expression.onnx": f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{COMMIT}/models/facial_expression_recognition/facial_expression_recognition_mobilefacenet_2022july.onnx",
    "face_detector.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
}

def download():
    target = ROOT / "models"
    target.mkdir(exist_ok=True)
    manifest_file = target / "manifest.json"
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    for name, url in ASSETS.items():
        path = target / name
        expected = manifest.get(name, {}).get("sha256")
        if path.exists() and expected and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            print(f"OK {name}")
            continue
        print(f"Downloading {name}...", flush=True)
        temporary = path.with_suffix(".download")
        try:
            with urllib.request.urlopen(url, timeout=120) as source, temporary.open("wb") as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if temporary.stat().st_size < 100_000 or (expected and digest != expected):
                raise RuntimeError(f"Invalid model checksum: {name}")
            temporary.replace(path)
            manifest[name] = {"url": url, "sha256": digest, "bytes": path.stat().st_size}
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Khong tai duoc {name}. Hai model pretrained da kem trong Git; chay git pull o thu muc goc de lay model. Neu file da bi xoa, khoi phuc model tu Git. Chi can Internet khi model trong may bi thieu/hong.") from exc
        finally:
            temporary.unlink(missing_ok=True)
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n")

if __name__ == "__main__":
    try:
        download()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
