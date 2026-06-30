# Provenance Guard Planning

## Architecture

```text
Submission flow
POST /submit
  -> validate JSON: text, creator_id
  -> Groq LLM signal: semantic authorship assessment
  -> stylometric signal: structural writing metrics
  -> confidence scoring: weighted AI-likelihood score
  -> transparency label: exact reader-facing label text
  -> audit log: structured submission event
  -> JSON response with content_id, attribution, confidence, label

Appeal flow
POST /appeal
  -> validate JSON: content_id, creator_reasoning
  -> find original content decision
  -> update status to under_review
  -> audit log: structured appeal event with original decision context
  -> JSON confirmation
```

The submission path keeps the two detection signals independent until the scoring layer combines them. The appeal path does not reclassify content automatically; it preserves the original decision, captures the creator's reasoning, and marks the content for human review.

## Detection Signals

Signal 1 is a Groq-hosted LLM classification using `llama-3.3-70b-versatile`. It captures semantic and stylistic coherence at a high level and returns an AI-likelihood score from 0 to 1 plus a short reason. Its blind spot is that LLM judgments can be overconfident and may penalize polished human writing.

Signal 2 is a stylometric heuristic function. It measures sentence length uniformity, vocabulary diversity, punctuation density, and personal voice markers. Its blind spot is that formal human writing can look uniform, while edited AI output can include enough casual markers to look human.

The scoring layer combines the signals as:

```text
ai_likelihood = (0.75 * llm_score) + (0.25 * stylometric_score)
```

The LLM receives more weight because it can inspect meaning and coherence, while the heuristic signal provides independent structural evidence that can pull overconfident model judgments back toward uncertainty.

## Uncertainty Representation

The system treats `ai_likelihood` as a calibrated estimate from 0 to 1, where 1 means very likely AI-generated and 0 means very likely human-written.

```text
ai_likelihood >= 0.70 -> likely_ai
ai_likelihood <= 0.30 -> likely_human
otherwise             -> uncertain
```

The response also includes `confidence`. For `likely_ai`, confidence is the AI likelihood. For `likely_human`, confidence is one minus the AI likelihood. For `uncertain`, confidence is intentionally capped near the middle: a 0.51 AI-likelihood result gets about 0.50 confidence, while a near-threshold uncertain result gets about 0.60. That keeps uncertain results from sounding falsely definitive.

## Transparency Label Design

| Variant | Exact label text |
| --- | --- |
| High-confidence AI | "High-confidence AI attribution: this text shows multiple signals consistent with AI-generated writing. Readers should treat the authorship claim as unverified." |
| High-confidence human | "High-confidence human attribution: this text shows multiple signals consistent with human-written work. Readers should still treat this as an automated assessment." |
| Uncertain | "Uncertain attribution: the system does not have enough confidence to label this as AI-generated or human-written. The creator may provide more context or appeal." |

## Appeals Workflow

Any creator can appeal a classification by calling `POST /appeal` with `content_id` and `creator_reasoning`. The system looks up the original decision, updates the content status to `under_review`, and appends an appeal event to the audit log with the creator's reasoning and a compact original decision object. A human reviewer would see the content ID, creator ID, original attribution, confidence, AI likelihood, label, individual signal scores, signal reasoning, and appeal reasoning.

## Anticipated Edge Cases

1. Formal human essays may look AI-generated because they have uniform sentence structure and polished vocabulary.
2. Short poems or fragments may not provide enough words for reliable stylometric metrics.
3. Lightly edited AI text with personal anecdotes may look human to the heuristic signal.
4. Non-native English writing may have repeated phrasing that the model or heuristics could misread as AI-like.

## API Surface

### POST /submit

Request:

```json
{
  "text": "Creative text to classify.",
  "creator_id": "creator-123"
}
```

Response:

```json
{
  "content_id": "...",
  "creator_id": "creator-123",
  "attribution": "likely_ai | likely_human | uncertain",
  "confidence": 0.82,
  "ai_likelihood": 0.82,
  "label": "...",
  "signals": {
    "groq_llm": {"score": 0.8},
    "stylometric": {"score": 0.6}
  },
  "status": "classified"
}
```

### POST /appeal

Request:

```json
{
  "content_id": "...",
  "creator_reasoning": "I wrote this myself from personal experience."
}
```

### GET /log

Returns recent structured audit log entries.

## AI Tool Plan

### M3: Submission endpoint and first signal

Provide the architecture section, API surface, and LLM signal description. Ask the AI tool to review the Flask route, the Groq prompt, and the audit-log shape. Verify by submitting one request and checking that `content_id`, attribution, confidence, and an audit event are returned.

### M4: Second signal and confidence scoring

Provide the detection signals and uncertainty representation sections. Ask the AI tool to review the stylometric metrics and the weighted scoring thresholds. Verify with four inputs: clearly AI, clearly human, formal human, and lightly edited AI.

### M5: Production layer

Provide the label text and appeals workflow sections. Ask the AI tool to review `POST /appeal`, `GET /log`, and the rate-limit configuration. Verify all three label variants are reachable, one appeal changes status to `under_review`, and rate limiting returns HTTP 429 after repeated submissions.
