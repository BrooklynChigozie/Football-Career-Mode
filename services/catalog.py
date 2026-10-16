"""Template database: players and clubs imported once, copied for every new career."""
from pathlib import Path

from services import database, importer, paths

KAGGLE_CSV = paths.DATA_DIR / "kaggle" / "players.csv"
SAMPLE_CSV = paths.DATA_DIR / "sample_players.csv"
TEMPLATE_DB = paths.USER_DIR / "template.db"


def source_csv() -> Path:
    """Real Kaggle data if present, otherwise the generated sample (created on first use)."""
    if KAGGLE_CSV.exists():
        return KAGGLE_CSV
    if not SAMPLE_CSV.exists():
        import sys
        sys.path.insert(0, str(paths.ROOT / "scripts"))
        import generate_sample_data
        generate_sample_data.main(SAMPLE_CSV)
    return SAMPLE_CSV


def ensure_template(template: Path | None = None, csv_path: Path | None = None, rebuild: bool = False) -> Path:
    template = Path(template or TEMPLATE_DB)
    if template.exists() and not rebuild and _template_current(template):
        return template
    template.unlink(missing_ok=True)
    conn = database.init_game_db(template)
    try:
        importer.import_players_csv(csv_path or source_csv(), conn)
    finally:
        conn.close()
    return template


def _template_current(template: Path) -> bool:
    """A template built by an older version lacks new columns and competitions: rebuild it."""
    try:
        conn = database.connect(template)
        try:
            r = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            return r is not None and int(r[0]) >= database.SCHEMA_VERSION
        finally:
            conn.close()
    except Exception:
        return False
