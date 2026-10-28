"""Local research jobs. Install optional dependencies with npm run setup:ai."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from .config import ROOT
from .database import db, now, public, audit
from .security import current_user, require_role

router=APIRouter(prefix="/api/research")
executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix="research")

class DatasetRegistration(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    path:str=Field(min_length=1,max_length=150)
    source:str=Field(min_length=5,max_length=500)
    license_info:str=Field(min_length=5,max_length=500)
    version:str=Field(default="v1",max_length=50)

@router.get("/datasets")
def datasets(user=Depends(current_user)):
    require_role(user,"engineer")
    return {"items":public(list(db.datasets.find().sort("created_at",-1))),"training_available":importlib.util.find_spec("torch") is not None}

@router.post("/datasets")
def register(body:DatasetRegistration,user=Depends(current_user)):
    require_role(user,"engineer")
    base=(ROOT/"data/datasets").resolve();path=(base/body.path).resolve()
    if not path.is_relative_to(base) or not path.is_dir():
        raise HTTPException(400,"Đặt dữ liệu trong data/datasets rồi nhập đường dẫn tương đối, ví dụ fer2013.")
    did=secrets.token_hex(12)
    db.datasets.insert_one({"id":did,**body.model_dump(),"created_at":now(),"audit":None,"status":"registered"})
    audit(user["id"],"register_dataset",did)
    return {"id":did}

def dataset_audit(did,path):
    try:
        from ai.audit_dataset import audit as run_audit
        result=run_audit(path)
        db.datasets.update_one({"id":did},{"$set":{"audit":result,"status":"ready" if result["ok"] else "invalid"}})
    except Exception as exc:
        db.datasets.update_one({"id":did},{"$set":{"status":"failed","error":str(exc)}})

@router.post("/datasets/{did}/audit")
def audit_dataset(did:str,user=Depends(current_user)):
    require_role(user,"engineer")
    record=db.datasets.find_one({"id":did})
    if not record:raise HTTPException(404,"Không tìm thấy dataset.")
    if importlib.util.find_spec("torch") is None:
        raise HTTPException(409,"Trong thư mục backend, chạy npm run setup:ai rồi khởi động lại npm run dev.")
    db.datasets.update_one({"id":did},{"$set":{"status":"auditing"}})
    executor.submit(dataset_audit,did,ROOT/"data/datasets"/record["path"])
    return {"ok":True}

class Training(BaseModel):
    dataset_id:str
    architecture:Literal["cnn","resnet18","mobilenet_v3_small"]="mobilenet_v3_small"
    epochs:int=Field(default=30,ge=1,le=100)
    batch_size:int=Field(default=32,ge=2,le=128)
    learning_rate:float=Field(default=.0001,gt=0,le=.1)

def train_run(rid,record,body):
    output=ROOT/"ai/runs"/rid
    logs=ROOT/"data/training-logs";logs.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,"-m","ai.train","--dataset",str(ROOT/"data/datasets"/record["path"]),"--model",body.architecture,"--output",str(output),"--epochs",str(body.epochs),"--batch-size",str(body.batch_size),"--lr",str(body.learning_rate)]
    db.training_runs.update_one({"id":rid},{"$set":{"status":"PROCESSING"}})
    try:
        with (logs/f"{rid}.log").open("w",encoding="utf-8") as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=12*3600)
        db.training_runs.update_one({"id":rid},{"$set":{"status":"COMPLETED" if result.returncode==0 else "FAILED","ended_at":now()}})
    except Exception as exc:
        db.training_runs.update_one({"id":rid},{"$set":{"status":"FAILED","error":str(exc),"ended_at":now()}})

@router.post("/train",status_code=202)
def train(body:Training,user=Depends(current_user)):
    require_role(user,"engineer")
    if importlib.util.find_spec("torch") is None:
        raise HTTPException(409,"Trong thư mục backend, chạy npm run setup:ai để cài PyTorch cho huấn luyện, rồi khởi động lại backend.")
    record=db.datasets.find_one({"id":body.dataset_id,"status":"ready"})
    if not record:raise HTTPException(400,"Dataset cần vượt kiểm tra chất lượng trước khi train.")
    if db.training_runs.count_documents({"status":{"$in":["QUEUED","PROCESSING"]}}):
        raise HTTPException(409,"Chỉ chạy một thực nghiệm tại một thời điểm trên bản local.")
    rid=secrets.token_hex(12)
    db.training_runs.insert_one({"id":rid,"user_id":user["id"],"config":body.model_dump(),"dataset_sha256":record["audit"]["dataset_sha256"],"status":"QUEUED","created_at":now()})
    executor.submit(train_run,rid,record,body);audit(user["id"],"start_training",rid)
    return {"id":rid}

@router.get("/runs")
def runs(user=Depends(current_user)):
    require_role(user,"engineer")
    items=list(db.training_runs.find().sort("created_at",-1).limit(30))
    for item in items:
        history=ROOT/"ai/runs"/item["id"]/"history.json"
        if history.is_file():
            try:item["history"]=json.loads(history.read_text())
            except json.JSONDecodeError:pass
        log=ROOT/"data/training-logs"/f"{item['id']}.log"
        if log.is_file():item["log_tail"]=log.read_text(encoding="utf-8",errors="replace")[-4000:]
    return public(items)
