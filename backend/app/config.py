import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")
MAX_UPLOAD = min(20, max(1, int(os.getenv("MAX_UPLOAD_MB", "10")))) * 1024 * 1024
MAX_QUEUE = 8
MAX_STORAGE = 200 * 1024 * 1024
CORS = [
    s.strip()
    for s in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if s.strip()
]


def env_alias(*names, default=""):
    return next((os.environ[n] for n in names if os.environ.get(n)), default)
