"""
Text normalization and a lightweight, dependency-free language guess.

A full statistical language-detection library (e.g. langdetect) was tried
and dropped -- it failed to build in this environment (a setuptools/legacy
packaging issue unrelated to this project) and pulling in a native-build
dependency for a "nice to have" field wasn't worth the fragility. Wealthsimple's
audience is overwhelmingly English/French (Canada), so a small stopword-count
heuristic covers the realistic cases; anything else is honestly labeled
"unknown" rather than guessed.
"""

from __future__ import annotations

import html
import re

_EN_STOPWORDS = {
    "the", "and", "is", "to", "of", "in", "it", "for", "on", "with",
    "this", "that", "was", "have", "my", "i", "you", "not", "but", "are",
}
_FR_STOPWORDS = {
    "le", "la", "les", "et", "est", "de", "un", "une", "je", "pas",
    "avec", "pour", "que", "ce", "mon", "ma", "tres", "très", "mais", "vous",
}

_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ']+")


def clean_text(raw_text: str) -> str:
    """Normalize text for downstream comparison/display: decode HTML
    entities, collapse whitespace, strip leading/trailing space. Never
    mutates the original comment_text -- callers store this separately as
    cleaned_text."""
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def guess_language(text: str) -> str:
    """Return 'en', 'fr', or 'unknown'. A best-effort heuristic, not a
    verified classification -- do not treat this as ground truth."""
    words = {w.lower() for w in _WORD_RE.findall(text)}
    if not words:
        return "unknown"
    en_hits = len(words & _EN_STOPWORDS)
    fr_hits = len(words & _FR_STOPWORDS)
    if en_hits == 0 and fr_hits == 0:
        return "unknown"
    return "en" if en_hits >= fr_hits else "fr"


def normalize_for_dedup(text: str) -> str:
    """Aggressive normalization used ONLY for duplicate comparison -- lowercase,
    strip punctuation, collapse whitespace. Never used for display."""
    text = clean_text(text).lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()
