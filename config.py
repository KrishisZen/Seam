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
OVERALL_SCORE_CURVE = 1.5

STYLE_TAG_GROUPS = {
    "Everyday": ["Casual", "Classic", "Minimal", "Smart Casual", "Normcore", "Coastal"],
    "Tailored & Heritage": ["Business Casual", "Formal", "Preppy", "Workwear", "Vintage", "Western"],
    "Street & Sport": ["Streetwear", "Athleisure", "Sporty", "Utility", "Outdoor", "Grunge"],
    "Expressive": ["Bohemian", "Romantic", "Edgy", "Avant-garde", "Y2K", "Artisanal"],
}
STYLE_TAGS = [tag for group in STYLE_TAG_GROUPS.values() for tag in group]
