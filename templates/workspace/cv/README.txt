Put your master CV and master cover letter here as Word .docx files, named as in config.yaml (master_cv,
master_letter). The routine never edits these files. engine/tools/build_application.py copies them for each
application and changes only the parts named in the CV map; your design stays as it is.

The CV map (cv/layout.yaml, path in config.yaml `layout`) tells the builder where those parts are, by their text:
- headline: the line under your name that is rewritten per job.
- sections: blocks whose items can be reordered per job (for example projects, skills), each found by its
  heading text and split into items by a simple rule (blank line, bold line, "Name:" line, ...).
- letter: the date line, recipient, subject and greeting of the cover letter; the body is the text after the
  greeting up to the first empty line.
Everything is optional: what isn't mapped simply isn't tailored. The format is described at the top of
engine/tools/cv_map.py. Experience bullets you want to reword or reorder go in variants.yaml with their exact
master text.

Onboarding writes the map for you. To do it by hand:
    python engine/tools/cv_map.py outline cv/<your CV>.docx    numbered lines, to pick the anchors from
    python engine/tools/cv_map.py check                       shows what every anchor finds
If you edit your master CV later and an anchor stops matching, setup_check.py warns and the routine stops
building documents until you say "remap my CV". If your CV can't be mapped (for example a PDF only), set
`layout: none` in config.yaml: the routine then writes drafts (job.md, application.md) but no documents.

Building PDFs uses Microsoft Word (engine/tools/docx2pdf.ps1), so it needs Windows with Word installed.
