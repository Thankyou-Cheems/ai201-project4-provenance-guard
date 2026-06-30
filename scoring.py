from __future__ import annotations


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def combine_signal_scores(llm_score: float, stylometric_score: float) -> dict:
    """Return attribution fields from two independent AI-likelihood signals."""
    ai_likelihood = clamp((0.75 * llm_score) + (0.25 * stylometric_score))

    if ai_likelihood >= 0.70:
        attribution = "likely_ai"
        confidence = ai_likelihood
    elif ai_likelihood <= 0.30:
        attribution = "likely_human"
        confidence = 1.0 - ai_likelihood
    else:
        attribution = "uncertain"
        confidence = 0.5 + (abs(ai_likelihood - 0.5) * 0.5)

    return {
        "ai_likelihood": round(ai_likelihood, 3),
        "attribution": attribution,
        "confidence": round(confidence, 3),
    }
