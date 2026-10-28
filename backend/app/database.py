from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from .config import settings

client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
db = client[settings.mongo_db]

def now():
    return datetime.now(timezone.utc)

def initialize():
    client.admin.command("ping")
    db.users.create_index("email", unique=True)
    db.auth_sessions.create_index("token_hash", unique=True)
    db.auth_sessions.create_index("expires_at", expireAfterSeconds=0)
    db.sessions.create_index([("user_id", ASCENDING), ("created_at", -1)])
    db.sessions.create_index("expires_at", expireAfterSeconds=0)
    db.jobs.create_index("expires_at", expireAfterSeconds=0)
    db.feedback.create_index("expires_at", expireAfterSeconds=0)
    db.consents.create_index([("user_id", 1), ("created_at", -1)])
    db.model_versions.create_index("id", unique=True)
    db.model_versions.update_one({"id":"opencv-mobilefacenet-v1"}, {"$setOnInsert":{
        "id":"opencv-mobilefacenet-v1", "name":"MobileFaceNet · Progressive Teacher", "version":"2022july",
        "engine":"opencv", "path":"expression.onnx", "status":"approved", "metrics":None,
        "source":"https://github.com/opencv/opencv_zoo/tree/main/models/facial_expression_recognition",
        "note":"Mô hình pretrained để chạy ngay. Chưa đánh giá trên tập test của đồ án.", "created_at":now(),
    }}, upsert=True)
    db.system.update_one({"_id":"active_model"}, {"$setOnInsert":{"model_id":"opencv-mobilefacenet-v1"}}, upsert=True)
    # A single-process local worker cannot resume partially processed jobs after restart.
    db.jobs.update_many({"status":{"$in":["QUEUED","PROCESSING"]}}, {"$set":{"status":"FAILED","error":"Máy chủ đã khởi động lại; hãy tải video lại."}})
    db.training_runs.update_many({"status":{"$in":["QUEUED","PROCESSING"]}}, {"$set":{"status":"FAILED","error":"Máy chủ khởi động lại; tạo run mới để tiếp tục."}})

def public(document):
    if document is None:
        return None
    if isinstance(document, list):
        return [public(x) for x in document]
    if isinstance(document, dict):
        return {k: public(v) for k,v in document.items() if k != "_id" and k != "password_hash" and k != "token_hash"}
    if isinstance(document, datetime):
        return document.isoformat()
    return document

def audit(actor, action, resource=""):
    db.audit_logs.insert_one({"actor_id":actor, "action":action, "resource":resource, "created_at":now()})
