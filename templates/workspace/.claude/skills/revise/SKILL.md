---
name: revise
description: Change an application draft that already exists - its CV headline or order, the letter, the keywords it shows - by sending the change to the tailor subagent, which edits and rebuilds it in a fresh context. Use when the user says "revise <folder>", "add Agile to the Checkmk CV", "make the letter shorter", "change the headline for <company>" or asks for any edit to a tailored application.
---
Argument: the application folder (its name, or words from the company and role) and what to change. Run everything
from the workspace folder. The tailor does the edit: don't open the folder's files, edit application.md or run
the build yourself. That keeps this conversation small.

1. Find the folder: `python engine/tools/ledger.py show <words>` or list `applications/` and match the company and
   role. Several matches: list them and ask which one. None: say so and stop.
2. A new fact about the candidate in the request ("we did sprints at Maven", "I know pytest basics"): record it
   first with the `skills` skill's step 3 (`python engine/tools/keywords.py fact ...`) and show the row. A yes
   needs where they used it; ask if they didn't say. Never record a fact the user didn't state.
3. Call the tailor subagent (Agent tool, subagent_type `tailor`, `run_in_background: false`) with one line:
   `revise applications/<folder> | <the user's request in their own words>`.
4. Reply with the tailor's `build`, `pdfs`, `keywords`, `grounding` and `actions` lines and the folder. A rule the
   tailor refused (in `actions`): explain it in one sentence.
5. End with: "For more changes to this draft, say `revise` again. Start a new conversation for other work."
