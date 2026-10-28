# Eval seed (S1-12)

33 real job ads with the labels the routine should give them for the **sample workspace**
(`examples/sample-workspace`: Lena Fischer, a media and communication student in Mannheim looking for marketing,
content, social media and communication roles; Rhine-Neckar area or remote). Sprint 2's `tools/eval_run.py` (S2-5)
runs the model parts of the routine on these ads and compares the result with the labels, so a scoring change can
be measured against a baseline.

## The ads
`ads/NN-<slug>.md`: YAML frontmatter, then the ad text as the Arbeitsagentur API returned it on the fetch date.
All ads are public postings from the Arbeitsagentur job board, fetched 2026-10-25. Contact names, email addresses
and phone numbers are replaced with `[name removed]`, `[email removed]` and `[phone removed]`; company names and
business addresses stay. The ads will close over time; the stored text is what counts, not the live URL.

The mix: 9 ads in her field near home (good fits to weak ones), 12 in her field but outside her area, and 12 out
of scope (sales, engineering, senior roles, an apprenticeship, a freelance trainer contract). Several are picked
because the title filter gets them wrong (a good fit it drops, or a near miss it keeps).

## Labels (`expected:`)
| Key | Values | Meaning |
|---|---|---|
| `title_filter` | `pass` / `drop` | What `search_jobs.py`'s title filter (`scope.py` with the sample profile) does with the title. Checked by `tests/test_eval_seed.py`, so it always matches the code; update it when the profile or filter changes on purpose. |
| `in_scope` | `true` / `false` | After reading the ad (routine step 3): her field and a role type she wants, not senior in disguise. Location doesn't count here. |
| `role_type` | Werkstudent / Internship / HiWi / Thesis / Junior / Other | Corrected from the ad, as step 3 asks (the title guess can differ). `Other` = none of the wanted types. |
| `hard_mismatch` | `null` or a reason | A blocker from step 4 or CLAUDE.md, e.g. `location: Berlin` (her CLAUDE.md: anything outside Rhine-Neckar or remote is a hard mismatch). Gaps in tools are never a hard mismatch for student roles. |
| `score` | `[low, high]` or `null` | Acceptable range for the 0-100 fit score (step 4). `null` for out-of-scope ads, which aren't scored. A hard mismatch keeps the score below 60. |
| `german_required` | none / basic / B2 / C1+ / unknown | As step 4 defines it ("sehr gute Deutschkenntnisse" counts as C1+). |
| `note` | text | Why, in one or two sentences, for whoever reviews a disagreement. |

Score ranges are judgement calls, deliberately wide: an eval run counts a score inside the range as agreement.
The labels that matter most are the clear ones: in scope or not, hard mismatch or not, and whether a job lands
above the tailoring threshold of 70 (ads 01-04 should, ads 05-07 are borderline, the rest shouldn't).

## Running an eval
`python tools/eval_run.py run` (from the engine folder) judges every ad the way the daily run judges a new job,
with a headless `claude -p` call per ad (no tools, an empty working folder), and grades the answers against the
labels. The prompt is built from this checkout's ROUTINE.md, RULES.md, rubric.md and the sample workspace, and score.py
turns the sub-scores into the fit score, so a run measures
the engine as it is. It writes `baselines/v<VERSION>.json` (every answer) and `baselines/v<VERSION>.md` (the
summary, disagreements in bold); `--label 0.3.0` names the files after another version, `--model` picks the model,
`--only 01,07` runs a few ads. A full run takes a few minutes and costs about $2-3 on Opus.

`python tools/eval_run.py compare baselines/v0.3.0.json baselines/v0.4.0.json` prints each metric's change and
exits 1 when one agrees on more than 2 ads fewer (`--tolerance`). Model answers vary from run to run, so a
drop of one or two ads is noise; read the disagreements in the .md before blaming a change. The release
checklist ([docs/RELEASING.md](../../docs/RELEASING.md)) runs both before each release.

| Metric | Counts |
|---|---|
| In scope | every ad |
| Role type, hard mismatch yes/no, score inside the range | in-scope ads |
| Tailor decision | ads whose label is clear about tailoring: score range all at or above 70 with no hard mismatch (tailor), or all below 70, a hard mismatch or out of scope (don't) |
| German level | every ad |

Only the grading and comparison are tested in CI (`tests/test_eval_run.py`); the model runs are on demand.
`baselines/v0.3.0.*` was recorded with the v0.3.0 routine (holistic 0-100 scoring) before Sprint 2 changed it.
