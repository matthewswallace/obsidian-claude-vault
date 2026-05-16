#!/usr/bin/env python3
"""
Inbox triage harness — Claude is the classifier; this script is plumbing.

Two commands:

    list <folder>                        Emit JSON array of candidates with
                                         {path, size, mtime, fm, preview} so
                                         Claude can batch-read and decide.

    apply <decisions.jsonl> [--dry]      Execute routing decisions:
                                         move/rename files, merge frontmatter
                                         (tags/project/related/status), log
                                         every change to _meta/triage.log
                                         (JSONL, reversible).

Decision JSONL schema (one line per file):

    {"src": "rel/path.md",
     "dst": "new/rel/path.md"      # optional — omit/null to keep in place
     "delete": false,              # optional — only for true noise
     "tags": ["tag1"],             # merged with existing
     "project": "banyan",          # set/overwrite
     "related": ["[[Other]]"],     # appended; dedup
     "status": "active",           # set/overwrite
     "note": "free text reasoning" # logged, not written to file
    }

Reversibility: every line of _meta/triage.log records src/dst/sha so reversal
is `mv dst src` plus body restoration if frontmatter changed (sha stored).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

VAULT = Path(__file__).resolve().parents[2]
LOG = VAULT / "_meta" / "triage.log"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
VANT4GE_KEYWORDS = re.compile(r"\bvant4ge|vantage|vantage point\b", re.IGNORECASE)
PREVIEW_CHARS = 400


def log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    try:
        fm = yaml.safe_load(raw) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def write_frontmatter(fm: dict, body: str) -> str:
    if not fm:
        return body
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip()
    return f"---\n{dumped}\n---\n{body}"


def merge_fm(existing: dict, decision: dict) -> dict:
    fm = dict(existing)
    tags = list(fm.get("tags") or [])
    if isinstance(tags, str):
        tags = [tags]
    for t in decision.get("tags") or []:
        if t not in tags:
            tags.append(t)
    if tags:
        fm["tags"] = tags

    related = list(fm.get("related") or [])
    if isinstance(related, str):
        related = [related]
    for r in decision.get("related") or []:
        if r not in related:
            related.append(r)
    if related:
        fm["related"] = related

    for key in ("project", "status"):
        if key in decision and decision[key] is not None:
            fm[key] = decision[key]

    fm.pop("status", None) if decision.get("status") == "" else None
    return fm


def cmd_list(folder: Path) -> int:
    if not folder.exists():
        print(f"folder not found: {folder}", file=sys.stderr)
        return 1
    out = []
    for f in sorted(folder.rglob("*.md")):
        if any(part.startswith(".") for part in f.parts):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            out.append({"path": str(f.relative_to(VAULT)), "error": str(e)})
            continue
        fm, body = read_frontmatter(text)
        preview = body.strip()[:PREVIEW_CHARS].replace("\n", " ")
        out.append({
            "path": str(f.relative_to(VAULT)),
            "size": f.stat().st_size,
            "mtime": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(),
            "fm": fm,
            "preview": preview,
            "vant4ge_flag": bool(VANT4GE_KEYWORDS.search(text)),
        })
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_apply(decisions_path: Path, dry: bool) -> int:
    if not decisions_path.exists():
        print(f"decisions file not found: {decisions_path}", file=sys.stderr)
        return 1

    run_ts = datetime.now(timezone.utc).isoformat()
    if not dry:
        log({"action": "run_start", "ts": run_ts, "decisions_file": str(decisions_path.relative_to(VAULT))})

    summary = {"moved": 0, "kept": 0, "deleted": 0, "errors": 0, "vant4ge_blocked": 0}

    with decisions_path.open(encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"line {line_num}: bad JSON: {e}", file=sys.stderr)
                summary["errors"] += 1
                continue

            src_rel = d.get("src")
            if not src_rel:
                print(f"line {line_num}: missing src", file=sys.stderr)
                summary["errors"] += 1
                continue
            src = VAULT / src_rel
            if not src.exists():
                print(f"line {line_num}: src missing: {src_rel}", file=sys.stderr)
                summary["errors"] += 1
                continue

            text = src.read_text(encoding="utf-8")
            old_sha = sha(text)

            if VANT4GE_KEYWORDS.search(text) and not d.get("vant4ge_ack"):
                print(f"line {line_num}: VANT4GE keyword in {src_rel} — add 'vant4ge_ack: true' to decision to override")
                summary["vant4ge_blocked"] += 1
                continue

            if d.get("delete"):
                entry = {"action": "delete", "ts": run_ts, "src": src_rel, "sha": old_sha, "note": d.get("note", "")}
                if not dry:
                    src.unlink()
                    log(entry)
                else:
                    print(f"[dry] DELETE {src_rel}")
                summary["deleted"] += 1
                continue

            fm, body = read_frontmatter(text)
            new_fm = merge_fm(fm, d)
            new_text = write_frontmatter(new_fm, body) if new_fm else text

            dst_rel = d.get("dst")
            if dst_rel and dst_rel != src_rel:
                dst = VAULT / dst_rel
                if dst.exists():
                    print(f"line {line_num}: dst exists, skipping: {dst_rel}", file=sys.stderr)
                    summary["errors"] += 1
                    continue
                entry = {"action": "move", "ts": run_ts, "src": src_rel, "dst": dst_rel,
                         "old_sha": old_sha, "new_sha": sha(new_text), "tags": d.get("tags"),
                         "project": d.get("project"), "related": d.get("related"), "note": d.get("note", "")}
                if not dry:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_text(new_text, encoding="utf-8")
                    src.unlink()
                    log(entry)
                else:
                    print(f"[dry] MOVE {src_rel} -> {dst_rel}")
                summary["moved"] += 1
            else:
                if new_text == text:
                    summary["kept"] += 1
                    continue
                entry = {"action": "kept_with_fm", "ts": run_ts, "src": src_rel,
                         "old_sha": old_sha, "new_sha": sha(new_text), "tags": d.get("tags"),
                         "project": d.get("project"), "related": d.get("related"), "note": d.get("note", "")}
                if not dry:
                    src.write_text(new_text, encoding="utf-8")
                    log(entry)
                else:
                    print(f"[dry] KEEP+FM {src_rel}")
                summary["kept"] += 1

    if not dry:
        log({"action": "run_end", "ts": run_ts, "summary": summary})
    print(f"\nSummary: {summary}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("folder")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("decisions")
    p_apply.add_argument("--dry", action="store_true")

    args = ap.parse_args()

    if args.cmd == "list":
        folder = VAULT / args.folder if not Path(args.folder).is_absolute() else Path(args.folder)
        sys.exit(cmd_list(folder))
    elif args.cmd == "apply":
        decisions = VAULT / args.decisions if not Path(args.decisions).is_absolute() else Path(args.decisions)
        sys.exit(cmd_apply(decisions, args.dry))


if __name__ == "__main__":
    main()
