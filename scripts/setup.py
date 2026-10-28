"""Create local credentials without replacing an existing .env."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
path = root/".env"
if not path.exists():
    path.write_text("MONGO_URI=mongodb://127.0.0.1:27017\nMONGO_DB=expression_lab\nMONGO_PASSWORD="+secrets.token_hex(24)+"\nADMIN_EMAIL=admin@expressionlab.com\nADMIN_PASSWORD="+secrets.token_urlsafe(18)+"\nAPP_PORT=8010\n",encoding="utf-8")
    print("Da tao .env. Tai khoan quan tri duoc ghi trong .env; khong chia se file nay.")
else:
    print("Giu nguyen cau hinh .env hien co.")
