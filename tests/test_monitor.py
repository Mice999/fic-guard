"""Tests for monitor.match_score."""
from __future__ import annotations

from fic_guard.monitor import match_score


SIGNATURE = "她终于抬起头，看着他，眼里有一种他从未见过的疲惫，又像是某种释然。"


def test_identical_sentence_scores_one():
    assert match_score(SIGNATURE, SIGNATURE) == 1.0


def test_snippet_containing_fragment_scores_one():
    snippet = "网友投稿：她终于抬起头，看着他，眼里有一种他从未见过的疲惫，又像是某种释然，看哭了好多人。"
    assert match_score(SIGNATURE, snippet) == 1.0


def test_unrelated_sentence_scores_low():
    unrelated = "今天的天气不错，适合出门散步，路上的风很凉爽，心情也变好了。"
    assert match_score(SIGNATURE, unrelated) < 0.2
