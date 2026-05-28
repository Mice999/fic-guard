"""Cross-site monitoring for the writer's own signature sentences.

Design notes:
- We do NOT crawl. We hand the user the search URLs / queries and let them
  decide where to look. The MVP optionally hits well-behaved search endpoints
  (DuckDuckGo HTML, Bing) with sane rate limits and a clearly-identified UA.
- Results are written to a local report file only. Nothing is uploaded.
- This is intentionally limited: writers monitor their own content. It is
  not a tool for surveilling third parties.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import requests

from ..fingerprint import Fingerprint


USER_AGENT = "fic-guard/0.1 (+https://github.com/) self-monitoring tool"
REQUEST_TIMEOUT = 15
MIN_DELAY_SECONDS = 3.0  # between requests, regardless of provider


@dataclass
class Finding:
    sentence: str           # the signature sentence searched
    provider: str           # which search engine
    query_url: str          # the URL the user can open to verify
    snippet: str            # a short result excerpt if available
    result_url: str         # the third-party URL (if any) where text appeared


@dataclass
class MonitorReport:
    work_id: str
    generated_at: str
    findings: list[Finding]
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "work_id": self.work_id,
                "generated_at": self.generated_at,
                "findings": [asdict(f) for f in self.findings],
                "notes": self.notes,
            },
            ensure_ascii=False,
            indent=2,
        )


def _load_search_engines() -> list[dict]:
    import sys
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: --add-data lands data at MEIPASS/fic_guard/data
        base = Path(sys._MEIPASS) / "fic_guard" / "data"  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent.parent / "data"
    with open(base / "search_engines.json", encoding="utf-8") as f:
        return json.load(f)


def build_search_queries(fp: Fingerprint) -> list[tuple[str, str]]:
    """Return (sentence, search_url) tuples the user can open manually."""
    engines = _load_search_engines()
    queries: list[tuple[str, str]] = []
    for sent in fp.signature_sentences:
        q = urllib.parse.quote(f'"{sent}"')
        for engine in engines:
            url = engine["url_template"].format(query=q)
            queries.append((sent, url))
    return queries


def _search_duckduckgo_html(query: str) -> list[Finding]:
    """Best-effort hit against DuckDuckGo's HTML endpoint.

    We do not parse aggressively. If the endpoint is blocked or its layout
    changes, we degrade gracefully to "no findings", and the user can still
    open the URL manually.
    """
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(f'"{query}"')
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return []

    if resp.status_code != 200 or not resp.text:
        return []

    findings: list[Finding] = []
    # Extremely conservative parser: pull out result links by simple markers.
    # We intentionally do not depend on bs4 to keep deps light. A "miss" here
    # just means the user opens the URL manually.
    text = resp.text
    import re
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        findings.append(
            Finding(
                sentence=query,
                provider="duckduckgo",
                query_url=url,
                snippet=title[:200],
                result_url=href,
            )
        )
        if len(findings) >= 5:
            break
    return findings


def run_monitor(
    fp: Fingerprint,
    *,
    use_network: bool = False,
    delay: float = MIN_DELAY_SECONDS,
) -> MonitorReport:
    """Run a monitoring pass.

    If `use_network` is False (default), we only produce a list of search URLs
    for the user to open. If True, we additionally attempt a best-effort hit
    against DuckDuckGo's HTML endpoint with a polite delay.
    """
    from datetime import datetime, timezone

    findings: list[Finding] = []
    notes: list[str] = []

    if not fp.signature_sentences:
        notes.append(
            "No signature sentences in this fingerprint. Re-run `fic-guard fingerprint` "
            "with a longer source text or a higher --count."
        )
        return MonitorReport(
            work_id=fp.work_id,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            findings=[],
            notes=notes,
        )

    # Always include the no-network URL list — the user can open these manually.
    for sent, url in build_search_queries(fp):
        findings.append(
            Finding(
                sentence=sent,
                provider="manual-open",
                query_url=url,
                snippet="",
                result_url="",
            )
        )

    if use_network:
        notes.append(
            "Network mode is best-effort. Search engines may rate-limit or block "
            "automated queries; an empty network result does not mean the text "
            "is safe — open the query URLs manually as well."
        )
        for sent in fp.signature_sentences:
            findings.extend(_search_duckduckgo_html(sent))
            time.sleep(delay)

    return MonitorReport(
        work_id=fp.work_id,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        findings=findings,
        notes=notes,
    )


def save_report(report: MonitorReport, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{report.work_id}.monitor.json"
    target.write_text(report.to_json(), encoding="utf-8")
    return target
