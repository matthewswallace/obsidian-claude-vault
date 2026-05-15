#!/usr/bin/env python3
"""
Theme miner for triage buckets.

Reads triage_buckets from .claude/vault.json (list of folder paths relative to vault root).
Outputs {meta}/triage-themes.md with:
- File count per bucket
- Top tags, projects (from frontmatter)
- Filename hygiene flags (UUID/hash/emoji artifacts)
- Suggested moves (theme clusters)
- Suggested renames

Read-only. Does not move or rename anything.
"""
import re
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_config import load_config, find_vault_root, folder

_cfg = load_config()
VAULT = find_vault_root()
META = VAULT / folder(_cfg, "meta", "_meta")

# Triage buckets configured per-vault. Fall back to empty.
BUCKETS = [VAULT / p for p in (_cfg.get("triage_buckets") or [])]
REPORT = META / "triage-themes.md"

UUID_RE = re.compile(r"[0-9a-f]{32}|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
HEX_TAIL_RE = re.compile(r"[\s_-]+[0-9a-f]{6,}$", re.I)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# Keyword clusters → suggested target folder (relative to vault root)
# CLUSTERS map keyword → target folder. Loaded from .claude/vault.json under "triage_clusters".
# Fallback to a minimal generic set if not configured.
import sys
sys.path.insert(0, str(Path(__file__).parent))
try:
    from vault_config import load_config
    _cfg = load_config()
    CLUSTERS = _cfg.get("triage_clusters") or {}
except Exception:
    CLUSTERS = {}

# Minimal generic fallback if vault.json doesn't define triage_clusters
if not CLUSTERS:
    CLUSTERS = {
        "recipe": "recipes",
        "ingredient": "recipes",
        "song": "music",
        "setlist": "music",
        "lyric": "music",
        "travel": "travel",
        "flight": "travel",
        "budget": "finances",
        "tax": "finances",
        "book": "reading-list",
        "article": "reading-list",
        "resume": "career",
        "interview": "career",
        "idea": "ideas",
        "essay": "writing",
        "blog": "writing",
    }


def parse_frontmatter(text):
    m = FRONTMATTER_RE.search(text)
    if not m:
        return {}
    fm_text = m.group(1)
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def has_filename_issues(name):
    issues = []
    stem = Path(name).stem
    if UUID_RE.search(stem):
        issues.append("uuid")
    if HEX_TAIL_RE.search(stem):
        issues.append("hex-tail")
    if EMOJI_RE.search(stem):
        issues.append("emoji")
    if len(stem) > 60:
        issues.append(f"long({len(stem)})")
    if stem.count("-") > 4 or stem.count("_") > 4:
        issues.append("punct-heavy")
    return issues


def suggest_filename(stem):
    """Strip artifacts, return cleaned stem."""
    s = stem
    s = UUID_RE.sub("", s)
    s = HEX_TAIL_RE.sub("", s)
    s = EMOJI_RE.sub("", s)
    s = re.sub(r"[\s_-]{2,}", " ", s)
    s = s.strip(" -_")
    if not s:
        s = "untitled"
    return s


def cluster_for(text, fm):
    """Pick the best target folder based on content + frontmatter."""
    blob = (text[:2000] + " " + " ".join(fm.values())).lower()
    scores = Counter()
    for kw, folder in CLUSTERS.items():
        c = blob.count(kw)
        if c:
            scores[folder] += c
    if not scores:
        return None, 0
    top, score = scores.most_common(1)[0]
    return top, score


def main():
    buckets_report = {}
    rename_suggestions = []
    move_suggestions = defaultdict(list)
    total_files = 0
    total_dirty = 0

    for bucket in BUCKETS:
        if not bucket.exists():
            buckets_report[str(bucket.relative_to(VAULT))] = {"files": 0, "missing": True}
            continue
        files = list(bucket.rglob("*.md"))
        bucket_data = {
            "files": len(files),
            "tags": Counter(),
            "projects": Counter(),
            "filename_issues": Counter(),
            "cluster_hits": Counter(),
        }
        for f in files:
            total_files += 1
            try:
                text = f.read_text(errors="ignore")
            except Exception:
                continue
            fm = parse_frontmatter(text)
            tags = fm.get("tags", "")
            for t in re.findall(r"[a-z0-9/_-]+", tags):
                if len(t) > 1:
                    bucket_data["tags"][t] += 1
            proj = fm.get("project", "")
            if proj and proj != "—":
                bucket_data["projects"][proj] += 1
            issues = has_filename_issues(f.name)
            if issues:
                total_dirty += 1
                for i in issues:
                    bucket_data["filename_issues"][i] += 1
                rename_suggestions.append({
                    "from": str(f.relative_to(VAULT)),
                    "stem_clean": suggest_filename(f.stem),
                    "issues": issues,
                })
            target, score = cluster_for(text, fm)
            if target and score >= 2:
                bucket_data["cluster_hits"][target] += 1
                move_suggestions[target].append({
                    "from": str(f.relative_to(VAULT)),
                    "score": score,
                })
        buckets_report[str(bucket.relative_to(VAULT))] = bucket_data

    # Write report
    lines = [
        "---",
        "generated: 2026-05-15",
        "purpose: Read-only theme mining + filename hygiene scan across triage buckets",
        "status: review",
        "---",
        "",
        "# Triage themes + hygiene report",
        "",
        f"**Total files scanned:** {total_files}  ",
        f"**Files with filename issues:** {total_dirty} ({100*total_dirty//max(total_files,1)}%)",
        "",
        "## Per-bucket summary",
        "",
    ]
    for path, data in buckets_report.items():
        if data.get("missing"):
            lines.append(f"### `{path}` — MISSING")
            continue
        lines += [
            f"### `{path}` — {data['files']} files",
            "",
            "**Top tags:** " + (", ".join(f"`{t}`({n})" for t, n in data["tags"].most_common(10)) or "_(none)_"),
            "",
            "**Top projects:** " + (", ".join(f"`{p}`({n})" for p, n in data["projects"].most_common(5)) or "_(none)_"),
            "",
            "**Filename issues:** " + (", ".join(f"{k}={v}" for k, v in data["filename_issues"].most_common()) or "_clean_"),
            "",
            "**Cluster hits (suggested moves):**",
        ]
        for folder, n in data["cluster_hits"].most_common(10):
            lines.append(f"- `{folder}` ← {n} files")
        lines.append("")

    lines += [
        "## Suggested rename samples (first 30 of " + str(len(rename_suggestions)) + ")",
        "",
        "| Current | Cleaned stem | Issues |",
        "|---------|--------------|--------|",
    ]
    for r in rename_suggestions[:30]:
        lines.append(f"| `{r['from']}` | `{r['stem_clean']}` | {', '.join(r['issues'])} |")
    lines += [
        "",
        "Full list: see `_meta/triage-renames.jsonl`",
        "",
        "## Suggested moves by target folder",
        "",
    ]
    for folder, items in sorted(move_suggestions.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"### `{folder}` ({len(items)} candidates)")
        for it in items[:8]:
            lines.append(f"- `{it['from']}` (score {it['score']})")
        if len(items) > 8:
            lines.append(f"- _...{len(items)-8} more_")
        lines.append("")

    lines += [
        "## How to apply",
        "",
        "Renames are NOT applied. To apply:",
        "1. Review this report.",
        "2. Run `python3 .claude/scripts/triage-apply.py --renames` (script to be created when user approves).",
        "3. Or apply move clusters one at a time with `--cluster <folder>`.",
        "",
        "All operations log to `_meta/triage-apply.log` (JSONL) and are reversible.",
    ]
    REPORT.write_text("\n".join(lines))

    # Also write the full rename list to JSONL for the apply script
    rename_file = VAULT / "_meta/triage-renames.jsonl"
    with rename_file.open("w") as f:
        for r in rename_suggestions:
            f.write(json.dumps(r) + "\n")

    # And the move suggestions
    move_file = VAULT / "_meta/triage-moves.jsonl"
    with move_file.open("w") as f:
        for folder, items in move_suggestions.items():
            for it in items:
                f.write(json.dumps({"target": folder, **it}) + "\n")

    print(f"Wrote {REPORT.relative_to(VAULT)}")
    print(f"Scanned {total_files} files. {total_dirty} have filename issues.")
    print(f"Move candidates: {sum(len(v) for v in move_suggestions.values())}")


if __name__ == "__main__":
    main()
