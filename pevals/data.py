"""Versioned dataset: a small help center corpus plus dev and held out question splits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SPLITS = ("dev", "heldout")


def version_dir(version: str = "v1") -> Path:
    return DATA / version


def corpus(version: str = "v1") -> dict[str, str]:
    """doc_id -> full text."""
    return {p.stem: p.read_text() for p in sorted((version_dir(version) / "corpus").glob("*.md"))}


def sentences(version: str = "v1") -> list[tuple[str, str]]:
    """(doc_id, sentence) for every non heading line."""
    out = []
    for doc_id, text in corpus(version).items():
        out += [(doc_id, line.strip()) for line in text.splitlines() if line.strip() and not line.startswith("#")]
    return out


def questions(split: str, version: str = "v1") -> list[dict]:
    if split not in SPLITS:
        raise SystemExit(f"Unknown split '{split}'. Use dev or heldout.")
    path = version_dir(version) / f"{split}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _files(version: str) -> list[Path]:
    d = version_dir(version)
    return sorted([*(d / "corpus").glob("*.md"), d / "dev.jsonl", d / "heldout.jsonl"])


def fingerprint(version: str = "v1") -> dict[str, str]:
    d = version_dir(version)
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in _files(version)}


def dataset_sha(version: str = "v1") -> str:
    return hashlib.sha256(json.dumps(fingerprint(version), sort_keys=True).encode()).hexdigest()[:12]


def check_manifest(version: str = "v1") -> list[str]:
    """Files that changed since MANIFEST.json was written. A changed dataset needs a new version."""
    manifest = json.loads((version_dir(version) / "MANIFEST.json").read_text())
    now = fingerprint(version)
    return sorted(k for k in set(now) | set(manifest["files"]) if now.get(k) != manifest["files"].get(k))
