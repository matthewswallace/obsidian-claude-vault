"""
Shared config loader for vault scripts.

Loads .claude/vault.json (vault-specific, gitignored) and exposes typed accessors.
If vault.json is missing, falls back to vault.example.json with a warning.
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional


def find_vault_root(start: Optional[Path] = None) -> Path:
    """Walk up from start (default: this file) until we find .claude/."""
    p = (start or Path(__file__)).resolve()
    while p != p.parent:
        if (p / ".claude").is_dir():
            return p
        p = p.parent
    raise RuntimeError("Could not locate vault root (no .claude/ found in any ancestor).")


def load_config(vault_root: Optional[Path] = None) -> dict:
    root = vault_root or find_vault_root()
    real = root / ".claude/vault.json"
    example = root / ".claude/vault.example.json"
    if real.exists():
        return json.loads(real.read_text())
    if example.exists():
        print(f"WARNING: {real} not found. Using {example}. Copy and customize.", file=sys.stderr)
        return json.loads(example.read_text())
    raise RuntimeError(f"No vault config at {real} or {example}.")


def isolation_regex(cfg: dict) -> Optional[re.Pattern]:
    """Compile the isolation entity's keyword regex, or None if not configured."""
    patterns = (cfg.get("isolation") or {}).get("patterns") or []
    if not patterns:
        return None
    return re.compile("|".join(rf"\b{p}\b" for p in patterns), re.I)


def overlap_regex(cfg: dict) -> Optional[re.Pattern]:
    """Compile the isolation-overlap context regex (e.g. client where isolation entity is mentioned legitimately)."""
    overlap = (cfg.get("isolation") or {}).get("overlap_with") or {}
    patterns = overlap.get("context_patterns") or []
    if not patterns:
        return None
    return re.compile("|".join(rf"\b{p}\b" for p in patterns), re.I)


def project_keywords(cfg: dict) -> dict:
    """Return project_keywords dict, excluding internal _comment entries."""
    pk = cfg.get("project_keywords") or {}
    return {k: v for k, v in pk.items() if not k.startswith("_") and isinstance(v, list)}


def folder(cfg: dict, key: str, default: str = "") -> str:
    return (cfg.get("folders") or {}).get(key, default)
