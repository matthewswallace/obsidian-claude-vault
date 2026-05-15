#!/bin/bash
# Install obsidian-claude-vault scaffold into a target Obsidian vault.
#
# Usage:
#   ./install.sh /path/to/your/vault
#
# What it does:
#   - Copies .claude/ scripts, hooks, skills, settings.json into <vault>/.claude/
#   - Copies CLAUDE.template.md to <vault>/CLAUDE.md if missing
#   - Creates <vault>/.claude/vault.json from vault.example.json if missing
#   - chmod +x all scripts and hooks
#   - Idempotent: re-running updates scripts but preserves your vault.json + CLAUDE.md
#
# What it does NOT do:
#   - Touch your vault content (folders like Daily/, Attachments/, your project folders)
#   - Overwrite an existing vault.json
#   - Install Obsidian plugins (do that in Obsidian's Community Plugins UI)

set -euo pipefail

TEMPLATE_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="${1:-}"

if [ -z "$VAULT" ]; then
  echo "Usage: $0 /path/to/your/vault"
  exit 1
fi

if [ ! -d "$VAULT" ]; then
  echo "ERROR: '$VAULT' is not a directory."
  exit 2
fi

VAULT="$(cd "$VAULT" && pwd)"
echo "Installing scaffold from: $TEMPLATE_DIR"
echo "Into vault:              $VAULT"
echo ""

# Confirm before clobbering an existing .claude/
if [ -d "$VAULT/.claude" ]; then
  echo "Existing .claude/ found in vault."
  read -p "Continue (will preserve vault.json and any custom files)? [y/N] " -n 1 -r
  echo
  [[ ! $REPLY =~ ^[Yy]$ ]] && exit 3
fi

mkdir -p "$VAULT/.claude/scripts" "$VAULT/.claude/hooks" "$VAULT/.claude/skills"

# Copy scripts (overwrite — they're the scaffold)
echo "→ scripts"
cp -v "$TEMPLATE_DIR"/.claude/scripts/*.py "$VAULT/.claude/scripts/"
cp -v "$TEMPLATE_DIR"/.claude/scripts/*.sh "$VAULT/.claude/scripts/"

# Copy hooks (overwrite)
echo "→ hooks"
cp -v "$TEMPLATE_DIR"/.claude/hooks/*.sh "$VAULT/.claude/hooks/"

# Copy skills (overwrite)
echo "→ skills"
for skill_dir in "$TEMPLATE_DIR"/.claude/skills/*/; do
  name="$(basename "$skill_dir")"
  mkdir -p "$VAULT/.claude/skills/$name"
  cp -v "$skill_dir"/* "$VAULT/.claude/skills/$name/"
done

# Settings.json — only copy if missing (don't clobber user customizations)
if [ ! -f "$VAULT/.claude/settings.json" ]; then
  echo "→ settings.json (new)"
  cp -v "$TEMPLATE_DIR/.claude/settings.json" "$VAULT/.claude/"
else
  echo "→ settings.json (kept existing)"
fi

# vault.example.json — always copy (reference)
cp -v "$TEMPLATE_DIR/.claude/vault.example.json" "$VAULT/.claude/"

# vault.json — only copy if missing
if [ ! -f "$VAULT/.claude/vault.json" ]; then
  cp -v "$TEMPLATE_DIR/.claude/vault.example.json" "$VAULT/.claude/vault.json"
  echo "  ⚠ Created vault.json from example. EDIT IT before running scripts."
else
  echo "→ vault.json (kept existing)"
fi

# CLAUDE.md — only copy if missing
if [ ! -f "$VAULT/CLAUDE.md" ]; then
  cp -v "$TEMPLATE_DIR/CLAUDE.template.md" "$VAULT/CLAUDE.md"
  echo "  ⚠ Created CLAUDE.md from template. Customize folder map + integrations."
else
  echo "→ CLAUDE.md (kept existing)"
fi

# Make all scripts and hooks executable
chmod +x "$VAULT/.claude/scripts/"*.py "$VAULT/.claude/scripts/"*.sh
chmod +x "$VAULT/.claude/hooks/"*.sh

echo ""
echo "✓ Install complete."
echo ""
echo "Next steps:"
echo "  1. Edit $VAULT/.claude/vault.json — set isolation, folders, project_keywords"
echo "  2. Edit $VAULT/CLAUDE.md — customize folder map + integrations"
echo "  3. (Optional) Install Obsidian Local REST API plugin → set key at ~/.config/obsidian-rest/key"
echo "  4. Open the vault in Claude Code: cd '$VAULT' && claude"
