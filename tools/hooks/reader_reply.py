"""SubagentStop hook: save the ad reader's or the mail reader's reply to data/ads/incoming/<agent id>.json.

Claude Code runs it when a subagent finishes (the workspace's .claude/settings.json starts it through
.claude/hooks/reader_reply.py, for the `ad-reader` and `mail-reader` agents only). The reply is the reader's
final message, so the routine no longer has to write it out itself: `extract.py save data/ads/incoming/` checks
and stores every reply in the folder. Before this hook the main session copied each reply into
data/ads/incoming.json with the Write tool, which cost a second copy of every reply in its context
(docs/research/token-usage-2026-11-08.md).

It never stops the subagent: a SubagentStop hook that exits 2 keeps the subagent running, so every error is
printed to stderr and the hook exits 0. The routine then finds no file and writes the reply itself.
"""
import json
import os
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import atomic  # noqa: E402

ROOT = Path(os.environ.get("JOBHUNT_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or TOOLS.parents[1])
INCOMING = ROOT / "data" / "ads" / "incoming"
AGENTS = {"ad-reader", "mail-reader"}


def main():
    event = json.loads(sys.stdin.read() or "{}")
    reply = event.get("last_assistant_message") or ""
    if event.get("agent_type") not in AGENTS or not reply.strip():
        return
    name = re.sub(r"[^A-Za-z0-9_-]", "", str(event.get("agent_id") or "")) or "reply"
    INCOMING.mkdir(parents=True, exist_ok=True)
    atomic.write_text(INCOMING / f"{name}.json", reply)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # exit 2 would keep the reader running; the routine falls back to writing the reply
        print(f"reader_reply: {e}", file=sys.stderr)
    sys.exit(0)
