from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "expression_lab"
    data_dir: str = str(ROOT / "data")
    admin_email: str = "admin@expressionlab.com"
    admin_password: str = ""
    cookie_secure: bool = False
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173"
    retention_days: int = 30
    max_upload_mb: int = 50
    max_video_seconds: int = 180
    confidence_threshold: float = 0.60
    margin_threshold: float = 0.10

settings = Settings()
