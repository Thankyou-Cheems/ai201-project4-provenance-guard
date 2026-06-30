# Provenance Guard

Project 4 for AI201. This is a Flask backend for classifying submitted creative text as likely AI-generated, likely human-written, or uncertain. It uses two independent detection signals, returns a confidence score and transparency label, supports appeals, rate-limits submissions, and writes a structured audit log.

## Setup

```powershell
uv venv --python 3.11
uv pip install -r requirements.txt
D:\Dev\AI201\_shared\link-global-env.ps1
uv run python app.py
```

The app runs on `http://127.0.0.1:5000`.

## Architecture Overview

Submissions enter through `POST /submit`, where the API validates `text` and `creator_id`, runs the Groq LLM signal, runs the stylometric signal, combines both scores into an AI-likelihood score, maps the result to a transparency label, writes a structured audit entry, and returns JSON with a `content_id`. Appeals enter through `POST /appeal`, where the original decision is looked up, status changes to `under_review`, and a second structured audit entry records the appeal reasoning.

## Detection Signals

Signal 1 is a Groq LLM classification using `llama-3.3-70b-versatile`. It captures semantic coherence, tone, and model-visible authorship clues. It can miss polished human writing, non-native English patterns, or lightly edited AI text.

Signal 2 is a stylometric heuristic signal. It measures sentence length uniformity, type-token ratio, punctuation density, and personal voice markers. It is independent from the LLM because it uses measurable structure instead of semantic judgment. It can misread formal human writing or short creative fragments.

## Confidence Scoring

The system calculates:

```text
ai_likelihood = (0.75 * llm_score) + (0.25 * stylometric_score)
```

Thresholds:

```text
ai_likelihood >= 0.70 -> likely_ai
ai_likelihood <= 0.30 -> likely_human
otherwise             -> uncertain
```

The API response includes both `ai_likelihood` and `confidence`. For human-attributed results, confidence is `1 - ai_likelihood`; for AI-attributed results, confidence is `ai_likelihood`; uncertain results are capped near the ambiguous middle so they do not sound more certain than the label really is.

I validated the scoring with four deliberately different inputs:

| Input type | Expected behavior | Actual score |
| --- | --- | --- |
| Polished generic AI-style paragraph | High AI likelihood | `likely_ai`, AI likelihood `0.817`, confidence `0.817` |
| Casual personal restaurant note | Lower AI likelihood | `likely_human`, AI likelihood `0.191`, confidence `0.809` |
| Formal academic paragraph | Borderline because polished human writing can look AI-like | `uncertain`, AI likelihood `0.661`, confidence `0.580` |
| Lightly edited AI-style paragraph | Borderline because personal framing softens the signal | `uncertain`, AI likelihood `0.336`, confidence `0.582` |

Signal details from the same run:

| Case | Groq LLM score | Stylometric score | Final attribution |
| --- | ---: | ---: | --- |
| Polished generic AI-style paragraph | `0.800` | `0.867` | `likely_ai` |
| Casual personal restaurant note | `0.200` | `0.162` | `likely_human` |
| Formal academic paragraph | `0.700` | `0.543` | `uncertain` |
| Lightly edited AI-style paragraph | `0.300` | `0.444` | `uncertain` |

## Transparency Labels

| Variant | Exact label text |
| --- | --- |
| High-confidence AI | "High-confidence AI attribution: this text shows multiple signals consistent with AI-generated writing. Readers should treat the authorship claim as unverified." |
| High-confidence human | "High-confidence human attribution: this text shows multiple signals consistent with human-written work. Readers should still treat this as an automated assessment." |
| Uncertain | "Uncertain attribution: the system does not have enough confidence to label this as AI-generated or human-written. The creator may provide more context or appeal." |

## API Usage

Submit content:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/submit `
  -ContentType 'application/json' `
  -Body '{"text":"The sun dipped below the horizon, painting the sky in amber light.","creator_id":"test-user-1"}'
```

Appeal a decision:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/appeal `
  -ContentType 'application/json' `
  -Body '{"content_id":"PASTE-CONTENT-ID-HERE","creator_reasoning":"I wrote this myself from personal experience."}'
```

Inspect the audit log:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/log
```

## Rate Limiting

`POST /submit` is limited to `10 per minute;100 per day` per remote address. The minute limit prevents script flooding during testing, while the daily limit is still high enough for a single creator trying several drafts. Local development uses Flask-Limiter's `memory://` storage, so limits reset when the server restarts.

Rate-limit evidence from a rapid local test of 12 `POST /submit` calls:

```text
[200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429, 429]
```

## Audit Log

The app writes JSON Lines to `logs/audit_log.jsonl` and stores the latest content status in `data/content_index.json`. Each submission captures timestamp, content ID, creator ID, attribution, confidence, both signal scores, label text, and status. Each appeal captures timestamp, content ID, creator ID, status, appeal reasoning, and original decision context.

Sample audit entries from a real run:

```json
[
  {
    "event": "submission",
    "content_id": "667145e8-ac49-436c-b204-f0301d7265c8",
    "creator_id": "ai-demo-user",
    "attribution": "likely_ai",
    "confidence": 0.817,
    "ai_likelihood": 0.817,
    "status": "classified",
    "signals": {
      "groq_llm": {"score": 0.8},
      "stylometric": {"score": 0.867}
    }
  },
  {
    "event": "submission",
    "content_id": "9c69195f-d3fd-4de9-866c-d765a1b301a9",
    "creator_id": "human-demo-user",
    "attribution": "likely_human",
    "confidence": 0.809,
    "ai_likelihood": 0.191,
    "status": "classified",
    "signals": {
      "groq_llm": {"score": 0.2},
      "stylometric": {"score": 0.162}
    }
  },
  {
    "event": "appeal",
    "content_id": "d9b7433c-240c-43cb-bae8-c6ee481bf9fb",
    "creator_id": "formal-demo-user",
    "status": "under_review",
    "appeal_reasoning": "I wrote this in a formal academic style, so I want a human review before readers see a final attribution label.",
    "original_decision": {
      "attribution": "uncertain",
      "confidence": 0.58,
      "ai_likelihood": 0.661,
      "signals": {
        "groq_llm": {"score": 0.7},
        "stylometric": {"score": 0.543}
      }
    }
  }
]
```

## Known Limitations

Formal human writing may be misclassified as AI-generated because both the LLM and the stylometric signal can interpret uniform sentence structure and polished vocabulary as AI-like. Short poems or fragments are also risky because there may not be enough text for stable stylometric metrics, so the implementation treats very short text as neutral evidence instead of forcing a strong classification.

## Spec Reflection

The spec helped by forcing the API contract, scoring thresholds, label text, and appeal behavior to be written before implementation. My implementation diverged from the first scoring draft after real testing: the original weighting made an obviously AI-style sample land too close to `uncertain`, so I shifted the weighted score toward the LLM signal while keeping the stylometric signal as an independent check. I also changed uncertain confidence so borderline results do not sound falsely definitive.

## AI Usage

1. I used an AI assistant to turn the Week 4 requirements into a concrete file layout, API surface, and implementation checklist. I revised the result to keep the project aligned with my existing AI201 `uv` workflow and the course requirement to create my own repo.
2. I used an AI assistant to review the first implementation for demo readiness. Based on that review, I tightened short-text handling, enriched appeal audit entries with original signal evidence, and adjusted uncertain confidence so borderline results do not sound more definitive than they are.
