from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

SQLITE_PATH = str(PROJECT_ROOT / "finance.db")
JSON_PATH = str(PROJECT_ROOT / "data.json")
