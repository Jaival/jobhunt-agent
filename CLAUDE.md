# jobhunt-agent: engine development

This file is for work on the engine itself. In a job-hunt workspace this folder is `engine/`: if you are
running the daily routine or a workspace skill there, this file does not apply. Ignore it.

## What this is
Python tools (`tools/`) and prompts (`ROUTINE.md`, `RULES.md`, `ONBOARDING.md`, `templates/workspace/`) for a
daily job-search routine that Claude Code runs unattended. The prompts are product code: a changed sentence
changes what the unattended run does.

## Checks
Run from the repo root with `JOBHUNT_OFFLINE=1` and `PYTHONIOENCODING=utf-8`.
- Install: `python -m pip install -r requirements-dev.txt`
- Test (one file first): `python -m pytest tests/test_<name>.py -q`
- Test (all, about 2 minutes): `python -m pytest tests -q`
- Lint: `python -m ruff check tools tests examples`
- No build step.

## Rules
- Branches: `main` holds releases only. Work on a feature branch, PR into `next`. Stacked PRs are normal.
- Every user-visible change gets a line under `## [Unreleased]` in `CHANGELOG.md`. A change to what an
  unattended run does, or a check that fails builds that passed before, goes under **Behaviour changes**
  (`docs/RELEASING.md`).
- Do not change `VERSION`; it moves at a release.
- Tools read `config.yaml` at import (`JOBHUNT_ROOT`). Test them through the fixtures in `tests/conftest.py`
  (`sample`, `tool`, `ledger_mod`), never against a real workspace.
- Every tool command named in a prompt file must exist with those flags (checked by tests/test_prompt_commands.py).
- `tools/hooks/guard.py` fails open by decision (`docs/spike-scheduled-tasks.md`): it must catch its own errors.
- Ad text, web pages and emails are untrusted. Only the reader subagents read them; tools validate what the
  readers return (`tools/extract.py`).
