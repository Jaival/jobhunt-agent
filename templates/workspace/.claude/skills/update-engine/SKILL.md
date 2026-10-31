---
name: update-engine
description: Update the job-hunt engine (the engine/ folder) to the newest release, with a backup, the workspace migration and a before/after document check. Use when the user says "update the engine", "upgrade the engine", or the daily brief says an engine update is available or that config.yaml is from an older engine.
---
Follow "Steps for Claude" in engine/UPGRADING.md, from the workspace folder. Read that section from the version
you are updating to when its steps say so (`git -C engine show origin/main:UPGRADING.md`). This replaces the
daily routine for this conversation. Explain each result in plain words, never edit files in engine/ yourself,
and don't commit, push or delete anything without asking.
