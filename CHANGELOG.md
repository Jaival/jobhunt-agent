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

### Added
- `VERSION` file and `engine/tools/version.py`: the engine has a version number (`0.3.0-dev` until the 0.3.0
  release). `setup_check.py` prints it on its first line (`engine_version` in `--json`), the daily brief shows
  it under Sources (weekend briefs too) and `upgrade.py status` shows the installed version and the one on GitHub.
- Releases are git tags `vX.Y.Z` on `main`; [docs/RELEASING.md](docs/RELEASING.md) explains the branches, what
  each number means and the release checklist. Earlier releases are tagged retroactively (`v0.1.0`, `v0.2.0`).

### Changed
- This changelog uses the Keep a Changelog layout with a "Behaviour changes" heading.
- `search_jobs.py` identifies itself to the job sources as `jobhunt-agent/<version> (+repo URL)` instead of
  posing as a browser (`Mozilla/5.0`). The Arbeitsagentur and Arbeitnow APIs accept it.

### Behaviour changes
- When an Arbeitsagentur ad text can't be fetched, the routine tries again or opens the job page, and the brief
  says which ads couldn't be read (before, the whole search was lost).
- Which jobs count as already seen: a job at the same company now matches an earlier one only with the same
  title words (in any order, ignoring gender forms, punctuation and filler words). Jobs the old similarity check
  hid ("SAP CO" behind "SAP FI", "Senior" behind "Junior") show up as new once; reposts with reordered words or
  the other gender form (Kauffrau / Kaufmann) now count as seen.

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

[Unreleased]: https://github.com/Jaival/jobhunt-agent/compare/v0.2.0...next
[0.2.0]: https://github.com/Jaival/jobhunt-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Jaival/jobhunt-agent/releases/tag/v0.1.0
