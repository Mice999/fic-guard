"""Common utilities."""
from __future__ import annotations

import re
from pathlib import Path


def read_text(path: str | Path) -> str:
    """Read a UTF-8 text file, tolerating BOM."""
    p = Path(path)
    return p.read_text(encoding="utf-8-sig")


# Split text into sentences. We deliberately keep this simple and language-agnostic:
# Chinese full-width punctuation and ASCII punctuation are both treated as boundaries.
_SENT_BOUNDARY = re.compile(r"(?<=[。！？!?\.])\s*")


def split_sentences(text: str) -> list[str]:
    """Split text into a list of non-empty, stripped sentences."""
    # Normalize whitespace within paragraphs but preserve sentence boundaries.
    parts = _SENT_BOUNDARY.split(text)
    return [s.strip() for s in parts if s and s.strip()]


def normalize_for_match(text: str) -> str:
    """Normalize a sentence for fuzzy matching: collapse whitespace, strip quotes."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"'""''「」『』")
    return text
