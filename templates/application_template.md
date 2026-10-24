---
# Copy to applications/<YYYY-MM-DD>_<Company>_<Role>/application.md, fill in, then run:
#   python engine/tools/build_application.py applications/<folder>
short: Company              # file names: <file_prefix>_CV_<short>.docx, <file_prefix>_Cover_Letter_<short>.docx
role_type: Werkstudent      # Werkstudent | HiWi | Internship | Thesis | Junior
date: 2026-10-19            # letter date; defaults to today
# languages: [de, en]       # one letter per language; default: config.yaml letter_languages, else [en]
recipient: Company GmbH, City   # or one line each: [Company GmbH, Personalabteilung, Street 1, 12345 City]
subject: "Application: <exact job title from the ad>"   # per language: {de: "Bewerbung als ...", en: "Application: ..."}
greeting: Dear <Company> team,  # per language: {de: "Sehr geehrte Damen und Herren,", en: "Dear <Company> team,"}
# closing: Best regards     # needs letter.closing in cv/layout.yaml; with two languages the default is
#                           # {de: Mit freundlichen Grüßen, en: Kind regards}
cv:
  headline: Marketing Student | Content, Social Media & Analytics   # needs cv.headline in cv/layout.yaml
  # One list per section mapped in cv/layout.yaml, keyed by its name there (cv_map.py check shows the item names).
  # Every list is optional; leave one out to keep the master order.
  # Anything you don't list keeps its place after the listed ones.
  # order by the job ad using projects.md; every CV keeps all projects
  projects: [Project A, Project B, Project C]
  skills: [Skill group A, Skill group B]
  # only with my approval: leave a project out of this one CV
  # omit_projects: [Project C]
  # omit_approved: 2026-10-21    # the date I said yes
  bullets:
    job1: [cicd, incidents, monitoring]   # group and ids from cv/variants.yaml
  variants:                 # optional: <id from cv/variants.yaml>: <approved option>, or master
                            # (approved defaults from variants.yaml apply unless overridden here)
---
First paragraph: the role, your enrolment (student roles), why this team.

One paragraph per block. Blank lines separate paragraphs. Body must be 250-350 words.

Student roles must mention your university (config.yaml), hours per week and "as soon as possible"; internships also the duration.

With two languages, put a line `<!-- de -->` before the German letter and `<!-- en -->` before the English one;
each body must be 250-350 words (German student letters: "ab sofort", "Stunden pro Woche").
