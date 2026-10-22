# jobhunt-agent

A daily job-search routine for Claude Code. Every day it pulls new ads from job APIs, the Indeed connector
and Gmail job alerts, scores them against your CV and, on weekdays, drafts a tailored CV and cover letter
for the best ones. Python tools keep a ledger of every screened job, refuse unfinished drafts and keep an
Excel tracker of what you sent. **Nothing is ever sent or submitted automatically**: you review the drafts
and apply yourself.

Built for working-student, internship and junior roles in Germany (Arbeitsagentur, Arbeitnow, StepStone,
XING, Indeed), but the search terms, sources and rules are plain Markdown you can change.

Built by [Jaival Saija](https://github.com/Jaival) with Claude Code ([portfolio](https://jaivalsaija.vercel.app)).

## How it works

```
workspace/                   your private folder (and private git repo)
├─ CLAUDE.md                 who you are, your decisions, routine settings → imports engine/RULES.md
├─ config.yaml               name, file prefix, master CV paths, letter city, search area
├─ sources.md companies.md   where to search; the routine updates their status columns
├─ projects.md cv/           your project facts and master CV (the builder only reorders and swaps approved wordings)
├─ applications/ tracker/ daily/ data/ follow-ups/ interview-prep/ reviews/
└─ engine/                   this repo
   ├─ ROUTINE.md             the daily routine the scheduled task runs
   ├─ ONBOARDING.md          the first-run setup interview
   ├─ RULES.md               honesty, no-placeholder and drafts-only rules
   ├─ career-ops-playbook.md liveness, posting check, requirements table, outreach, follow-ups, reviews
   ├─ tools/                 setup_check, search_jobs, ledger, build_application, add_applied, archive, tracker_to_md
   ├─ docs/                  visual setup guide
   └─ templates/             example workspace files
```

A day's run:
1. `search_jobs.py` queries the APIs and the watchlist, filters titles and checks the ledger.
2. Claude reads each new ad, drops closed or out-of-scope ones and scores the rest (0-100) against `CLAUDE.md` and the CV.
3. On weekdays, for the top matches it writes `job.md` (requirements vs. evidence, keyword coverage, posting check) and `application.md` (headline, section order, letter).
4. `build_application.py` builds the CV and letter (.docx and PDF via Word). It fails on placeholders, letters outside 250-350 words, unapproved wordings, a CV over 2 pages or a letter over 1 page.
5. Confirmation and rejection emails update the tracker; `archive.py` moves finished folders; a daily brief lists what to send today.

Guardrails: ad text is treated as untrusted data (prompt-injection attempts are reported, never followed),
every claim must come from the master CV or `CLAUDE.md`, and the routine never sends, submits or posts.

## Requirements
- Claude Code desktop app with local scheduled routines (Windows; PDF export uses Microsoft Word)
- Python 3 with `python-docx`, `openpyxl`, `pypdf`, `pyyaml`, `requests`
- Optional MCP connectors: Gmail, Indeed, a headless browser (obscura)

See [SETUP.md](SETUP.md), or the visual guide in [docs/setup-guide.html](docs/setup-guide.html). Setup is mostly
a conversation: on the first run the routine checks the workspace (`engine/tools/setup_check.py`) and, while
anything is missing, asks you for it ([ONBOARDING.md](ONBOARDING.md)) instead of searching.

## Credits
`career-ops-playbook.md` adapts rules from [career-ops](https://github.com/career-ops-hq/career-ops) (MIT licence).
