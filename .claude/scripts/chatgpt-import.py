#!/usr/bin/env python3
"""
ChatGPT export importer.

Reads vault config from .claude/vault.json for isolation patterns + project keywords.

Input:  {inbox}/chatgpt-export-*.zip (or path passed as --zip)
Output: {archive}/chatgpt-import/YYYY-MM/{date} {slug}.md      (one per conversation)
        {archive}/chatgpt-import/_isolation-review/...          (any matching isolation keywords)
        {meta}/chatgpt-index.md                                  (master index)
        {meta}/chatgpt-import.log                                (JSONL, reversible)

Default: dry-run. Pass --apply to actually write files.

Strategy:
- Parse conversations.json
- For each conversation, linearize the main message branch (skip regeneration siblings)
- Compute rich frontmatter (date, model, msg_count, word_count_user, detected keywords/projects, source)
- Slugify title with filename hygiene rules (strip emoji/UUIDs, ≤60 chars)
- Isolation pre-filter: any configured isolation keyword → review bucket, NOT main archive
- Write markdown body: "## User" / "## ChatGPT" blocks, plain prose
- Master index with one row per conversation: date, title, msgs, words, projects, link

After import, project-merge / theme-mining are SEPARATE on-demand operations.
"""
import argparse
import json
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from vault_config import load_config, find_vault_root, isolation_regex, project_keywords, folder

CFG = load_config()
VAULT = find_vault_root()
INBOX = VAULT / folder(CFG, "inbox", "_inbox")
META = VAULT / folder(CFG, "meta", "_meta")
ARCHIVE = VAULT / folder(CFG, "archive", "_archive") / "chatgpt-import"
ISOLATION_BUCKET = ARCHIVE / "_isolation-review"
LOG = META / "chatgpt-import.log"
INDEX = META / "chatgpt-index.md"

ISOLATION_RE = isolation_regex(CFG)
PROJECT_KEYWORDS = project_keywords(CFG)

# Strip common emoji/symbol ranges
EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF -⁯︀-️‍]"
)
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
HEX_TAIL_RE = re.compile(r"[\s_-]+[0-9a-f]{12,}$", re.I)


def slugify(title: str, fallback: str = "untitled") -> str:
    """Title → safe filename slug, ≤60 chars, hygiene rules applied."""
    if not title or not title.strip():
        title = fallback
    s = EMOJI_RE.sub("", title)
    s = UUID_RE.sub("", s)
    s = HEX_TAIL_RE.sub("", s)
    # Replace path separators and tricky chars
    s = re.sub(r"[/\\:*?\"<>|]", "-", s)
    s = re.sub(r"\s+", " ", s).strip(" -_.")
    if not s:
        s = fallback
    if len(s) > 60:
        s = s[:60].rsplit(" ", 1)[0].strip()
    return s


def linearize(mapping: dict, root_id: str) -> list:
    """Walk the message tree, following each node's first child (main branch).
    ChatGPT export 'mapping' is {id: {message, parent, children: [...]}}. Children
    are typically [latest, ...older regenerations]; we follow children[0]."""
    result = []
    node_id = root_id
    while node_id:
        node = mapping.get(node_id, {})
        msg = node.get("message")
        if msg and msg.get("content"):
            result.append(msg)
        children = node.get("children") or []
        node_id = children[0] if children else None
    return result


def extract_text(msg: dict) -> str:
    """Pull the text body out of a message regardless of content type."""
    content = msg.get("content") or {}
    parts = content.get("parts") or []
    text_chunks = []
    for p in parts:
        if isinstance(p, str):
            text_chunks.append(p)
        elif isinstance(p, dict):
            # Multimodal: skip image bytes, keep any text/transcripts
            if p.get("content_type") == "audio_transcription":
                text_chunks.append(p.get("text", ""))
            elif "text" in p:
                text_chunks.append(p["text"])
    return "\n".join(t for t in text_chunks if t).strip()


def detect_projects(text: str) -> list:
    """Return list of project tags whose patterns hit in the text."""
    hits = []
    lower = text.lower()
    for tag, patterns in PROJECT_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, lower):
                hits.append(tag)
                break
    return hits


def is_isolation(text: str) -> bool:
    return bool(ISOLATION_RE.search(text)) if ISOLATION_RE else False


def yaml_list(items):
    if not items:
        return "[]"
    return "[" + ", ".join(json.dumps(i) for i in items) + "]"


def build_markdown(conv: dict, messages: list, all_text: str, projects: list, isolation_flag: bool) -> str:
    title = conv.get("title") or "Untitled"
    created = conv.get("create_time") or 0
    updated = conv.get("update_time") or created
    dt_created = datetime.fromtimestamp(created, tz=timezone.utc) if created else None
    dt_updated = datetime.fromtimestamp(updated, tz=timezone.utc) if updated else None

    models = sorted(set(m.get("metadata", {}).get("model_slug") for m in messages if m.get("metadata", {}).get("model_slug")))
    word_count_user = sum(len(extract_text(m).split()) for m in messages if (m.get("author") or {}).get("role") == "user")
    word_count_assistant = sum(len(extract_text(m).split()) for m in messages if (m.get("author") or {}).get("role") == "assistant")
    msg_count = len(messages)

    tags = ["chatgpt"] + projects
    if isolation_flag:
        tags.append("isolation-review")

    fm_lines = [
        "---",
        f"source: chatgpt-export",
        f"original_id: {conv.get('id','')}",
        f"created: {dt_created.date().isoformat() if dt_created else ''}",
        f"updated: {dt_updated.date().isoformat() if dt_updated else ''}",
        f"title: {json.dumps(title)}",
        f"models: {yaml_list(models)}",
        f"msg_count: {msg_count}",
        f"user_words: {word_count_user}",
        f"assistant_words: {word_count_assistant}",
        f"projects: {yaml_list(projects)}",
        f"tags: {yaml_list(tags)}",
        "---",
        "",
        f"# {title}",
        "",
        f"_Imported from ChatGPT export. Original id: `{conv.get('id','')}`._",
        "",
    ]

    body = []
    for m in messages:
        role = (m.get("author") or {}).get("role")
        if role not in ("user", "assistant"):
            continue
        text = extract_text(m)
        if not text:
            continue
        heading = "## User" if role == "user" else "## ChatGPT"
        body.append(heading)
        body.append("")
        body.append(text)
        body.append("")

    return "\n".join(fm_lines + body)


def import_conversations(zip_path: Path, apply: bool):
    if not zip_path.exists():
        print(f"ERROR: zip not found at {zip_path}", file=sys.stderr)
        sys.exit(2)

    print(f"Reading {zip_path.relative_to(VAULT) if zip_path.is_relative_to(VAULT) else zip_path}...")
    with zipfile.ZipFile(zip_path) as z:
        with z.open("conversations.json") as f:
            convs = json.load(f)
    print(f"Loaded {len(convs)} conversations from export.")

    if apply:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        ISOLATION_BUCKET.mkdir(parents=True, exist_ok=True)
        LOG.parent.mkdir(parents=True, exist_ok=True)

    index_rows = []
    stats = Counter()
    project_counts = Counter()
    seen_slugs = set()

    for conv in convs:
        mapping = conv.get("mapping") or {}
        # Find the actual root (parent==None or 'client-created-root' style)
        roots = [nid for nid, node in mapping.items() if node.get("parent") is None]
        if not roots:
            stats["no_root"] += 1
            continue
        messages = linearize(mapping, roots[0])
        # Filter out system messages without content
        messages = [m for m in messages if m and m.get("content")]

        all_text = "\n\n".join(extract_text(m) for m in messages)
        title = conv.get("title") or ""
        full_text = title + "\n" + all_text

        isolation_flag = is_isolation(full_text)
        projects = detect_projects(full_text)
        for p in projects:
            project_counts[p] += 1

        created = conv.get("create_time") or 0
        dt = datetime.fromtimestamp(created, tz=timezone.utc) if created else None
        ymd = dt.date().isoformat() if dt else "undated"
        ym = ymd[:7] if dt else "undated"

        slug = slugify(title, fallback=f"chat-{conv.get('id','')[:8]}")
        filename_base = f"{ymd} {slug}.md"

        target_dir = ISOLATION_BUCKET if isolation_flag else (ARCHIVE / ym)
        target = target_dir / filename_base

        # Collision: append a short id suffix
        if target in seen_slugs or (apply and target.exists()):
            suffix = (conv.get("id") or "")[:6]
            target = target.with_stem(target.stem + f" {suffix}")
        seen_slugs.add(target)

        stats["isolation"] += 1 if isolation_flag else 0
        stats["total"] += 1
        stats["empty"] += 1 if not messages else 0

        md = build_markdown(conv, messages, all_text, projects, isolation_flag)

        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(md)
            with LOG.open("a") as f:
                f.write(json.dumps({
                    "ts": time.strftime("%FT%T%z"),
                    "op": "import",
                    "src_id": conv.get("id"),
                    "dst": str(target.relative_to(VAULT)),
                    "isolation": isolation_flag,
                    "msgs": len(messages),
                    "projects": projects,
                }) + "\n")

        index_rows.append({
            "date": ymd,
            "title": title or "(untitled)",
            "path": str(target.relative_to(VAULT)),
            "msgs": len(messages),
            "user_words": sum(len(extract_text(m).split()) for m in messages if (m.get("author") or {}).get("role") == "user"),
            "projects": projects,
            "isolation": isolation_flag,
        })

    # Write master index
    index_rows.sort(key=lambda r: r["date"], reverse=True)
    lines = [
        "---",
        "source: chatgpt-import",
        f"generated: {time.strftime('%FT%T%z')}",
        f"total: {stats['total']}",
        "---",
        "",
        f"# ChatGPT Import Index",
        "",
        f"**{stats['total']} conversations imported** ({stats['isolation']} routed to isolation-review).",
        "",
        "## Project distribution",
        "",
    ]
    for p, n in project_counts.most_common():
        lines.append(f"- **{p}**: {n}")
    lines += [
        "",
        "## All conversations (newest first)",
        "",
        "| Date | Title | Msgs | User words | Projects | Path |",
        "|------|-------|------|-----------|----------|------|",
    ]
    for r in index_rows:
        prefix = "[!] " if r["isolation"] else ""
        proj = ", ".join(r["projects"]) or "—"
        lines.append(f"| {r['date']} | {prefix}{r['title'][:60]} | {r['msgs']} | {r['user_words']} | {proj} | [link]({r['path'].replace(' ', '%20')}) |")

    if apply:
        INDEX.write_text("\n".join(lines))

    print()
    print(f"{'APPLIED' if apply else 'DRY-RUN'}:")
    print(f"  Total:            {stats['total']}")
    print(f"  Isolation bucket: {stats['isolation']}")
    print(f"  Empty:            {stats['empty']}")
    print()
    print("Top projects:")
    for p, n in project_counts.most_common(15):
        print(f"  {p:20s} {n}")
    if apply:
        print()
        print(f"Index → {INDEX.relative_to(VAULT)}")
        print(f"Archive → {ARCHIVE.relative_to(VAULT)}/")
        print(f"Isolation review → {ISOLATION_BUCKET.relative_to(VAULT)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, help="path to export zip (default: auto-find in _inbox/)")
    ap.add_argument("--apply", action="store_true", help="actually write files (default: dry-run)")
    args = ap.parse_args()

    if args.zip:
        zip_path = args.zip
    else:
        candidates = sorted(INBOX.glob("chatgpt-export*.zip"))
        if not candidates:
            print(f"No chatgpt-export*.zip in {INBOX.relative_to(VAULT)}/. Drop it there or pass --zip.", file=sys.stderr)
            sys.exit(2)
        zip_path = candidates[-1]
        print(f"Auto-selected: {zip_path.relative_to(VAULT)}")

    import_conversations(zip_path, args.apply)


if __name__ == "__main__":
    main()
