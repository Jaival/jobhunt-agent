# Token usage of the daily routine (2026-10-29 to 2026-11-08)

Labels: **[m]** measured from transcripts, **[e]** estimated, **not logged** = the logs don't show it.

Method: 10 scheduled runs in the window. Trace ids = sha1(session id)[:8], as in the harness. Per API call: input + output + cache read + cache write, deduped by message id. Routine part = records before the first "session is being continued" (manual follow-up after the run). "Carried" cost of a tool output = result chars / 3.5 x later calls in the run (estimated). Subagents from `<session>/subagents/*.jsonl` and `.meta.json`.

## Totals (10 scheduled runs)
| Part | Tokens | Calls |
|---|---|---|
| Main session, routine part | 39.5M [m] | 329 [m] |
| Subagents: ad-reader (26 runs) | 5.8M [m] | 107 [m] |
| Subagents: tailor (6 jobs) | 1.8M [m] | 52 [m] |
| Subagents: sonnet-worker (3, ad hoc) | 1.1M [m] | 18 [m] |
| Manual chat continued in the run's session | 40.0M [m] | ~400 [m] |

- Routine per run: main 3.95M avg [m], 1.9M–5.8M; context grows from ~51k to 106k–197k [m].
- All 10 routine mains and all 35 subagents ran on Sonnet 5.5 [m]. Only the 377dcc86 chat used Opus [m].
- Phase split of the routine main [m, phase = last tool's step]: reading ads 12.4M, tracker/Gmail 7.2M,
  tailor hand-off 5.6M, follow-ups 3.1M, score 1.3M, search 1.4M, brief 1.3M, setup/context ~2M.
  Phase is less useful than the cost shape below: 43% of main tokens are the fixed start context.

## Top 5 token sinks
| # | Sink | Tokens | Sessions |
|---|---|---|---|
| 1 | Manual chat continued inside the scheduled session (CV/font/site work after the run) | 40.0M [m] | cc:377dcc86 24.1M (Opus, 3 compactions), cc:a2d704da 9.0M, cc:cf8f8671 3.0M, cc:bec7310f 2.6M, cc:fee39e8d 1.3M |
| 2 | Fixed start context, paid on every main call: 50.4k–51.9k tokens [m] | 16.9M [m] (43% of routine main) | all 10 runs |
| 3 | Waiting for background subagents: 30 empty turns, 10 sleep, 10 mid-run wrap_up, 1 Monitor | 5.4M [m], 51 calls | worst: cc:bec7310f, cc:fee39e8d, cc:a2d704da |
| 4 | Ad-reader reply handled twice: subagent 5.8M [m] + reply in main 1.4M carried [e] + main re-types it into incoming.json (397k chars written [m], 2.2M carried [e]) | ~9.4M | all runs; 174 of 208 tasks are `file` tasks [m] |
| 5 | Engine docs read in full by main each run: ROUTINE.md (21.4k chars) 1.9M carried, playbook (13.2k) 1.2M carried | 3.1M [e] | all 10 runs |

Fixed start context breakdown (cc:cb089d9d first call) [m, chars]: 45 eager tool schemas 68.8k (Claude
browser tools ~26k, visualize 4.2k, plugin suggest/search 5.9k, SendUserFile 3.3k, session tools 4.9k,
terminal 1.1k); system prompt 14.3k; instruction files 23.6k (workspace CLAUDE.md 11.0k, RULES.md 6.6k, user
CLAUDE.md 2.4k, context7 rule 1.7k, MEMORY 1.0k); deferred-tool list 16.8k (298 names: Notion 77, Upwork 33,
Drive 16, session mgmt 20, Chrome 20, sidebar 13 ...); agent list 2.8k; MCP instructions 4.2k.
Finding: exact-name denies (PowerShell, Skill, ScheduleWakeup, ListAgents) are absent from the tool list [m].
The `mcp__claude_ai_Notion__*`-style denies do NOT match: Desktop names connectors by UUID, so Notion,
Upwork and Drive still load [m]. `mcp__*__form_input` also left the Claude-browser form_input in the list [m].

Not sinks [m]: tailor 0.3M per job, 2–4 builds each; no ad was sent to the reader in two runs (206 ids);
Gmail reads in main 0.36M carried [e]; search_jobs output ~1.9k tokens per run.

## Proposals, ranked by tokens saved (per 10 runs)

### P0 (already applied 2026-11-08, verify only): follow-up work in a new session
- Saving: part of 40.0M. A fresh session starts at ~51k, a continued one at 62–66k [m] and keeps growing to
  187k [m]. [e] 5–15M, depends on the user.
- Change: none in the engine. Rule is in `~/.claude/CLAUDE.md` "Threads and context". Optional: ROUTINE.md last
  line tells the user to open a new session for changes.
- Verify: next harness run, "chat" tokens in scheduled sessions ≈ 0.

### P1: cut tools the routine never calls from the fixed context — [e] 5–6M (≈12–14% of routine)
- Change: workspace `.claude/settings.json` (template `templates/workspace/.claude/settings.json`):
  deny the Claude-browser, visualize, plugin-suggest/search, SendUserFile, terminal, sidebar/session-mgmt tools by
  exact names; deny Notion/Upwork/Drive with the names Desktop really uses (`deniedMcpServers` by Desktop's
  server name, or deny by the logged names). `ad-reader.md`: `tools:` allowlist instead of `disallowedTools`
  (its start context is 31k without CLAUDE.md vs 18k for tailor with CLAUDE.md [m]).
- Math: ~45k chars ≈ 12k tokens per main call x 329 [e] ≈ 4M; ~3k from the deferred list x 329 ≈ 1M;
  ad-reader ~10k x 107 calls ≈ 1M.
- No function lost: routine calls only Read/Write/Edit/Bash/Glob/Grep/Agent/ToolSearch/WebFetch, Desktop
  update_plan/wrap_up, Gmail search/get, obscura, Indeed (reader) [m: tool-call counts]. Keep exactly these.
- Risk: medium. A wrong name denies a needed tool; connector UUIDs differ per user (engine is generic).
  Wildcard denies did not remove tools here: must test which forms remove a tool from context.
- Verify: next run's first-call cache write < 40k; `api-request-shape` tool count; brief has all sections.

### P2: call subagents in the foreground — [e] ~4.5M (of 5.4M measured wait cost)
- Change: ROUTINE.md step 2 (ad-reader) and step 5 (tailor): "Agent tool with `run_in_background: false`";
  several ad-readers in one message still run in parallel. Desktop defaults to background [m: meta
  `requestShape: background` on all 35].
- No function lost: same agents, same tasks, same replies; the reply comes back in the tool result.
- Also removes the 6 `sleep` guard blocks and the 2 bad Monitor calls from the 2026-11-08 review.
- Risk: low–medium; must confirm a Desktop scheduled run accepts foreground Agent calls.
- Verify: 0 mid-run calls with no tool / only sleep or wrap_up (now 51 [m]).

### P3: read `file` ads with `extract.py read` (no subagent, no re-typing) — [e] 2–3M net
- Change: ROUTINE.md step 2: for `| file` tasks (84% [m]) run `python engine/tools/extract.py read --model
  sonnet` (code exists: headless `claude -p`, no tools, no MCP, empty cwd, `--json-schema`, same reader
  instructions + schema). Main then reads the stored extracts for scoring; ad-reader keeps url/indeed/list.
  tools/extract.py `cmd_read`: print tokens/cost per ad (claude -p runs are **not logged** in transcripts).
  Alternative covering all task kinds: a SubagentStop hook that saves the reader's reply to
  data/ads/incoming/ (removes the 397k-char Write copy) — needs a hook-docs check.
- No function lost: same prompt and schema; `extract.py save` checks replaced by the same `problems()` check
  in `cmd_read`; this path is the one the eval suite already measures (baseline v1.0.0).
- Risk: medium. Model must be pinned (default could be Opus); serial claude -p is slower; a usage limit gives
  FAILED lines (retried next run).
- Verify: `tools/eval_run.py run --model sonnet` + `compare` vs v1.0.0; incoming.json Write chars → ~0 for file
  tasks; `extract.py check data/ads`.

### P4: split ROUTINE.md and the playbook by step/day — [e] ~1.2M
- Change: main never needs playbook C, D (tailor-only) or H, I (Fridays): 6.3k of 13.2k chars [m]. ROUTINE.md:
  move step 9 (Fridays), weekend mode, setup-failure and "subagent missing" fallbacks to a file read only when
  that case applies. Tailor reads only B–D.
- No function lost: same text, read on the day/case it applies.
- Risk: low–medium; model may skip the extra read on Fridays.
- Verify: Friday brief still has the weekly review; Read sizes in the next runs.

### P5: Gmail status mails via the reader, not main — [e] ~0.4M
- Change: ROUTINE.md step 7 + ad-reader.md: a `list mail-status | <since>` task that returns fixed fields
  (kind confirmation/rejection/interview, company, role, date). Main runs add_applied / tracker as now.
- No function lost: same matches, same tools; main no longer reads untrusted mail text (fits rule 7).
- Risk: low; one more schema in extract.py save.
- Verify: same tracker rows on a day with a confirmation mail.

### Lower
- P6 [e] ~0.5M: move tailor-only facts (cover-letter facts, CV tailoring decisions) out of the always-loaded
  CLAUDE.md into a file the tailor reads. Risk: main writes outreach/follow-ups and may need them. Ask first.
- P7 [e] ~0.3M: `brief.py` renders fixed brief parts (Decisions checklist, folder moves, sources, guard line).
- P8 (0 tokens, lower usage weight): `model: sonnet` in ad-reader.md and tailor.md. Both inherit today
  [m: no `model:` field]; an Opus main would run them on Opus. Haiku for ad-reader only after
  `eval_run.py --model haiku` matches v1.0.0 (German 94%, role type 95%). Tailor and main stay Sonnet.
- Already fixed by hand (not counted): get_job_details retries, guard-block retries.

## How to measure after each change
Re-run the harness weekly review and the per-run split: routine main per run (now 3.95M avg), first-call cache
write (now ~51k), mid-run wait calls (now 51 / 5.4M), incoming.json Write chars (now 397k), subagent tokens.
Outputs: same brief sections, `extract.py check` passes, eval compare within tolerance.
