from contextlib import asynccontextmanager
from pathlib import Path
import logging
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .accounts import router as accounts_router
from .analysis import router as analysis_router, worker
from .management import router as management_router
from .research import router as research_router, executor as research_executor
from .config import ROOT, settings
from .database import db, initialize, now
from .security import hash_password
from .inference import engine

@asynccontextmanager
async def lifespan(app):
    initialize()
    if settings.admin_password and not db.users.find_one({"email":settings.admin_email.lower()}):
        if len(settings.admin_password)<10:
            raise RuntimeError("ADMIN_PASSWORD phải có ít nhất 10 ký tự.")
        db.users.insert_one({"id":secrets.token_hex(12),"email":settings.admin_email.lower(),"name":"Quản trị viên","password_hash":hash_password(settings.admin_password),"role":"admin","status":"active","consent":False,"created_at":now()})
    # Remove only files owned by the previous local video worker.
    temporary = Path(settings.data_dir)/"tmp"
    temporary.mkdir(parents=True,exist_ok=True)
    for file in temporary.iterdir():
        if file.is_file():
            file.unlink(missing_ok=True)
    try:
        active = db.system.find_one({"_id":"active_model"})
        engine.load(db.model_versions.find_one({"id":active["model_id"]}))
    except Exception as exc:
        engine.error = str(exc)
        logging.exception("AI model failed to load")
    yield
    db.jobs.update_many({"status":{"$in":["QUEUED","PROCESSING"]}},{"$set":{"cancel_requested":True}})
    worker.shutdown(wait=True,cancel_futures=True)
    research_executor.shutdown(wait=False,cancel_futures=True)
    engine.close()

app = FastAPI(title="Expression Lab API",version="1.0.0",lifespan=lifespan)

@app.middleware("http")
async def safety_headers(request: Request,call_next):
    if request.method in ("POST","PUT","PATCH","DELETE"):
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins.split(","):
            return JSONResponse({"detail":"Origin không được phép."},status_code=403)
        length = request.headers.get("content-length","")
        if length.isdigit() and int(length)>(settings.max_upload_mb+2)*1024*1024:
            return JSONResponse({"detail":"File vượt giới hạn."},status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/api/health")
def health():
    try:
        db.command("ping")
        mongo = True
    except Exception:
        mongo = False
    status = engine.status()
    return JSONResponse({"ok":mongo and status["ready"],"mongodb":mongo,"ai":status,"retention_days":settings.retention_days},status_code=200 if mongo and status["ready"] else 503)

app.include_router(accounts_router)
app.include_router(analysis_router)
app.include_router(management_router)
app.include_router(research_router)

dist = ROOT/"frontend/dist"
if dist.exists():
    app.mount("/",StaticFiles(directory=dist,html=True),name="frontend")
