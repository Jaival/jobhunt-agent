---
name: skills
description: Record what the candidate says about a skill job ads ask for (yes with where they used it, learning, or no) in skills.md, or list the skills the routine wants to ask about. Use when the user says "I know Agile from Maven", "add pytest as learning", "I don't know Kubernetes", "skills", "what skills did you ask me about" or answers a "Do you know <term>?" question from the brief.
---
Changes only skills.md, through the tool. Run everything from the workspace folder.

1. No skill named ("skills", "what did you ask me"): run `python engine/tools/keywords.py ask` and show its
   `ASK` lines with "answer each as yes <where>, learning or no". Stop.
2. For each skill the user names, take the status from their own words:
   - `yes` only when they say they used it, with where (job, project, course, team practice). Without a where,
     ask "where did you use it?" and wait. Never write a where they didn't say.
   - `learning` for basics, a course in progress, "I can learn it"; `no` for "I don't know it".
   - Other spellings they mention ("Scrum, sprints") go into `--alias`.
3. `python engine/tools/keywords.py fact "<skill>" <yes|learning|no> [--note "<their words>"] [--alias "<a>, <b>"]`
   for each. `FAILED`: show the reason and fix the input.
4. Reply: each row the tool printed, and "the next tailoring uses this; say `revise <folder>` to update a draft".
