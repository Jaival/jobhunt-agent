# Fit-score rubric

Routine step 4 scores each in-scope job with five sub-scores from 0 to 5, one per criterion below. Pick the
anchor that fits best; use the number between two anchors when the job sits between them. The candidate's
facts come from CLAUDE.md and the master CV only; the job's facts from the ad (its extract, from v0.4.0 on).
`python engine/tools/score.py` turns the sub-scores into the 0-100 fit score, not judged here: skills sets the
base (4 -> 88, 3 -> 70, 2 -> 58), each other criterion below 5 takes points off, `score_bonus` skills add points
and a hard mismatch halves the total (details in score.py, settings in config.yaml `scoring:`). So skills
decides how good a fit is; the other four mostly say what stands in the way.

**A 0 is a hard mismatch** for seniority, language, location and hours: give a 0 only when the anchor's 0 case
applies, and say why in the reasons. A 0 for skills is not a hard mismatch (a job outside the candidate's field
is out of scope in step 3 and isn't scored at all). Decisions in CLAUDE.md override these anchors, as they
override RULES.md (for example "German C1 roles are fine for student roles" or "Berlin is fine").

## skills: overlap with the candidate's real strengths
Count the ad's critical and high requirements and its main tasks against the strengths, confirmed facts and
projects in CLAUDE.md and the master CV. Student roles score against the skills listed in CLAUDE.md "Routine
settings"; tools the candidate doesn't have yet are gaps that lower this score, never a 0.

| Score | Anchor |
|---|---|
| 5 | Nearly every critical and high requirement and the main tasks are backed by real evidence (a project, a job, a confirmed fact) |
| 4 | Most critical and high requirements backed by evidence; the gaps are preferred items or one tool that can be learned quickly |
| 3 | About half backed; the rest adjacent experience the candidate can describe as transferable |
| 2 | The field fits, but only a few requirements are backed; the main tasks are new to the candidate |
| 1 | The field fits on paper only; almost nothing in the ad is backed |
| 0 | Nothing in the ad matches the candidate's strengths |

HiWi roles at the institutes CLAUDE.md "Routine settings" lists: one point more (at most 5).

## seniority: does the level fit
| Score | Anchor |
|---|---|
| 5 | A role type the candidate wants (config.yaml `profile.role_types`) asking no professional experience beyond what the candidate has |
| 4 | Wanted role type; asks for first experience (an internship, a working-student job) that the candidate has |
| 3 | Junior role asking 1-2 years the candidate has only partly, or a student role asking for prior experience the candidate lacks |
| 2 | Asks 2-3 years for a junior role, or the tasks read like an experienced role despite the title |
| 1 | Asks 3-4 years, or full ownership of a function |
| 0 | Senior-only: 5+ years, people management, or "experienced professional" (RULES.md rule 3) |

## language: the ad's language requirements against the candidate's levels
German levels as defined in the extract: C1+ ("sehr gute", fluent, verhandlungssicher, Muttersprache), B2
("gute"), basic, none, unknown. Do the same for other required languages, English included.

| Score | Anchor |
|---|---|
| 5 | The candidate meets every required language level with room to spare, or none is required |
| 4 | Meets every requirement; or unknown (a German ad that states no level) and the candidate is at least B2 |
| 3 | Unknown requirement and the candidate is below B2 in the ad's language; or one level short on a preferred language |
| 2 | One level short on a required language for a student role (flag it; RULES.md rule 2 says how the letter handles it) |
| 1 | Two or more levels short on a required language for a student role |
| 0 | A junior role requiring C1+ in a language the candidate has below C1, unless CLAUDE.md records a different decision (RULES.md rule 3; ROUTINE.md step 4) |

## location: the workplace against CLAUDE.md "Routine settings"
| Score | Anchor |
|---|---|
| 5 | Fully remote, or in the candidate's home city |
| 4 | Within the area CLAUDE.md accepts, an easy commute; or hybrid with an office in that area |
| 3 | Inside the accepted area but a long commute; or the location is unknown (the job has `location_check` or the ad doesn't say): note it under gaps |
| 2 | Outside the accepted area, but CLAUDE.md says the candidate would relocate or travel for such roles |
| 1 | Outside the accepted area, but the ad offers working mostly from home ("home office possible", on-site only now and then) |
| 0 | Outside the area CLAUDE.md accepts, on-site or hybrid (regular office days there), when CLAUDE.md doesn't accept that place (its hard-mismatch rule, for example "anything further is a hard mismatch") |

## hours: hours, start, duration and eligibility
Against the availability in CLAUDE.md (hours per week in semester and in breaks, earliest start, internship
duration) and the enrolment conditions (RULES.md rule 3).

| Score | Anchor |
|---|---|
| 5 | Hours, start and duration all fit; the candidate meets the enrolment conditions |
| 4 | Fits with one small difference (a few more hours than the semester availability, a start a few weeks later) |
| 3 | Not stated (hours, start or duration unknown): note it under gaps; or a larger difference that is usually negotiable |
| 2 | Clearly more hours than the availability (a full-time role for a student: the letter asks about a part-time arrangement, RULES.md rule 9), or a duration the candidate can't fully offer |
| 1 | Pflichtpraktikum only (mandatory internships): "check eligibility" under gaps, never a 0 |
| 0 | The candidate can't be eligible: enrolment required for the whole contract and the candidate won't be enrolled, or a condition the ad makes explicit that the candidate doesn't meet |
