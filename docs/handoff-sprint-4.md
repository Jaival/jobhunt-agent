# Handoff: Sprint 4 (v1.0.0, "Versioned & interactive")

Written 2026-11-01, when the sprint's code was merged into `next`. Delete this file once v1.0.0 is released.

## Done
Every item was its own stacked PR; all are merged into `next` (517 tests pass there) and the issues are closed.

| PR | Item | Issue |
|---|---|---|
| #75 | S4-1 Release channels: `engine_channel: stable / next`, `upgrade.py status`, setup_check's update check | #27 |
| #76 | S4-2 Release workflow: a pushed `vX.Y.Z` tag creates the GitHub Release (`tools/release_notes.py`) | #28 |
| #83 | S4-3 Version stamping: brief first line, job.md `Engine` line, ledger `--model` (replaces #77, closed when its base branch was deleted) | #29 |
| #78 | S4-5 Commands: `tailor`, `why`, `sent`, `job-status` skills; `extract.py add`, `ledger.py show` | #30 |
| #79 | S4-6 Decision inbox: the brief's Decisions checklist, `tools/decisions.py`, `data/decisions_done.txt` | #31 |
| #80 | S4-4 Workspace history: `git init` in `--init`, `tools/history.py commit` after each run, setup_check warning | #32 |
| #81 | S4-7 Title filter: seniority words only for Junior titles, other exclude words at a word start | #33 |

Decisions made during the sprint:
- Decisions are read from the newest earlier brief with a Decisions section only; repeat runs skip them.
- The decisions log was added so a run that stops after acting, before its brief, doesn't act twice. One gap
  stays: a run that stops between the action and `decisions.py done` can repeat that one action.
- `--init` stays out of the daily run (it changes permissions); the run only runs `setup_check.py`, and the
  history warning tells the user to run `--init`.
- Seniority words still match inside a word (Teamleiter, Projektmanager), against the issue's "word
  boundaries", because German seniority titles are compounds.

## Still to do for "done when" (ROADMAP.md)
- A test workspace on `v0.5.0` updates to `v1.0.0` via "update the engine", ignoring commits on `next`.
- Pushing the `v1.0.0` tag creates the GitHub Release (the workflow is tested offline only).
- `tailor <url>` from Claude Code builds an application with the same checks as the daily run.
- A ticked "skip" box is acted on by the next run.
- A scheduled run that ends with a `history.py commit`.

## Release (docs/RELEASING.md checklist)
- Steps 2-4 before the tag: `upgrade.py compare` on both sample workspaces, the guard test, and the judgment
  eval (`eval_run.py run --label 1.0.0`, compare against v0.5.0; costs money).
- v1.0.0 is the first MAJOR: write `docs/upgrading/v1.0.0.md` (the new history, the Decisions checklist, the
  stable channel checking out tags, the title-filter behaviour change) and the CHANGELOG title.
- After the tag: PR `main` → `next` with `VERSION` `1.1.0-dev`, and add v1.0.0 to the tags table.

## Open decisions
- Every existing workspace becomes a git repo at its next update; reverting the engine doesn't undo that.
- A global `commit.gpgsign=true` can make the scheduled commit fail; the error shows in the run's reply only.
- More student titles with manager / leiter / staff / lead now reach scoring; watch the first briefs.
- The stray remote branch `s3-3-skills` is still on GitHub.
