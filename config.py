from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
CONTENT_INDEX_PATH = DATA_DIR / "content_index.json"
AUDIT_LOG_PATH = LOG_DIR / "audit_log.jsonl"

GROQ_MODEL = "llama-3.3-70b-versatile"
SUBMIT_RATE_LIMIT = "10 per minute;100 per day"
RECENT_LOG_LIMIT = 20
