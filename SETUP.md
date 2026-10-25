# Setting up the daily routine (Claude Desktop scheduled task)

A visual version of this guide is in [docs/setup-guide.html](docs/setup-guide.html).

1. Install Claude Desktop (Code tab), Python 3 and Git. For PDFs you need Microsoft Word (Windows or macOS) or
   the free LibreOffice (libreoffice.org); without either you still get .docx files. Then the Python packages
   (the first run offers to install them for you):
   `pip install python-docx openpyxl pypdf pyyaml requests` (on macOS with Word, also `docx2pdf`)
   (after step 2, `pip install -r engine/requirements.txt` installs the exact versions the engine is tested with)
2. Create a workspace folder somewhere permanent (e.g. Documents/JobHunt), clone this repo into it as `engine`
   and let the check script copy the templates and create the folders (it never overwrites a file):
   ```
   mkdir JobHunt
   cd JobHunt
   git clone https://github.com/Jaival/jobhunt-agent engine
   python engine/tools/setup_check.py --init
   ```
   It lists what is still TODO. You can fill in `config.yaml`, `CLAUDE.md`, `projects.md`, `sources.md` and
   `cv/` by hand, or leave them: the first run asks you for everything (step 4).
3. Open Claude Desktop, go to the Code tab, click **Scheduled** in the sidebar (or under **More**), then
   **New task** (choose **Set up manually** if a menu opens).
   - Name: job-hunt-daily
   - Instructions (the box under the name): "Run my job-application routine in this folder. Read engine/ROUTINE.md and follow it exactly. It checks the setup at the start of every run and only asks me questions if something is missing. Finish by replying with a 3-line summary and the path of today's brief."
   - Advanced settings > General: turn on **Only on this computer** (the routine needs your local files). If
     that switch is at the top of the dialog instead, turn it on before filling in anything else.
   - Local folder: the workspace folder (trust it when asked)
   - Trigger: Daily, 07:30 (weekends run a short search-only mode)
   - Model (menu in the instructions box): a strong model
   - Description, if the form asks: Find, score and tailor jobs; update tracker; write daily brief
   - Click **Create**. Leave **Worktree** off in the task's Edit form: the routine must write into the folder itself.
4. On the task's page click **Run now** and stay with it. The routine runs `setup_check.py` first; while anything is TODO it doesn't
   search but follows [ONBOARDING.md](ONBOARDING.md): about ten short rounds of questions (you, studies, roles,
   which job titles to keep, languages, CV, strengths and gaps, projects, rules, search terms, connectors),
   saved after every round. Any field works, not only tech. In the CV round it reviews your CV and cover letter
   for ATS problems (cv/ats-review.md; any improved copy is used only after you say yes) and maps your CV
   (cv/layout.yaml) so the builder can tailor your own design. If you change your CV later, say "remap my CV".
   If a scheduled run finds the setup unfinished while you're away, it writes a "Setup needed" brief with the
   next questions; open that run from the task's **History** list and reply there, or say "continue the job-hunt setup" in Claude Code in the folder.
5. During that first run, when it asks for permissions (bash, curl, python, writing files), choose "always allow". Future runs then go through without stalling.
6. Settings > This computer > System: turn on **Keep computer awake**. Scheduled tasks only run while the app is open and the computer is awake. After sleep, one run catches up for the most recent missed time (within seven days).
7. Close the tracker in Excel before the routine runs; an open file can't be saved. If it was open, rows go to tracker/pending_rows.csv.
8. Connectors: if you connected Indeed or Gmail in Claude, the routine uses them. Browsing uses the obscura MCP; make sure it is configured in Claude Desktop, and on the first "Run now" choose "always allow" for each obscura tool.
9. Recommended: set up daily email job alerts on StepStone, XING and LinkedIn. Alert emails are the most reliable way to get jobs from those sites, since they often block automated access.

Updating: when the daily brief says an engine update is available, open your workspace in Claude Code and say
"update the engine" ([UPGRADING.md](UPGRADING.md)). Claude backs up your settings, keeps any edits made inside
engine/, updates config.yaml, and builds documents with the old and the new engine to show you they still come
out the same. Engines from before October 2026 need a one-time prompt; it's in UPGRADING.md. Never edit files in
engine/ yourself: put wishes in custom.md.

Each morning, open daily/<date>.md and follow the plan.
