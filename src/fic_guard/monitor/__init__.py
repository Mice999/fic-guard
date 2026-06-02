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
import re
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

_DEFAULT_SERPER_KEY = "1283abcce70a885a0ab75f4f872e24b968851d43"


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


def _decode_bing_redirect(href: str) -> str:
    """Extract the real destination URL from a Bing /ck/a redirect href.

    Bing encodes the target as  u=a1<base64url>  in the redirect query string.
    Returns the original href unchanged if decoding fails.
    """
    import base64, html as _html
    clean = _html.unescape(href)
    m = re.search(r'[?&]u=(a1[A-Za-z0-9+/\-_]+)', clean)
    if not m:
        return href
    raw = m.group(1)[2:]  # strip leading 'a1'
    padded = raw + "=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception:
        return href


def _search_bing_html(query: str) -> list[Finding]:
    """Best-effort hit against Bing's HTML search endpoint.

    DuckDuckGo /html/ now returns a bot-challenge page (status 202) instead of
    results, so we switched to Bing. Degrades gracefully to an empty list on
    any parse failure or network error.
    """
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(f'"{query}"')
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
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for li in soup.select("li.b_algo")[:5]:
            a = li.select_one("h2 a")
            if not a:
                continue
            href = a.get("href", "")
            result_url = _decode_bing_redirect(href) if "bing.com/ck/a" in href else href
            if not result_url.startswith(("http://", "https://")):
                continue
            p = li.select_one("p")
            snippet = p.get_text(strip=True)[:200] if p else ""
            title = a.get_text(strip=True)[:200]
            findings.append(
                Finding(
                    sentence=query,
                    provider="bing",
                    query_url=url,
                    snippet=snippet or title,
                    result_url=result_url,
                )
            )
    except Exception:
        # bs4 unavailable or parse error — fall back to regex
        for m in re.finditer(
            r'<li[^>]+class="b_algo"[^>]*>.*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        ):
            result_url = _decode_bing_redirect(m.group(1))
            if not result_url.startswith(("http://", "https://")):
                continue
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()[:200]
            findings.append(
                Finding(
                    sentence=query,
                    provider="bing",
                    query_url=url,
                    snippet=title,
                    result_url=result_url,
                )
            )
            if len(findings) >= 5:
                break

    return findings


def _search_serper(query: str, api_key: str) -> list[Finding]:
    """Hit the Serper Google Search API (https://serper.dev).

    Requires a valid API key. Returns up to 10 organic results as Findings.
    Degrades gracefully to an empty list on any error.
    """
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": f'"{query}"', "num": 10},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return []

    if resp.status_code != 200:
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    query_url = "https://www.google.com/search?q=" + urllib.parse.quote(f'"{query}"')
    findings: list[Finding] = []
    for item in data.get("organic", []):
        link = item.get("link", "")
        if not link.startswith(("http://", "https://")):
            continue
        snippet = (item.get("snippet") or item.get("title") or "")[:200]
        findings.append(
            Finding(
                sentence=query,
                provider="serper",
                query_url=query_url,
                snippet=snippet,
                result_url=link,
            )
        )
    return findings


def run_monitor(
    fp: Fingerprint,
    *,
    use_network: bool = False,
    delay: float = MIN_DELAY_SECONDS,
    serper_api_key: str | None = None,
) -> MonitorReport:
    """Run a monitoring pass.

    If `use_network` is False (default), only produce manual search URLs.
    If True, search via Serper (Google) when `serper_api_key` is provided,
    otherwise fall back to best-effort Bing HTML scraping.
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
        effective_key = serper_api_key or _DEFAULT_SERPER_KEY
        if effective_key:
            notes.append(
                "使用 Serper (Google) API 搜索，结果为 Google 实时索引。"
                "空结果不代表安全，建议同时手动打开链接核查。"
            )
        else:
            notes.append(
                "Network mode is best-effort. Search engines may rate-limit or block "
                "automated queries; an empty network result does not mean the text "
                "is safe — open the query URLs manually as well."
            )
        for sent in fp.signature_sentences:
            if effective_key:
                findings.extend(_search_serper(sent, effective_key))
            else:
                findings.extend(_search_bing_html(sent))
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
