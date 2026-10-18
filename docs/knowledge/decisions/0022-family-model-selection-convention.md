---
status: proposed
date: 2026-10-18
decision-makers: [maintainers]
---

# 0022. Follow the family's model-selection convention, as one of its pilot projects

## Context and Problem Statement

The setup chat picks its model and effort in this kit's own config, and nothing measures whether
the pick is right. The family is piloting one model-selection convention across its pilot
projects, and model choices are the AI KB's topic ([0021](0021-knowledge-base-family.md)). Does
this kit follow it, and what does that change here?

## Considered Options

- Follow the convention, with any exception recorded here as a "Model override" decision
- Keep this kit's own model choices

## Decision Outcome

Chosen option: "Follow the convention", because the setup chat is already on its default for an
agent with tools that changes things (Claude Opus 5.5 at `medium` effort) and already reads its
model, effort and provider from `NERDIO_MODEL`, `NERDIO_EFFORT` and `NERDIO_MODEL_PROVIDER`, as
the convention asks.

Also recorded in: [ai-brain 0006](https://github.com/nickprignano/ai-brain/blob/main/docs/knowledge/decisions/0006-model-selection-convention.md),
the source of truth for the defaults, fallbacks, measures and pilot dates. The facts behind it
(model IDs, prices, Foundry hosting and quota) are on the AI KB's
[Claude API page](https://github.com/nickprignano/ai-brain/blob/main/docs/knowledge/claude-api/README.md#choosing-a-model).

For the pilot this kit:

- Logs, per chat request, the model, effort, `usage`, `stop_reason` and latency, so tokens per
  completed setup turn and the failure rate can be measured: one JSON line per model call in the
  app's log, counts and timings only ([docs/assistant.md](../../assistant.md#cost)).
- Keeps the Claude API with workload identity federation as the main path and Foundry as the
  fallback where a tenant has quota ([0020](0020-claude-api-federation-for-the-chat.md)), which
  matches the convention's fallback rules.
- Files its pilot numbers as feedback on the AI KB's Claude API page.

### Consequences

- Good, because a model change for the chat follows evidence and the family's rules.
- Bad, because nothing is measured until the chat has real setups behind it.
- Neutral, because no default changes today.

## More Information

Revisit at the family's pilot review on 2026-12-01.
