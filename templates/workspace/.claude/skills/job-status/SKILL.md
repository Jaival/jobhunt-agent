---
name: job-status
description: Show the job hunt at a glance - drafts to send, applications waiting for an answer, follow-ups due, interviews, open actions and the engine version - without searching or changing anything. Use when the user says "status", "job status", "where am I", "what's open" or "show my pipeline".
---
Read-only summary; don't search for jobs or run the daily routine. Run everything from the workspace folder.

1. `python engine/tools/setup_check.py`: the engine line, NOT READY items and warnings (an engine update
   available, the guard).
2. `python engine/tools/tracker_to_md.py` (it only regenerates the views), then read tracker/applications.md and
   applications/INDEX.md.
3. The newest daily/*.md: its first line, summary line and "Your actions".
4. Reply in at most 15 lines:
   - engine version and channel, and whether an update is available;
   - drafts to send: count, the oldest one's age, the top 3 by score with their folders;
   - sent and waiting for an answer: count; follow-ups due today or overdue;
   - interviews coming up, and whether each has interview-prep/<Company>.md;
   - open actions from the newest brief, and setup warnings.
   End with the commands: `tailor <url>`, `why <job>`, `sent <folder>`.
