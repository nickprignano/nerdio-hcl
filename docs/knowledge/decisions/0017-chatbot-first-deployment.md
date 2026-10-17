---
status: accepted
date: 2026-10-17
decision-makers: [maintainers]
---

# 0017. Every Azure deployment is chatbot-first

## Context and Problem Statement

The kit has three front doors over one engine: the setup chat, `./nerdio` in Cloud Shell and
the GitHub Actions forms ([0008](0008-chat-front-door.md)). Since the chat can drive the deploy
pipeline ([0016](0016-gated-deploy-pipeline.md)), it can carry a deployment much further than
answering questions. But several steps still drop the user back into Cloud Shell or a portal,
and Cloud Shell on an iPad loses long applies when it idles out. Which front door do we design
for first, and how do we find what's left?

## Considered Options

- Chatbot-first: every deployment starts in the chat, and each step it can't drive is a gap to close
- Keep the three doors equal and let users pick
- Cloud Shell-first, with the chat as an explainer

## Decision Outcome

Chosen option: "Chatbot-first", because the chat plus the gated pipeline is the only path that
is turnkey, survives a sleeping iPad and still keeps every apply behind a person's approval.

- Each deployment step is listed in [chatbot-first.md](../chatbot-first.md) with whether the
  chat drives it, what blocks it and the fix. A step the chat can't drive is a gap to automate,
  not a reason to hand the user a command, unless it is one of the inherent steps below.
- Inherent, and staying out of chat: the one-time bootstrap that creates the chat and the
  pipeline's identities, approving an apply (in GitHub), and anything that handles a secret.
- The chat still can't change the tenant itself. It works through the pipeline: read-only runs
  (readiness check, plans) after the user's yes, applies after a reviewer's approval.
- `./nerdio` and the Actions forms stay. They're the engine the chat and pipeline run, and the
  way the kit works without AI. They are no longer the main path we design for.
- Testing: the first full chat-driven deployment runs in a separate trial tenant, from the
  bootstrap onwards. The first production deployment follows the same path, built fresh from the
  chat rather than adopted from an earlier Cloud Shell sandbox run, so it gets production names.
  `bootstrap.sh --adopt` stays for anyone who started in Cloud Shell and wants to keep that
  deployment.

### Consequences

- Good, because users talk to one place and approve applies with a tap; nothing needs to stay
  open for a long apply.
- Good, because each gap is written down with its fix, so the inventory is the backlog.
- Bad, because more of the deployment runs as the pipeline's identities, which makes the
  apply identity's rights and the approval gate matter more.
- Bad, because a GitHub account and a repository with environments are now part of the main
  path, not an option.
- Neutral, because Nerdio's first-run wizard stays a browser step, guided by the chat, until
  Nerdio ships the APIs for it.

## More Information

Inventory: `docs/knowledge/chatbot-first.md`. Revisit when the first live chat-driven
deployment has run, and when Nerdio ships first-run or directory-profile APIs.
