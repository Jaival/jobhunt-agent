# Upgrading a workspace set up with the old engine

Workspaces set up before the "any field" update (the version that hardcoded IT job titles and needed one fixed
two-column CV layout) need three new things after `git pull`, or the routine stops:

- a `profile:` block in config.yaml: which job titles to keep (search_jobs.py exits without it);
- `cv/layout.yaml`, a map of your master CV and letter (the builder stops without it);
- optional new settings: `internship_duration`, `pdf_engine`.

You don't have to do this by hand. Open Claude Code in your **workspace folder** (the one that contains
`engine/`), paste the prompt below, and answer its questions. It keeps your current behaviour exactly,
proves it by comparing old and new results, and changes nothing it can't undo.

## The prompt

```text
Upgrade my job-hunt workspace to the new jobhunt-agent engine, safely. Work in this folder (it contains
engine/, config.yaml and CLAUDE.md). Don't change my CV, my letter, CLAUDE.md facts or any application
folder; don't commit, push or delete anything without asking me. Stop and ask if anything below doesn't match
what you find.

1. Safety first
   - Run `git -C engine status --short`. If engine/ has local changes, stop and show them to me.
   - Note the current engine version: `git -C engine rev-parse HEAD` (call it OLD).
   - Copy config.yaml, CLAUDE.md and cv/ to backups/pre-upgrade-<today>/ (create the folder).
   - If this folder is a git repo with uncommitted changes, tell me and ask whether to continue.

2. Update the engine
   - `git -C engine pull --ff-only`. If that fails, stop and tell me why.
   - Keep the old version next to it for comparison: `git -C engine worktree add ../engine-old OLD`
     (engine-old/ sits in this folder, so its tools find my config and CV). Add `engine-old/` to .gitignore
     if this folder is a git repo.
   - Read engine/README.md, engine/UPGRADING.md and engine/templates/workspace/config.yaml for the new keys.

3. Title filter (profile: in config.yaml)
   - Add this block, which reproduces the old hardcoded filter exactly (with one bug fixed: "tga" had a stray
     character and never matched):
       profile:
         role_types: [Werkstudent, HiWi, Internship, Thesis, Junior]
         include_titles: [devops, cloud, platform, plattform, infrastru, '\bsre\b', reliabil, linux,
                          'system ?admin', systemadmin, system engineer, systems engineer, kubernetes, network,
                          netzwerk, it-admin, '\bit\b', informatik, security, sicherheit, software, backend,
                          frontend, 'full.?stack', entwickl, developer, web, app, mobile, python, test, 'qa\b',
                          quality, automation, automatisierung, engineer]
         junior_include_titles: [devops, cloud, platform, plattform, infrastru, '\bsre\b', reliabil, linux,
                                 'system ?admin', systemadmin, system engineer, systems engineer, kubernetes,
                                 network, netzwerk, it-admin, '\bit\b', informatik, security, sicherheit]
         junior_exclude_titles: [informatik]
         exclude_titles: [senior, '\blead\b', principal, staff, architect, architekt, manager, leiter, head of,
                          director, vertrieb, sales, marketing, recruit, buchhalt, accounting, finanz, einkauf,
                          procurement, ausbildung, azubi, dozent, logopäd, lager, empfang, 'bar &', 'service \(',
                          social media, design, elektro, mechan, maschinenbau, gebäude, '\btga\b', flight,
                          unsolicited, initiativ, fachinformatiker, wirtschaftsinformatiker]
         score_bonus: []
   - Fill score_bonus from the skills my CLAUDE.md "Routine settings" say should add points (ask me if unclear).
   - Prove it: run each version's in_scope over every title in data/seen_jobs.csv (column "title"), for
     example with a small script in backups/ that imports search_jobs from engine-old/tools and then, in a
     separate process, from engine/tools, and writes {title: kept} to two JSON files. Show me every title
     whose result differs. Only "...tga..." titles may differ; anything else means the profile is wrong.
   - Then ask me whether I want to change the profile (for example narrow it to my field). Change it only on
     a yes, after showing the result.

4. CV map (cv/layout.yaml)
   - The old builder expected: the CV is one table; the headline is the 2nd paragraph of the header cell; a
     PROJECTS section ends at EXPERIENCE, each project a title line ("Name, description") followed by a line
     with "|"; a "Skills" block of ability headings with "- " bullets ending at "LEADERSHIP & INITIATIVE"; a
     "Technical Proficiency" block of "Name: ..." lines. In the letter: paragraph 4 = date, 5 = recipient,
     6 = subject, 8 = greeting (1-based), body until the first empty paragraph.
   - Run `python engine/tools/cv_map.py outline <master_cv>` and the same for master_letter (paths in
     config.yaml). Write cv/layout.yaml following the format at the top of engine/tools/cv_map.py. Name the
     sections projects, abilities and technical, so my existing application.md files keep working. A
     starting point (adjust anchors and skip to what the outline shows):
       cv:
         headline: {after: "<the line before the headline, usually my name>"}
         sections:
           projects:  {start: PROJECTS, end: [EXPERIENCE], items: blank_line, title_marker: "|", name_split: ","}
           abilities: {start: Skills, end: [LEADERSHIP & INITIATIVE], items: no_dash}
           technical: {start: Technical Proficiency, skip: <lines between heading and first "Name:" line>,
                       items: colon, name_split: ":"}
       letter:
         date: {starts_with: "<letter_city>,"}
         recipient: {text: "<paragraph 5 exactly>"}
         subject: {starts_with: "<start of paragraph 6>"}
         greeting: {starts_with: "<start of paragraph 8>"}
   - Add `layout: cv/layout.yaml` to config.yaml. Run `python engine/tools/cv_map.py check` until it says OK
     and the item names match the ones my application.md files use.

5. Other settings in config.yaml
   - internship_duration: the old builder required "12 months" in internship letters. Use the duration from my
     CLAUDE.md (Rule 9 values / availability); if none is there, ask me.
   - pdf_engine: word (what the old engine used; LibreOffice may not see my fonts). Mention that auto also
     falls back to LibreOffice if I ever want that.
   - The new onboarding records a kept CV layout as a decision. Ask me whether to add to CLAUDE.md "My
     decisions on the rules": "CV layout (my decision, <today>): the two-column table layout stays; ATS checks
     and CV reviews don't flag it again." Add it only on a yes.

6. Prove the builder still makes the same documents
   - Pick up to 5 folders in applications/ (or applications/_sent/) that have an application.md. For each,
     copy only application.md to backups/upgrade-test/old/<folder>/ and backups/upgrade-test/new/<folder>/.
   - Build each copy with `--no-pdf`: old ones with engine-old/tools/build_application.py, new ones with
     engine/tools/build_application.py (pass the full path of the copy).
   - Compare each pair of .docx files part by part (they are zip files), ignoring docProps/core.xml (it holds
     the build time). Report: identical / different (which part) / failed in both the same way.
   - If any differ, stop and show me; don't continue until we understand why.

7. Finish
   - `python engine/tools/setup_check.py` must say READY. Fix or explain every TODO and warning.
   - Remove the old copy: `git -C engine worktree remove ../engine-old`, and delete backups/upgrade-test/
     after asking me. Keep backups/pre-upgrade-<today>/.
   - Summarise: engine version OLD -> new, what you added to config.yaml and cv/layout.yaml, the title and
     builder comparison results, and anything I should decide. Optional next step to mention: say "run the ATS
     review" to have my CV and letter checked with the new checklist.
   - If this folder is a git repo, suggest a commit message, but don't commit until I say so.
```

## If something goes wrong

- Put the old engine back: `git -C engine checkout <OLD>` (the prompt notes the version first), and restore
  config.yaml from `backups/pre-upgrade-<date>/`.
- "remap my CV": rebuilds cv/layout.yaml when an anchor no longer matches.
