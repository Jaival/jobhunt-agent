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
| Do subagents with restricted tools work? | **Yes**, also with Desktop's bundled Claude Code | The `reader` subagent (`tools: Read, Glob`) had no Write tool. The project hook fired for subagent calls (`agent_type: "reader"` in the CLI, `"general-purpose"` with the Desktop build) and deny rules applied inside them. No daily run has used a subagent yet. |

### Where the task runs matters (Desktop test, 2026-10-25)
The first attempts at the Desktop check ran as **Cowork** tasks with the folder attached, not as Code-tab tasks:
twice in a cloud container (the files went to `/home/claude`) and once from a session outside the folder that
reached it through `device_bash`. Desktop recorded the folder under `localAgentModeTrustedFolders` (Cowork) and
the Code tab's `scheduled-tasks.json` only lists `job-hunt-daily`. In all three runs **none
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

### Browser and network policy (S1-2, agreed 2026-10-25)
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

## Local check with Desktop's Claude Code (2026-10-25)

Run with the Claude Code build that Desktop bundles and launches for Code-tab sessions
(`Claude-Data/…/claude-code/2.1.308/claude.exe`, `CLAUDE_CODE_ENTRYPOINT=claude-desktop`), `-p` in the throwaway
folder, permission mode **auto**, the same five-step prompt:

| Step | Result |
|---|---|
| Write `engine/a.txt` | **Blocked** by the deny rule: `File is in a directory that is denied by your permission settings.` |
| Write `forbidden.txt` | **Blocked** by the hook: `PreToolUse:Write hook error: [python "${CLAUDE_PROJECT_DIR}/guard.py"]: guard: 'forbidden' is blocked by the spike guard` |
| Tools ending in `send_message` / `create_draft` | **None.** `mcp__claude_ai_Gmail__send_message` and `create_draft` were removed; `delete_draft`, `get_draft` etc. stayed. |
| `reader` subagent: read `input.txt`, write `sub.txt` | Read `hello`; **no Write tool**, so no `sub.txt`. |
| `hooklog.jsonl` | Entries with `permission_mode: "auto"`. |

A second run (bypass mode, a `general-purpose` subagent) logged the subagent's Write with
`agent_type: "general-purpose"`, and the subagent's Write to `engine/b.txt` was denied with the same message.

Notes for S1-2:
- A call stopped by a deny rule never reaches the hook (the `engine/a.txt` Write isn't in the log). The heartbeat
  must therefore come from any allowed call, which every run has plenty of.
- The hook sees the Agent tool's prompt as `tool_input`, so a word-match block also fires on a subagent launch
  that merely mentions the pattern. Match on the fields that matter (paths, commands, URLs), not the whole input.

What is left untested is only the Desktop **scheduler** starting such a session. It launches the same binary with
the task's folder as `cwd` (see the `job-hunt-daily` sessions), and the S1-2 heartbeat line in the brief checks it
on every real run. The user-level fallback (`~/.claude/settings.json`) is not needed.
