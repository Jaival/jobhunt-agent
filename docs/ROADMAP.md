# Roadmap to v1.0

Four two-week sprints, ordered by risk: first make the unattended run safe and stop it losing jobs, then make
its judgments measurable, then restructure it, and finally ship versioned releases you can steer interactively.
Each sprint item is a GitHub issue titled with its ID (e.g. "S1-4: ..."), in a milestone per sprint.

Starting point: `main` at `62eca7d` (2026-10-24), 54 tests passing.

## Assumptions (change these and re-plan)
- **Team:** 1 maintainer working with Claude Code, about 10 h/week.
- **Capacity:** 20 h per sprint, **planned to ~75% (15 h)** to leave room for user issues and surprises.
- **Estimates** are hours of focused work, including tests and docs.
- **Compatibility:** existing workspaces must keep working. Anything that changes workspace files gets a migration
  in `tools/upgrade.py`, a `CHANGELOG.md` entry and, if needed, a format version bump.

## Roadmap at a glance
| Sprint | Dates | Goal | Release | Load |
|---|---|---|---|---|
| 1. Safe & lossless | Mon 26 Oct – Fri 6 Nov 2026 | An unattended run can't send, leak data or edit the engine, no job is silently lost, and releases are numbered | `v0.3.0` | 15.75 h (79%) |
| 2. Measurable judgment | Mon 9 Nov – Fri 20 Nov 2026 | Scoring has an eval baseline, the tool-holding agent never sees raw ad text, and fit scores come from a rubric | `v0.4.0` | 15.5 h (78%) |
| 3. Grounded & modular | Mon 23 Nov – Fri 4 Dec 2026 | Every letter is checked against its sources, and each job is tailored in a fresh context | `v0.5.0` | 14.5 h (73%) |
| 4. Versioned & interactive | Mon 7 Dec – Fri 18 Dec 2026 | Users update to tagged releases only, and can steer the agent with commands and a decision inbox | `v1.0.0` | 14.5 h (73%) |

---

## Branches and releases

### Branches (from Sprint 1)
- **`main` is stable:** it only moves when a release is merged and tagged. `upgrade.py` and the "update available"
  check follow `main`, so users get tested releases from Sprint 1 on, with no code change.
- **`next`** collects the sprint's work. Every item is a feature branch (`s1-4-details-crash`) and a PR into
  `next`, closing its issue.
- **Release:** PR `next` → `main`, then tag `vX.Y.Z` on `main`.
- **Hotfix:** branch from `main`, PR into `main`, tag a PATCH release, then merge `main` back into `next`.
- **Development happens in a separate clone**, never in a workspace's `engine/`: that copy runs the daily routine,
  `setup_check.py` warns about edits in it, and from Sprint 1 the permission template and hook block them. The
  maintainer's own workspace is the first user of each release.

### What gets versioned
An agent's behaviour comes from more than its code: the **code** (`tools/`), the **prompts** (ROUTINE.md, RULES.md,
the playbook, ONBOARDING.md, from Sprint 2 the rubric and subagent prompts), the **file formats** a workspace
depends on, and the **model** that runs it.

| Thing | How it's versioned | Where |
|---|---|---|
| Engine (code + prompts) | One semantic version, `MAJOR.MINOR.PATCH` | `VERSION` file, git tag `vX.Y.Z`, GitHub Release |
| Workspace formats | A separate integer per format, bumped only when a migration is needed | `config_version` (exists), `ledger_version` (sidecar `data/seen_jobs.meta.json`, so the CSV stays plain), `application_version`, `ad_extract_version` |
| Model | Not pinned; each release says which model it was evaluated with | Release notes, eval baseline, daily brief |
| The user's workspace | The user's own git repo, one commit per run | Sprint 4 (S4-4) |

Prompts are **not** versioned separately: they ship in the same tag as the code that calls them, so a release is
always a tested combination.

### What the version numbers mean
- **MAJOR:** the workspace needs a migration that changes users' files, or a rule changes what documents say
  (e.g. a grounding rule that can fail builds that passed before).
- **MINOR:** new features or settings, or prompt changes that change behaviour without a migration (new source,
  new brief section, different scoring weights). Listed under **"Behaviour changes"** in the CHANGELOG.
- **PATCH:** bug and doc fixes that don't change documents or scores for an unchanged workspace.

### History
- Retroactive tags: `v0.1.0` = `2db97fa` (2026-10-23, "any field", PR #1), `v0.2.0` = `62eca7d` (2026-10-24,
  smoother updates and German letters, PR #2).
- Each sprint ends with a minor release; `v1.0.0` ships at the end of Sprint 4. 1.0 is the promise that updates
  are safe.

### Channels (Sprint 4)
- **stable** (default): `upgrade.py` checks out the newest tag; "update available" only for a newer tag.
- **next** (opt-in, `engine_channel: next`): follows the `next` branch, for the maintainer and testers.

### Release checklist
1. CI green on `next` (tests on Windows + Ubuntu).
2. Eval run compared with the previous release's baseline (from Sprint 2); no regression beyond tolerance.
3. `upgrade.py compare` on both sample workspaces: documents identical, or differences explained in the CHANGELOG.
4. `VERSION` bumped, CHANGELOG section in Keep a Changelog style (Added / Changed / **Behaviour changes** /
   Fixed / Migration).
5. PR `next` → `main`, merge, push tag `vX.Y.Z`: a workflow reruns the tests and creates the GitHub Release
   from the CHANGELOG section (from Sprint 4; by hand before).
6. Update the maintainer's own workspace with "update the engine" and watch the next daily run.

### Traceability
Every daily brief, ledger row and `job.md` records the engine version (and, best effort, the model). The Friday
review can then show whether a change in reply rates or scores started with a particular release: a prompt edit
can shift behaviour as much as a code change.

---

## Making the agent interactive
You can already open a workspace in Claude Code and talk to it, or reply to a scheduled run from its History.
What's missing is a defined set of interactions.

| Level | What it is | Effort | When |
|---|---|---|---|
| **1. Commands** | Skills with a clear contract: `tailor <url>`, `why <job>` (score with sub-scores), `sent <folder>`, `status` | Low | Sprint 4 |
| **2. Decision inbox** | A "Decisions" checklist in the daily brief (tailor / skip / mark sent / approve wording / answer); the next run acts on ticked boxes and confirms in its brief | Medium | Sprint 4 |
| **3. Dashboard** | Read-only pipeline page (HTML or Claude artifact), later with buttons that write to the decision inbox | High | After v1.0 |

Design rule for every level: interactive actions call the **same Python tools and rules** as the scheduled run
(builder checks, ledger, "never send"), so talking to the agent can never bypass a guardrail.

---

## Sprint 1: Safe & lossless
**Dates:** Mon 26 Oct – Fri 6 Nov 2026 | **Release:** `v0.3.0`
**Goal:** An unattended run is limited by enforced permissions instead of instructions alone, search and ledger can
no longer silently drop jobs, and the engine has a version number.

| Priority | ID | Item | Estimate | Depends on |
|---|---|---|---|---|
| P0 | S1-0 | **Spike, do first:** in a throwaway workspace and scheduled task, check whether Claude Desktop scheduled tasks honour workspace `.claude/settings.json` permissions and hooks (and user-level ones), the MCP tool names there (Gmail, Indeed, obscura), and whether subagents with restricted tools work. Decide the browser policy (see S1-2). Write the findings to `docs/spike-scheduled-tasks.md`. | 1 h | — |
| P0 | S1-1 | **Permission template** `templates/workspace/.claude/settings.json`: allow `python engine/tools/*.py`; deny the Gmail write tools (`send_message`, `reply`, `forward`, `create_draft`, `trash_*`, `*spam*`); allow `curl` only for the Indeed redirect lookup; deny `Edit`/`Write` on `engine/**` and the master CV/letter. `setup_check.py --init` copies it; **an `upgrade.py migrate` step installs it in existing workspaces** (merging with an existing settings.json, never overwriting). | 3 h | S1-0 |
| P0 | S1-2 | **PreToolUse hook** `tools/hooks/guard.py`: blocks writes into `engine/` and the master files, the Gmail send tools, and `curl`/WebFetch **and browser navigation** to hosts outside the policy from S1-0 (the obscura browser can leak data through a URL as easily as curl). Prints a reason the model can put in the brief. Tests included. Documented limits: it can't fully parse Bash (e.g. `python -c` writing a file); the permission template and the spike's findings are the main control, the hook is defence in depth. | 3 h | S1-0 |
| P0 | S1-3 | **SETUP.md step 5 and setup guide:** replace "always allow bash/curl/python" with "the permission template is installed"; `setup_check.py` warns if the template or hook is missing. | 1 h | S1-1, S1-2 |
| P0 | S1-4 | **Fix the `--details` crash** (`tools/search_jobs.py`): error handling and status check around `ba_detail`; write `candidates.json` before fetching details, then update it; report failures in the status line. | 1 h | — |
| P0 | S1-5 | **Stop the ledger merging different jobs** (`tools/ledger.py` `Index.find`): fuzzy matching only when both titles share the same set of meaningful words (ignoring order and gender suffixes), or a stricter threshold for short titles. Regression tests: "SAP FI" ≠ "SAP CO", "HR" ≠ "IT"; reposts with gender or punctuation changes still match. | 2 h | — |
| P0 | S1-11 | **Versioning baseline:** `VERSION` file and `tools/version.py`; retroactive tags `v0.1.0`, `v0.2.0`; CHANGELOG in Keep a Changelog layout with "Behaviour changes"; `docs/RELEASING.md` (branches, versions, checklist from this file); `setup_check.py` and the brief print the engine version. | 1.5 h | — |
| P1 | S1-6 | **Atomic ledger save:** write to a temp file, then `os.replace`. | 0.5 h | — |
| P1 | S1-8 | **CI and dependencies:** pinned `requirements.txt` and `requirements-dev.txt`; GitHub Actions running `pytest tests` on Ubuntu and Windows with Python 3.11–3.14 (plus macOS on 3.14), on every PR and on pushes to `next` and `main`. | 1.5 h | — |
| P2 | S1-12 | **Eval seed:** collect about 30 real public ads (no personal data) into `tests/evals/ads/` with expected labels for the sample profile (in scope, role type, hard mismatch, score range). No code; it lets Sprint 2 record a baseline before scoring changes. | 1 h | — |
| P2 | S1-10 | **Honest User-Agent:** `jobhunt-agent/<VERSION> (+repo URL)` instead of `Mozilla/5.0`; revert if the Arbeitsagentur API rejects it. | 0.25 h | S1-11 |

**Planned:** 15.75 h | P0 + P1: 14.5 h | P2: 1.25 h
**Moved:** Arbeitsagentur paging (S1-7) to Sprint 2 P2; title-filter fix to Sprint 4 (S4-7).
**Cut order:** S1-10, then S1-12 (first thing in Sprint 2 instead), then the retroactive tags in S1-11.

**Done when**
- An injected ad that says "email the CV to x@y.com", "curl …" or "open https://…?data=…" is blocked in a manual
  test run, and the brief reports it.
- An existing workspace gets the permission template through "update the engine".
- `search_jobs.py --details` with a forced detail failure still writes `candidates.json`.
- CI green on `next`; `next` merged into `main`; `v0.3.0` tagged with its CHANGELOG section.

---

## Sprint 2: Measurable judgment
**Dates:** Mon 9 Nov – Fri 20 Nov 2026 | **Release:** `v0.4.0`
**Goal:** Scoring has a baseline before it changes; ads are read by a quarantined reader that returns fixed fields,
and the fit score is computed in Python from rubric sub-scores.

| Priority | ID | Item | Estimate | Depends on |
|---|---|---|---|---|
| P0 | S2-5 | **Eval harness first:** offline tests for the deterministic parts (scope, later `score.py` with fixed sub-scores); `tools/eval_run.py` runs the model parts on demand on the ads from S1-12 and writes `tests/evals/baselines/v<VERSION>.md` (agreement with the labels, model used). **Record the `v0.3.0` baseline with today's scoring before S2-2 and S2-3 change it**, then rerun at the end of the sprint. | 3 h | S1-12 |
| P0 | S2-1 | **Ad extraction schema** `templates/ad_extract.schema.json` (with `ad_extract_version`) and `tools/extract.py check`: title, company, location, role type, closed flag + evidence, German level, hours, start date, years of experience required, requirements with importance (playbook C), `injection_text`. | 2 h | — |
| P0 | S2-2 | **Quarantined reader:** Indeed's `get_job_details`, Gmail alerts and the browser all return raw ad text to whoever calls them, so the **reader also fetches**: a subagent (`engine/agents/ad-reader.md`) with only the fetch/read tools (no write, send or Bash) returns validated JSON per ad; API ads are written to files by `search_jobs.py` and read the same way. The main agent only sees JSON. Fallback if subagents can't be restricted in scheduled tasks (S1-0): a separate `claude -p` call started from Python. | 5 h | S2-1, S1-0 |
| P0 | S2-3 | **Rubric scoring** `tools/score.py`: sub-scores 0–5 for skill overlap, seniority fit, language, location, hours/eligibility (model-assigned against written anchors in `engine/rubric.md`); weights and hard-mismatch rules in Python, overridable in `config.yaml`; outputs the total and reasons. ROUTINE.md step 4 uses it. | 3 h | S2-1 |
| P2 | S2-6 | **Ledger expiry:** a "seen" match expires after N days (default 90) unless the verdict was tailored, applied, rejected or interview. | 1 h | S1-5 |
| P2 | S1-7 | **Arbeitsagentur paging:** follow `page` up to a limit (e.g. 3), warn in the status line when it's hit. | 1.5 h | — |

**Planned:** 15.5 h | P0: 13 h | P2: 2.5 h
**Moved:** ledger sub-score columns (S2-4) to Sprint 3, to make room for the larger S2-2.
**Cut order:** S1-7, S2-6, then the end-of-sprint model rerun of S2-5 (keep the `v0.3.0` baseline and offline tests).

**Done when**
- A full manual "Run now" on a sample workspace completes with no raw ad text in the main agent's context.
- The same ad scored twice gives totals within ±5.
- Baselines `v0.3.0.md` and `v0.4.0.md` are checked in and `v0.4.0` is no worse beyond tolerance; `v0.4.0` tagged.

---

## Sprint 3: Grounded & modular
**Dates:** Mon 23 Nov – Fri 4 Dec 2026 | **Release:** `v0.5.0`
**Goal:** The builder refuses letters with claims not backed by the candidate's own files, and the daily run tailors
each job in its own fresh-context subagent.

| Priority | ID | Item | Estimate | Depends on |
|---|---|---|---|---|
| P0 | S3-1 | **Grounding check** in `build_application.py`: every number and percentage, and every skill or tool term from a known vocabulary (built from the master CV, CLAUDE.md, projects.md, the ad JSON and a shipped skills list), must appear in those sources. **Not keyed on capital letters:** German capitalises every noun, so that would fail most German letters. Unmatched terms fail the build with a list; `grounding_ok: [term]` in application.md for reviewed exceptions. Tests with both sample workspaces (EN and DE). | 4 h | S2-1 |
| P0 | S3-2 | **One subagent per job for tailoring:** ROUTINE.md step 5 hands each selected job to `engine/agents/tailor.md` (input: ad JSON, CV text, CLAUDE.md, projects.md, rules; output: `job.md`, `application.md`, build result). The main agent only collects results for the brief. | 4 h | S2-2, S3-1 |
| P1 | S3-3 | **On-request workflows become skills:** ATS review, "update the engine", "remap my CV", onboarding; ROUTINE.md keeps only the daily run. Old trigger phrases still work. | 3 h | — |
| P1 | S2-4 | **Ledger stores sub-scores and versions:** optional columns `subscores`, `engine_version`, `model` (old rows load with blanks); `ledger_version` in `data/seen_jobs.meta.json`; `ledger.py set --subscores`. Playbook H's Friday review reports score against outcome per sub-score and engine version. | 2 h | S2-3, S1-11 |
| P1 | S3-4 | **University name variants:** `university` accepts a list; the student-letter check accepts any of them. | 0.5 h | — |
| P1 | S3-5 | **`config.py` raises `ConfigError`** instead of exiting; each tool's `main()` turns it into a clean message and exit code. | 1 h | S1-8 |

**Planned:** 14.5 h | P0: 8 h | P1: 6.5 h
**Moved:** the plugin packaging write-up (S3-6) to Later.
**Cut order:** S3-4, then S2-4 (S4-3 then stamps only the brief and `job.md`), then S3-3 only if Sprint 4 can absorb it (S4-5 needs it).

**Done when**
- A letter with an invented metric ("increased traffic by 40%") fails the build; the German sample letter still passes.
- A daily run with 3 tailored jobs shows three separate subagent runs, and the brief format is unchanged.
- The eval baseline is no worse than `v0.4.0`; the grounding check is listed as a MAJOR-level behaviour change in the
  CHANGELOG; `v0.5.0` tagged.

---

## Sprint 4: Versioned & interactive
**Dates:** Mon 7 Dec – Fri 18 Dec 2026 | **Release:** `v1.0.0`
**Goal:** Users only receive tagged releases, every output says which version made it, and the agent can be steered
with commands and a decision inbox.

| Priority | ID | Item | Estimate | Depends on |
|---|---|---|---|---|
| P0 | S4-1 | **Release channels in `upgrade.py` and `setup_check.py`:** `status` compares the installed tag with the newest tag; `apply` checks out that tag; `engine_channel: stable|next` in config.yaml (migration adds it, default stable; next follows the `next` branch). Since `main` is already release-only, the move for users on `main` is just "check out the newest tag". Tests with a local bare repo. | 2 h | S1-11 |
| P0 | S4-2 | **Release workflow:** on tag push `v*`, run tests, check that `VERSION` matches the tag and the CHANGELOG has its section, create the GitHub Release from it. `docs/RELEASING.md` updated. | 2 h | S1-8, S1-11 |
| P0 | S4-3 | **Version stamping:** daily brief header (`engine vX.Y.Z · model …`), `job.md` `**Engine:**`, ledger columns from S2-4 filled on every write; PDF/docx metadata untouched (ATS). | 1.5 h | S2-4 |
| P0 | S4-5 | **Commands (level 1):** skills `tailor <url>`, `why <job>`, `sent <folder>`, `status`, calling the existing tools and rules. Documented in README with examples. | 3 h | S3-3 |
| P1 | S4-6 | **Decision inbox (level 2):** "Decisions" checklist at the top of the brief; `tools/decisions.py` parses ticked boxes, the next run acts through the same tools and confirms each action. Unticked items carry over for 7 days. | 3 h | S4-5 |
| P1 | S4-4 | **Workspace history:** if the workspace isn't a git repo, `setup_check.py --init` runs `git init` with a `.gitignore` (engine/, backups/, Office temp files); **if it already is one, it's left as it is.** The routine commits its own changes at the end of each run ("daily run 2026-12-14, engine v1.0.0"). Never adds a remote or pushes. | 1.5 h | — |
| P2 | S4-7 | **Title filter fix** (`tools/scope.py`): exclusion words on word boundaries; seniority words (`manager`, `staff`, `leiter`, `lead`) only for Junior/unlabelled titles. A behaviour change. | 1.5 h | S1-8 |

**Planned:** 14.5 h | P0: 8.5 h | P1: 4.5 h | P2: 1.5 h
**Cut order:** S4-7, then S4-4, then S4-6 (ship `v1.0.0` with commands only; the inbox becomes `v1.1.0`).

**Done when**
- A test workspace on `v0.5.0` updates to `v1.0.0` via "update the engine", ignoring commits on `next`.
- Pushing the `v1.0.0` tag creates the GitHub Release automatically.
- `tailor <url>` from Claude Code produces a built application with the same checks as the daily run; a ticked
  "skip" box is acted on by the next run.

---

## Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Scheduled tasks don't honour workspace `settings.json` or hooks the way the CLI does | Sprint 1's security work wouldn't apply where it matters | S1-0 first; if workspace level doesn't work, document user-level settings and have `setup_check.py` verify them |
| Subagents aren't available, or can't be restricted, in scheduled tasks | S2-2 and S3-2 blocked | Checked in S1-0; fallback: a separate `claude -p` call with restricted tools, started from Python |
| The hook can't see every way to write a file or reach the network (Bash, browser) | False sense of safety | Permissions are the main control, the hook is defence in depth; limits documented in S1-2 |
| Stricter rules (hook, grounding, title filter) block legitimate work | Failed builds or empty results | Every block prints a reason and the fix; grounding has reviewed exceptions; tested on the German sample too; CHANGELOG explains each change |
| Workspace changes break existing users | Upgrade friction | Migrations in `upgrade.py`, backward-compatible ledger columns, `upgrade.py compare` before and after |
| Version or model stamps are wrong | Misleading Friday reviews | Engine version from `VERSION`, never the model; the model field is labelled best effort |
| Workspace git history leaks personal data | Privacy leak | Local only, no remote added; README warns; `engine/` excluded via `.gitignore` |
| Decision inbox misread (box ticked by accident) | Wrong action | Actions are reversible and confirmed in the next brief; nothing is ever sent |
| Model-based evals are noisy or cost money | Hard to tell regressions from noise | Deterministic parts in CI; model evals on demand against a checked-in baseline with a tolerance |
| Solo capacity (exams, the job hunt itself, holidays in Sprint 4) | Sprints slip | 25% buffer, cut lists, each sprint ships a usable release on its own |

## Definition of done (every item)
- [ ] Feature branch, PR into `next` that closes the item's issue, self-review plus `/code-review`
- [ ] Tests added or updated; CI green (from S1-8 on)
- [ ] Both sample workspaces (`examples/`) still build end to end
- [ ] `CHANGELOG.md` entry under the right heading (behaviour changes explicit); migration in `upgrade.py` and a note in `UPGRADING.md` if workspace files change
- [ ] Docs updated (README, ROUTINE.md, SETUP.md or the setup guide, whichever applies)
- [ ] One manual "Run now" on a real workspace for anything that changes the daily routine

**Every sprint end:** `next` merged into `main`, `VERSION` bumped, tag pushed, GitHub Release created, eval
baseline saved (from Sprint 2), short retro.

## Key dates
| Date | Event |
|---|---|
| Mon 26 Oct 2026 | Sprint 1 start (S1-0 spike first) |
| Fri 30 Oct 2026 | Sprint 1 check-in: spike findings, go/no-go on the hook and browser policy |
| Fri 6 Nov 2026 | Sprint 1 end: blocked-injection demo; tag `v0.3.0` |
| Mon 9 Nov 2026 | Sprint 2 start: `v0.3.0` eval baseline first |
| Fri 13 Nov 2026 | Sprint 2 check-in: extraction schema frozen |
| Fri 20 Nov 2026 | Sprint 2 end: tag `v0.4.0` |
| Mon 23 Nov 2026 | Sprint 3 start |
| Fri 27 Nov 2026 | Sprint 3 check-in: grounding false-positive rate on both sample workspaces |
| Fri 4 Dec 2026 | Sprint 3 end: tag `v0.5.0` |
| Mon 7 Dec 2026 | Sprint 4 start |
| Fri 11 Dec 2026 | Sprint 4 check-in: tag-based update tested on a copy of a real workspace |
| Fri 18 Dec 2026 | Sprint 4 end: **`v1.0.0`**, announced in the README; plan the next cycle |

## Later (not scheduled)
- Plugin packaging write-up (formerly S3-6): what moving `engine/` to a Claude Code plugin means for install,
  updates and `upgrade.py`; then the move itself, with the plugin version replacing the git-tag channel.
- Interactive level 3: read-only pipeline dashboard, then buttons that write to the decision inbox.
- Model-graded honesty eval for letters (every claim traceable), run weekly against tailored applications.
- Standalone app on the Claude Agent SDK or a chat bot, only if commands and the inbox aren't enough.
