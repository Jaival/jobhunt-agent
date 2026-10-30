# jobhunt-agent

A daily job-search routine for Claude Code. Every day it pulls new ads from job APIs, the Indeed connector
and Gmail job alerts, scores them against your CV and, on weekdays, drafts a tailored CV and cover letter
for the best ones. Python tools keep a ledger of every screened job, refuse unfinished drafts and keep an
Excel tracker of what you sent. **Nothing is ever sent or submitted automatically**: you review the drafts
and apply yourself.

Built for working-student, internship and junior roles in Germany (Arbeitsagentur, Arbeitnow, StepStone,
XING, Indeed), in **any field**: marketing, nursing, engineering or software. The first run asks what you are
looking for and turns it into your own title filter, search terms and rules, all plain text you can change.
Before tailoring anything it checks your CV and cover letter for ATS problems and suggests fixes, then maps
your own CV design so the builder can tailor it without you switching to a template.

Built by [Jaival Saija](https://github.com/Jaival) with Claude Code ([portfolio](https://jaivalsaija.vercel.app)).

## How it works

```
workspace/                   your private folder (and private git repo)
├─ CLAUDE.md                 who you are, your decisions, routine settings → imports engine/RULES.md
├─ config.yaml               name, master CV paths, letter city, search area, profile (which titles to keep)
├─ sources.md companies.md   where to search; the routine updates their status columns
├─ custom.md                 wishes for the engine (never edit engine/ itself: it blocks updates)
├─ projects.md cv/           your project facts, master CV and its map cv/layout.yaml (the builder only reorders
│                            and swaps approved wordings)
├─ applications/ tracker/ daily/ data/ follow-ups/ interview-prep/ reviews/
├─ .claude/                  permission rules, guard hook, subagents (ad-reader, tailor) and skills for the
│                            requests: ats-review, update-engine, remap-cv, onboarding
└─ engine/                   this repo
   ├─ ROUTINE.md             the daily routine the scheduled task runs
   ├─ ONBOARDING.md          the first-run setup interview
   ├─ UPGRADING.md           "update the engine": backup, migration, old-vs-new document check, rollback
   ├─ CHANGELOG.md VERSION   what each release adds, with the setting to use; the engine version
   ├─ ats-checklist.md       the CV and cover letter review (also on request: "run the ATS review")
   ├─ RULES.md               honesty, no-placeholder and drafts-only rules
   ├─ career-ops-playbook.md liveness, posting check, requirements table, outreach, follow-ups, reviews
   ├─ tools/                 setup_check, search_jobs, scope, ats_scan, cv_map, build_application, pdf_export,
   │                         upgrade, ledger, add_applied, archive, tracker_to_md, version
   ├─ docs/                  visual setup guide, roadmap to v1.0 (ROADMAP.md), how releases work (RELEASING.md)
   ├─ examples/              filled-in sample workspaces (a fictional marketing student; a German mechanical
   │                         engineer with a plain-paragraph CV and German + English letters)
   ├─ tests/                 pytest suite
   └─ templates/             example workspace files
```

A day's run:
1. `search_jobs.py` queries the APIs and the watchlist, filters titles with your `profile:` and checks the ledger.
2. Claude reads each new ad, drops closed or out-of-scope ones and scores the rest (0-100) against `CLAUDE.md` and the CV: five 0-5 sub-scores from the anchors in `rubric.md`, which `tools/score.py` turns into the total.
3. On weekdays, it hands each top match to a `tailor` subagent with a fresh context, which writes `job.md` (requirements vs. evidence, keyword coverage, posting check) and `application.md` (headline, item order of the mapped CV sections, letter).
4. `build_application.py` builds the CV and letter (.docx, and PDF via Word or LibreOffice). It fails on placeholders, letters outside 250-350 words, unapproved wordings, numbers or skills that aren't in your own files or the ad, a CV over 2 pages or a letter over 1 page.
5. Confirmation and rejection emails update the tracker; `archive.py` moves finished folders; a daily brief lists what to send today.

Guardrails: ad text is treated as untrusted data (prompt-injection attempts are reported, never followed),
every claim must come from the master CV or `CLAUDE.md`, and the routine never sends, submits or posts. The last
part is enforced, not just asked for: permission rules in the workspace's `.claude/settings.json` and a guard hook
(`tools/hooks/guard.py`) block sending, typing into pages, edits of `engine/` and the master files, and network
calls to hosts other than the job sites. They apply to a local Code-tab task; the brief says whether the guard ran.

## Requirements
- Claude Desktop (Code tab) with a local scheduled task (Scheduled > New task > Only on this computer)
- Your CV and a cover letter as Word .docx files (Word, Google Docs and LibreOffice can all export one)
- For PDFs: Microsoft Word (Windows or macOS) or the free LibreOffice; without either you still get .docx files
- Python 3.11 or newer with `python-docx`, `openpyxl`, `pypdf`, `pyyaml`, `requests`
- Optional MCP connectors: Gmail, Indeed, a headless browser (obscura)

See [SETUP.md](SETUP.md), or the visual guide in [docs/setup-guide.html](docs/setup-guide.html). Setup is mostly
a conversation: on the first run the routine checks the workspace (`engine/tools/setup_check.py`) and, while
anything is missing, asks you for it ([ONBOARDING.md](ONBOARDING.md)) instead of searching. No programming
needed: it explains terms like Werkstudent or ATS as it goes and asks before installing anything.

## Development
`python -m pip install -r requirements-dev.txt` once (the pinned versions CI tests with), then
`python -m pytest tests` in this folder. The tests build the sample
workspace in [examples/sample-workspace](examples/sample-workspace) end to end (no PDFs).

Work in a separate clone, not in a workspace's `engine/`. `main` only moves with releases (that's what users
update to); changes go through feature branches and PRs into `next`. Versions and releases are described in
[docs/RELEASING.md](docs/RELEASING.md), the plan to v1.0 in [docs/ROADMAP.md](docs/ROADMAP.md).

## Credits
`career-ops-playbook.md` adapts rules from [career-ops](https://github.com/career-ops-hq/career-ops) (MIT licence).
