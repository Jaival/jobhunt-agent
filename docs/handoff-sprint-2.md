# Handoff: Sprint 2 (v0.4.0, "Measurable judgment")

Written 2026-10-28, when the sprint's code was done. Delete this file once v0.4.0 is released.

## Done
Every item is its own PR, stacked in this order. Merge them in this order into `next`, then retarget each one to
`next` once the one below it is merged.

| PR | Item | Issue |
|---|---|---|
| #55 | S2-5 Eval harness and the `v0.3.0` baseline (`tools/eval_run.py`) | #15 |
| #56 | S2-1 Ad extraction schema, `extract.py check` | #16 |
| #57 | S2-3 Rubric scoring: `rubric.md`, `tools/score.py`, config `scoring:` | #18 |
| #58 | S2-2 Quarantined `ad-reader` subagent, `extract.py pending/save/read/attach` | #17 |
| #59 | S2-6 Ledger expiry (`ledger_expiry_days`) | #19 |

S1-7 (Arbeitsagentur paging) was already done in Sprint 1.

Eval (claude-opus-5-5, reader then judge, interim and not checked in), v0.3.0 -> S2-2:
- In scope: 29 -> 31 of 33
- Role type: 20 -> 20 of 21
- Hard mismatch: 20 -> 20 of 21
- Score: 20 -> 19 of 21
- Tailor: 30 -> 30 of 30
- German: 24 -> 32 of 33

The ads that still disagree:
- 02: scored 89 against [70, 88]
- 08: judged in scope
- 19: its location was judged a hard mismatch

## Still to do for "done when" (ROADMAP.md)
- A manual "Run now" on a sample workspace, checking that no raw ad text reaches the main agent's context. Not
  done yet: it needs the Code tab and real connectors.
- Check that the same ad scored twice gives totals within ±5. Not measured yet: run
  `eval_run.py run --only 01,02,19 --label rerun` twice and compare (about $0.50).
- At release: `eval_run.py run --label 0.4.0` on `next`, `compare` it against v0.3.0, commit both files and tag
  v0.4.0 (docs/RELEASING.md).

## Open decisions
- The score levels in score.py were tuned on the same 33 eval ads, so the eval flatters them. More labelled ads
  would show whether they hold.
- `data/ads/` is never cleaned up: the extracts and texts pile up. A cleanup step could go with `archive.py`.
- The ad reader can still reach the Gmail label tools; it's only told not to use them. Denying them would mean
  denying them by name in the agent's `disallowedTools`.
- Each ad now costs one extra model call for the reader, about $0.05.
- The headless eval hits the 5-hour usage limit around 25 ads with `--jobs 4`. The errors now show the reason;
  rerun the failed ads with `--only`.
