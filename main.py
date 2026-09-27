import sys
from pathlib import Path

# Add backend directory to path so imports work seamlessly from root
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: F401, E402
