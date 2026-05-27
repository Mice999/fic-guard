"""fic-guard command-line interface."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .common import read_text
from .fingerprint import (
    embed_watermark,
    extract_watermark,
    generate_fingerprint,
    load_fingerprint,
    save_fingerprint,
    strip_watermark,
)
from .monitor import run_monitor, save_report
from .safe_publish import QUESTIONS, run_interactive, score_answers
from .timestamp import make_proof, ots_hint, save_proof, verify_proof

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

console = Console()


@click.group()
@click.version_option(__version__, prog_name="fic-guard")
def main() -> None:
    """fic-guard: a self-protection toolkit for fiction writers.

    All operations are local-first. No data is uploaded anywhere.
    """


# ---------- fingerprint ----------

@main.group()
def fingerprint() -> None:
    """Generate and inspect work fingerprints."""


@fingerprint.command("make")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--work-id", required=True, help="Identifier you choose for this work (e.g. 'my-fic-ch1').")
@click.option("-k", "--count", default=5, show_default=True, help="Number of signature sentences to pick.")
@click.option("--seed", type=int, default=None, help="Optional deterministic seed for reproducible sampling.")
@click.option("-o", "--out-dir", default=".fic-guard", show_default=True, help="Where to write the fingerprint file.")
def fingerprint_make(source: str, work_id: str, count: int, seed: int | None, out_dir: str) -> None:
    """Generate a fingerprint for a text file."""
    text = read_text(source)
    fp = generate_fingerprint(text, work_id=work_id, k=count, seed=seed)
    path = save_fingerprint(fp, out_dir)
    console.print(Panel.fit(
        f"[bold green]Fingerprint saved[/]\n"
        f"file:    {path}\n"
        f"work_id: {fp.work_id}\n"
        f"sha256:  {fp.sha256}\n"
        f"chars:   {fp.char_count}\n"
        f"sigs:    {len(fp.signature_sentences)}",
        title="fingerprint make",
    ))


@fingerprint.command("show")
@click.argument("fingerprint_file", type=click.Path(exists=True, dir_okay=False))
def fingerprint_show(fingerprint_file: str) -> None:
    """Print a saved fingerprint nicely."""
    fp = load_fingerprint(fingerprint_file)
    table = Table(title=f"fingerprint: {fp.work_id}", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("signature sentence")
    for i, s in enumerate(fp.signature_sentences, 1):
        table.add_row(str(i), s)
    console.print(table)
    console.print(f"[dim]sha256:[/] {fp.sha256}")
    console.print(f"[dim]created:[/] {fp.created_at}")


@fingerprint.command("watermark")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--payload", required=True, help="Short string to embed invisibly (e.g. a per-platform tag).")
@click.option("-o", "--output", required=True, type=click.Path(dir_okay=False), help="Where to write the watermarked text.")
@click.option("--every", default=200, show_default=True, help="Embed the payload roughly every N characters.")
def fingerprint_watermark(source: str, payload: str, output: str, every: int) -> None:
    """Embed an invisible (zero-width) watermark into a text file."""
    text = read_text(source)
    out = embed_watermark(text, payload, every_n_chars=every)
    Path(output).write_text(out, encoding="utf-8")
    console.print(f"[green]Watermarked text written to[/] {output}")
    console.print(
        "[dim]Note: zero-width watermarks survive plain copy-paste but can be stripped "
        "by a motivated attacker. Use them together with signature sentences and timestamp proofs.[/]"
    )


@fingerprint.command("extract")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
def fingerprint_extract(source: str) -> None:
    """Try to extract zero-width watermark payloads from a text file."""
    text = read_text(source)
    found = extract_watermark(text)
    if not found:
        console.print("[yellow]No watermark found.[/]")
        sys.exit(1)
    # Deduplicate while preserving order.
    seen = []
    for f in found:
        if f not in seen:
            seen.append(f)
    console.print("[green]Watermark payload(s) found:[/]")
    for f in seen:
        console.print(f"  • {f!r}")


@fingerprint.command("strip")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", required=True, type=click.Path(dir_okay=False))
def fingerprint_strip(source: str, output: str) -> None:
    """Remove zero-width watermark characters from a text file."""
    text = read_text(source)
    Path(output).write_text(strip_watermark(text), encoding="utf-8")
    console.print(f"[green]Stripped text written to[/] {output}")


# ---------- timestamp ----------

@main.group()
def timestamp() -> None:
    """Create and verify local proofs of existence."""


@timestamp.command("make")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--work-id", required=True)
@click.option("-o", "--out-dir", default=".fic-guard", show_default=True)
def timestamp_make(source: str, work_id: str, out_dir: str) -> None:
    """Create a SHA-256 proof file for the given text."""
    text = read_text(source)
    proof = make_proof(text, work_id=work_id)
    path = save_proof(proof, out_dir)
    console.print(Panel.fit(
        f"[bold green]Proof saved[/]\n"
        f"file:    {path}\n"
        f"sha256:  {proof.sha256}\n"
        f"chars:   {proof.char_count}\n"
        f"created: {proof.created_at}",
        title="timestamp make",
    ))
    console.print(Panel(ots_hint(path, proof.sha256), title="next steps (optional)", border_style="dim"))


@timestamp.command("verify")
@click.argument("proof_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
def timestamp_verify(proof_file: str, source: str) -> None:
    """Verify that a text file still matches a previously-saved proof."""
    text = read_text(source)
    ok = verify_proof(proof_file, text)
    if ok:
        console.print("[bold green]MATCH[/]: the file is byte-identical to the one proofed.")
    else:
        console.print("[bold red]MISMATCH[/]: the file has been modified since the proof was made.")
        sys.exit(1)


# ---------- monitor ----------

@main.command()
@click.argument("fingerprint_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--network/--no-network", default=False, help="Attempt best-effort search via DuckDuckGo HTML.")
@click.option("-o", "--out-dir", default=".fic-guard", show_default=True)
def monitor(fingerprint_file: str, network: bool, out_dir: str) -> None:
    """Generate search URLs (and optionally hit them) for a fingerprint."""
    fp = load_fingerprint(fingerprint_file)
    report = run_monitor(fp, use_network=network)
    path = save_report(report, out_dir)
    console.print(f"[green]Monitor report written to[/] {path}")
    if report.findings:
        manual = [f for f in report.findings if f.provider == "manual-open"]
        if manual:
            console.print(f"\n[bold]Open these URLs manually to check:[/]")
            for f in manual[:10]:
                console.print(f"  [dim]({f.sentence[:30]}...)[/] {f.query_url}")
            if len(manual) > 10:
                console.print(f"  [dim]... and {len(manual) - 10} more in the report file.[/]")
    for note in report.notes:
        console.print(f"[yellow]note:[/] {note}")


# ---------- safe-publish ----------

@main.command("safe-publish")
def safe_publish_cmd() -> None:
    """Interactive pre-publish safety checklist (offline)."""
    console.print(Panel(
        "回答几个问题，帮你评估发布前的暴露风险。\n"
        "[dim]这是一个本地、不联网的清单，答案不会保存到任何地方。[/]",
        title="safe-publish",
    ))

    def prompt_fn(prompt: str, options: list[tuple[str, str]]) -> str:
        console.print(f"\n[bold]{prompt}[/]")
        for i, (_, label) in enumerate(options, 1):
            console.print(f"  {i}. {label}")
        while True:
            raw = Prompt.ask("选择", default="1")
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return options[idx][0]
            except ValueError:
                pass
            console.print("[red]请输入有效的数字。[/]")

    result = run_interactive(prompt_fn)
    color = {"low": "green", "moderate": "yellow", "high": "red"}[result.band]
    console.print(Panel(
        f"暴露风险评级：[bold {color}]{result.band}[/]  ({result.score}/{result.max_score})",
        title="结果",
    ))
    console.print("[bold]建议：[/]")
    for s in result.suggestions:
        console.print(f"  • {s}")


# ---------- guide ----------

@main.command()
def guide() -> None:
    """Print the quickstart guide."""
    console.print(Panel(
        "1) [bold]fingerprint[/] 你的作品：\n"
        "   fic-guard fingerprint make ./mywork.txt --work-id mywork-ch1\n\n"
        "2) [bold]timestamp[/] 存证：\n"
        "   fic-guard timestamp make ./mywork.txt --work-id mywork-ch1\n\n"
        "3) [bold]watermark[/]（可选）在发布到不同平台时各嵌入一个不同的标签：\n"
        "   fic-guard fingerprint watermark ./mywork.txt --payload site-A --output mywork.site-A.txt\n\n"
        "4) 定期 [bold]monitor[/] 检查作品是否在别处出现：\n"
        "   fic-guard monitor .fic-guard/mywork-ch1.fingerprint.json\n\n"
        "5) 发布前跑一遍 [bold]safe-publish[/] 自检：\n"
        "   fic-guard safe-publish",
        title="quickstart",
    ))


# ---------- web ----------

@main.command()
@click.option("--port", type=int, default=8765, show_default=True, help="Port to listen on.")
@click.option("--no-browser", is_flag=True, help="Do not open browser automatically.")
def web(port: int, no_browser: bool) -> None:
    """Launch a local web UI at http://127.0.0.1:<port>."""
    import threading

    from waitress import serve

    from .web import create_app

    app = create_app(port)
    url = f"http://127.0.0.1:{port}"
    console.print(Panel.fit(
        f"[green]fic-guard web[/] 运行中\n"
        f"地址：[bold]{url}[/]\n"
        f"按 [bold]Ctrl+C[/] 退出",
        title="web",
    ))
    if not no_browser:
        def _open():
            import time, sys
            time.sleep(1.5)
            try:
                if sys.platform == "win32":
                    os.startfile(url)
                else:
                    import webbrowser
                    webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    serve(app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":  # pragma: no cover
    main()
