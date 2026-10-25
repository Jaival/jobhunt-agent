# Updating the engine

The engine (this folder, `engine/` in your workspace) gets new features and fixes. Your own files (config.yaml,
CLAUDE.md, your CV, applications) stay yours, and an update never changes them without showing you first.

**How you hear about it:** when GitHub has a newer engine, the daily brief says "engine update available: say
'update the engine'". Nothing is installed on its own.

**How to update:** open your workspace folder in Claude Code (Claude Desktop's **Code** tab, the same place your
scheduled task runs) and say **update the engine**. Claude:

1. backs up config.yaml, CLAUDE.md, custom.md and your cv/ folder to `backups/pre-upgrade-<date>/`;
2. keeps any changes someone made inside `engine/` (saved as a patch, and set aside with git) and tells you which
   of them the new engine now has a setting for;
3. pulls the new engine and brings config.yaml up to date (`engine/tools/upgrade.py migrate`);
4. builds a test application, plus up to 5 of your real ones, with the old and the new engine, compares the
   documents and your job-title filter, and shows you every difference in plain words;
5. only removes the temporary copies after you say yes. `upgrade.py rollback` puts everything back.

Wishes the engine can't do yet go in `custom.md` in your workspace, never into `engine/` itself (edits there
block updates). On each update Claude checks them against [CHANGELOG.md](CHANGELOG.md) and drafts a GitHub issue
for the rest, which you can post if you like.

## Guides per release

What each release changes in your workspace and daily run, what the update shows you, and how to check it:

- [v0.2.0 to v0.3.0](docs/upgrading/v0.3.0.md): permission rules and a guard for the daily run, no lost jobs.
- [v0.1.0 to v0.2.0](docs/upgrading/v0.2.0.md): the first "update the engine", German letters. Also for
  workspaces from before v0.1.0.

## First update from an older engine

Engines from before October 2026 don't know "update the engine" yet. Paste this into Claude Code, opened in your
workspace folder (the one that contains `engine/` and `config.yaml`):

```text
Update my job-hunt engine safely. Work in this folder (it contains engine/ and config.yaml). First check that you
can run commands here (git --version, python --version); if you can't, stop and tell me to open this folder in
Claude Code's Code tab. Then run `git -C engine fetch origin`, read the update instructions with
`git -C engine show origin/main:UPGRADING.md`, and follow its "Steps for Claude". Don't commit, push or delete
anything without asking me.
```

## Steps for Claude

Run everything from the workspace folder. Explain each result to the user in plain words; they may not be
technical. Never edit files in engine/ yourself.

0. **Can you run commands?** Run `git --version` and `python --version`. If this session can't run commands on
   the user's computer, stop: tell them to open the workspace folder in Claude Desktop's Code tab and say "update
   the engine" there. Don't work in a copy somewhere else.
1. **Fetch the new engine next to the old one:** `git -C engine fetch origin`, then
   `git -C engine worktree add ../engine-new origin/main` (engine-new/ sits in the workspace; remove a stale one
   first with `git -C engine worktree remove --force ../engine-new`). Add `engine-new/` to .gitignore if the
   workspace is a git repo.
2. **Look:** `python engine-new/tools/upgrade.py status`. Summarise: engine version, how many new changes and what
   they are (the commit titles), local edits in engine/, config version. If the workspace is a git repo with
   uncommitted changes, say so and ask whether to continue.
3. **Back up:** `python engine-new/tools/upgrade.py prepare`. If engine/ had local edits, read
   `backups/pre-upgrade-<date>/engine-local-changes.patch`. For every change, say which new setting does the same
   job (prepare lists the ones it recognises) or, if none does, draft a wish for custom.md (copy
   engine/templates/workspace/custom.md if the file doesn't exist) and show it. Ask: "Update now? Your edits are
   kept in the backup and in git, and 'rollback' brings them back." Continue only on a yes.
4. **Update:** `python engine-new/tools/upgrade.py apply`.
5. **Settings:** `python engine/tools/upgrade.py migrate`. It prints what it wrote, runs the CV map check and adds
   missing permission rules to `.claude/settings.json` (existing rules stay).
   - "permission rules: NOT INSTALLED": the file isn't valid JSON. Show the user the error, fix the file with
     their OK, and run `python engine/tools/setup_check.py --init`.
   - "CV map: PROBLEMS": fix cv/layout.yaml with `python engine/tools/cv_map.py outline <file>` (the format is at
     the top of engine/tools/cv_map.py) until `python engine/tools/cv_map.py check` says OK.
   - "not read by this engine": find out what the key did (the patch, the old engine's code in
     backups/pre-upgrade-<date>/engine-old/). If a new setting covers it, use it; otherwise it's a custom.md wish.
6. **Check:** `python engine/tools/setup_check.py --init` must say READY. Fix every TODO; explain the warnings.
7. **Prove it:** `python engine/tools/upgrade.py compare`. "SAME DOCUMENTS" means the new engine builds exactly
   what the old one did and keeps the same job titles. For each difference, look at the built files in
   backups/pre-upgrade-<date>/test/ and explain it: a fix in the new engine (say what it fixes), a setting that
   needs adjusting (adjust it and compare again), or a real problem (stop; offer `upgrade.py rollback`). Continue
   only when the user accepts the result.
8. **Offers (each only on a yes, after showing the change):**
   - The migrated `profile:` keeps the old title filter exactly. If CLAUDE.md describes a narrower search (for
     example junior roles only, or another field), propose the narrower profile and show which ledger titles it
     would drop.
   - Wishes in custom.md: read [CHANGELOG.md](CHANGELOG.md). Mark each wish the new engine covers
     (`- Status: covered by <setting> (<date>)`) and offer to set it up. For each open wish, draft a GitHub issue
     (title and a short body: what, why, an example) the user can paste at
     https://github.com/Jaival/jobhunt-agent/issues/new. Never post it yourself.
9. **Finish:** after the user's yes, `python engine/tools/upgrade.py finish` (removes engine-new/, the test
   builds and the saved engine copy; keeps the backup). Summarise: engine version old -> new, what changed in
   config.yaml and cv/layout.yaml, the compare result, and anything still to decide. If the workspace is a git
   repo, suggest a commit message, but don't commit until the user says so.

## If something goes wrong

- `python engine/tools/upgrade.py rollback` (or `python engine-new/tools/upgrade.py rollback` before step 4
  finished): the old engine version, its local edits and the old config.yaml come back; a cv/layout.yaml the
  update wrote is moved into the backup folder.
- By hand: `git -C engine reset --hard <old commit>` (in backups/pre-upgrade-<date>/upgrade.json), then
  `git -C engine stash pop` if the edits were set aside, and copy config.yaml back from the backup.
- "remap my CV" rebuilds cv/layout.yaml when an anchor no longer matches.
