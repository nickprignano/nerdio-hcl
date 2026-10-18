---
title: "Chatbot-first deployment: where chat stops"
summary: "Every deployment step, whether the setup chat can drive it today, what blocks it, and the automation fix or workaround"
topic: roadmap
status: plan
last_reviewed: 2026-10-17
---

# Chatbot-first deployment: where chat stops

Every Azure deployment the kit does starts in the setup chat ([decision 0017](decisions/0017-chatbot-first-deployment.md)).
This page lists each step of a deployment, whether chat can drive it today, and, where it
can't, what blocks it and what we do about it. Update a row when its fix lands or a live run
proves it wrong.

"Chat drives it" means the user talks to the chat and, at most, approves something in GitHub.
It never means chat applies anything: applies still wait for a named reviewer
([0016](decisions/0016-gated-deploy-pipeline.md)), and secrets never pass through the conversation.

None of this has run against a live tenant yet. The first full chat-driven deployment runs in
a trial tenant, from the bootstrap onwards; the first production deployment follows the same
path from a clean start.

## Step by step

| # | Step | Chat today | What blocks it | Fix or workaround | State |
|---|---|---|---|---|---|
| 0 | Tenant intake: the organization's own approval to deploy into this subscription | No, by design | Some tenants govern subscriptions through an intake or change process (a lab management tool, a change board). It's theirs, not the kit's | Follow it before step 1, every time, and record the approval. The chat asks about it first and stops until it's approved. Never bypass it to save time | Rule |
| 1 | Deploy the chat itself (`./nerdio assistant`) | No | Something has to exist before the chat can | One Cloud Shell paste, once per tenant. Cannot go away: it is the bootstrap | Inherent |
| 1a | Connect the chat to Claude (Claude API, [0020](decisions/0020-claude-api-federation-for-the-chat.md)) | No | Trusting the chat's identity is an Anthropic organization admin's call, and their sign-in is interactive | `./nerdio assistant --connect-claude` after one `ant auth login`, in the same Cloud Shell session; or the Claude Console with `--console`. Not needed with Foundry, which waits on Microsoft quota instead | Built, untested live |
| 2 | Pipeline bootstrap (`scripts/pipeline/bootstrap.sh`) | No | Needs Owner, a Graph role admin and `gh auth login`: the rights the pipeline's identities get | Same Cloud Shell session as step 1. It also sets the repository settings the kit needs in Terraform (`modules/github-repo`: kb labels, read-only workflow token, Actions pull requests, a ruleset on `main`). Next: one command that runs steps 1 and 2 together | Next |
| 3 | Create the chat's GitHub App | Yes, two clicks | GitHub requires a person to confirm an app | `/setup/github` manifest flow (PR #11) | Done |
| 4 | Make the chat image public | No | GitHub has no API for package visibility | Once, by the kit's maintainer only. Community users pull the public image | Inherent, maintainer only |
| 5 | Discover and configure answers | Yes | | `get_questions` and `set_answers` against the schema | Done |
| 6 | Readiness check | Paste only | The chat can't run commands in the tenant | `preflight` stage in the deploy workflow, run as the read-only plan identity. Chat starts it and reads the results | Built, untested live |
| 7 | Fix what preflight finds (quota, vCPU, PIM roles) | No | `./nerdio fix` runs as the person in Cloud Shell | Quota and vCPU requests can move to a gated pipeline job (they need write rights, so behind the apply approval). PIM activation is the person's own and stays a Cloud Shell paste | Next |
| 8 | Save answers for the pipeline | Yes | | `pipeline_save_answers` | Done |
| 9 | Take over a deployment made from Cloud Shell | No | Cloud Shell runs name things differently from the answers, so the pipeline would plan replacements | `bootstrap.sh --adopt` moves the state and carries over the values that run used; plans lay them over the answers and list them | Built, untested live |
| 10 | Plan and apply the platform stage | Yes, with a GitHub approval | Applies need a reviewer, by design | Pipeline (0016). Also fixes Cloud Shell's idle timeout killing long applies | Done, untested live |
| 11 | Explain a failed run | Links only | The chat saw job conclusions, not the error | Each run saves its error and the log's last lines, IDs masked; chat reads them with the known-errors list | Built, untested live |
| 12 | Nerdio app code deploy (Automation job) | Partly | The apply doesn't wait for the job | `nerdio_health` check warns until the app answers. Next: a verify stage the chat can start | Next |
| 13 | Admin consent | Yes | | Terraform grants it with `grant_admin_consent = true` | Done |
| 14 | Nerdio first-run wizard | Guided only | Nerdio has no API for the directory profile or first run | Chat walks through it screen by screen with the exact names from the apply's result. Lasting fix needs Nerdio's APIs ([upstream asks](nerdio/upstream-contributions.md)); optional Playwright bridge on the roadmap | Needs Nerdio |
| 15 | Enable Nerdio's REST API (Settings > Integrations) | Guided only | No API to turn it on | Part of the wizard walkthrough. Ask Nerdio to enable it at install | Needs Nerdio |
| 16 | Plan and apply the config stage | Yes, with a GitHub approval | | Pipeline (0016) | Done, untested live |
| 17 | Golden image build (Packer) | No | No pipeline stage; Packer from Cloud Shell is untested | Add an image stage to the deploy workflow, behind the same approval | Next |
| 18 | Add the image in Nerdio | No | `nerdio/nme` has no image resource | Nerdio API lists gallery images; `Mastercard/restapi` as a stopgap, and an image resource as an upstream ask | Next / needs Nerdio |
| 19 | Hardening (`enable_hardening`, private access) | Plan only | With public access off, GitHub-hosted runners can't reach Key Vault or state | A self-hosted runner in the VNet (Container Apps job), then the same pipeline | Next |
| 20 | Verify and hand over | No | No checks the chat can run | Post-deploy checks (`check` blocks, `terraform test`) as a pipeline stage, plus a Playwright launch test | Next |
| 21 | Update the chat (new image) | No | The chat's own stage isn't in the pipeline | Add `00-assistant` as a pipeline stage; the chat can then plan its own update, still behind approval | Next |
| 22 | Recover a stuck state lock | No | `force-unlock` is a person's call | Gated workflow input that unlocks a named lock ID after approval | Next |
| 23 | Tear down | No | Destroy isn't in the pipeline | Destroy as a separate workflow behind approval, never offered by the chat unprompted | Later |

## What only Nerdio can remove

Steps 14, 15 and 18 need Nerdio to ship an API or provider resource: directory profile, first
run, REST API enablement and images. The asks, with the evidence, are in
[upstream-contributions.md](nerdio/upstream-contributions.md). Until then, the chat guides the
person through those screens with exact values, so nothing has to be looked up.

## What can never move into chat

- The first bootstrap (steps 1 and 2): something with Owner and Graph admin rights has to create
  the identities the chat and pipeline use.
- Approving an apply: the approval lives in GitHub, outside anything the chat or a prompt can
  reach. That's the point.
- Anything handling a secret: the person runs that step; the chat never sees the value.
