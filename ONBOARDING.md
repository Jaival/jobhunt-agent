# First-run setup: interview the candidate and fill in the workspace

ROUTINE.md step 0 sends you here when `python engine/tools/setup_check.py` reports anything as TODO.
Don't search for jobs during setup. The goal is a workspace that passes the check, built only from what
the candidate tells you or what is in their own CV.

## Ground rules
- Ask, don't guess. Every fact in CLAUDE.md and projects.md must come from the candidate's answers or their CV.
  If something is unclear, ask a follow-up instead of filling the gap.
- Ask in short rounds (one topic at a time, at most 4 questions per round). Use the AskUserQuestion tool when
  it is available and the answer is a choice (role types, German level, yes/no); ask in plain text for free
  answers (name, city, skills). Offer sensible defaults so the candidate can just confirm.
- Never ask for passwords, API keys or bank details. Contact details (email, phone, LinkedIn) are optional:
  they only go into CLAUDE.md for letters, and only if the candidate wants them there.
- Save after every round, so an interrupted setup continues where it stopped (`setup_check.py` shows what's left).
- **Nobody there to answer?** A scheduled run may have no one watching. Then write `daily/<today>.md` with the
  title "Setup needed", the TODO list from `setup_check.py`, and the questions of the next round. End the reply
  with: "Setup isn't finished. Reply here or open Claude Code in this folder and say 'continue the job-hunt setup'."
  Don't invent answers to get past this.

## 0. Scaffold
Run `python engine/tools/setup_check.py --init`. It copies the templates (never overwriting a file) and creates
the folders. If it says a Python package is missing, show the `pip install` line and ask the candidate to run it
(or run it if they agree).

## 1. Welcome
Tell the candidate in 3-4 sentences what the routine does (daily search, scoring, drafts on weekdays, nothing
is ever sent automatically) and that setup takes about 15 minutes of questions. Ask them to have their CV ready.

## 2. Rounds of questions
Write each answer into the file named in brackets right after the round.

1. **About you** [config.yaml: applicant, file_prefix, letter_city; CLAUDE.md "Who I am"]
   Full name as it should appear on documents; the city they live in (also the letter's date line);
   optional email, phone, LinkedIn, portfolio for the letter header. file_prefix = the name with underscores.
2. **Studies and status** [config.yaml: university; CLAUDE.md "Who I am", "What I'm looking for"]
   Enrolled student? Degree, university, focus. Work permit situation, only if they want it on the CV.
3. **What you're looking for** [CLAUDE.md "What I'm looking for", "Routine settings"]
   Role types (multi-select: working student / internship / research assistant (HiWi) / thesis / junior / other);
   fields (cloud and DevOps, backend, frontend, full-stack, data, IT support, ...); hours per week in semester and
   in breaks; earliest start; internship duration; location: home area radius, willing to relocate, remote,
   other countries.
4. **Languages** [CLAUDE.md "Who I am", "My decisions on the rules"]
   English and German level (A1-C2 or native). If German is below C1: should student roles that ask for
   German still be drafted (with the level disclosed honestly)? This becomes a rule-3 decision in CLAUDE.md.
5. **CV and cover letter** [cv/, config.yaml: master_cv, master_letter]
   Ask for the path of their CV and a cover letter they like (.docx preferred; PDF is fine to read from).
   Copy them into cv/ as `<file_prefix>_CV.docx` and `<file_prefix>_CoverLetter.docx` and set the paths.
   Run `setup_check.py`: if it warns about the CV layout, explain what cv/README.txt expects and offer to build a
   master CV in that layout from their CV's content (same facts, nothing added). Show it and get a clear yes
   before setting it as master_cv. If they decline, tailoring still writes job.md and application.md, but the
   documents can't be built: say so plainly.
6. **Strengths, facts and gaps** [CLAUDE.md "Real strengths", "Confirmed facts", "Gaps"]
   Read the CV, propose a list of strengths it clearly supports, and ask the candidate to tick what they can
   back up in an interview. Ask for numbers behind CV bullets (team size, users, incidents, time saved) and
   record only confirmed ones. Ask what they must never be presented as having (tools, languages, seniority).
7. **Projects** [projects.md]
   For each project on the CV: status, stack, repo or demo link, what is really done (CI, deployment, users),
   and anything not to claim yet. Copy the CV lines word for word into "CV text". Fill the table and the
   suggested order by role type. Remove the example projects.
8. **Rules and daily plan** [CLAUDE.md "My decisions on the rules", "Routine settings"]
   Read out the defaults from engine/RULES.md rule 9 (start date, hours, weekdays, duration, salary wording) and
   ask for changes. Ask how much time they have per day and turn it into the "Plan for today" line.
9. **Search** [sources.md, config.yaml: search.home, companies.md]
   Propose 5-8 search terms from rounds 3 and 4 (mix English and German titles) and let them edit the list.
   Set search.home (city and radius in km). Ask for their university's job board URL (row "University job
   board") and for companies they'd like to watch (add them to companies.md with empty ATS/Endpoint).
10. **Connectors (optional)** [nothing to write; mention in the summary]
    Check which tools this session has: Gmail (job alerts, confirmations, rejections), Indeed, the obscura
    browser. List the missing ones as optional, with what each adds. Suggest email job alerts on StepStone,
    XING and LinkedIn.

## 3. Finish
- Run `python engine/tools/setup_check.py` until it says READY. Fix what you can, ask about the rest.
- Show a short summary: target roles, location, languages, strengths, projects, search terms, and anything
  they should still check (for example the CV layout or a missing connector).
- Ask them to read CLAUDE.md once: it's what every letter will be based on.
- Tell them the next scheduled run will search, score and (on weekdays) draft. If they want results today,
  they can say "run the routine now".
- If the workspace is a git repo, suggest committing; never push without asking.
