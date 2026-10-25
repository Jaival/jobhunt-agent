# First-run setup: interview the candidate and fill in the workspace

ROUTINE.md step 0 sends you here when `python engine/tools/setup_check.py` reports anything as TODO.
Don't search for jobs during setup. The goal is a workspace that passes the check, built only from what
the candidate tells you or what is in their own CV.

## Ground rules
- Never edit files in engine/ (local edits block updates). What the candidate wants that config.yaml, the CV map or
  CLAUDE.md can't express goes in custom.md as a wish (engine/templates/workspace/custom.md shows the format).
- Ask, don't guess. Every fact in CLAUDE.md and projects.md must come from the candidate's answers or their CV.
  If something is unclear, ask a follow-up instead of filling the gap.
- Ask in short rounds (one topic at a time, at most 4 questions per round). Use the AskUserQuestion tool when
  it is available and the answer is a choice (role types, German level, yes/no); ask in plain text for free
  answers (name, city, skills). Offer sensible defaults so the candidate can just confirm.
- Plain language. The candidate may not be technical and may not know German job-market words. Explain a term the
  first time you use it (see the glossary below), and never assume a field: the routine works for marketing,
  engineering, healthcare or software alike.
- Never ask for passwords, API keys or bank details. Contact details (email, phone, LinkedIn) are optional:
  they only go into CLAUDE.md for letters, and only if the candidate wants them there.
- Save after every round, so an interrupted setup continues where it stopped (`setup_check.py` shows what's left).
- **Nobody there to answer?** A scheduled run may have no one watching. Then write `daily/<today>.md` with the
  title "Setup needed", the TODO list from `setup_check.py`, and the questions of the next round. End the reply
  with: "Setup isn't finished. Reply here or open Claude Code in this folder and say 'continue the job-hunt setup'."
  Don't invent answers to get past this.

## Glossary (explain these when they come up)
- **Werkstudent** (working student): a paid part-time job for enrolled students, usually up to 20 hours a week in term.
- **HiWi** (studentische / wissenschaftliche Hilfskraft): a student or research assistant job at a university or institute.
- **Praktikum** (internship); **Pflichtpraktikum** is one the study programme requires.
- **Thesis** (Bachelor-/Masterarbeit) written with a company.
- **Junior**: a first full-time job after graduating.
- **ATS** (applicant tracking system): the software that reads a CV before a person does. It can garble columns,
  text boxes and headers, and it matches the ad's keywords.
- **Anschreiben**: the cover letter; German letters follow a fixed business-letter layout (RULES.md rule 6).

## 0. Scaffold
Run `python engine/tools/setup_check.py --init`. It copies the templates (never overwriting a file) and creates
the folders. If it says a Python package is missing, explain in one sentence what the packages are for (reading
and writing Word files, the Excel tracker, the job APIs), show the `pip install` line and ask whether you may run
it. Run it on a yes; otherwise ask the candidate to run it and check again.

## 1. Welcome
Tell the candidate in 3-4 plain sentences what the routine does (every day it looks for new job ads, rates how
well each fits them, and on weekdays drafts a CV and cover letter for the best ones; nothing is ever sent
automatically) and that setup takes about 20 minutes of questions. Ask them to have their CV and, if they have
one, a cover letter ready (Word .docx is best).

## 2. Rounds of questions
Write each answer into the file named in brackets right after the round.

1. **About you** [config.yaml: applicant, file_prefix, letter_city; CLAUDE.md "Who I am"]
   Full name as it should appear on documents; the city they live in (also the letter's date line);
   optional email, phone, LinkedIn, portfolio for the letter header. file_prefix = the name with underscores.
2. **Studies and status** [config.yaml: university; CLAUDE.md "Who I am", "What I'm looking for"]
   Enrolled student? If yes: degree, university, focus. If not, skip the student questions in later rounds and
   leave `university` empty. Work permit situation, only if they want it on the CV.
3. **What you're looking for** [CLAUDE.md "What I'm looking for", "Routine settings"]
   Role types (multi-select, explain each with the glossary: working student / internship / research assistant
   (HiWi) / thesis / junior; students only see the student types if they are enrolled). Their field in their own
   words (for example "online marketing", "mechanical design", "nursing", "backend development"), and whether
   junior roles should be narrower than student roles. For student roles: hours per week in term and in breaks,
   earliest start, internship duration. Location: home area radius, willing to relocate, remote, other countries.
3b. **Which job titles to keep** [config.yaml: profile]
   Turn round 3 into the `profile:` block: `role_types`; `include_titles` = 8-20 words that appear in job titles
   in their field, in English and German (marketing → marketing, content, social media, kommunikation, pr,
   kampagne); `junior_include_titles` if junior roles are narrower; `exclude_titles` = the template's seniority
   words plus fields they never want; `score_bonus` = 3-6 skills from their CV that should add points. Show the
   lists as plain words, explain that a job is kept only when its title contains one of them, and let them edit.
   Run `setup_check.py`: it reports a word list that doesn't work.
4. **Languages** [CLAUDE.md "Who I am", "My decisions on the rules"]
   English and German level (A1-C2 or native; explain the scale if needed), and any other languages. If German is below C1: should student roles that ask for
   German still be drafted (with the level disclosed honestly)? This becomes a rule-3 decision in CLAUDE.md.
5. **CV and cover letter** [cv/, config.yaml: master_cv, master_letter]
   Ask for the path of their CV and a cover letter they like (.docx preferred; PDF is fine to read from).
   Copy them into cv/ as `<file_prefix>_CV.docx` and `<file_prefix>_CoverLetter.docx` and set the paths.
   If they only have a PDF, ask whether they can export a .docx from the program they wrote it in (Word, Google
   Docs, LibreOffice; Canva exports are often text boxes and can't be tailored).
   **ATS review first:** follow engine/ats-checklist.md. Scan both files, explain the findings in plain words,
   write cv/ats-review.md, and on a yes make the improved copies and switch the master to them only after the
   candidate has looked at them. If they want to keep a layout the scan warns about (tables, columns), record
   that as a decision in CLAUDE.md "My decisions on the rules" so later reviews don't flag it again.
   **Map the CV** (also the "remap my CV" request; the format is at the top of engine/tools/cv_map.py): run
   `python engine/tools/cv_map.py outline <master_cv>` and the same for the letter. Write cv/layout.yaml: the
   headline line under the name, a "City, date" line if the CV has one, the sections whose items may be
   reordered per job (projects, skill groups, ... with the rule that splits them into items) and the letter's
   date, recipient (the first line of the address block), subject, greeting and closing lines. Use anchor text that appears only once and won't change per job. Run `python engine/tools/cv_map.py
   check` until it says OK, then show the candidate in plain words what will change per job (the headline, the
   order of those items, the letter text) and that everything else stays exactly as they designed it.
   If the CV can't be mapped (no .docx, text boxes the scan flagged and they want to keep), set `layout: none`
   in config.yaml and say plainly: tailoring still writes job.md and application.md, but no finished
   documents; they can send the drafts by hand or say "remap my CV" once they have a .docx.
   cv/variants.yaml starts with example entries that aren't in their CV, and the builder stops on those. Replace
   them with the experience bullets of their CV that letters may reorder (exact master text, `variants: {}`), or
   leave the file with only its header comments.
6. **Strengths, facts and gaps** [CLAUDE.md "Real strengths", "Confirmed facts", "Gaps"]
   Read the CV, propose a list of strengths it clearly supports, and ask the candidate to tick what they can
   back up in an interview. Ask for numbers behind CV bullets (team size, customers, budget, users, time saved,
   results) and record only confirmed ones. Ask what they must never be presented as having (tools, languages, seniority).
7. **Projects** [projects.md]
   For each project on the CV (coursework, campaigns, research, portfolio pieces and side projects all count;
   if there are none, delete the example projects and move on): status, tools used, link, what is really done
   (results, users, what is live), and anything not to claim yet. Copy the CV lines word for word into "CV text". Fill the table and the
   suggested order by role type. Remove the example projects.
8. **Rules and daily plan** [CLAUDE.md "My decisions on the rules", "Routine settings"]
   Read out the defaults from engine/RULES.md rule 9 (start date, hours, weekdays, duration, salary wording) and
   ask for changes. Ask how much time they have per day and turn it into the "Plan for today" line.
9. **Search** [sources.md, config.yaml: search.home, companies.md]
   Propose 5-8 search terms from rounds 3 and 3b (mix English and German titles, e.g. "Werkstudent Marketing",
   "Working Student Content") and let them edit the list. Replace the example terms in sources.md, and mark
   field-specific platforms they don't need (e.g. tech-only boards) as "no".
   Set search.home (city and radius in km). If they only want jobs in some places, set search.areas (cities to
   search instead of the whole country) and, for a whole federal state, search.regions (for example [Bayern],
   with region_plz postcode starts for ads that don't name the state). Ask for their university's job board URL (row "University job
   board") and for companies they'd like to watch (add them to companies.md with empty ATS/Endpoint).
10. **Connectors (optional)** [nothing to write; mention in the summary]
    Check which tools this session has: Gmail (job alerts, confirmations, rejections), Indeed, the obscura
    browser. List the missing ones as optional, with what each adds. Suggest email job alerts on StepStone,
    XING and LinkedIn.

## 3. Finish
- Run `python engine/tools/setup_check.py --init` until it says READY. Fix what you can, ask about the rest.
  `--init` also makes the master CV and letter you just set read-only for later runs.
- Show a short summary: target roles, the title words from 3b, location, languages, strengths, projects, search terms, and anything
  they should still check (for example a CV that couldn't be mapped or a missing connector).
- Ask them to read CLAUDE.md once: it's what every letter will be based on.
- Tell them the next scheduled run will search, score and (on weekdays) draft. If they want results today,
  they can say "run the routine now".
- If the workspace is a git repo, suggest committing; never push without asking.
