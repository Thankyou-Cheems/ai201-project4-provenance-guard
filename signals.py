from __future__ import annotations

import json
import math
import os
import re
from typing import Any

from groq import Groq

from config import GROQ_MODEL
from scoring import clamp


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def run_llm_signal(text: str) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "name": "groq_llm",
            "score": 0.5,
            "attribution": "uncertain",
            "reasoning": "GROQ_API_KEY is missing, so the LLM signal returned neutral.",
            "error": "missing_api_key",
        }

    client = Groq(api_key=api_key)
    prompt = (
        "Classify whether the submitted creative text is more likely AI-generated "
        "or human-written. Return only JSON with keys ai_probability, attribution, "
        "and reasoning. ai_probability must be a number from 0 to 1 where 1 means "
        "very likely AI-generated. attribution must be one of likely_ai, "
        "likely_human, uncertain."
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.0,
            max_tokens=250,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = _extract_json(content)
        score = clamp(float(parsed.get("ai_probability", 0.5)))
        attribution = parsed.get("attribution") or _attribution_from_score(score)
        return {
            "name": "groq_llm",
            "score": round(score, 3),
            "attribution": attribution,
            "reasoning": str(parsed.get("reasoning", "")).strip(),
        }
    except Exception as exc:  # Keep the API usable while surfacing provider failure.
        return {
            "name": "groq_llm",
            "score": 0.5,
            "attribution": "uncertain",
            "reasoning": "Groq signal failed; neutral score used.",
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_stylometric_signal(text: str) -> dict[str, Any]:
    words = re.findall(r"[A-Za-z']+", text.lower())
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[.!?]+", text)
        if sentence.strip()
    ]
    word_count = len(words)
    sentence_lengths = [
        len(re.findall(r"[A-Za-z']+", sentence))
        for sentence in sentences
        if sentence.strip()
    ]

    if word_count == 0:
        return {
            "name": "stylometric",
            "score": 0.5,
            "reasoning": "No words were available for stylometric analysis.",
            "metrics": {},
        }

    if word_count < 30:
        return {
            "name": "stylometric",
            "score": 0.5,
            "reasoning": (
                "Text is shorter than 30 words, so stylometric evidence is too sparse "
                "and the signal returns a neutral score."
            ),
            "metrics": {
                "word_count": word_count,
                "sentence_count": len(sentence_lengths),
                "short_text_guard": True,
            },
        }

    type_token_ratio = len(set(words)) / word_count
    avg_sentence_length = sum(sentence_lengths) / max(len(sentence_lengths), 1)
    variance = (
        sum((length - avg_sentence_length) ** 2 for length in sentence_lengths)
        / max(len(sentence_lengths), 1)
    )
    sentence_stdev = math.sqrt(variance)
    punctuation_density = len(re.findall(r"[,;:!?]", text)) / max(word_count, 1)
    first_person_density = len(re.findall(r"\b(i|me|my|mine|we|our|us)\b", text.lower())) / word_count
    casual_markers = len(re.findall(r"\b(ok|honestly|like|kinda|maybe|probably|lol|ugh)\b", text.lower()))

    uniformity_score = 1.0 - clamp(sentence_stdev / 14.0)
    vocabulary_score = 1.0 - clamp((type_token_ratio - 0.35) / 0.35)
    punctuation_score = 1.0 - clamp(punctuation_density / 0.12)
    personal_voice_penalty = clamp((first_person_density * 8.0) + (casual_markers * 0.08))

    generic_phrase_count = len(
        re.findall(
            r"\b(it is important to note|furthermore|moreover|in conclusion|stakeholders|responsible deployment|transformative)\b",
            text.lower(),
        )
    )

    ai_score = clamp(
        (0.40 * uniformity_score)
        + (0.30 * vocabulary_score)
        + (0.20 * punctuation_score)
        + 0.10
        + (generic_phrase_count * 0.08)
        - (0.35 * personal_voice_penalty)
    )

    metrics = {
        "word_count": word_count,
        "sentence_count": len(sentence_lengths),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "sentence_length_stdev": round(sentence_stdev, 2),
        "type_token_ratio": round(type_token_ratio, 3),
        "punctuation_density": round(punctuation_density, 3),
        "first_person_density": round(first_person_density, 3),
        "casual_marker_count": casual_markers,
        "generic_phrase_count": generic_phrase_count,
    }

    return {
        "name": "stylometric",
        "score": round(ai_score, 3),
        "reasoning": (
            "Score combines sentence uniformity, vocabulary diversity, punctuation "
            "density, and personal voice markers."
        ),
        "metrics": metrics,
    }


def _attribution_from_score(score: float) -> str:
    if score >= 0.70:
        return "likely_ai"
    if score <= 0.30:
        return "likely_human"
    return "uncertain"
