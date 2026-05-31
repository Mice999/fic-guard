from __future__ import annotations

import io
import re

from flask import Blueprint, abort, redirect, render_template, request, send_file, url_for

from ..fingerprint import Fingerprint, embed_watermark, generate_fingerprint
from ..monitor import run_monitor
from ..safe_publish import QUESTIONS, score_answers
from ..timestamp import make_proof

bp = Blueprint("main", __name__)

_WORK_ID_RE = re.compile(r"^[\w\-\.]{1,100}$")


def _read_text() -> str | None:
    """Return text from file upload, falling back to pasted textarea."""
    f = request.files.get("text_file")
    if f and f.filename:
        try:
            return f.read().decode("utf-8")
        except UnicodeDecodeError:
            return None
    paste = (request.form.get("text_paste") or "").strip()
    return paste or None


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/fingerprint", methods=["GET", "POST"])
def fingerprint():
    if request.method == "POST":
        text = _read_text()
        work_id = (request.form.get("work_id") or "").strip()
        if not text:
            return render_template("fingerprint.html", error="请上传文件或粘贴文本内容。")
        if not _WORK_ID_RE.match(work_id):
            return render_template(
                "fingerprint.html",
                error="作品 ID 只能包含字母、数字、连字符、下划线或点，且不能为空。",
            )
        fp = generate_fingerprint(text, work_id=work_id)
        if not fp.signature_sentences:
            return render_template(
                "fingerprint.html",
                error="文本内容太短，无法提取签名句。请粘贴 200 字以上的内容（建议粘贴完整章节）。",
            )
        return send_file(
            io.BytesIO(fp.to_json().encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"{work_id}.fingerprint.json",
        )
    return render_template("fingerprint.html")


@bp.route("/timestamp", methods=["GET", "POST"])
def timestamp():
    if request.method == "POST":
        text = _read_text()
        work_id = (request.form.get("work_id") or "").strip()
        if not text:
            return render_template("timestamp.html", error="请上传文件或粘贴文本内容。")
        if not _WORK_ID_RE.match(work_id):
            return render_template(
                "timestamp.html",
                error="作品 ID 只能包含字母、数字、连字符、下划线或点，且不能为空。",
            )
        proof = make_proof(text, work_id=work_id)
        return send_file(
            io.BytesIO(proof.to_json().encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"{work_id}.proof.json",
        )
    return render_template("timestamp.html")


@bp.route("/watermark", methods=["GET", "POST"])
def watermark():
    if request.method == "POST":
        text = _read_text()
        payload = (request.form.get("payload") or "").strip()
        try:
            every = max(50, int(request.form.get("every") or 200))
        except ValueError:
            every = 200
        if not text:
            return render_template("watermark.html", error="请上传文件或粘贴文本内容。")
        if not payload:
            return render_template("watermark.html", error="请填写水印 payload。")
        out = embed_watermark(text, payload, every_n_chars=every)
        return send_file(
            io.BytesIO(out.encode("utf-8")),
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name="watermarked.txt",
        )
    return render_template("watermark.html")


@bp.route("/safe-publish", methods=["GET", "POST"])
def safe_publish():
    result = None
    answers: dict[str, str] = {}
    if request.method == "POST":
        answers = {q.key: (request.form.get(q.key) or "") for q in QUESTIONS}
        if any(not v for v in answers.values()):
            return render_template(
                "safe_publish.html",
                questions=QUESTIONS,
                error="请回答所有问题。",
                answers=answers,
            )
        result = score_answers(answers)
    return render_template("safe_publish.html", questions=QUESTIONS, result=result, answers=answers)


@bp.route("/watermark/extract", methods=["GET", "POST"])
def watermark_extract():
    if request.method == "POST":
        text = _read_text()
        if not text:
            return render_template("watermark_extract.html", error="请上传文件或粘贴文本内容。")
        from ..fingerprint import extract_watermark
        payloads = extract_watermark(text)
        seen = []
        for p in payloads:
            if p not in seen:
                seen.append(p)
        return render_template("watermark_extract.html", payloads=seen)
    return render_template("watermark_extract.html")


@bp.route("/monitor", methods=["GET", "POST"])
def monitor():
    if request.method == "POST":
        f = request.files.get("fingerprint_file")
        if not f or not f.filename:
            return render_template("monitor.html", error="请上传指纹 JSON 文件。")
        try:
            fp = Fingerprint.from_json(f.read().decode("utf-8"))
        except Exception:
            return render_template(
                "monitor.html",
                error="无法解析指纹文件，请确认是 fic-guard 生成的 .fingerprint.json 文件。",
            )
        report = run_monitor(fp, use_network=False)
        report.notes = [
            "指纹中没有签名句，请重新生成指纹时粘贴更多内容（建议完整章节，200 字以上）。"
            if "No signature sentences" in n else n
            for n in report.notes
        ]
        urls = [
            fi for fi in report.findings
            if fi.provider == "manual-open"
            and fi.query_url.startswith(("https://", "http://"))
        ]
        return render_template("monitor.html", report=report, urls=urls)
    return render_template("monitor.html")


# ── Library ──────────────────────────────────────────────────────────────────

from ..library import (  # noqa: E402
    add_finding as _lib_add_finding,
    add_work,
    dashboard_stats,
    get_work,
    list_findings,
    list_works,
    update_finding_status,
    update_last_checked,
)


@bp.route("/library")
def library():
    stats = dashboard_stats()
    works = list_works()
    return render_template("library.html", stats=stats, works=works)


@bp.route("/library/add", methods=["GET", "POST"])
def library_add():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        f = request.files.get("fingerprint_file")
        if not title:
            return render_template("library_add.html", error="请填写作品标题。")
        if not f or not f.filename:
            return render_template("library_add.html", error="请上传指纹文件。")
        try:
            fp_json = f.read().decode("utf-8")
            fp = Fingerprint.from_json(fp_json)
        except Exception:
            return render_template(
                "library_add.html",
                error="无法解析指纹文件，请确认是 fic-guard 生成的 .fingerprint.json 文件。",
            )
        add_work(title=title, work_id=fp.work_id, fingerprint_json=fp_json, notes=notes)
        return redirect(url_for("main.library"))
    return render_template("library_add.html")


@bp.route("/library/<int:work_id>")
def library_detail(work_id: int):
    work = get_work(work_id)
    if work is None:
        abort(404)
    findings = list_findings(work_id)
    return render_template("library_detail.html", work=work, findings=findings)


@bp.route("/library/<int:work_id>/check", methods=["POST"])
def library_check(work_id: int):
    work = get_work(work_id)
    if work is None:
        abort(404)
    try:
        fp = Fingerprint.from_json(work.fingerprint_json)
    except Exception:
        abort(400)
    report = run_monitor(fp, use_network=False)
    for fi in report.findings:
        _lib_add_finding(
            work_id=work_id,
            sentence=fi.sentence,
            provider=fi.provider,
            query_url=fi.query_url,
            snippet=fi.snippet,
            result_url=fi.result_url,
        )
    update_last_checked(work_id)
    return redirect(url_for("main.library_detail", work_id=work_id))


@bp.route("/library/findings/<int:finding_id>/status", methods=["POST"])
def library_finding_status(finding_id: int):
    status = (request.form.get("status") or "").strip()
    try:
        update_finding_status(finding_id, status)
    except ValueError:
        abort(400)
    return redirect(request.referrer or url_for("main.library"))
