---
status: accepted
date: 2026-10-17
decision-makers: [maintainers]
---

# 0016. Deploy through GitHub Actions with OIDC and a reviewer gate; chat drives the pipeline

## Context and Problem Statement

Deploying means pasting commands into Cloud Shell, stage by stage. The goal is a turnkey,
chat-driven deployment ([0008](0008-chat-front-door.md), [0014](0014-self-hosted-setup-chatbot.md)),
but the chatbot runs in the tenant it deploys, is reachable from the internet and is driven by a
language model. How can chat run the deployment without anything chat-facing holding the rights
to change the tenant?

## Considered Options

- GitHub Actions with OIDC identities and a required-reviewer environment; the chatbot starts runs
- The chatbot runs Terraform itself, as a Container Apps job with a privileged managed identity
- Keep pasting commands into Cloud Shell

## Decision Outcome

Chosen option: "GitHub Actions with OIDC identities and a required-reviewer environment",
because the approval lives in GitHub, outside anything the chatbot or a prompt can reach, and no
long-lived credential exists anywhere.

- A one-time Cloud Shell bootstrap (`environments/example/00-pipeline`, `modules/deploy-pipeline`)
  creates the state storage, a read-only **plan** identity and a privileged **apply** identity,
  each federated to one GitHub environment, plus the environments themselves. It's the one step
  that can't move into chat: something has to exist before the chatbot can.
- Plans run without approval. Applies run only after a named reviewer approves, from `main`, with
  no admin bypass, and apply the saved plan whose hash the plan job recorded.
- The plan identity names the apply identity as the deployer (`deployer_object_id`), so the plan
  shows the role assignments and ownership the apply will really create.
- IDs are environment secrets so GitHub masks them; the workflow never prints a GUID.
- Next: the chatbot gets tools to change answers through a pull request, start a plan and explain
  it. It can request an apply but never approve one. The chatbot never holds Azure rights beyond
  calling its model, which keeps 0014's rule that nothing in the conversation changes the tenant.

### Consequences

- Good, because nobody pastes commands after the bootstrap, and a phone tap approves an apply.
- Good, because a compromised or misled chatbot can at most start a plan; it can't apply.
- Good, because state moves off Cloud Shell's drive into storage with versioning and Entra-only access.
- Bad, because the apply identity holds tenant-wide Graph roles (app registrations, consent).
  The gate protects them; teams that grant consent themselves can trim them.
- Bad, because required reviewers need a public repository or a paid GitHub plan.
- Neutral, because the first live run is still to come: Graph role grants to managed identities,
  OIDC token refresh during long applies, and runner access to Key Vault are unverified.

## More Information

Design: `docs/pipeline.md`. Rejected: running Terraform inside the chatbot's own job, because a
web-facing, prompt-driven app would hold Owner-level rights with no gate outside itself.
Revisit when Nerdio ships first-run and directory-profile APIs, which would remove the remaining
browser step.
