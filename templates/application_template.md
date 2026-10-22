---
# Copy to applications/<YYYY-MM-DD>_<Company>_<Role>/application.md, fill in, then run:
#   python engine/tools/build_application.py applications/<folder>
short: Company              # file names: <file_prefix>_CV_<short>.docx, <file_prefix>_Cover_Letter_<short>.docx
role_type: Werkstudent      # Werkstudent | HiWi | Internship | Thesis | Junior
date: 2026-10-19            # letter date; defaults to today
recipient: Company GmbH, City
subject: "Application: <exact job title from the ad>"
greeting: Dear <Company> team,
cv:
  headline: DevOps Engineer | Cloud, CI/CD & Python
  # Every list below is optional; leave one out to keep the master order.
  # Anything you don't list keeps its place after the listed ones.
  # order by the job ad using projects.md; every CV keeps all projects
  projects: [Project A, Project B, Project C]
  abilities: [Cloud Infrastructure & AWS, CI/CD & Release Management, Troubleshooting & Monitoring, Security & Networking Fundamentals, Communication & Teamwork]
  technical: [Cloud, DevOps, Security, Code, AI, Data, Learning]
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
