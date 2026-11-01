---
name: sent
description: Record that the candidate sent an application - adds the tracker row, moves the folder to applications/_sent/ and updates the ledger. Use when the user says "sent <folder>", "I sent the application to <company>", "I applied to <company>" or "mark <folder> as sent".
---
Argument: the application folder (its name, or words from the company and role), and optionally the date and
how it was sent. Only the candidate sends; this only records it. Run everything from the workspace folder.

1. Find the folder in applications/ (not _sent/ or _archive/). Several matches: list them and ask which one.
   None: say so and list the unsent drafts (applications/INDEX.md).
2. `python engine/tools/add_applied.py applications/<folder> --date <the date the user gives, else today>
   [--via Portal|Email]`. It backs up the tracker, adds the row, moves the folder to applications/_sent/ and
   refreshes tracker/applications.md. If it says Excel has the tracker open, ask the user to close it and run it
   again. "already in the tracker": say so and stop.
3. `python engine/tools/ledger.py set <the URL in job.md> --verdict applied --model <your model id>`.
4. Reply: the row it added (company, role, date, via), the new folder place, and the first follow-up date (7 days
   later, playbook F).
