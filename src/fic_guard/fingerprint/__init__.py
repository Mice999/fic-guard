"""Text fingerprinting and zero-width watermarking.

Two complementary techniques:

1. **Signature sentences**: pick sentences from the work that have high
   identifying value (long enough to be unique, short enough to be searchable,
   not generic dialogue). These can later be searched on third-party sites.

2. **Zero-width watermark**: insert invisible characters that encode a short
   payload (e.g. a per-platform tag). If the text is copy-pasted verbatim,
   the watermark survives. Stripping it is trivial for a motivated attacker,
   but it catches lazy scrapers — which is most of them.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from ..common import normalize_for_match, split_sentences


# Zero-width characters used to encode bits.
ZW_ZERO = "\u200b"  # ZERO WIDTH SPACE   -> bit 0
ZW_ONE = "\u200c"   # ZERO WIDTH NON-JOINER -> bit 1
ZW_DELIM = "\u200d"  # ZERO WIDTH JOINER  -> start/end delimiter


@dataclass
class Fingerprint:
    """A fingerprint package for one work."""
    work_id: str            # user-chosen identifier
    sha256: str             # hash of the original (un-watermarked) text
    char_count: int
    signature_sentences: list[str]
    created_at: str         # ISO 8601 timestamp

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Fingerprint":
        return cls(**json.loads(s))


def _sentence_score(sentence: str) -> float:
    """Heuristic: prefer sentences that are uniquely searchable.

    Higher score = better signature candidate.
    """
    s = sentence.strip()
    n = len(s)
    # Length sweet spot: 15-40 chars for Chinese, 40-120 for English-ish.
    # We approximate by counting CJK chars vs ASCII.
    cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    if cjk > n / 2:
        # CJK-heavy
        if n < 12 or n > 60:
            return 0.0
        ideal = 1.0 - abs(n - 30) / 30
    else:
        if n < 30 or n > 150:
            return 0.0
        ideal = 1.0 - abs(n - 80) / 80

    # Penalize sentences that are mostly dialogue marks or punctuation.
    alnum_ratio = sum(1 for c in s if c.isalnum() or "\u4e00" <= c <= "\u9fff") / max(n, 1)
    if alnum_ratio < 0.5:
        return 0.0

    # Penalize very common-feeling sentences (heuristic: too few unique chars).
    uniq_ratio = len(set(s)) / max(n, 1)
    if uniq_ratio < 0.3:
        return 0.0

    return ideal * uniq_ratio


def pick_signature_sentences(text: str, k: int = 5, seed: int | None = None) -> list[str]:
    """Pick k sentences from the text suitable as search signatures.

    Sampling is deterministic when a seed is given, so a writer can re-generate
    the same fingerprint later.
    """
    sentences = split_sentences(text)
    scored = [(s, _sentence_score(s)) for s in sentences]
    scored = [(s, sc) for s, sc in scored if sc > 0]
    if not scored:
        return []
    # Sort by score, then take top 3k candidates and randomly sample k of them.
    scored.sort(key=lambda x: x[1], reverse=True)
    pool = [s for s, _ in scored[: max(k * 3, k)]]
    rng = random.Random(seed if seed is not None else 0)
    rng.shuffle(pool)
    return [normalize_for_match(s) for s in pool[:k]]


def generate_fingerprint(
    text: str,
    work_id: str,
    *,
    k: int = 5,
    seed: int | None = None,
) -> Fingerprint:
    """Produce a Fingerprint for a given work."""
    from datetime import datetime, timezone

    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sigs = pick_signature_sentences(text, k=k, seed=seed)
    return Fingerprint(
        work_id=work_id,
        sha256=sha,
        char_count=len(text),
        signature_sentences=sigs,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ---------- Zero-width watermark ----------

def _encode_bits(payload: str) -> str:
    """Encode a UTF-8 payload as a zero-width bitstring with delimiters."""
    bits = "".join(f"{b:08b}" for b in payload.encode("utf-8"))
    zw = "".join(ZW_ONE if b == "1" else ZW_ZERO for b in bits)
    return ZW_DELIM + zw + ZW_DELIM


def _decode_bits(zw_segment: str) -> str:
    """Decode a zero-width segment (without delimiters) back to a UTF-8 payload."""
    bits = "".join("1" if c == ZW_ONE else "0" for c in zw_segment if c in (ZW_ZERO, ZW_ONE))
    # Trim to a multiple of 8.
    bits = bits[: len(bits) - len(bits) % 8]
    by = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return by.decode("utf-8", errors="replace")


def embed_watermark(text: str, payload: str, *, every_n_chars: int = 200) -> str:
    """Embed a zero-width watermark into text.

    The payload is repeated roughly every `every_n_chars` characters so that
    even partial scrapes retain it.
    """
    encoded = _encode_bits(payload)
    if not text:
        return encoded
    out: list[str] = []
    for i, ch in enumerate(text):
        out.append(ch)
        if i > 0 and i % every_n_chars == 0:
            out.append(encoded)
    out.append(encoded)
    return "".join(out)


def extract_watermark(text: str) -> list[str]:
    """Extract all watermark payloads found in the text. May return duplicates.

    First we try the strict, delimiter-bounded form. If that yields nothing,
    we fall back to scanning every maximal run of ZW_ZERO/ZW_ONE characters
    so that watermarks survive a copy that lost their delimiters.
    """
    findings: list[str] = []

    # Strict pass: split on delimiters.
    parts = text.split(ZW_DELIM)
    for i in range(1, len(parts), 2):
        seg = parts[i]
        if not seg:
            continue
        if all(c in (ZW_ZERO, ZW_ONE) for c in seg):
            try:
                findings.append(_decode_bits(seg))
            except Exception:
                continue

    if findings:
        return findings

    # Lenient pass: scan for any maximal run of ZW_ZERO/ZW_ONE.
    run: list[str] = []
    runs: list[str] = []
    for ch in text:
        if ch in (ZW_ZERO, ZW_ONE):
            run.append(ch)
        else:
            if run:
                runs.append("".join(run))
                run = []
    if run:
        runs.append("".join(run))

    for seg in runs:
        # Need at least one byte's worth of bits.
        if len(seg) < 8:
            continue
        try:
            decoded = _decode_bits(seg)
        except Exception:
            continue
        # Filter out garbage: require the decoded string to be mostly printable.
        if decoded and sum(1 for c in decoded if c.isprintable()) >= max(1, len(decoded) // 2):
            findings.append(decoded)
    return findings


def strip_watermark(text: str) -> str:
    """Remove all zero-width characters used by this tool from text."""
    for ch in (ZW_ZERO, ZW_ONE, ZW_DELIM):
        text = text.replace(ch, "")
    return text


def save_fingerprint(fp: Fingerprint, out_dir: str | Path) -> Path:
    """Save a fingerprint as JSON into out_dir/<work_id>.fingerprint.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{fp.work_id}.fingerprint.json"
    target.write_text(fp.to_json(), encoding="utf-8")
    return target


def load_fingerprint(path: str | Path) -> Fingerprint:
    return Fingerprint.from_json(Path(path).read_text(encoding="utf-8"))
