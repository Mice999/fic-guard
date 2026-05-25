"""Tests for timestamp and safe_publish modules."""
from __future__ import annotations

from pathlib import Path

from fic_guard.safe_publish import QUESTIONS, run_interactive, score_answers
from fic_guard.timestamp import make_proof, save_proof, verify_proof


def test_proof_roundtrip(tmp_path: Path):
    text = "hello world 你好世界"
    proof = make_proof(text, work_id="t1")
    p = save_proof(proof, tmp_path)
    assert p.exists()
    assert verify_proof(p, text) is True
    assert verify_proof(p, text + "x") is False


def test_safe_publish_all_low_risk():
    # Pick the lowest-point option for each question.
    answers = {}
    for q in QUESTIONS:
        # The option with 0 points.
        for k, _, p in q.options:
            if p == 0:
                answers[q.key] = k
                break
    result = score_answers(answers)
    assert result.score == 0
    assert result.band == "low"


def test_safe_publish_all_high_risk():
    answers = {}
    for q in QUESTIONS:
        # The option with max points.
        max_opt = max(q.options, key=lambda o: o[2])
        answers[q.key] = max_opt[0]
    result = score_answers(answers)
    assert result.score == result.max_score
    assert result.band == "high"
    assert len(result.suggestions) >= 3


def test_interactive_stub_pathway():
    # Simulate a UI by always picking the first option.
    def stub(prompt: str, options):
        return options[0][0]
    result = run_interactive(stub)
    assert result.max_score > 0
    assert isinstance(result.suggestions, list) and result.suggestions
