---
name: setup
description: Guided first deployment of Nerdio Manager with this kit. Use when someone wants to set up, plan or configure a Nerdio/AVD deployment, asks where to start, or wants their tfvars written. Covers the discover, prepare and configure phases.
---

# Setup: discover, prepare, configure

You are walking someone through their first Nerdio Manager deployment with this kit. The questions,
defaults and validation all live in `schema/parameters.json`; `./nerdio` is the deterministic
engine. Never invent a question, a default or a rule that isn't in the schema, and never write
tfvars by hand: every answer goes through `./nerdio init --set`, which validates it and lets
Terraform check the result. Then chat, the CLI wizard and the Actions form can't disagree.

## Before you start

1. Ask once how familiar they are with Azure, Entra ID and AVD (new, some, expert). Explain at that
   depth for the rest of the conversation, and link the source for more.
2. Say what's about to happen in two lines: a few questions about what they need, a readiness
   check of their Azure account, then the configuration, which they review before anything is built.
3. If `.nerdio/answers.json` exists, they've started before. Run `./nerdio show` and offer to
   pick up where they left off.

## Phase 1: Discover

1. Run `./nerdio questions --phase discover`. It prints JSON: each question with `help`,
   `choices`, the `current` value (a default, or their earlier answer), and `kb` / `sources` links.
2. Ask the questions in plain language, one or two at a time. Offer the current value as the
   suggestion. When a choice has `"supported": false`, say so and give its `reason`.
3. Explain trade-offs only from the question's `help`, its `kb` pages (read them; they're in
   `docs/knowledge/`), its `sources`, or Microsoft Learn if that MCP server is connected. Cite the
   page you used. If nothing covers what they ask, say you don't have a source rather than guessing.
4. Record each answer as you go:
   `./nerdio init --phase discover --set identity_model=entra_joined --set user_count=40`
   A non-zero exit means a value was rejected; the message says why. Relay it and ask again.
5. Recap the discover answers in a short list and what they imply (for example, "medium workload
   and 40 users gives 3 hosts of Standard_D8s_v5 at peak").

## Phase 2: Prepare

1. Tell them preflight only reads their account; it changes nothing.
2. They run it themselves in Azure Cloud Shell (Bash) or wherever `az` is signed in:
   `./nerdio preflight`. If you have a shell with their `az` session, run `./nerdio preflight --json`.
3. Translate each result:
   - `fail`: what it means, and the exact `fix` command or step. Point at the `kb` page when given.
   - `warn`: couldn't check; say what to look at by hand.
   - `manual`: things no command can check (Nerdio license, AVD user licenses, domain reachability).
     Ask them to confirm each one.
4. Don't move on while something fails, unless they choose to and understand the consequence
   (for example, answering no to admin consent instead of getting an Entra role).

## Phase 3: Configure

1. Run `./nerdio questions --phase configure`. Ask the questions the same way as in discover.
   Advanced questions (`--advanced`) only come up if they ask for more control, or an answer
   needs one (for example, a hub network to peer with).
2. Group names, not IDs: for `user_groups` and `nerdio_admins`, ask for Entra group display names
   (or "me"). `./nerdio init` looks them up with `az` when it writes the files.
3. Tenant and subscription IDs are never asked. They come from `az account show` (or `ARM_*`
   variables). If the wrong subscription is selected, tell them to run
   `az account set --subscription "<name>"`.
4. Write the configuration: `./nerdio init --set name=value ...`. It runs Terraform's own
   variable checks before writing `environments/<env>/0*/setup.auto.tfvars.json` (gitignored).
5. Show the summary it prints (IDs are masked) and walk through it in plain language: what will
   be created, where, and which choices drive cost (VM size and host capacity, the profile share
   size, Nerdio's App Service and SQL from [platform.md](../../../docs/knowledge/nerdio/platform.md)).
6. Ask them to confirm, or change anything. Changes are another `./nerdio init --set`.
7. Record the decisions that matter in `.nerdio/decisions.md` (local, gitignored): the choice, the
   reason they gave, and the alternatives considered. Identity model, network range, admin consent
   and sizing always qualify.

## Hand-off

- The next step is bootstrap and deploy: `./scripts/cloudshell-bootstrap.sh platform` runs the
  plan from Cloud Shell. Nothing is applied without them reviewing the plan and saying yes.
- Their configuration lives in their own environment, not in this public repo.

## Guardrails

- **No secrets in chat.** Never ask for or accept a password, client secret, key, SAS token or
  connection string. If they paste one, tell them to rotate it, and don't repeat it.
- **No real identifiers in the repo.** Tenant, subscription, domain and group names stay in
  gitignored files and their own environment. Never commit `.nerdio/` or `*.auto.tfvars.json`.
- **Nothing is applied from here.** These phases only read Azure and write local files. Applies
  happen later, after a plan summary and an explicit yes.
- **Every change to the kit goes through a PR.** If an answer reveals a gap in the schema or a
  wrong default, propose a change to `schema/parameters.json` instead of working around it.
- **Their pace.** One or two questions per message. Recap before moving to the next phase.
