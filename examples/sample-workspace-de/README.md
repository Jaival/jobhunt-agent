# German sample workspace

A filled-in workspace for **Jonas Becker**, a fictional mechanical engineer looking for junior simulation roles in
Bayern. It shows a German CV and letter that look nothing like the other sample, and the tests in `engine/tests/`
build from it.

- `config.yaml`: junior roles only; `name_in_master` (the master files say "Jonas Michael Becker").
- `cv/layout.yaml`: the map of his plain-paragraph CV (project title lines with Word list bullets, "Name: ..."
  skill lines, a "Regensburg, date" line) and his letter (three-line address, no empty line before the closing).
- `applications/.../application.md`: one tailored application.

The CV and letter themselves aren't stored here; `python make_docs.py` writes them into `cv/`. To try it, follow
the steps in `../sample-workspace/README.md` with this folder.
