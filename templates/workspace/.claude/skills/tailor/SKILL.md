---
name: tailor
description: Tailor one job the user names by its link, outside the daily run - the ad reader reads the ad, the job is scored with the rubric, and the tailor subagent writes and builds the CV and letter. Use when the user says "tailor <url>", "/tailor <url>", "apply to this job" or pastes a job link and asks for an application.
---
Argument: the job's link (`https://...`; for Indeed the `viewjob?jk=` link). One job, with the same tools, checks
and rules as the daily run (engine/ROUTINE.md steps 2-5, RULES.md): never read the ad yourself, never send
anything. This replaces the daily routine for this conversation. Run everything from the workspace folder.

1. `python engine/tools/setup_check.py`. On NOT READY, say what is TODO and stop.
2. `python engine/tools/extract.py add <url>`.
   - `FAILED`: say why (for example an Indeed short link) and stop.
   - `SEEN`: tell the user the earlier verdict, score and date (`python engine/tools/ledger.py show <url>`), and
     ask whether to tailor it again. Stop on a no.
3. If it printed a `read ...` line, call the ad-reader subagent (Agent tool, subagent_type `ad-reader`) with that
   line only. Write its reply unchanged to data/ads/incoming.json and run
   `python engine/tools/extract.py save data/ads/incoming.json`. `UNREAD` or `CLOSED`: tell the user and stop.
   `FAILED`: send the task once more, then stop. Without the ad-reader subagent, stop: say "ad reader missing:
   run setup_check.py --init".
4. Score it as ROUTINE.md step 4: five sub-scores against engine/rubric.md from data/ads/<id>.json, then
   `python engine/tools/score.py skills=N seniority=N language=N location=N hours=N --ad data/ads/<id>.json`.
   A hard mismatch or a score under 70: show the score and its reasons, and ask whether to tailor anyway.
5. `python engine/tools/ledger.py record --model <your model id>`, then
   `python engine/tools/ledger.py set <url> --verdict screened --score N --subscores skills=N seniority=N
   language=N location=N hours=N --model <your model id> --note "on request"`.
6. Create applications/<today>_<Company>_<Role>/ and call the tailor subagent (subagent_type `tailor`) with the
   task line from ROUTINE.md step 5 (notes: "on request", plus "no build: ..." when setup_check warned about
   the CV map or config.yaml has `layout: none`). Don't write job.md, application.md or the letter yourself.
7. `python engine/tools/ledger.py set <url> --verdict tailored --score N --model <your model id>` when the tailor
   built or wrote it.
8. Reply: the score with its sub-scores and reasons, the tailor's `build`, `pdfs`, `personalise`, `grounding` and
   `actions` lines, the folder, and "say 'sent <folder>' when you have sent it". Offer an outreach note
   (playbook E) only as a draft.
