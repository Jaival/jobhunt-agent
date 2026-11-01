---
name: why
description: Explain why a job got its fit score or verdict - the five rubric sub-scores, hard mismatches and reasons - from the ledger and the job's ad extract, without changing anything. Use when the user says "why <job>", "why did <company> score N", "why was <job> skipped" or "explain the score of <folder>".
---
Argument: the job, as a link, an application folder, or words from the company and title. Read-only: change no
file, and never read the ad text itself (only its extract). Run everything from the workspace folder.

1. Find the job: `python engine/tools/ledger.py show <link or words>`. For a folder, use the `- **URL:**` line of
   its job.md. Several matches: list them and ask which one. `NOT FOUND`: say the routine hasn't seen it, and
   offer `tailor <url>`.
2. With sub-scores: run `python engine/tools/score.py <the sub-scores> --ad <extract>` with the job's extract
   (data/ads/<id>.json, or ad.json in its application folder; leave `--ad` out when there is none). It prints the
   total, any hard mismatch and the reasons. If its total differs from the stored score, say why it can: the
   `scoring:` weights in config.yaml or the engine changed since (the row's engine version).
3. Without sub-scores (a row from before the rubric, or a job skipped before scoring): give the verdict, score
   and note, and say it wasn't scored with the rubric.
4. Reply: verdict, score, each sub-score with the anchor it matches in engine/rubric.md, hard mismatches,
   reasons, and for a tailored job the Gaps line of its job.md. End with what would change the score (for example
   "C1 German required: a B2 certificate wouldn't change it; hours 3 -> 5 if the employer accepts 15 h").
