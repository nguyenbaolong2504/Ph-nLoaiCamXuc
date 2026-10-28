import asyncio
import base64
from collections import Counter
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from .config import ROOT, settings
from .database import db, now, public
from .inference import engine, decode_image, LABELS
from .security import current_user, require_consent, resolve_token

router = APIRouter()
worker = ThreadPoolExecutor(max_workers=1,thread_name_prefix="video")

def counts_for(frames):
    return dict(Counter(face["expression"] for frame in frames for face in frame["faces"] if face.get("expression")))

def save_session(user_id, source, title, frames, model_id, duration=0):
    # Recheck consent after inference and before persisting a result.
    if not db.users.find_one({"id":user_id,"consent":True,"status":"active"}):
        return None
    sid = secrets.token_hex(12)
    db.sessions.insert_one({"id":sid,"user_id":user_id,"source_type":source,"title":title[:120],"status":"COMPLETED","model_id":model_id,"created_at":now(),"expires_at":now()+timedelta(days=settings.retention_days),"frames":frames,"counts":counts_for(frames),"frame_count":len(frames),"face_count":sum(len(f["faces"]) for f in frames),"duration_ms":duration})
    return sid

async def read_upload(file, limit):
    content = bytearray()
    while chunk := await file.read(1024*1024):
        content.extend(chunk)
        if len(content)>limit:
            raise HTTPException(413,"File vượt quá giới hạn dung lượng.")
    return bytes(content)

@router.post("/api/analysis/image")
async def image(file: UploadFile=File(...),save: bool=Form(False),threshold: float=Form(.6),user=Depends(current_user)):
    require_consent(user)
    if not 0.3 <= threshold <= .95:
        raise HTTPException(422,"Ngưỡng dự đoán phải từ 0.3 đến 0.95.")
    content = await read_upload(file,10*1024*1024)
    try:
        decoded = await asyncio.to_thread(decode_image,content)
        result = await asyncio.to_thread(engine.analyze,decoded,threshold)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except RuntimeError as exc:
        raise HTTPException(503,str(exc))
    result["timestamp_ms"] = 0
    result["session_id"] = await asyncio.to_thread(save_session,user["id"],"image",file.filename or "Ảnh",[dict(result)],result["model_id"]) if save else None
    return result

def run_video(jid,path,user_id,save,threshold):
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise ValueError("Không đọc được video. Hãy dùng MP4 H.264.")
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not 1 <= fps <= 240 or total<=0 or total/fps > settings.max_video_seconds:
            raise ValueError(f"Video cần có thời lượng tối đa {settings.max_video_seconds} giây và FPS hợp lệ.")
        db.jobs.update_one({"id":jid},{"$set":{"status":"PROCESSING"}})
        step = max(1,round(fps/2))
        frames, index, started = [],0,time.monotonic()
        while True:
            job = db.jobs.find_one({"id":jid},{"cancel_requested":1})
            active = db.users.find_one({"id":user_id,"consent":True,"status":"active"},{"id":1})
            if not job or job.get("cancel_requested") or not active:
                db.jobs.update_one({"id":jid},{"$set":{"status":"CANCELLED","result":None}})
                return
            ok, frame = cap.read()
            if not ok:
                break
            if index/fps > settings.max_video_seconds or time.monotonic()-started>900:
                raise ValueError("Video vượt giới hạn thời gian xử lý.")
            if index%step == 0:
                h,w = frame.shape[:2]
                if w*h>3840*2160:
                    raise ValueError("Video vượt độ phân giải 4K.")
                if max(h,w)>1280:
                    frame = cv2.resize(frame,(round(w*1280/max(h,w)),round(h*1280/max(h,w))))
                result = engine.analyze(frame,threshold)
                result["timestamp_ms"] = round(index/fps*1000)
                frames.append(result)
                db.jobs.update_one({"id":jid},{"$set":{"progress":min(99,round(index/total*100)),"processed_frames":len(frames)}})
            index+=1
        if not frames:
            raise ValueError("Video không có khung hình đọc được.")
        if len({f["model_id"] for f in frames}) != 1:
            raise ValueError("Mô hình đã thay đổi trong lúc xử lý. Hãy chạy lại video.")
        # Cancellation at the final frame must not persist a completed session.
        job = db.jobs.find_one({"id":jid})
        if not job or job.get("cancel_requested"):
            db.jobs.update_one({"id":jid},{"$set":{"status":"CANCELLED"}})
            return
        sid = save_session(user_id,"video",job["title"],frames,frames[0]["model_id"],round(index/fps*1000)) if save else None
        db.jobs.update_one({"id":jid},{"$set":{"status":"COMPLETED","progress":100,"session_id":sid,"result":{"frames":frames,"counts":counts_for(frames),"frame_count":len(frames),"duration_ms":round(index/fps*1000),"model_id":frames[0]["model_id"]}}})
    except Exception as exc:
        db.jobs.update_one({"id":jid},{"$set":{"status":"FAILED","error":str(exc)[:300]}})
    finally:
        cap.release()
        Path(path).unlink(missing_ok=True)

@router.post("/api/analysis/video",status_code=202)
async def video(file: UploadFile=File(...),save: bool=Form(False),threshold: float=Form(.6),user=Depends(current_user)):
    require_consent(user)
    if not engine.status()["ready"]:
        raise HTTPException(503,"Mô hình chưa sẵn sàng.")
    if not .3<=threshold<=.95:
        raise HTTPException(422,"Ngưỡng không hợp lệ.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp4",".webm",".mov",".avi"):
        raise HTTPException(400,"Chỉ hỗ trợ MP4, WebM, MOV, AVI.")
    if db.jobs.count_documents({"status":{"$in":["QUEUED","PROCESSING"]}})>=4:
        raise HTTPException(429,"Hàng đợi đang đầy, hãy thử lại sau.")
    temp = Path(settings.data_dir)/"tmp"
    temp.mkdir(parents=True,exist_ok=True)
    fd,path = tempfile.mkstemp(suffix=suffix,dir=temp)
    try:
        size = 0
        with os.fdopen(fd,"wb") as out:
            while chunk := await file.read(1024*1024):
                size+=len(chunk)
                if size>settings.max_upload_mb*1024*1024:
                    raise HTTPException(413,"Video vượt quá giới hạn dung lượng.")
                out.write(chunk)
        jid = secrets.token_hex(12)
        db.jobs.insert_one({"id":jid,"user_id":user["id"],"title":file.filename or "Video","status":"QUEUED","progress":0,"cancel_requested":False,"created_at":now(),"expires_at":now()+timedelta(hours=1)})
        worker.submit(run_video,jid,path,user["id"],save,threshold)
        return {"id":jid,"status":"QUEUED"}
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise

@router.get("/api/jobs/{jid}")
def job(jid:str,user=Depends(current_user)):
    found = db.jobs.find_one({"id":jid,"user_id":user["id"]})
    if not found:
        raise HTTPException(404,"Không tìm thấy tác vụ.")
    return public(found)

@router.post("/api/jobs/{jid}/cancel")
def cancel(jid:str,user=Depends(current_user)):
    result = db.jobs.update_one({"id":jid,"user_id":user["id"],"status":{"$in":["QUEUED","PROCESSING"]}},{"$set":{"cancel_requested":True}})
    if not result.matched_count:
        raise HTTPException(404,"Tác vụ đã kết thúc hoặc không tồn tại.")
    return {"ok":True}

class Smoother:
    def __init__(self):
        self.previous = []
        self.counter = 0

    @staticmethod
    def iou(a,b):
        x,y = max(a[0],b[0]),max(a[1],b[1])
        right,bottom = min(a[0]+a[2],b[0]+b[2]),min(a[1]+a[3],b[1]+b[3])
        intersection = max(0,right-x)*max(0,bottom-y)
        return intersection/max(1,a[2]*a[3]+b[2]*b[3]-intersection)

    def apply(self,result,threshold):
        used = set()
        for face in result["faces"]:
            matches = [(self.iou(face["box"],old["box"]),i,old) for i,old in enumerate(self.previous) if i not in used]
            match = max(matches,key=lambda x:x[0]) if matches else None
            if match and match[0]>.3:
                _,i,old = match; used.add(i)
                face["face_id"] = old["face_id"]
                if face["scores"] and old["scores"]:
                    face["scores"] = {k:.6*face["scores"][k]+.4*old["scores"][k] for k in LABELS}
            else:
                self.counter+=1; face["face_id"] = self.counter
            if face["scores"]:
                order = sorted(face["scores"],key=face["scores"].get,reverse=True)
                best,second = order[:2]
                face["score"] = face["scores"][best]
                accepted = face["score"]>=threshold and face["score"]-face["scores"][second]>=settings.margin_threshold
                face["expression"] = best if accepted else None
                face["status"] = "OK" if accepted else "UNCERTAIN"
        self.previous = result["faces"]
        return result

@router.websocket("/ws/analysis/live")
async def live(ws: WebSocket):
    if ws.headers.get("origin") not in settings.allowed_origins.split(","):
        await ws.close(code=1008); return
    try:
        user = await asyncio.to_thread(resolve_token,ws.cookies.get("expression_session"))
        require_consent(user)
    except HTTPException:
        await ws.close(code=1008); return
    await ws.accept()
    frames, smoother, started = [],Smoother(),time.monotonic()
    options = {}
    try:
        options = await asyncio.wait_for(ws.receive_json(),timeout=15)
        threshold = float(options.get("threshold",.6))
        if not .3<=threshold<=.95:
            raise ValueError("Ngưỡng không hợp lệ.")
        while len(frames)<600:
            message = await asyncio.wait_for(ws.receive(),timeout=30)
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") == "stop":
                sid = await asyncio.to_thread(save_session,user["id"],"webcam","Phiên webcam",frames,frames[0]["model_id"],round((time.monotonic()-started)*1000)) if frames and options.get("save") else None
                await ws.send_json({"type":"stopped","session_id":sid})
                break
            content = message.get("bytes")
            if not content or len(content)>2*1024*1024:
                raise ValueError("Khung hình không hợp lệ hoặc vượt 2 MB.")
            # Validate the login, account state and consent on every frame.
            fresh = await asyncio.to_thread(resolve_token,ws.cookies.get("expression_session"))
            require_consent(fresh)
            image = await asyncio.to_thread(decode_image,content)
            result = await asyncio.to_thread(engine.analyze,image,threshold)
            if frames and frames[0]["model_id"] != result["model_id"]:
                raise ValueError("Mô hình đã đổi, hãy bắt đầu phiên mới.")
            result = smoother.apply(result,threshold)
            result["timestamp_ms"] = round((time.monotonic()-started)*1000)
            frames.append(result)
            await ws.send_json({"type":"result",**result})
        else:
            await ws.send_json({"type":"error","detail":"Phiên đạt giới hạn 600 khung hình. Dừng và bắt đầu phiên mới."})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type":"error","detail":str(exc)[:200]})
        except RuntimeError:
            pass
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass
