"""Timestamp / proof-of-existence helpers.

MVP scope:
- Compute a SHA-256 of the work and write a local proof file.
- Provide a stub for OpenTimestamps (bitcoin-anchored, free, no account) that
  the user can run via the standalone `ots` CLI; we don't bundle the OTS
  dependency to keep installation lightweight.

A local proof file alone is NOT a court-grade timestamp. To make it
court-grade, anchor the hash to something the writer does not control:
- Publish the hash on a public account (microblog, fediverse, etc.) —
  the platform's own timestamp then becomes corroborating evidence.
- Run `ots stamp <proof.json>` to anchor to the Bitcoin blockchain.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Proof:
    work_id: str
    sha256: str
    char_count: int
    created_at: str
    tool_version: str
    host: str       # platform string, helps the writer remember which device made the proof

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def make_proof(text: str, work_id: str) -> Proof:
    from .. import __version__
    return Proof(
        work_id=work_id,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        char_count=len(text),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        tool_version=__version__,
        host=platform.platform(),
    )


def save_proof(proof: Proof, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{proof.work_id}.proof.json"
    target.write_text(proof.to_json(), encoding="utf-8")
    return target


def verify_proof(proof_path: str | Path, text: str) -> bool:
    """Recompute the hash of `text` and compare against the proof."""
    data = json.loads(Path(proof_path).read_text(encoding="utf-8"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest() == data["sha256"]


OTS_HINT = """\
To anchor this proof to the Bitcoin blockchain (free, no account required):

  pip install opentimestamps-client
  ots stamp {proof_path}

This produces a {proof_path}.ots file. Keep both files together. Months later
you (or anyone) can run `ots verify {proof_path}.ots` to prove the file
existed at the time of stamping.

Alternatively, post the SHA-256 below on any public timestamped channel
(microblog, fediverse) where the platform itself records the time:

    {sha}
"""


def ots_hint(proof_path: str | Path, sha: str) -> str:
    return OTS_HINT.format(proof_path=proof_path, sha=sha)
