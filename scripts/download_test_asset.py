"""Fetch the public NASA software-test fixture when absent from a source checkout."""
import hashlib
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def ensure():
    path=ROOT/"tests/assets/astronaut.png"
    if not path.is_file():
        path.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen("https://raw.githubusercontent.com/scikit-image/scikit-image/v0.19.3/skimage/data/astronaut.png",timeout=60) as source:
            data=source.read()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Invalid test image download")
        path.write_bytes(data)
    return path

if __name__=="__main__":
    print(ensure())
