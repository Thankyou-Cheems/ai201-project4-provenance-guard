from __future__ import annotations

from uuid import uuid4

import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audit import get_recent_audit_entries, record_appeal, record_submission
from config import RECENT_LOG_LIMIT, SUBMIT_RATE_LIMIT
from labels import label_for_attribution
from scoring import combine_signal_scores
from signals import run_llm_signal, run_stylometric_signal

load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "provenance_guard",
            "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        }
    )


@app.post("/submit")
@limiter.limit(SUBMIT_RATE_LIMIT)
def submit():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    creator_id = str(payload.get("creator_id", "")).strip()

    if not text or not creator_id:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "message": "Both text and creator_id are required.",
                }
            ),
            400,
        )

    content_id = str(uuid4())
    llm_signal = run_llm_signal(text)
    stylometric_signal = run_stylometric_signal(text)
    scoring = combine_signal_scores(
        float(llm_signal["score"]),
        float(stylometric_signal["score"]),
    )
    label = label_for_attribution(scoring["attribution"])

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "status": "classified",
        "attribution": scoring["attribution"],
        "confidence": scoring["confidence"],
        "ai_likelihood": scoring["ai_likelihood"],
        "label": label,
        "signals": {
            "groq_llm": llm_signal,
            "stylometric": stylometric_signal,
        },
    }
    record_submission(content_id, record)
    return jsonify(record)


@app.post("/appeal")
def appeal():
    payload = request.get_json(silent=True) or {}
    content_id = str(payload.get("content_id", "")).strip()
    creator_reasoning = str(payload.get("creator_reasoning", "")).strip()

    if not content_id or not creator_reasoning:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "message": "Both content_id and creator_reasoning are required.",
                }
            ),
            400,
        )

    found, entry = record_appeal(content_id, creator_reasoning)
    if not found:
        return jsonify(entry), 404
    return jsonify({"message": "Appeal received.", "appeal": entry})


@app.get("/log")
def log():
    raw_limit = request.args.get("limit", RECENT_LOG_LIMIT)
    try:
        limit = max(1, min(int(raw_limit), 100))
    except (TypeError, ValueError):
        limit = RECENT_LOG_LIMIT
    return jsonify({"entries": get_recent_audit_entries(limit)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
