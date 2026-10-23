# Sample workspace

A filled-in workspace for **Lena Fischer**, a fictional media and communication student looking for marketing
roles. It shows what onboarding produces for someone outside tech, and the tests in `engine/tests/` build from it.

- `config.yaml`: the `profile:` block keeps marketing titles and drops sales; `layout` points to the CV map.
- `CLAUDE.md`, `projects.md`: her profile, facts and projects.
- `cv/layout.yaml`: the map of her single-column CV (bold project titles, "Name: ..." skill lines).
- `cv/variants.yaml`: three internship bullets, one with an approved shorter wording.
- `applications/.../application.md`: one tailored application (CV choices + letter).

The CV and letter themselves aren't stored here; `python make_docs.py` writes them into `cv/`.

To try the builder on it, copy this folder somewhere, put a copy of the engine at `<copy>/engine`, then:

```bash
python make_docs.py
python engine/tools/setup_check.py --init
python engine/tools/cv_map.py check
python engine/tools/build_application.py applications/2026-10-23_Example-Company_Working-Student-Marketing
```
