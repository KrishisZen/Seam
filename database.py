"""Small SQLite helpers and schema for SEAM."""
import sqlite3
from contextlib import contextmanager
from config import DATABASE_PATH


def connect():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


@contextmanager
def get_db():
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS garments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL CHECK(length(trim(name)) > 0),
            category TEXT NOT NULL CHECK(category IN ('Tops','Bottoms','Outerwear','Footwear','Accessories')),
            color TEXT NOT NULL DEFAULT '', material TEXT NOT NULL DEFAULT '',
            fit TEXT NOT NULL DEFAULT '', style_tags TEXT NOT NULL DEFAULT '',
            image_path TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
            palette TEXT NOT NULL DEFAULT '', brightness REAL, saturation REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS outfits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL CHECK(length(trim(name)) > 0),
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS outfit_garments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outfit_id INTEGER NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
            garment_id INTEGER NOT NULL REFERENCES garments(id) ON DELETE CASCADE,
            UNIQUE(outfit_id, garment_id)
        );
        CREATE TABLE IF NOT EXISTS outfit_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            outfit_id INTEGER NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
            color_score REAL NOT NULL, style_score REAL NOT NULL,
            silhouette_score REAL NOT NULL, completeness_score REAL NOT NULL,
            balance_score REAL NOT NULL, overall_score REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def rows(query, params=()):
    with get_db() as db:
        return db.execute(query, params).fetchall()


def row(query, params=()):
    with get_db() as db:
        return db.execute(query, params).fetchone()
