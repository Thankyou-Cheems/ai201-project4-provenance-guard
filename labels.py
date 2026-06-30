LABEL_TEXT = {
    "likely_ai": (
        "High-confidence AI attribution: this text shows multiple signals consistent "
        "with AI-generated writing. Readers should treat the authorship claim as unverified."
    ),
    "likely_human": (
        "High-confidence human attribution: this text shows multiple signals consistent "
        "with human-written work. Readers should still treat this as an automated assessment."
    ),
    "uncertain": (
        "Uncertain attribution: the system does not have enough confidence to label this "
        "as AI-generated or human-written. The creator may provide more context or appeal."
    ),
}


def label_for_attribution(attribution: str) -> str:
    return LABEL_TEXT.get(attribution, LABEL_TEXT["uncertain"])
