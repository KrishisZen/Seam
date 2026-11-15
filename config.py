"""Application configuration for SEAM."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "seam.sqlite3"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
MAX_CONTENT_LENGTH = 80 * 1024 * 1024
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
SECRET_KEY = "change-this-local-development-key"
SCORING_WEIGHTS = {
    "color": 0.30,
    "style": 0.25,
    "silhouette": 0.20,
    "completeness": 0.15,
    "balance": 0.10,
}
