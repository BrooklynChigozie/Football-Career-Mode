"""Filesystem locations used by the platform services."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
USER_DIR = ROOT / "userdata"          # app.db and save files live here (git-ignored)
APP_DB = USER_DIR / "app.db"
SAVES_DIR = USER_DIR / "saves"
