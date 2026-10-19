# Model-selection pilot: measuring and reporting

This kit is one of the pilot projects for the family's model-selection convention
([decision 0022](knowledge/decisions/0022-family-model-selection-convention.md), which points to
[ai-brain 0006](https://github.com/nickprignano/ai-brain/blob/main/docs/knowledge/decisions/0006-model-selection-convention.md)).
The pilot runs from 2026-10-18 to 2026-11-30, and the family reviews it on 2026-12-01.

## What is set where

| Where | Model and effort | Set in |
|---|---|---|
| Project chat (routing, short answers, memory) | `claude-sonnet-5-5`, `low` | The project's instructions |
| Threads and Claude Code sessions in this repo | `claude-opus-5-5`, `medium`; raise effort before switching model | The project's instructions, and `.claude/settings.json` (`model`, `effortLevel`) |
| Setup chat (an app with tools that change things) | `claude-opus-5-5`, `medium` | `NERDIO_MODEL` and `NERDIO_EFFORT`, from the `00-assistant` stage's tfvars |

The setup chat stays on the convention's default for its kind of app, so it needs no
"Model override" decision. Write one only if the pilot's numbers show it needs something else.

## What to collect

**Setup chat (app measures).** Each chat turn is one task. Its `chat_turn` log line has the outcome,
model calls, tool errors, latency and summed tokens ([assistant.md](assistant.md#cost)). From Cloud
Shell, for the pilot window:

```bash
az monitor log-analytics query -w "$(az monitor log-analytics workspace list -g rg-nme-assistant --query '[0].customerId' -o tsv)" \
  --analytics-query 'ContainerAppConsoleLogs_CL
  | where TimeGenerated between (datetime(2026-10-18) .. datetime(2026-12-01))
  | where Log_s has "\"chat_turn\"" | extend r = parse_json(Log_s)
  | summarize turns = count(), completed = countif(tostring(r.outcome) == "completed" and toint(r.tool_errors) == 0),
      input = sum(toint(r.input_tokens)), output = sum(toint(r.output_tokens)),
      cache_read = sum(toint(r.cache_read_input_tokens)), cache_write = sum(toint(r.cache_creation_input_tokens)),
      p95_ms = percentile(toint(r.latency_ms), 95) by model = tostring(r.model), effort = tostring(r.effort)
  | extend failure_pct = round(100.0 * (turns - completed) / turns, 1),
      cache_hit_pct = round(100.0 * cache_read / (input + cache_read + cache_write), 1),
      tokens_per_completed = iff(completed > 0, (input + output + cache_read + cache_write) / completed, long(null))'
```

- **Failure rate:** turns that ended in a refusal, `max_tokens`, the step limit, a failed model
  call or a tool error. A user retry after a failed call shows up as an `error` turn; the server
  keeps no state, so it can't see other retries.
- **Cache hit rate:** cache read tokens over all input tokens. Near zero means the prompt cache
  is breaking.
- **Dollars per completed task:** multiply the token counts by the prices on the AI KB's
  [Claude API page](https://github.com/nickprignano/ai-brain/blob/main/docs/knowledge/claude-api/README.md#choosing-a-model).
  Don't copy prices into this repo.

If no setups ran during the pilot, say so in the report instead of estimating.

**Project sessions (Claude measures).** Keep a running tally while you work:

- **Bump rate:** threads that had to move up a model or effort level, or needed you to redo work,
  over all threads in the window. Note which step each bump took (`high`, `xhigh`, Fable).
- **Restarts:** sessions you restarted because quality slipped.
- **Cache share:** run `/usage` in Claude Code near the end of the pilot and note the prompt-cache
  share it reports.

## Reporting

File the numbers on 2026-11-30, before the review on 2026-12-01, as a knowledge base feedback issue
on [ai-brain](https://github.com/nickprignano/ai-brain/issues/new/choose) against its Claude API
page (`claude-api/README.md`). Counts and percentages only: no tenant, subscription, environment,
resource or user names, no employer or customer detail, and no transcript text.

```markdown
Project: Nerdio (nerdio-hcl), pilot 2026-10-18 to 2026-11-30, convention ai-brain 0006

Claude sessions
- Threads: <n>; bumped: <n> (<pct>%): to high <n>, to xhigh <n>, to Fable <n>; redone <n>
- Restarts: <n>
- Cache share (/usage): <pct>%
- Tasks that failed: <n>, each in one line (what kind of task, what went wrong)

Setup chat (claude-opus-5-5, medium)
- Turns: <n>; failure rate: <pct>% (refusal <n>, max_tokens <n>, step limit <n>, error <n>, tool errors <n>)
- Tokens per completed turn: <n>; cache hit rate: <pct>%; p95 latency: <ms> ms
- Model override needed: no / yes (why)
```
