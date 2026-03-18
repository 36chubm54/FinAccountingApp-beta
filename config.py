from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

SQLITE_PATH = str(PROJECT_ROOT / "finance.db")
JSON_PATH = str(PROJECT_ROOT / "data.json")

# How many timestamped JSON backups to keep in `project/backups/`.
# Older backups are pruned on startup after creating a new one.
JSON_BACKUP_KEEP_LAST = 30

# Size threshold (in bytes) for considering the SQLite database "large".
# If the database file size exceeds this value, a background export may be triggered.
LAZY_EXPORT_SIZE_THRESHOLD = 50 * 1024 * 1024  # 50 MiB
