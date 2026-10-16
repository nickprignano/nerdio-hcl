# Guided setup

Before anything is deployed, the kit needs about fifteen answers: what you're building, where,
and for how many people. They're defined once in [`schema/parameters.json`](../schema/README.md),
and every front door asks the same questions, applies the same defaults and runs the same checks.

| Phase | What happens | Chat | Command line | Button |
|---|---|---|---|---|
| Discover | Environment, identity model, users, workload | `setup` skill | `./nerdio init --phase discover` | configure workflow |
| Prepare | Read-only readiness checks | `setup` skill runs or explains them | `./nerdio preflight` | not yet |
| Configure | Names, network, storage, identity, first host pool | `setup` skill | `./nerdio init` | configure workflow (dry run) |

Bootstrap, deploy, the Nerdio wizard steps, verify and handover come next on the roadmap. Until
then, continue with [deployment-runbook.md](deployment-runbook.md).

## Command line

Works anywhere with Python 3, `az` and Terraform, including Azure Cloud Shell (Bash) in a browser.

```bash
az account show                 # the tenant and subscription the kit will use
./nerdio init                   # answer the questions; Enter keeps the suggestion
./nerdio preflight              # check roles, providers, region, VM size and quota
./nerdio show                   # what you answered, and what came from defaults
```

- `./nerdio init --advanced` also asks about subnets, naming, the profile share size and more.
- `./nerdio init --set user_count=40 --set workload=heavy` answers without prompts. A blank value
  (`--set prefix=`) goes back to the default.
- Answers are saved in `.nerdio/answers.json`, so you can stop and pick up later. Only what you
  typed is saved; anything left at its default keeps following your other answers.
- Tenant and subscription IDs are never asked. They come from `ARM_TENANT_ID` and
  `ARM_SUBSCRIPTION_ID` if set, otherwise from `az account show`.
- For groups, give display names (`AVD Users`) or `me`; they're looked up with `az` when the files
  are written.

`init` writes `setup.auto.tfvars.json` into `environments/example/01-platform` and
`02-nerdio-config` (`--env <folder>` for another environment). Both files are gitignored. Before
writing, Terraform itself checks the values against the stages' variable declarations, without
signing in or downloading providers. If you also use `scripts/cloudshell-bootstrap.sh`, its
`sandbox.auto.tfvars` loads first and `setup.auto.tfvars.json` overrides it.

## Preflight

`./nerdio preflight` only reads. It reports each check as pass, fail (with the fix), warn
(couldn't check) or confirm-yourself:

- Tools: Terraform 1.9 or later, `az`, `jq`, `git`.
- Sign-in, and **Owner** on the subscription.
- **Global Administrator**, or **Privileged Role Administrator + Cloud Application Administrator**,
  when Terraform grants admin consent. Roles eligible through PIM must be activated first.
- Resource providers for AVD and for what Nerdio deploys.
- The region, the VM size in that region, and vCPU quota for the host pool at full scale.
- Things no command can check: the Nerdio license and AVD user licenses.

`./nerdio preflight --json` gives the same results for the chat skill.

## Chat

Open the repo in Claude Code (terminal, desktop or web) and ask to set up Nerdio. The `setup`
skill in `.claude/skills/setup/` asks the schema's questions in conversation, cites the knowledge
base for its recommendations, runs `./nerdio` to record and check every answer, and shows the
result for review. It never asks for secrets and never applies anything.

## Button

**Actions > configure > Run workflow** shows the main questions as a form. It renders the tfvars
with placeholder IDs and has Terraform check them, so you can try answers without touching Azure.
The form is generated from the schema (`./nerdio form --write`), and CI fails if they drift.
Plan and apply will join it with the deploy workflow.
