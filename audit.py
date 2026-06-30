from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import AUDIT_LOG_PATH, CONTENT_INDEX_PATH, DATA_DIR, LOG_DIR


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)


def _load_index() -> dict[str, Any]:
    _ensure_dirs()
    if not CONTENT_INDEX_PATH.exists():
        return {}
    try:
        return json.loads(CONTENT_INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Content index is not valid JSON: {exc}") from exc


def _save_index(index: dict[str, Any]) -> None:
    _ensure_dirs()
    temp_path = CONTENT_INDEX_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(index, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temp_path, CONTENT_INDEX_PATH)


def append_audit_entry(entry: dict[str, Any]) -> dict[str, Any]:
    _ensure_dirs()
    enriched = {"timestamp": utc_now(), **entry}
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched, sort_keys=True) + "\n")
    return enriched


def record_submission(content_id: str, record: dict[str, Any]) -> dict[str, Any]:
    index = _load_index()
    index[content_id] = record
    _save_index(index)
    return append_audit_entry({"event": "submission", **record})


def record_appeal(content_id: str, creator_reasoning: str) -> tuple[bool, dict[str, Any]]:
    index = _load_index()
    if content_id not in index:
        return False, {
            "error": "content_not_found",
            "message": f"No content exists for content_id {content_id}",
        }

    index[content_id]["status"] = "under_review"
    index[content_id]["appeal_reasoning"] = creator_reasoning
    _save_index(index)

    original = index[content_id]
    original_decision = {
        "attribution": original.get("attribution"),
        "confidence": original.get("confidence"),
        "ai_likelihood": original.get("ai_likelihood"),
        "label": original.get("label"),
        "signals": {
            name: {
                "score": signal.get("score"),
                "reasoning": signal.get("reasoning"),
            }
            for name, signal in original.get("signals", {}).items()
        },
    }

    entry = append_audit_entry(
        {
            "event": "appeal",
            "content_id": content_id,
            "creator_id": index[content_id].get("creator_id"),
            "status": "under_review",
            "appeal_reasoning": creator_reasoning,
            "original_decision": original_decision,
        }
    )
    return True, entry


def get_recent_audit_entries(limit: int) -> list[dict[str, Any]]:
    _ensure_dirs()
    if not Path(AUDIT_LOG_PATH).exists():
        return []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines[-limit:] if line.strip()]
    return entries
