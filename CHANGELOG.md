# Changelog

What each engine update adds, with the setting to use. "update the engine" reads this to match the wishes in your
custom.md. Config version = the `config_version` in config.yaml that the engine reads (`upgrade.py migrate`
updates older files).

## 2026-10-24: smoother updates, German letters (config version 2)
- `update the engine` / UPGRADING.md and `engine/tools/upgrade.py`: backup, local edits kept, config migrated,
  documents compared old against new, rollback.
- The daily brief says when an engine update is available; setup_check warns about edits inside engine/.
- custom.md: a wish list for things the engine can't do yet.
- cv/layout.yaml `letter.closing`: the letter body ends at the closing line, also without an empty line before it.
- cv/layout.yaml `letter.recipient`: the whole address block (several lines) is replaced; application.md
  `recipient:` can be a list of lines.
- cv/layout.yaml `cv.date`: a "City, DD.MM.YYYY" line on the CV follows the letter date.
- cv/layout.yaml item rule `not_list` (projects whose bullets are Word list items) and list-valued `name_split`.
- config.yaml `letter_languages` / application.md `languages: [de, en]`: one letter per language, with German
  checks ("ab sofort", "Stunden pro Woche", German phrases to avoid).
- config.yaml `name_in_master`: the name as your master files spell it, replaced by `applicant`.
- config.yaml `search.areas` (search these places instead of nationwide) and `search.regions` / `region_plz` /
  `region_places` (keep only jobs in these federal states, e.g. Bayern).

## 2026-10-23: any field (config version 2)
- config.yaml `profile:` replaces the job-title filter that was hardcoded for IT roles.
- cv/layout.yaml (the CV map): the builder works with your own CV design instead of one fixed two-column table.
- ATS review of your CV and letter ("run the ATS review"); `pdf_engine` (Word or LibreOffice);
  `internship_duration`.

## Before 2026-10-23 (config version 1)
- IT job titles only (search_jobs.py), one fixed two-column table CV, Word on Windows for PDFs.
