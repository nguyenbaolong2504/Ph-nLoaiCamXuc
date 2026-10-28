import hashlib
import secrets
import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError
from .database import db, now, public, audit
from .security import current_user, hash_password, verify_password, create_login

router = APIRouter(prefix="/api")
attempts = defaultdict(deque)
attempt_lock = Lock()

class Register(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2,max_length=80)
    password: str = Field(min_length=10,max_length=128)

class Login(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

class Profile(BaseModel):
    name: str = Field(min_length=2,max_length=80)

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10,max_length=128)

class Consent(BaseModel):
    granted: bool

@router.post("/auth/register",status_code=201)
def register(body: Register, response: Response):
    user = {"id":secrets.token_hex(12),"email":str(body.email).lower(),"name":body.name.strip(),"password_hash":hash_password(body.password),"role":"user","status":"active","consent":False,"created_at":now()}
    try:
        db.users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(409,"Email này đã được đăng ký.")
    create_login(response,user)
    audit(user["id"],"register")
    return public(user)

@router.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    key = (request.client.host if request.client else "local") + ":" + str(body.email).lower()
    with attempt_lock:
        clock = time.monotonic()
        while attempts[key] and attempts[key][0] < clock-300:
            attempts[key].popleft()
        if len(attempts[key]) >= 10:
            raise HTTPException(429,"Thử lại sau 5 phút vì có quá nhiều lần đăng nhập.")
        attempts[key].append(clock)
        if len(attempts)>5000:
            for old in list(attempts)[:1000]:
                if old != key:
                    del attempts[old]
    user = db.users.find_one({"email":str(body.email).lower(),"status":"active"})
    if not user or not verify_password(body.password,user["password_hash"]):
        raise HTTPException(401,"Email hoặc mật khẩu không đúng.")
    with attempt_lock:
        attempts.pop(key,None)
    create_login(response,user)
    audit(user["id"],"login")
    return public(user)

@router.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("expression_session","")
    db.auth_sessions.delete_one({"token_hash":hashlib.sha256(token.encode()).hexdigest()})
    response.delete_cookie("expression_session",path="/")
    return {"ok":True}

@router.get("/users/me")
def me(user=Depends(current_user)):
    return public(user)

@router.put("/users/me")
def profile(body: Profile,user=Depends(current_user)):
    db.users.update_one({"id":user["id"]},{"$set":{"name":body.name.strip()}})
    return public(db.users.find_one({"id":user["id"]}))

@router.put("/users/me/password")
def change_password(body: PasswordChange,response: Response,user=Depends(current_user)):
    if not verify_password(body.current_password,user["password_hash"]):
        raise HTTPException(400,"Mật khẩu hiện tại không đúng.")
    db.users.update_one({"id":user["id"]},{"$set":{"password_hash":hash_password(body.new_password)}})
    db.auth_sessions.delete_many({"user_id":user["id"]})
    create_login(response,user)
    return {"ok":True}

@router.post("/consents")
def consent(body: Consent,user=Depends(current_user)):
    db.users.update_one({"id":user["id"]},{"$set":{"consent":body.granted}})
    db.consents.insert_one({"user_id":user["id"],"purpose":"facial_expression_analysis","policy_version":"1.0","granted":body.granted,"created_at":now()})
    if not body.granted:
        db.jobs.update_many({"user_id":user["id"],"status":{"$in":["QUEUED","PROCESSING"]}},{"$set":{"cancel_requested":True}})
    audit(user["id"],"consent_granted" if body.granted else "consent_withdrawn")
    return {"granted":body.granted}

@router.get("/consents")
def consents(user=Depends(current_user)):
    return public(list(db.consents.find({"user_id":user["id"]}).sort("created_at",-1).limit(50)))

@router.delete("/users/me/data")
def delete_data(user=Depends(current_user)):
    db.jobs.update_many({"user_id":user["id"]},{"$set":{"cancel_requested":True}})
    for collection in (db.sessions, db.feedback, db.jobs):
        collection.delete_many({"user_id":user["id"]})
    db.data_requests.insert_one({"user_id":user["id"],"type":"delete_analysis_data","status":"COMPLETED","created_at":now(),"resolved_at":now()})
    audit(user["id"],"delete_analysis_data")
    return {"ok":True}

@router.get("/users/me/export")
def export_data(user=Depends(current_user)):
    return public({"user":user,"sessions":list(db.sessions.find({"user_id":user["id"]})),"consents":list(db.consents.find({"user_id":user["id"]})),"feedback":list(db.feedback.find({"user_id":user["id"]}))})
