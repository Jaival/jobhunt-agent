Put your master CV and master cover letter here, named as in config.yaml (master_cv, master_letter).
The routine never edits these files. engine/tools/build_application.py copies them for each application and
changes only the headline, the order of sections and approved bullet variants.

The builder finds parts of the master CV by their text, so the CV needs this structure (Word .docx):
- The whole CV is one table: row 1 is the header (its 2nd paragraph is the headline, replaced per job),
  row 2 has a main column (left) and a side column (right).
- Section headings in capitals: PROJECTS, EXPERIENCE, EDUCATION, CERTIFICATIONS.
  Each project is a title line ("Name, description") followed by a line containing "|" (stack | link | year)
  and a body line.
- The side column has a "Skills" heading (ability headings with "- " bullets below), followed by
  "LEADERSHIP & INITIATIVE", and a "Technical Proficiency" block of "Name: ..." lines.
- Experience bullets you want to reorder are listed in variants.yaml with their exact master text.

The master cover letter: paragraph 4 is the date line, 5 the recipient, 6 the subject, 8 the greeting;
the body follows the greeting and ends at the first empty paragraph before the closing.

Building PDFs uses Microsoft Word (engine/tools/docx2pdf.ps1), so it needs Windows with Word installed.
