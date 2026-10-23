# ATS review: checklist for the candidate's CV and cover letter

Used by onboarding (round 5, before the builder is set up), by playbook I (master CV review) and on request
("run the ATS review"). An ATS (applicant tracking system) reads the CV before a person does: it extracts the
text, files it into fields (name, contact, experience, education, skills) and matches it against the ad.

## How to run it
1. `python engine/tools/ats_scan.py <cv> --json` and `python engine/tools/ats_scan.py <letter> --letter --json`
   (scan the PDF too if there is one: it shows what an ATS actually extracts). This gives the mechanical findings.
2. Read the CV and letter text and go through the judgment checks below.
3. Write `cv/ats-review.md`: a table of findings (severity, what, where, suggested fix, who fixes it: "I can do
   it" or "do it yourself in Word, steps: ..."), then before/after text for every wording change you propose.
   Skip findings that CLAUDE.md records as the candidate's decision (for example a kept two-column layout).
4. Explain the must-fix items in plain words and ask which suggestions the candidate wants.
5. Only on a clear yes: make a copy, `cv/<file_prefix>_CV_improved.docx` (and `..._CoverLetter_improved.docx`),
   apply the accepted **text-level** changes with python-docx (paragraph text, headings, dates, adding a line),
   keeping every paragraph's formatting. Never remove or restructure tables, text boxes, columns or images:
   those go to the candidate as steps. Re-run `ats_scan.py` on the copy and show what changed.
6. Only after the candidate has looked at the copy (open it in Word) and says yes: keep the original as
   `cv/<file_prefix>_CV_original.docx`, point `master_cv` / `master_letter` in config.yaml at the improved copy,
   and continue with the CV map (onboarding round 5). If they say no, keep the original as the master.

## Severity
- **must-fix:** the ATS loses information (text boxes, contact details only in the header, image-only PDF).
- **should-fix:** the ATS may misfile something or a recruiter will stumble (non-standard headings, mixed date
  formats, too long, no summary line).
- **warning:** works in most ATS but is a risk; the candidate decides (tables and columns).
- **note:** good to know, no action needed.

## CV: mechanical (ats_scan.py reports these)
- Text boxes or shapes holding text. Headers and footers holding text, especially name and contact details.
- Images and icons (a phone icon without the word "Phone"); a photo is optional in Germany, never required.
- Tables or multi-column sections.
- Uncommon fonts (fine in the PDF; config.yaml `fallback_font` should be a common one).
- The candidate's name is the first line of text; email (and phone) are in the body.
- Standard section headings: Experience / Berufserfahrung, Education / Ausbildung, Skills / Kenntnisse,
  Languages / Sprachen (Projects and Certifications when used).
- One date format throughout (MM/YYYY recommended); 1-2 pages for students and juniors.

## CV: judgment (Claude checks these)
- **Headline or summary line** under the name: says who they are and what they're aiming for in one line. The
  builder replaces it per job, so if it's missing, suggest adding one (one line, about 72 characters).
- **Keywords for the target roles:** list the 10-15 terms that typical ads in the candidate's field ask for
  (CLAUDE.md "What I'm looking for"; label them "typical, check against real ads" until the routine has found
  some), and mark each as present / missing. Suggest adding a missing term only where the CV or CLAUDE.md backs it.
- **Skills section:** an explicit list of skills and tools as words, not only bars, stars or logos.
- **Bullets:** action + what + tool or method + result. Flag weak openers ("helped", "responsible for", "worked
  on") and bullets with no outcome. Ask for the number behind a result; never invent one.
- **Consistency:** job titles, company names and dates match LinkedIn (ask if unsure); no unexplained gaps
  longer than 6 months without a line in CLAUDE.md.
- **File name:** `<Name>_CV.pdf` style, not "CV_final2.pdf".
- **Germany-specific:** date of birth, nationality and photo are optional; a signature is not needed. Work
  permit status helps non-EU candidates (only if they want it on the CV).

## Cover letter
- Name and contact details in the body, a date line, recipient, subject line and greeting (RULES.md rule 6).
- 250-350 words, one page. One paragraph that's specific to a company (it will be rewritten per job, but the
  master shows the candidate's tone).
- No placeholders, no banned phrases (the builder's list: "passionate", "I am writing to express", "team
  player", "results-driven" and similar), no claims that aren't in the CV or CLAUDE.md.
- For student roles: enrolment, hours per week, earliest start.
