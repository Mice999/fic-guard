from __future__ import annotations

import secrets
import sys
from pathlib import Path

from flask import Flask, abort, request
from flask_wtf.csrf import CSRFProtect

_csrf = CSRFProtect()


def create_app(port: int) -> Flask:
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: --add-data lands templates at MEIPASS/fic_guard/web/templates
        base = Path(sys._MEIPASS) / "fic_guard" / "web"  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent

    app = Flask(__name__, template_folder=str(base / "templates"))
    app.secret_key = secrets.token_hex(32)
    app.config["PORT"] = port
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB upload cap

    _csrf.init_app(app)

    _allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}

    @app.before_request
    def _check_host() -> None:
        # DNS-rebinding defense: reject non-local Host headers
        if request.host not in _allowed:
            abort(403)

    from .routes import bp
    app.register_blueprint(bp)

    return app
