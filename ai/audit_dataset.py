import argparse
from collections import Counter
import hashlib
from pathlib import Path
from PIL import Image
from .common import LABELS, save_json

def audit(root):
    root = Path(root)
    seen,duplicates,errors,distribution = {},[],[],{}
    fingerprint = hashlib.sha256()
    for split in ("train","val","test"):
        distribution[split] = {}
        for label in LABELS:
            files = sorted((root/split/label).glob("*"))
            count = 0
            for path in files:
                if not path.is_file():
                    continue
                try:
                    with Image.open(path) as image:
                        # Decoded RGB hashes detect identical pixels saved in different formats.
                        image = image.convert("RGB")
                        digest = hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
                    fingerprint.update(f"{split}/{label}/{path.name}:{digest}".encode())
                    if digest in seen and seen[digest][0]!=split:
                        duplicates.append([str(path),str(seen[digest][1])])
                    seen[digest] = (split,path)
                    count+=1
                except Exception as exc:
                    errors.append({"file":str(path),"error":str(exc)})
            distribution[split][label] = count
            if not count:
                errors.append({"file":str(root/split/label),"error":"Missing or empty class"})
    return {"dataset_sha256":fingerprint.hexdigest(),"distribution":distribution,"cross_split_duplicates":duplicates,"errors":errors,"ok":not duplicates and not errors,"note":"Kiểm tra ảnh trùng tuyệt đối; chưa phát hiện ảnh gần trùng hoặc cùng danh tính."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("dataset");parser.add_argument("--output",default="dataset-audit.json")
    args = parser.parse_args(); result = audit(args.dataset);save_json(args.output,result)
    print(f"ok={result['ok']} duplicate_pairs={len(result['cross_split_duplicates'])} errors={len(result['errors'])}")
    raise SystemExit(0 if result["ok"] else 1)
