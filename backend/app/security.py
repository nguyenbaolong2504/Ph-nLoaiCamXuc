import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import HTTPException, Request
from .database import db, now
from .config import settings

def hash_password(password):
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + result.hex()

def verify_password(password, stored):
    try:
        salt, expected = stored.split(":")
        result = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(result.hex(), expected)
    except (ValueError, TypeError):
        return False

def resolve_token(token):
    if not token:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    session = db.auth_sessions.find_one({"token_hash":hashlib.sha256(token.encode()).hexdigest(),"expires_at":{"$gt":now()}})
    user = db.users.find_one({"id":session["user_id"],"status":"active"}) if session else None
    if not user:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn.")
    return user

def current_user(request: Request):
    return resolve_token(request.cookies.get("expression_session"))

def require_role(user, *roles):
    if user["role"] not in roles and user["role"] != "admin":
        raise HTTPException(403, "Bạn không có quyền thực hiện chức năng này.")

def create_login(response, user):
    token = secrets.token_urlsafe(32)
    db.auth_sessions.insert_one({"token_hash":hashlib.sha256(token.encode()).hexdigest(),"user_id":user["id"],"expires_at":now()+timedelta(days=7)})
    response.set_cookie("expression_session", token, httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=7*86400, path="/")

def require_consent(user):
    if not user.get("consent", False):
        raise HTTPException(403, "Bạn cần đồng ý xử lý hình ảnh trước khi phân tích.")
