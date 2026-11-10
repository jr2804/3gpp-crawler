"""Draft release notes from the commits since the previous tag using an OpenAI-compatible LLM."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from argparse import ArgumentParser
from pathlib import Path

DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"
MAX_LOG_CHARS = 12000
RETRY_STATUSES = {429, 500, 502, 503, 504}

PROMPT = """You write GitHub release notes for the Python project 3gpp-crawler.
Input: commit subjects and bodies since the previous release, one commit per block.
Output: Markdown only, no preamble. Use these sections, omitting empty ones:
### Breaking changes, ### Features, ### Fixes, ### Documentation, ### Maintenance.
Each item is one short line in the present tense, without commit hashes.
Mention a breaking change only when a commit marks it (`!` after the type or a BREAKING CHANGE footer).
Do not invent changes that are not in the input."""


def run_git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def previous_tag(tag: str) -> str | None:
    tags = [t for t in run_git("tag", "--sort=-v:refname").split() if t != tag]
    return tags[0] if tags else None


def commit_log(tag: str) -> str:
    previous = previous_tag(tag)
    revision = f"{previous}..HEAD" if previous else "HEAD"
    log = run_git("log", "--no-merges", "--format=%s%n%b%x1e", revision)
    blocks = [block.strip() for block in log.split("\x1e") if block.strip()]
    return "\n\n".join(blocks)[:MAX_LOG_CHARS]


def post_chat(request: urllib.request.Request, *, attempts: int = 4) -> dict:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:500].decode(errors="replace")
            print(f"HTTP {exc.code} from LLM endpoint (attempt {attempt}/{attempts}): {detail}", file=sys.stderr)
            if exc.code not in RETRY_STATUSES or attempt == attempts:
                raise
            time.sleep(attempt * 20)
    raise RuntimeError("unreachable")


def draft_notes(log: str, *, api_key: str, api_base: str, model: str) -> str:
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": log},
        ],
    }
    request = urllib.request.Request(  # noqa: S310
        f"{api_base.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    payload = post_chat(request)
    return payload["choices"][0]["message"]["content"].strip()


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, help="Write the Markdown notes here")
    parser.add_argument("--dry-run", action="store_true", help="Print the commit log and exit")
    args = parser.parse_args()

    log = commit_log(args.tag)
    if args.dry_run:
        print(log)
        return 0
    if not log:
        print("no commits since the previous tag", file=sys.stderr)
        return 1

    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        print("LLM_API_KEY is not set", file=sys.stderr)
        return 1

    notes = draft_notes(
        log,
        api_key=api_key,
        api_base=os.environ.get("LLM_API_BASE") or DEFAULT_API_BASE,
        model=os.environ.get("LLM_MODEL") or DEFAULT_MODEL,
    )
    if not notes:
        print("LLM returned empty notes", file=sys.stderr)
        return 1
    if args.output:
        args.output.write_text(notes + "\n", encoding="utf-8")
    else:
        print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
