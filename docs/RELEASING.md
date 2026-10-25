# Releasing the engine

How the engine is branched, versioned and released. Users get the engine through "update the engine"
([UPGRADING.md](../UPGRADING.md)), which follows `main`, so `main` only moves when a release is tagged.

## Branches
- **`main` is stable:** it only moves when a release is merged and tagged. `upgrade.py` and the "update
  available" check in `setup_check.py` follow it.
- **`next`** collects the work for the next release. Every change is a feature branch named after its issue
  (`s1-4-details-crash`) and a PR into `next` that closes the issue.
- **Release:** a release branch from `next` sets `VERSION` and the CHANGELOG heading, PR into `main`, merge,
  then tag `vX.Y.Z` on `main` and merge `main` back into `next` (see the checklist).
- **Hotfix:** branch from `main`, fix, set `VERSION` to the PATCH version and add its CHANGELOG section, PR into
  `main`, tag it, then merge `main` back into `next` (keeping `next`'s `-dev` VERSION).
- **Develop in a separate clone**, never in a workspace's `engine/`: that copy runs the daily routine and
  `setup_check.py` warns about edits in it. The maintainer's own workspace is the first user of each release.

## What gets versioned
An agent's behaviour comes from its **code** (`tools/`), its **prompts** (ROUTINE.md, RULES.md, the playbook,
ONBOARDING.md, ats-checklist.md), the **file formats** a workspace depends on, and the **model** that runs it.

| Thing | How it's versioned | Where |
|---|---|---|
| Engine (code + prompts) | One semantic version, `MAJOR.MINOR.PATCH` | `VERSION`, git tag `vX.Y.Z`, GitHub Release |
| Workspace formats | An integer per format, bumped only when a migration is needed | `config_version` in config.yaml (`CONFIG_VERSION` in `setup_check.py`) |
| Model | Not pinned; each release says which model it was tried with | Release notes |

Prompts aren't versioned separately: they ship in the same tag as the code that calls them, so a release is
always a tested combination.

## What the numbers mean
- **MAJOR:** the workspace needs a migration that changes the user's files, or a rule changes what documents
  say (for example a check that fails builds that passed before).
- **MINOR:** new features or settings, or prompt changes that change behaviour without a migration (a new
  source, a new brief section, different scoring). These go under **Behaviour changes** in the CHANGELOG.
- **PATCH:** bug and doc fixes that don't change documents or scores for an unchanged workspace.

Until 1.0.0, a migration or document-changing rule bumps MINOR instead of MAJOR; each sprint ends with a minor
release.

## The VERSION file
- On `main` it holds the released version (`0.3.0`), equal to the tag without the `v`.
- On `next` it holds the coming version with `-dev` (`0.4.0-dev`), so a development engine never claims to be a
  release.
- `python engine/tools/version.py` prints it with the commit (`-dirty` when engine/ has local edits);
  `setup_check.py` prints it on its first line, the daily brief copies it and `upgrade.py status` shows it.

## Changelog
[CHANGELOG.md](../CHANGELOG.md) follows Keep a Changelog. Every PR into `next` adds its lines under
`## [Unreleased]`, under Added / Changed / **Behaviour changes** / Fixed / Migration. "update the engine" reads
the changelog to match the user's wishes in custom.md, so write entries for users: name the setting or the
effect, not the function.

## Release checklist
1. Tests pass on `next` (CI on Windows, Ubuntu and macOS).
2. `upgrade.py compare` on both sample workspaces (`examples/`): documents identical, or the differences
   explained in the CHANGELOG.
3. The guard test in [tests/evals/guard-test.md](../tests/evals/guard-test.md): every forced attempt is stopped
   and the brief lists it.
4. Branch `release-X.Y.Z` from `next`: set `VERSION` to `X.Y.Z`; rename `## [Unreleased]` to
   `## [X.Y.Z] - YYYY-MM-DD: <short title>`, add a new empty `## [Unreleased]` above it, and update the
   compare links at the bottom.
5. PR `release-X.Y.Z` → `main`, merge. (`next` never gets a release `VERSION`: it keeps `-dev`.)
6. Tag the merged commit and push the tag:
   ```
   git fetch origin
   git show origin/main:VERSION          # must print X.Y.Z; if not, the merge isn't there yet
   git tag -a vX.Y.Z -m "vX.Y.Z" origin/main
   git push origin vX.Y.Z
   ```
   Create the GitHub Release from the CHANGELOG section (by hand until the release workflow exists).
7. PR `main` → `next` to bring the CHANGELOG section back, and in it set `VERSION` to the next `-dev` version
   (e.g. `0.4.0-dev`), so `next` never claims a release number.
8. Update the maintainer's own workspace with "update the engine" and watch the next daily run.

## Tags so far
| Tag | Commit | Date | What |
|---|---|---|---|
| `v0.1.0` | `2db97fa` | 2026-10-23 | Any field (PR #1), tagged retroactively |
| `v0.2.0` | `62eca7d` | 2026-10-24 | Smoother updates, German letters (PR #2), tagged retroactively |
