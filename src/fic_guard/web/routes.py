from __future__ import annotations

import io
import re

from flask import Blueprint, render_template, request, send_file

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
