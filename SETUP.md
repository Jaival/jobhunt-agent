# Setting up the local routine (Claude Desktop)

1. Create a workspace folder somewhere permanent (e.g. Documents/JobHunt) and clone this repo into it as `engine`:
   `git clone https://github.com/Jaival/jobhunt-agent engine`
   Then copy everything from `engine/templates/workspace/` up into the workspace folder and create the empty
   folders `applications/`, `daily/`, `data/`, `follow-ups/`, `interview-prep/`, `reviews/`, `backups/`.
   Make the workspace its own **private** git repo if you want history; add `engine/` to its `.gitignore`.
2. Fill in `config.yaml` (name, file prefix, master CV paths, letter city, university, search area) and
   `CLAUDE.md` (who you are, availability, strengths, gaps, decisions, routine settings). Put your master CV
   and cover letter into `cv/` (see `cv/README.txt` for the structure the builder expects), and describe your
   projects in `projects.md`. Edit `sources.md` (search terms) and `companies.md` (watchlist).
3. Install the Python packages: `pip install python-docx openpyxl pypdf pyyaml requests`.
   Check the setup: `python engine/tools/build_application.py --help` must run without a config error.
4. Open Claude Desktop, go to the Code tab, then Routines > New routine > Local.
   - Name: job-hunt-daily
   - Description: Find, score and tailor jobs; update tracker; write daily brief
   - Instructions: "Run my job-application routine in this folder. Read engine/ROUTINE.md and follow it exactly. Finish by replying with a 3-line summary and the path of today's brief."
   - Folder: the workspace folder (trust it when asked)
   - Schedule: daily, 07:30 (weekends run a short search-only mode)
   - Model: a strong model
5. Click "Run now" once and watch it. When it asks for permissions (bash, curl, python, writing files), choose "always allow". Future runs then go through without stalling.
6. Settings > Desktop app > General: turn on "Keep computer awake". The routine only runs while the app is open and the computer is awake. Missed runs catch up once when the computer wakes.
7. Close the tracker in Excel before the routine runs; an open file can't be saved. If it was open, rows go to tracker/pending_rows.csv.
8. Connectors: if you connected Indeed or Gmail in Claude, the routine uses them. Browsing uses the obscura MCP; make sure it is configured in Claude Desktop, and on the first "Run now" choose "always allow" for each obscura tool.
9. Recommended: set up daily email job alerts on StepStone, XING and LinkedIn. Alert emails are the most reliable way to get jobs from those sites, since they often block automated access.

Updating: `git pull` inside `engine/`. Your workspace files are never touched by an update.

Each morning, open daily/<date>.md and follow the plan.
