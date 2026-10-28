"""Start the native FastAPI backend; cwd and configuration are repo-relative."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    parser = argparse.ArgumentParser(description="Expression Lab local backend")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    from backend.app.config import settings
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    import uvicorn

    for name in ("expression.onnx", "face_detector.tflite"):
        if not (ROOT / "models" / name).is_file():
            raise SystemExit("Thieu model AI. Trong backend, chay npm run setup de tai model truoc.")
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except PyMongoError:
        raise SystemExit("Khong ket noi duoc MongoDB. Hay bat dich vu MongoDB local hoac sua MONGO_URI trong .env thanh URI Atlas.")
    finally:
        client.close()
    print(f"Backend: http://127.0.0.1:{settings.app_port} | API: http://127.0.0.1:{settings.app_port}/docs", flush=True)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=settings.app_port,
                reload=args.reload, reload_dirs=[str(ROOT / "backend")] if args.reload else None)

if __name__ == "__main__":
    main()
