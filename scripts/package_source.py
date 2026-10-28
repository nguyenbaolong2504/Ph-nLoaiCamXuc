"""Package a clean deliverable, excluding credentials, caches and dependencies."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SKIP={".git","node_modules","__pycache__",".venv",".pytest_cache","test-results","playwright-report","data","runs"}

def package(destination):
    destination=Path(destination).resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED,compresslevel=7) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative=path.relative_to(ROOT)
            if any(part in SKIP for part in relative.parts) or path.name==".env" or path.suffix in (".pyc",".tsbuildinfo",".log") or not path.is_file():
                continue
            archive.write(path,Path("ExpressionLab")/relative)
    with zipfile.ZipFile(destination) as archive:
        bad=archive.testzip()
        if bad:raise RuntimeError(f"Invalid archive entry: {bad}")
        if any(n.endswith("/.env") or "/node_modules/" in n for n in archive.namelist()):
            raise RuntimeError("Archive contains local state")
        for name,record in __import__('json').loads(archive.read('ExpressionLab/models/manifest.json')).items():
            digest=hashlib.sha256(archive.read('ExpressionLab/models/'+name)).hexdigest()
            if digest!=record['sha256']:raise RuntimeError('Archived model checksum mismatch')
    print(f"Archive verified: {destination.stat().st_size} bytes")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("output");package(p.parse_args().output)
