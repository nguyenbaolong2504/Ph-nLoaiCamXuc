from collections import Counter
from datetime import timedelta
import csv
import io
import json
from pathlib import Path
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal
from .database import db, public, now, audit
from .security import current_user, require_role
from .config import ROOT, settings
from .inference import engine, LABELS

router = APIRouter(prefix="/api")

def owned_session(sid,user):
    session = db.sessions.find_one({"id":sid,"user_id":user["id"],"expires_at":{"$gt":now()}})
    if not session:
        raise HTTPException(404,"Không tìm thấy phiên phân tích.")
    return session

@router.get("/sessions")
def sessions(q:str=Query("",max_length=120),source:str="",expression:str="",date_from:str="",date_to:str="",page:int=Query(1,ge=1),user=Depends(current_user)):
    from datetime import datetime, timezone
    query = {"user_id":user["id"],"expires_at":{"$gt":now()}}
    if source in ("image","video","webcam"):
        query["source_type"] = source
    if expression in LABELS:
        query[f"counts.{expression}"] = {"$gt":0}
    if q:
        import re
        query["title"] = {"$regex":re.escape(q),"$options":"i"}
    try:
        dates = {}
        if date_from:
            dates["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        if date_to:
            dates["$lt"] = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)+timedelta(days=1)
        if dates:
            query["created_at"] = dates
    except ValueError:
        raise HTTPException(422,"Ngày không hợp lệ.")
    return {"items":public(list(db.sessions.find(query,{"frames":0}).sort("created_at",-1).skip((page-1)*20).limit(20))),"total":db.sessions.count_documents(query),"page":page}

@router.get("/sessions/{sid}")
def detail(sid:str,user=Depends(current_user)):
    return public(owned_session(sid,user))

@router.delete("/sessions/{sid}")
def delete(sid:str,user=Depends(current_user)):
    owned_session(sid,user)
    db.sessions.delete_one({"id":sid,"user_id":user["id"]})
    db.feedback.delete_many({"session_id":sid,"user_id":user["id"]})
    return {"ok":True}

@router.get("/sessions/{sid}/report")
def report(sid:str,user=Depends(current_user)):
    session = owned_session(sid,user)
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(["session_id","model_id","timestamp_ms","face_id","status","expression","score",*LABELS])
    for frame in session["frames"]:
        for face in frame["faces"]:
            writer.writerow([sid,session["model_id"],frame.get("timestamp_ms",0),face["face_id"],face["status"],face["expression"] or "",face["score"],*[face["scores"].get(k,"") for k in LABELS]])
        if not frame["faces"]:
            writer.writerow([sid,session["model_id"],frame.get("timestamp_ms",0),"","NO_FACE"])
    return Response("\ufeff"+out.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="expression-{sid}.csv"'})

class Feedback(BaseModel):
    session_id: str
    frame_index: int = Field(ge=0)
    face_id: int
    suggested_label: Literal["angry","disgust","fear","happy","neutral","sad","surprise"]
    comment: str = Field(default="",max_length=500)

@router.post("/feedback")
def feedback(body: Feedback,user=Depends(current_user)):
    session = owned_session(body.session_id,user)
    if body.frame_index>=len(session["frames"]) or body.face_id not in [f["face_id"] for f in session["frames"][body.frame_index]["faces"]]:
        raise HTTPException(404,"Kết quả không tồn tại.")
    db.feedback.insert_one({"id":secrets.token_hex(12),"user_id":user["id"],**body.model_dump(),"review_status":"pending","created_at":now(),"expires_at":session["expires_at"]})
    return {"ok":True}

def statistics(query):
    data = list(db.sessions.find({**query,"expires_at":{"$gt":now()}},{"frames":0}))
    labels,sources,activity = Counter(),Counter(),Counter()
    for item in data:
        labels.update(item.get("counts",{})); sources[item["source_type"]]+=1
        activity[item["created_at"].strftime("%d/%m")]+=1
    return {"sessions":len(data),"frames":sum(d["frame_count"] for d in data),"faces":sum(d["face_count"] for d in data),"counts":dict(labels),"sources":dict(sources),"activity":dict(activity)}

@router.get("/statistics")
def stats(user=Depends(current_user)):
    return statistics({"user_id":user["id"]})

@router.get("/models")
def models(user=Depends(current_user)):
    return {"items":public(list(db.model_versions.find().sort("created_at",-1))),"active_id":engine.model_id,"engine":engine.status()}

class ModelRegistration(BaseModel):
    name: str = Field(min_length=2,max_length=100)
    version: str = Field(min_length=1,max_length=50)
    path: str = Field(max_length=200)
    report_path: str = Field(max_length=200)

@router.post("/models")
def register_model(body: ModelRegistration,user=Depends(current_user)):
    require_role(user,"engineer")
    path = (ROOT/"models"/body.path).resolve()
    report_path = (ROOT/"models"/body.report_path).resolve()
    if not path.is_relative_to((ROOT/"models").resolve()) or path.suffix != ".pt" or not path.is_file():
        raise HTTPException(400,"Đặt file TorchScript .pt trong thư mục models.")
    if not report_path.is_relative_to((ROOT/"models").resolve()) or not report_path.is_file():
        raise HTTPException(400,"Cần báo cáo đánh giá JSON trong thư mục models.")
    try:
        import hashlib
        report = json.loads(report_path.read_text())
        if report.get("model_sha256") != hashlib.sha256(path.read_bytes()).hexdigest() or report.get("split")!="test":
            raise ValueError("Báo cáo test không khớp checksum model.")
        if report.get("labels") != LABELS or not 0 <= report["accuracy"] <= 1 or not 0 <= report["macro_f1"] <= 1:
            raise ValueError("Metric hoặc thứ tự nhãn không hợp lệ.")
    except (ValueError,KeyError) as exc:
        raise HTTPException(400,str(exc))
    mid = secrets.token_hex(12)
    db.model_versions.insert_one({"id":mid,**body.model_dump(),"engine":"torchscript","metrics":report,"status":"evaluated","created_at":now()})
    audit(user["id"],"register_model",mid)
    return {"id":mid}

@router.post("/models/{mid}/approve")
def approve_model(mid:str,user=Depends(current_user)):
    require_role(user,"engineer")
    result = db.model_versions.update_one({"id":mid,"status":"evaluated"},{"$set":{"status":"approved"}})
    if not result.matched_count:
        raise HTTPException(400,"Mô hình cần được đánh giá trước.")
    audit(user["id"],"approve_model",mid)
    return {"ok":True}

@router.post("/models/{mid}/activate")
def activate_model(mid:str,user=Depends(current_user)):
    require_role(user,"engineer")
    record = db.model_versions.find_one({"id":mid,"status":"approved"})
    if not record:
        raise HTTPException(400,"Mô hình chưa được phê duyệt.")
    if db.jobs.count_documents({"status":{"$in":["QUEUED","PROCESSING"]}}):
        raise HTTPException(409,"Chờ tác vụ video kết thúc trước khi đổi model.")
    try:
        engine.load(record)
    except Exception as exc:
        raise HTTPException(400,f"Kiểm tra mô hình thất bại: {exc}")
    db.system.update_one({"_id":"active_model"},{"$set":{"model_id":mid}},upsert=True)
    audit(user["id"],"activate_model",mid)
    return {"ok":True}

@router.get("/admin/statistics")
def admin_stats(user=Depends(current_user)):
    require_role(user,"admin")
    return {**statistics({}),"users":db.users.count_documents({})}

@router.get("/admin/users")
def users(user=Depends(current_user)):
    require_role(user,"admin")
    return public(list(db.users.find().sort("created_at",-1).limit(200)))

class UserChange(BaseModel):
    role: Literal["user","admin","engineer","annotator"]
    status: Literal["active","locked"]

@router.patch("/admin/users/{uid}")
def update_user(uid:str,body:UserChange,user=Depends(current_user)):
    require_role(user,"admin")
    if uid == user["id"]:
        raise HTTPException(400,"Không thể tự thay đổi quyền hoặc khóa tài khoản đang dùng.")
    if not db.users.update_one({"id":uid},{"$set":body.model_dump()}).matched_count:
        raise HTTPException(404,"Không tìm thấy người dùng.")
    if body.status == "locked":
        db.auth_sessions.delete_many({"user_id":uid})
        db.jobs.update_many({"user_id":uid},{"$set":{"cancel_requested":True}})
    audit(user["id"],"update_user",uid)
    return {"ok":True}

@router.get("/admin/audit")
def logs(user=Depends(current_user)):
    require_role(user,"admin")
    return public(list(db.audit_logs.find().sort("created_at",-1).limit(100)))

@router.get("/admin/feedback")
def feedback_queue(user=Depends(current_user)):
    require_role(user,"engineer","annotator")
    return public(list(db.feedback.find().sort("created_at",-1).limit(100)))

class Review(BaseModel):
    status: Literal["reviewed","rejected"]

@router.patch("/admin/feedback/{fid}")
def review_feedback(fid:str,body:Review,user=Depends(current_user)):
    require_role(user,"engineer","annotator")
    db.feedback.update_one({"id":fid},{"$set":{"review_status":body.status,"reviewer_id":user["id"]}})
    return {"ok":True}
