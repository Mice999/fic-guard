"""Tests for fingerprint module."""
from __future__ import annotations

from fic_guard.fingerprint import (
    embed_watermark,
    extract_watermark,
    generate_fingerprint,
    pick_signature_sentences,
    strip_watermark,
)


SAMPLE_CN = (
    "他站在窗边，夕阳把屋子染成了一种近乎温柔的橙色。"
    "她在屋子的另一端，没有抬头，只是说：你回来了。"
    "桌上的茶已经凉了，杯壁上挂着一圈细细的水痕，像被时间忘在那里的指纹。"
    "外面的猫又叫了一声，他想起小时候在外婆家见过的一只灰色的猫。"
    "屋子里没有别人。他走过去，在她身边坐下，没有说话。"
    "电视里在播一个旧得发黄的纪录片，主持人的声音在房间里像水一样漫开。"
    "她终于抬起头，看着他，眼里有一种他从未见过的疲惫，又像是某种释然。"
)


def test_signature_sentences_are_picked():
    sigs = pick_signature_sentences(SAMPLE_CN, k=3, seed=42)
    assert len(sigs) == 3
    for s in sigs:
        assert len(s) >= 12
        assert s in SAMPLE_CN.replace("\n", "") or any(s in p for p in SAMPLE_CN.split("。"))


def test_signature_sentences_deterministic_with_seed():
    a = pick_signature_sentences(SAMPLE_CN, k=3, seed=7)
    b = pick_signature_sentences(SAMPLE_CN, k=3, seed=7)
    assert a == b


def test_generate_fingerprint_roundtrip():
    fp = generate_fingerprint(SAMPLE_CN, work_id="t", k=4, seed=1)
    j = fp.to_json()
    from fic_guard.fingerprint import Fingerprint
    fp2 = Fingerprint.from_json(j)
    assert fp == fp2
    assert len(fp.sha256) == 64


def test_watermark_roundtrip():
    wm = embed_watermark(SAMPLE_CN, "site-A", every_n_chars=50)
    # Visible content (after stripping) is unchanged.
    assert strip_watermark(wm) == SAMPLE_CN
    # Payload extractable.
    payloads = extract_watermark(wm)
    assert "site-A" in payloads


def test_watermark_survives_partial_copy():
    # Embed every 30 chars; take a middle slice; payload should still appear.
    wm = embed_watermark(SAMPLE_CN, "tag", every_n_chars=30)
    slice_ = wm[40:200]
    payloads = extract_watermark(slice_)
    assert "tag" in payloads


def test_strip_is_idempotent():
    wm = embed_watermark(SAMPLE_CN, "x")
    once = strip_watermark(wm)
    twice = strip_watermark(once)
    assert once == twice == SAMPLE_CN


def test_empty_text_does_not_crash():
    assert pick_signature_sentences("", k=3) == []
    fp = generate_fingerprint("", work_id="empty", k=3)
    assert fp.signature_sentences == []
    assert fp.char_count == 0
