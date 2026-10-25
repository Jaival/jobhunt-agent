# Spike S1-0: permissions, hooks and subagents in scheduled tasks

Date: 2026-10-25. Claude Code 2.1.310 (CLI) and Claude Desktop (Code tab, local scheduled tasks).

Question: can Sprint 1 rely on a workspace `.claude/settings.json` (permission rules and a PreToolUse hook) to limit
what the unattended daily run can do, and can Sprint 2 rely on subagents with restricted tools?

## How this was checked
1. **Docs:** [Desktop scheduled tasks](https://code.claude.com/docs/en/desktop-scheduled-tasks),
   [Desktop](https://code.claude.com/docs/en/desktop), [permissions](https://code.claude.com/docs/en/permissions),
   [hooks](https://code.claude.com/docs/en/hooks).
2. **The real daily runs:** the transcripts of the 11 `job-hunt-daily` runs (18–25 Oct 2026) in
   `~/.claude/projects/<JobHunt workspace>/`: permission mode, tool names, hook events.
3. **A throwaway workspace in the CLI** (`claude -p --permission-mode bypassPermissions`) with deny rules, a
   Python PreToolUse hook and a subagent limited to `Read, Glob`.

## Findings

| Question | Answer | Evidence |
|---|---|---|
| Do Desktop sessions read workspace `.claude/settings.json`? | **Yes**, the same files as the CLI | Docs: "The desktop app reads the same settings files as the CLI." Scheduled tasks also apply allow rules from `~/.claude/settings.json`. |
| Which permission mode do the daily runs use? | **Auto** (one run in bypass) | 10 of 11 transcripts `permissionMode: auto`, 1 `bypassPermissions`. The mode is set per task in Desktop. |
| Do deny rules hold in auto and bypass mode? | **Yes** | Deny is evaluated first and "an allow rule can't carve an exception out of a deny rule". CLI test in bypass mode: `Edit(/engine/**)` blocked a Write, `Bash(curl *)` blocked curl. |
| Do hooks run in scheduled runs? | **Yes**, but see the next row | Every daily-run transcript has PreToolUse hook events (from installed plugins). CLI test: the project hook ran in bypass mode and blocked with exit code 2. |
| Can a hook be launched with `bash`? | **No.** In Desktop, `bash` is the WSL stub and fails | Each daily run logs hundreds of `hook_non_blocking_error`: `WSL ... execvpe(/bin/bash) failed`. A hook that fails to start is **non-blocking**: the tool call goes ahead. |
| What are the Gmail and Indeed tool names? | **Different per user and per surface** | Desktop scheduled runs: `mcp__7d0bd227-…__send_message` (Gmail) and `mcp__679f2676-…__search_jobs` (Indeed), a connector ID instead of a name. CLI: `mcp__claude_ai_Gmail__send_message`. |
| Can a shipped template still deny the Gmail write tools? | **Yes, with a tool-name glob** | Deny rules accept globs in the tool name. CLI test: `mcp__*__send_message`, `mcp__*__create_draft`, `mcp__*__trash_*`, `mcp__*__*spam*` removed those tools from every connector (Gmail and Upwork) while `untrash_*` stayed. |
| obscura tool names | `mcp__obscura__browser_*` | Daily runs call `browser_navigate` (243), `browser_evaluate` (241), `browser_markdown` (63), `browser_close`, `browser_links`. |
| Does an `Edit` deny on `engine/**` stop all writes there? | **No** | CLI test: `python -c "open('engine/b.txt','w')..."` wrote the file. Edit/Read rules cover the file tools, recognised Bash file commands and redirects, not arbitrary programs. |
| Are project allow rules always applied? | **Only in a trusted folder** | CLI in an untrusted folder: "Ignoring 2 permissions.allow entries … not trusted". Deny rules and hooks still applied. Desktop asks to trust the folder when the task is created. |
| Do subagents with restricted tools work? | **Yes in the CLI**; not yet seen in Desktop | The `reader` subagent (`tools: Read, Glob`) had no Write tool. The project hook fired for its calls with `agent_type: "reader"`. No daily run has used a subagent yet. |

### Where the task runs matters (Desktop test, 2026-10-25)
The first attempt at the Desktop check ran twice: once as a **cloud** task (the files went to `/home/claude` in a
container) and once from a session outside the folder that reached it through `device_bash`. In both runs **none
of the folder's `.claude/` config applied**: the writes went through, `guard.py` never ran, the `send_message`
tools were still listed (as `mcp__Gmail__send_message`, a third naming scheme) and the `reader` agent was unknown.
So the guards only exist in a **local Claude Code session whose project folder is the workspace**, which is what
`job-hunt-daily` is today (its transcripts have `entrypoint: claude-desktop` and the JobHunt folder as `cwd`).
Consequences:
- SETUP.md and the setup guide must say: create the task in the **Code** tab with **Only on this computer** on
  and the workspace as the local folder, never as a cloud task or a Cowork task with the folder attached.
- The run can't rely on the guard being there, so it must check: the hook writes a heartbeat (e.g.
  `data/guard.log`), and the brief says "guard active" or warns when no heartbeat was written this run (S1-2/S1-3).

## Decisions

### Permission template (S1-1)
- **Deny by suffix, not by server name:** `mcp__*__send_message`, `mcp__*__reply`, `mcp__*__forward`,
  `mcp__*__create_draft`, `mcp__*__update_draft`, `mcp__*__trash_*`, `mcp__*__*spam*`. These also cover other
  connectors' send tools, which the routine never needs.
- `Edit(/engine/**)` and `Edit` on the master CV and letter (paths from config.yaml), `Bash(curl *)` and
  `Bash(wget *)`. curl is then allowed only through the hook's Indeed redirect exception (see below), because an allow
  rule can't make an exception to a deny rule.
- Allow `Bash(python engine/tools/*)`. The daily runs are in auto mode, so allow rules mainly save classifier calls.
  They are not the safety control.
- Don't use bare `mcp__claude_ai_Gmail__…` names: they don't match in Desktop scheduled runs.

### Hook (S1-2)
- Launch the hook as `python "${CLAUDE_PROJECT_DIR}/engine/tools/hooks/guard.py"`, never as `bash …`. The daily
  run already relies on `python` being on PATH.
- The hook **fails open**: if it can't start, or crashes with an exit code other than 2, the call goes ahead. So the
  deny rules stay the main control, the hook must catch its own exceptions, and `setup_check.py` should run the hook
  once to prove it starts.
- Block with exit code 2 and a one-line reason on stderr. The model sees the reason and can put it in the brief.
- It must look at Bash commands for writes into `engine/` and the master files (`python -c`, `Set-Content`, `>`),
  best effort, because the `Edit` deny doesn't cover them.
- Match tools by suffix (`^mcp__.*__(send_message|reply|forward|create_draft|update_draft)$`), as in the template.
- It runs inside subagents too, so S2-2 and S3-2 get the same guard.

### Browser and network policy (S1-2, recommendation)
A host allowlist for the browser would break the routine, which reads career pages on any company site. Instead:
- **curl and WebFetch** (JSON APIs only, per ROUTINE.md): an allowlist of hosts, namely `rest.arbeitsagentur.de`,
  `www.arbeitnow.com`, the Personio, Ashby, Greenhouse and Lever API hosts, the hosts in `companies.md`, and `curl` to
  `to.indeed.com` only in the redirect-lookup form (`-o /dev/null -w "%{redirect_url}"`).
- **Browser navigation** (`mcp__obscura__browser_navigate`, `mcp__Claude_Browser__navigate`): any host, but the
  URL must pass a **leak check**, the same one applied to curl and WebFetch. It only allows `http`/`https` on the
  default ports and no IP-address hosts. The URL must not contain the candidate's email, phone number or name (read
  from config.yaml and CLAUDE.md), and no query or path value may be longer than about 64 characters of base64- or
  hex-like text.
- **Browser tools that send data:** deny `browser_type`, `browser_set_cookie`, `browser_set_storage_state` and
  `browser_upload*` in the template. For `browser_evaluate` (used in every run to read pages), the hook blocks
  scripts that contain `fetch`, `XMLHttpRequest`, `sendBeacon`, `WebSocket`, `import(`, `window.open` or an
  assignment to `location`/`src`/`href`.
- Documented limit: a page can still be told something by *which* URL the agent opens. The leak check catches
  personal data in the URL, not a deliberately encoded message.

## Still to confirm in Claude Desktop (10 minutes, before S1-1 merges)

The first attempt didn't run locally (see above); this has to be repeated as a local Code-tab task.
The docs say Desktop reads the same files, and the transcripts show hooks firing. But no run has used a
*project* hook or a subagent yet. In a throwaway folder (not the JobHunt workspace):
1. Create `.claude/settings.json` with `"deny": ["Edit(/engine/**)", "mcp__*__send_message"]` and a PreToolUse
   hook `python "${CLAUDE_PROJECT_DIR}/guard.py"` that logs its input to a file and exits 2 when the input contains
   `forbidden`. Add `.claude/agents/reader.md` with `tools: Read, Glob`.
2. Create a local scheduled task on that folder, schedule **Manual**, permission mode **Auto** (as the daily run),
   prompt: "Write engine/a.txt; write forbidden.txt; list your tools whose names end in send_message; ask the reader
   subagent to write sub.txt; report what was blocked, quoting the errors." Click **Run now**.
3. Expected: engine/a.txt and forbidden.txt blocked, no `send_message` tool, the log has entries including one with
   `agent_type: reader`, and no sub.txt.

If the project file is ignored in scheduled runs, fall back to the same rules in `~/.claude/settings.json` (user
level, which the docs confirm for allow rules), installed and checked by `setup_check.py`.
