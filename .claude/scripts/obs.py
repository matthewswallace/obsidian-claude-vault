#!/usr/bin/env python3
"""
Thin wrapper around the Obsidian Local REST API.

Reads key from ~/.config/obsidian-rest/key (mode 600, NOT in vault).
Server: https://127.0.0.1:27124 (self-signed cert, verify=False).

CLI usage:
  obs.py ping                        # health check
  obs.py get <path>                  # GET a vault file
  obs.py put <path> < body           # PUT (replace) file contents
  obs.py append <path> < body        # append to file
  obs.py list <folder>               # list files in folder
  obs.py search <query>              # simple text search
  obs.py active                      # info on currently-open note

Python usage:
  from obs import api
  api.get('Daily/2026-05-15.md')
  api.put('Daily/2026-05-15.md', '# Hello')
  api.append('Daily/2026-05-15.md', '\\n- note')
"""
import json
import os
import sys
import urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip3 install requests", file=sys.stderr)
    sys.exit(2)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


KEY_PATH = Path.home() / ".config/obsidian-rest/key"
BASE = "https://127.0.0.1:27124"


def _key():
    if not KEY_PATH.exists():
        print(f"Missing API key at {KEY_PATH}. Get it from Obsidian Settings → Local REST API.", file=sys.stderr)
        sys.exit(3)
    return KEY_PATH.read_text().strip()


def _headers(content_type="application/json"):
    return {
        "Authorization": f"Bearer {_key()}",
        "Content-Type": content_type,
    }


class Api:
    def ping(self):
        r = requests.get(f"{BASE}/", headers=_headers(), verify=False, timeout=5)
        return r.json()

    def get(self, vault_path):
        path = urllib.parse.quote(vault_path)
        r = requests.get(f"{BASE}/vault/{path}", headers=_headers("text/markdown"), verify=False, timeout=10)
        r.raise_for_status()
        return r.text

    def put(self, vault_path, content):
        path = urllib.parse.quote(vault_path)
        r = requests.put(f"{BASE}/vault/{path}", headers=_headers("text/markdown"), data=content.encode("utf-8"), verify=False, timeout=10)
        r.raise_for_status()
        return True

    def append(self, vault_path, content):
        path = urllib.parse.quote(vault_path)
        r = requests.post(f"{BASE}/vault/{path}", headers=_headers("text/markdown"), data=content.encode("utf-8"), verify=False, timeout=10)
        r.raise_for_status()
        return True

    def delete(self, vault_path):
        path = urllib.parse.quote(vault_path)
        r = requests.delete(f"{BASE}/vault/{path}", headers=_headers(), verify=False, timeout=10)
        r.raise_for_status()
        return True

    def list(self, folder=""):
        path = urllib.parse.quote(folder)
        r = requests.get(f"{BASE}/vault/{path}/" if folder else f"{BASE}/vault/", headers=_headers(), verify=False, timeout=10)
        r.raise_for_status()
        return r.json().get("files", [])

    def search_simple(self, query, ctx=100):
        r = requests.post(
            f"{BASE}/search/simple/?query={urllib.parse.quote(query)}&contextLength={ctx}",
            headers=_headers(),
            verify=False,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def active(self):
        r = requests.get(f"{BASE}/active/", headers=_headers(), verify=False, timeout=5)
        r.raise_for_status()
        return r.json()

    def commands(self):
        r = requests.get(f"{BASE}/commands/", headers=_headers(), verify=False, timeout=5)
        r.raise_for_status()
        return r.json()

    def exec_command(self, command_id):
        r = requests.post(f"{BASE}/commands/{command_id}/", headers=_headers(), verify=False, timeout=10)
        r.raise_for_status()
        return True


api = Api()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    try:
        if cmd == "ping":
            print(json.dumps(api.ping(), indent=2))
        elif cmd == "get":
            print(api.get(args[0]))
        elif cmd == "put":
            body = sys.stdin.read()
            api.put(args[0], body)
            print(f"PUT {args[0]} ({len(body)} bytes)")
        elif cmd == "append":
            body = sys.stdin.read()
            api.append(args[0], body)
            print(f"APPEND {args[0]} ({len(body)} bytes)")
        elif cmd == "delete":
            api.delete(args[0])
            print(f"DELETE {args[0]}")
        elif cmd == "list":
            folder = args[0] if args else ""
            for f in api.list(folder):
                print(f)
        elif cmd == "search":
            results = api.search_simple(" ".join(args))
            for r in results:
                print(f"{r.get('filename','?')} ({r.get('score','?')})")
        elif cmd == "active":
            print(json.dumps(api.active(), indent=2))
        elif cmd == "commands":
            for c in api.commands().get("commands", []):
                print(f"{c['id']}\t{c['name']}")
        else:
            print(f"Unknown command: {cmd}", file=sys.stderr)
            sys.exit(1)
    except requests.HTTPError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
