# Changelog

What each engine release changes, with the setting to use. "update the engine" reads this to match the wishes in
your custom.md. The layout follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the version numbers
follow [docs/RELEASING.md](docs/RELEASING.md). Each release lists:

- **Added / Changed / Fixed:** new features and settings, changes to existing ones, bug fixes.
- **Behaviour changes:** anything that changes, for a workspace you haven't touched, which jobs are found or kept,
  their scores, or what the documents say. Read these before updating.
- **Migration:** what "update the engine" changes in your workspace files. Config version = the `config_version`
  in config.yaml that the engine reads (`upgrade.py migrate` updates older files).

## [Unreleased]

### Changed
- The daily run calls the ad reader and the tailor in the foreground (`run_in_background: false`): the reply
  comes back as the call's result, so the run no longer spends turns waiting with `sleep` or empty turns
  (51 such calls, 5.4M tokens in 10 runs; docs/research/token-usage-2026-11-08.md). The ad reader also drops
  the Desktop tools it never uses (file sending, plugin search, the Claude browser), whose schemas loaded on
  every call.
- The ad reader puts a job under `unreadable` with the reason `connector error` when Indeed's `get_job_details`
  fails, instead of retrying. The tailor stops at once on a guard block or permission refusal.
- The workspace permission template denies Desktop tools that no run or session in a workspace has used (plugin
  install and search, worktrees, the terminal, session, sidebar, window and connector tools, the Chrome
  extension), so their schemas no longer load on every call. Tools you use yourself in the workspace (the Claude
  browser, file sending, widgets, scheduled tasks) stay. Migration: `setup_check.py --init` or "update the engine"
  adds the rules to `.claude/settings.json`.
- The ad reader's replies are saved by a hook (`.claude/hooks/reader_reply.py`, SubagentStop) to
  `data/ads/incoming/`, and `extract.py save data/ads/incoming/` stores all of them; a reply that saved cleanly is
  deleted, a failed one stays. The daily run and the `tailor <url>` command no longer copy each reply into
  incoming.json themselves (397k characters re-typed in 10 runs). Without the hook they fall back to the old way
  and say so. Migration: `setup_check.py --init` or "update the engine" installs the hook.

## [1.1.0] - 2026-11-08: your own design

### Added
- `font: keep` in config.yaml: the builder keeps the master CV's and letter's own fonts instead of setting every
  font to one family, so a two-font design (for example a sans text font and a mono font for headings and dates)
  survives tailoring, and the PDF export and page check can stay on. `fallback_font` may now be a map from font
  to substitute (`{Inter: Arial, JetBrains Mono: Consolas}`); a single name still applies to every font.
- `never_write:` in config.yaml: phrases or regexes that must never appear in a CV or letter (for example a
  fact your CLAUDE.md forbids); a match fails the build. (#88)
- The grounding check also reads numbers written as words ("three", "twenty-five", "zwölf"; not "one"/"ein").
  One that isn't in your files or the ad is a warning; `grounding_number_words: fail` makes it an error. (#88)
- The letter's tagline line can be tailored: map it as `letter: headline:` in cv/layout.yaml; the builder fills it
  from `letter_headline:` in application.md (one text or `{de: ..., en: ...}`), else from `cv.headline`. A set
  `letter_headline` is grounded like the CV headline. (#90)
- Project pool: a section in cv/layout.yaml with `max: N` and `further: {starts_with: "..."}` keeps the first N
  items in the job's order as full blocks and names the others at the front of the list after ': ' on the
  further line, so the master can hold more projects than fit on 2 pages. (#91)

### Fixed
- One stale cv/variants.yaml entry (its master text no longer in the master CV) stopped every build. Now only
  builds that pick or reorder it stop; the others print a warning, and `cv_map.py check` lists stale entries. (#89)

### Migration
- Config version 2, unchanged. The new settings (`font: keep`, `never_write`, `grounding_number_words`,
  `letter_headline`, a project pool) are all optional: without them the documents stay the same
  (`upgrade.py compare`: SAME DOCUMENTS on both sample workspaces).
- `upgrade.py migrate` updates `.claude/agents/tailor.md` (it orders a project pool).

## [1.0.0] - 2026-11-01: versioned & interactive

### Added
- Release channels: `engine_channel: stable` (the default) in config.yaml updates the engine to the newest release
  tag only; `engine_channel: next` follows the `next` branch, for testers. `upgrade.py status` shows the channel and
  the update it would get, and `setup_check.py` (so the daily brief) says "engine update available (release
  vX.Y.Z)" only for a newer release on stable.
- Version stamps: the daily brief starts with `engine X.Y.Z (commit) · model <id>`, each job.md has an
  `- **Engine:**` line, and `ledger.py record --model <id>` stamps the engine version and model on every row it
  adds (as `set` already did). Your CV and letter files stay free of them: their metadata names only you.
- Commands you can type in Claude Code, as skills in `.claude/skills/` (README "Commands"): `tailor <url>`
  reads, scores and tailors one job you name; `why <job>` explains a score from its sub-scores; `sent <folder>`
  adds the tracker row, moves the folder to `_sent/` and marks the job applied; `status` (or `/job-status`; Claude
  Code's own `/status` is something else) shows drafts, follow-ups due and open actions. They use the daily run's
  tools and checks. New tool commands for them: `extract.py add <url>` and `ledger.py show <job>`.
- Decision inbox: the daily brief starts with a "Decisions" checklist (tailor a job that scored 60-69, mark
  today's drafts as sent, skip a draft 7-14 days old). Tick a box in the brief and the next run acts on it with the
  same tools and confirms it under "Done from your decisions"; unticked boxes stay on the list for 7 days. New
  tool: `decisions.py` reads the ticked boxes and logs each one it acted on in `data/decisions_done.txt`, so a
  run that stops halfway never acts on the same box twice.
- Workspace history: `setup_check.py --init` makes the workspace folder a local git repo (unless it is one already)
  with a `.gitignore` that leaves out `engine/`, `backups/` and Office temp files. Each daily run ends with
  `history.py commit` ("daily run 2026-12-14, engine v1.0.0"), so you can see or undo what a run changed. It never
  adds a remote or pushes.

### Changed
- "update the engine" on the stable channel checks out the release tag (engine/ is then on a tag, not on the
  `main` branch) instead of pulling `main`. An engine that is ahead of the newest release, for example after
  testing on next, stays where it is until a newer release comes out.
- The engine line of the daily brief moved from the Sources line in Details to the brief's first line.

### Behaviour changes
- Title filter (`profile.exclude_titles`): the seniority words `manager`, `staff`, `leiter` and `lead` now drop
  only Junior and unlabelled titles, so "Werkstudent Produktmanagement" or "Praktikum Leiterplattendesign" is
  kept. They still match inside a word ("Teamleiter", "Projektmanager"). Every other exclude word now matches at
  the start of a word only: `art` drops "Art Direction" but no longer "Startup Marketing". On the 33 labelled
  ads, no title changes result for either sample profile. `upgrade.py compare` lists the titles in your ledger
  that the new filter treats differently.

### Migration
- `upgrade.py migrate` adds `engine_channel: stable` to config.yaml when it has no channel.
- `upgrade.py migrate` (and `setup_check.py --init`) copies the four command skills into `.claude/skills/`, and
  the updated tailor subagent.
- "update the engine" runs `setup_check.py --init`, which starts the workspace history in an existing workspace.

## [0.5.0] - 2026-10-30: grounded & modular

### Added
- Grounding check in `build_application.py`: every number and every skill or tool term (the shipped list in
  `tools/skills.txt` plus your `profile.score_bonus`) in a letter or the CV headline must appear in your master
  CV, CLAUDE.md (not its "Gaps" section), projects.md, cv/variants.yaml or the job's `ad.json`, or the build fails
  with the list. A percentage needs the same percentage; "1,200" and "1.200" are the same number. Terms only the
  ad has pass with a "from the ad only" line. `grounding_ok: [term]` in application.md lets reviewed exceptions
  through.
- Tailor subagent: `.claude/agents/tailor.md` tailors one job in a fresh context (Read, Write, Edit, Glob, Grep
  and Bash only: no web, mail, browser or agent tools). It attaches the extract, writes job.md and
  application.md, builds the documents and replies with a fixed block (folder, build, pdfs, personalise,
  grounding, actions) that the routine copies into the brief.
- Skills for the on-request workflows in `.claude/skills/`: `ats-review` ("run the ATS review", "check my CV"),
  `update-engine` ("update the engine"), `remap-cv` ("remap my CV") and `onboarding` (the setup interview). The
  same phrases work as before; RULES.md lists them, so they also work before the skills are installed.
- Ledger columns `subscores` (the five rubric sub-scores), `engine_version` and `model`: `ledger.py set
  --subscores skills=4 seniority=5 language=3 location=5 hours=4 --model <id>` stores them and every `set` stamps
  the engine version. `data/seen_jobs.meta.json` holds `ledger_version: 2`. The Friday review (playbook H) compares
  sub-scores and engine versions against outcomes.
- config.yaml `university` accepts a list of names (`[Universität Mannheim, University of Mannheim]`); a student
  letter passes when it names any of them.

### Changed
- ROUTINE.md holds only the daily run; the on-request workflows moved to the skills and RULES.md "On request".
- `config.py` raises `ConfigError` instead of exiting, so code that imports a tool can catch a missing or
  incomplete config.yaml. Running a tool prints the same message as before and exits with 1.

### Behaviour changes
- **Major:** letters that passed before can fail the build: an invented metric ("increased traffic by 40%"),
  a number from nowhere, or a tool the candidate only lists under Gaps. The routine corrects the letter and
  rebuilds; it never adds facts to your files to make a letter pass.
- Each tailored job is written by its own `tailor` subagent, one after the other, so no job's ad, letter or
  build errors carry over into the next one. The brief's format stays the same; outreach notes and the ledger
  are still written by the main run.
- Scoring is unchanged: on the 33 labelled ads `tests/evals/baselines/v0.5.0.md` agrees with `v0.4.0.md` on every
  metric (in scope 29, role type 20, hard mismatch 20, score inside the range 19, tailor decision 30, German 31).

### Fixed
- `guard.py --status` cut long paths in its "refused" lines after 80 characters, so in a workspace with a long path
  the file name was lost (`...\e`). A long path now keeps its end, with `...` in front.
- "update the engine" builds your recent applications with each job's `ad.json`, so the grounding check no longer
  reports a letter as failing with the new engine because it names a term from the ad.

### Migration
- `upgrade.py migrate` (and `setup_check.py --init`) copies `.claude/agents/tailor.md` and the four skills
  in `.claude/skills/` into the workspace.
- The seen-jobs ledger gets three new columns on its next save; older rows keep them blank. Nothing to do.

## [0.4.0] - 2026-10-29: measurable judgment

### Added
- Eval harness: `python tools/eval_run.py run` judges the 33 labelled ads in `tests/evals/ads/` the way the daily
  run judges a new job (one headless `claude -p` call per ad, no tools) and writes
  `tests/evals/baselines/v<version>.md` and `.json`: agreement with the labels per metric, the model used, the
  cost. `eval_run.py compare` shows what changed between two baselines and fails when a metric drops by more than
  2 ads. The `v0.3.0` baseline (recorded before this sprint changed the scoring) and the `v0.4.0` one are checked in; the release
  checklist runs the eval before each release. For engine development only; the daily run doesn't use it.
- Ad extracts: `templates/ad_extract.schema.json` (`ad_extract_version: 1`) lists the facts the routine takes
  from a job ad: title, company, location, remote, language, role type, closed flag with the words that show it,
  German level, hours per week, start, duration, years of experience, enrolment, Pflichtpraktikum, up to 12
  requirements with their importance (playbook C) and the ad's wording, tasks, and `injection_text` for any
  instructions found in the ad. `python engine/tools/extract.py check <file or folder>` validates extracts and
  refuses links, email addresses and AI instructions in any field other than `url` and `injection_text`.
- Rubric scoring: `engine/rubric.md` holds written anchors (0-5) for five criteria (skills, seniority, language,
  location, hours/eligibility), and `python engine/tools/score.py skills=4 seniority=5 language=3 location=5 hours=4`
  turns them into the fit score with its reasons: skills sets the base (5 -> 95, 4 -> 88, 3 -> 70, 2 -> 58),
  each other criterion below 5 takes points off (4 -> 2, 3 -> 5, 2 -> 8, 1 -> 20), the `score_bonus` skills add 3
  points each (at most two) and a hard mismatch (a 0 for seniority, language, location or hours) halves the
  total. The levels were set against the labelled eval ads; config.yaml `scoring:` can change the weights of the
  deductions, which criteria are blockers, and the bonus points.
- Quarantined ad reader: the `ad-reader` subagent (`.claude/agents/ad-reader.md`) reads every ad, Indeed job,
  Gmail job alert and careers page and returns only extracts and leads as JSON. It has no write, shell or agent
  tools and doesn't load CLAUDE.md, so it knows nothing about the candidate. `python engine/tools/extract.py
  pending` lists the ads without an extract as reader tasks, `extract.py save <reply>` validates the reader's
  reply and writes `data/ads/<id>.json` (leads go through the title filter and the ledger), `extract.py read`
  is the fallback through headless `claude -p` and `extract.py attach <id> <folder>` copies the extract and the
  ad text into the job folder. `search_jobs.py` writes full ad texts to `data/ads/<id>.txt` instead of
  candidates.json.
- Ledger expiry: config.yaml `ledger_expiry_days` (default 90, 0 = never). A job the ledger has as screened,
  skipped or closed for longer than that counts as new again; `ledger.py record` reuses its row (new date, the
  old date and verdict in the note) and `ledger.py check` prints `NEW (seen <date> <verdict>, expired)`.
  Tailored, applied, rejected and interview rows never expire.

### Behaviour changes
- Fit scores come from the rubric: the routine gives five 0-5 sub-scores and score.py computes the total,
  instead of the model choosing a 0-100 number. The same judgment now always gives the same score, but scores
  can move by several points against older runs, and a hard mismatch always lands below 60 (usually
  below 40). On the 33 labelled ads (`tests/evals/baselines/v0.4.0.md` against `v0.3.0.md`): German level
  24 -> 31 agree, scores inside the labelled range 20 -> 19 (ad 02 scores 89 against [70, 88]; ad 19's location
  is judged a hard mismatch, which now pulls its score to 16), every other metric unchanged. The same ad scored
  twice stayed within 3 points.
- The routine never reads ad text itself: it judges, scores and tailors from the extract, so instructions hidden
  in an ad can't reach the context that holds the CV and the tools. job.md links `ad.json` and `ad.txt` instead of
  holding the ad text. Injection attempts in the brief come from the extract's `injection_text`.
- Jobs skipped or screened more than 90 days ago show up as new again when they're reposted or still online.

### Migration
- `upgrade.py migrate` (and `setup_check.py --init`) copies `.claude/agents/ad-reader.md` into the workspace;
  `setup_check.py` warns while it's missing. Config version stays 2.

### Fixed
- `upgrade.py migrate` no longer lists `scoring:` in config.yaml as an unknown setting.
- A deny rule for the `Agent` tool in `.claude/settings.json` kept the daily run from calling the ad reader, and
  setup_check didn't notice. `upgrade.py migrate` and `setup_check.py --init` now remove it (and print
  `removed deny Agent`) after saving the file as `.claude/settings.json.bak-<date>`; until then setup_check warns.
- A job whose ad the reader couldn't read (bot check, empty page) is no longer recorded in the ledger as screened,
  so the next run tries it again instead of never showing it. A job whose page is gone (404, 410) is recorded as
  closed and listed under "Skipped: closed".

## [0.3.0] - 2026-10-25: safe & lossless

### Added
- `VERSION` file and `engine/tools/version.py`: the engine has a version number (`0.3.0-dev` until the 0.3.0
  release). `setup_check.py` prints it on its first line (`engine_version` in `--json`), the daily brief shows
  it under Sources (weekend briefs too) and `upgrade.py status` shows the installed version and the one on GitHub.
- Releases are git tags `vX.Y.Z` on `main`; [docs/RELEASING.md](docs/RELEASING.md) explains the branches, what
  each number means and the release checklist. Earlier releases are tagged retroactively (`v0.1.0`, `v0.2.0`).
- Permission rules for the unattended run: `templates/workspace/.claude/settings.json` denies the tools that send
  or type data (Gmail send / reply / forward / drafts / trash / spam, under every connector name; browser typing,
  form filling and cookies; Drive sharing) and edits of `engine/` and `.claude/`. `setup_check.py --init` merges it
  into the workspace's `.claude/settings.json` and also makes the master CV and letter from config.yaml read-only;
  `setup_check.py` warns while rules are missing. Deny rules hold in every permission mode, auto included. They
  apply to a local Code-tab task only, not to cloud or Cowork tasks ([spike](docs/spike-scheduled-tasks.md)).
- A guard hook, `tools/hooks/guard.py`, checks tool calls before they run (defence in depth on top of the
  permission rules). It blocks writes into `engine/`, `.claude/` and the master files (also through Bash and
  PowerShell), curl / wget / WebFetch / inline Python HTTP to hosts other than the job APIs and the hosts in
  companies.md and sources.md (to.indeed.com only as the redirect lookup), URLs carrying the candidate's name,
  email, phone, address, birth date or last name (also as base64, base32, hex or double URL-encoded text in any
  path segment or query value) or a long encoded value, IP addresses and odd ports, and page scripts that make
  network calls. Browser navigation to a host outside companies.md and sources.md also refuses a shorter value
  that decodes to text or looks random; plain words in a query (`?cv=SAP+FI+5+years`) still pass.
  Every block prints a reason. `guard.py --status` says whether the guard ran this session and also lists the
  calls the permission rules refused (they never reach the hook; read from the session transcript); the brief
  shows it under Sources and lists what was blocked or refused. `setup_check.py` starts the hook once to prove it
  blocks.
- Eval seed: 33 real public ads in `tests/evals/ads/` with the labels the routine should give them for the sample
  workspace (in scope, role type, hard mismatch, score range, German level), contact data removed. Sprint 2
  records a scoring baseline against them; a test keeps the labels well-formed and the title-filter label in step
  with `scope.py`.
- Upgrade guides per release in `docs/upgrading/` ([v0.2.0 to v0.3.0](docs/upgrading/v0.3.0.md),
  [v0.1.0 to v0.2.0](docs/upgrading/v0.2.0.md)), linked from UPGRADING.md: what each update shows step by
  step, what changes in the daily run and how to check it worked.

### Changed
- This changelog uses the Keep a Changelog layout with a "Behaviour changes" heading.
- `search_jobs.py` identifies itself to the job sources as `jobhunt-agent/<version> (+repo URL)` instead of
  posing as a browser (`Mozilla/5.0`). The Arbeitsagentur and Arbeitnow APIs accept it.
- SETUP.md and the setup guide: the task must be a **Code**-tab task with "Only on this computer" and permission
  mode Auto (cloud and Cowork tasks run without the safety rules); step 5 no longer says to "always allow"
  bash, curl and python, since the rules are installed by `setup_check.py --init`.

### Behaviour changes
- When an Arbeitsagentur ad text can't be fetched, the routine tries again or opens the job page, and the brief
  says which ads couldn't be read (before, the whole search was lost).
- Which jobs count as already seen: a job at the same company now matches an earlier one only with the same
  title words (in any order, ignoring gender forms, punctuation and filler words). Jobs the old similarity check
  hid ("SAP CO" behind "SAP FI", "Senior" behind "Junior") show up as new once; reposts with reordered words or
  the other gender form (Kauffrau / Kaufmann) now count as seen.
- The daily run can no longer send or draft email, type into web pages, or change engine/, .claude/ or the master
  CV and letter: those tool calls are refused with "denied by your permission settings". Nothing in the routine
  needs them.
- curl and WebFetch only reach the job APIs and the hosts in companies.md and sources.md; other web pages are
  read with the browser. The brief gets a "guard active" line and a "Blocked by the guard" list.
- Arbeitsagentur searches follow the result pages (up to 3 of 100) instead of stopping after the first 100, so a
  broad term can bring in more jobs. A search with even more results is named in a "page limit" warning, and the
  brief suggests narrowing it.

### Migration
- `upgrade.py migrate` adds the missing permission rules and the guard hook to `.claude/settings.json`, keeping
  every rule and hook already there (`--dry-run` lists them), and copies `.claude/hooks/jobhunt_guard.py`.
  `settings.local.json` isn't touched. Config version stays 2.

### Fixed
- `search_jobs.py --details` no longer crashes when an Arbeitsagentur ad can't be fetched: candidates.json is
  written before the details (atomically), a job without its text gets `detail_error`, the status line counts
  the failures, and after 3 failures in a row the remaining ads are skipped instead of each waiting 30 s.
- The seen-jobs ledger no longer treats different jobs at one company as the same job, so they're screened
  instead of skipped as already seen. No migration: existing rows are matched by their titles.
- The seen-jobs ledger is saved through a temp file, so a run stopped while saving keeps the old ledger instead
  of a half-written one.

## [0.2.0] - 2026-10-24: smoother updates, German letters

Config version 2.

### Added
- `update the engine` / UPGRADING.md and `engine/tools/upgrade.py`: backup, local edits kept, config migrated,
  documents compared old against new, rollback.
- The daily brief says when an engine update is available; setup_check warns about edits inside engine/.
- custom.md: a wish list for things the engine can't do yet.
- cv/layout.yaml `cv.date`: a "City, DD.MM.YYYY" line on the CV follows the letter date.
- cv/layout.yaml item rule `not_list` (projects whose bullets are Word list items) and list-valued `name_split`.
- config.yaml `letter_languages` / application.md `languages: [de, en]`: one letter per language, with German
  checks ("ab sofort", "Stunden pro Woche", German phrases to avoid).
- config.yaml `name_in_master`: the name as your master files spell it, replaced by `applicant`.
- config.yaml `search.areas` (search these places instead of nationwide) and `search.regions` / `region_plz` /
  `region_places` (keep only jobs in these federal states, e.g. Bayern).

### Changed
- cv/layout.yaml `letter.closing`: the letter body ends at the closing line, also without an empty line before it.
- cv/layout.yaml `letter.recipient`: the whole address block (several lines) is replaced; application.md
  `recipient:` can be a list of lines.

## [0.1.0] - 2026-10-23: any field

Config version 2.

### Added
- ATS review of your CV and letter ("run the ATS review"); `pdf_engine` (Word or LibreOffice);
  `internship_duration`.

### Changed
- config.yaml `profile:` replaces the job-title filter that was hardcoded for IT roles.
- cv/layout.yaml (the CV map): the builder works with your own CV design instead of one fixed two-column table.

### Behaviour changes
- Which job titles are kept now comes from your `profile:` block instead of a fixed list of IT titles.

### Migration
- config.yaml moves to config version 2 (`profile:` and the CV map). Workspaces from before 0.1.0: say "update
  the engine" (0.2.0's `upgrade.py migrate` does it).

## Before 0.1.0

Config version 1.

- IT job titles only (search_jobs.py), one fixed two-column table CV, Word on Windows for PDFs.

[Unreleased]: https://github.com/Jaival/jobhunt-agent/compare/v1.1.0...next
[1.1.0]: https://github.com/Jaival/jobhunt-agent/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Jaival/jobhunt-agent/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/Jaival/jobhunt-agent/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Jaival/jobhunt-agent/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Jaival/jobhunt-agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Jaival/jobhunt-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Jaival/jobhunt-agent/releases/tag/v0.1.0
