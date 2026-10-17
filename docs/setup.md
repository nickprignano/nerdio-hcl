# Guided setup

Before anything is deployed, the kit needs about fifteen answers: what you're building, where,
and for how many people. They're defined once in [`schema/parameters.json`](../schema/README.md),
and every front door asks the same questions, applies the same defaults and runs the same checks.

| Phase | What happens | Chat | Command line | Button |
|---|---|---|---|---|
| Discover | Environment, identity model, users, workload | setup chatbot | `./nerdio init --phase discover` | configure workflow |
| Prepare | Read-only readiness checks | bot gives the command and reads the result | `./nerdio preflight` | not yet |
| Configure | Names, network, storage, identity, first host pool | setup chatbot | `./nerdio init` | configure workflow (dry run) |

Bootstrap, deploy, the Nerdio wizard steps, verify and handover come next on the roadmap. Until
then, continue with [deployment-runbook.md](deployment-runbook.md).

## Command line

Works anywhere with Python 3, `az` and Terraform, including Azure Cloud Shell (Bash) in a browser.

```bash
az account show                 # the tenant and subscription the kit will use
./nerdio init                   # answer the questions; Enter keeps the suggestion
./nerdio preflight              # check roles, network, policy, providers, region and quota
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

- Tools: Terraform 1.11 or later, `az`, `jq`, `git`.
- Sign-in, and **Owner** on the subscription (or Contributor plus User Access Administrator or
  Role Based Access Control Administrator).
- **Global Administrator**, or **Privileged Role Administrator + Cloud Application Administrator**,
  when Terraform grants admin consent. Roles eligible through PIM must be activated first.
- That you can create app registrations, when the kit creates the Nerdio Entra app. Many tenants
  turn this off for ordinary users; Cloud Application Administrator or Application Developer covers it.
- Resource providers for AVD and for what Nerdio deploys.
- The region, the VM size in that region, and vCPU quota for the host pool at full scale.
- With the terraform install, the App Service plan for Nerdio Manager (B3 by default): that the SKU
  is offered in the region and the subscription has quota for one. Sandbox and trial subscriptions
  often have a limit of 0, and the apply would otherwise fail late with "without additional quota".
- Networking: whether the AVD address range overlaps the subscription's other VNets (a warning) or
  the hub (a failure), whether you can read the hub and create the peering on it (Network
  Contributor), and whether privatelink DNS zones already exist elsewhere, such as a central DNS
  subscription the AVD VNet should link to instead.
- With the terraform install, whether the region takes new Azure SQL servers and offers the S1 tier.
- Enforced Azure Policy assignments on the subscription, listed for you to review. A deny (allowed
  regions or SKUs, no public endpoints, required tags) otherwise only shows up during the apply.
- In Cloud Shell, that storage is persistent, so Terraform state survives the session.
- Things no command can check: the Nerdio license and AVD user licenses.

`./nerdio preflight --json` gives the same results for the setup chatbot.

Resources an earlier run of the kit created (resource groups tagged `nerdio-kit-role`) don't count as
overlaps or as someone else's DNS zones, so a rerun after a partial apply stays clean.

When a region is the problem (a restricted VM size, no quota, or Azure SQL closed to new servers),
`./nerdio preflight --regions` runs the region checks across every region in the same geography and
prints one line per region. `--regions centralus,westus3` checks just those, and `--set` tries a
different answer for one run without saving it:

```bash
./nerdio preflight --regions
./nerdio preflight --regions --set vm_size=Standard_D8as_v5
./nerdio init --set location=centralus        # then keep the region that passes
```

## Fixing what preflight finds

Preflight's fix lines point at commands, not portal clicks. Each one shows exactly what it will
send and does nothing until you type `yes` (`--yes` skips the question, for pipelines):

```bash
./nerdio fix quota                                     # App Service quota (B3), as an Azure Support request
./nerdio fix quota --status                            # the kit's quota requests and their status
./nerdio fix vcpu --family standardDSv5Family --limit 48   # VM vCPU quota through the Azure Quota API
./nerdio fix roles                                     # activate eligible PIM roles (Entra and subscription Owner)
```

- App Service quota has no self-service API, so `fix quota` opens the request with Azure Support
  through its REST API (no paid support plan needed for quota). Replies go to your account's email.
- vCPU quota uses the Azure Quota API; most increases apply within minutes.
- `fix roles` only activates roles you're already eligible for. The `az` sign-in can't manage Entra
  PIM roles, so for those it signs in to Microsoft Graph PowerShell (built into Cloud Shell) with a
  device code; that needs the Graph PowerShell app consented for the PIM scopes in your tenant. Run
  `az login` afterwards so your token carries the new roles. PIM settings that need approval or a ticket number still need the portal.

The portal is the last resort: a command prints the portal path only if Azure refuses the request.
Cloud Shell's storage choice is the one thing with no command; Cloud Shell asks it on first start.

## Sharing output

Plans and errors name your subscription, tenant and object IDs, public IPs and account names.
To share output for help, in an issue or a chat, mask them first:

```bash
./nerdio redact --tail 40                 # the bootstrap script's last Terraform run
terraform plan 2>&1 | ./nerdio redact     # anything else, piped in
```

The bootstrap script keeps each Terraform run's output in `.nerdio/logs/` (gitignored, readable
only by you). Masking is best effort, so read what you paste. Secrets never belong in shared output;
Terraform already hides sensitive values.

## Chat

The setup chatbot runs in your own tenant and asks the schema's questions in conversation. It
cites the knowledge base for its recommendations, records and checks every answer with the same
engine, and shows the result for review. For anything that has to run in your tenant, it gives you
one command to paste into Cloud Shell. It never asks for secrets and never applies anything. How to
deploy it: [assistant.md](assistant.md).

## Button

**Actions > configure > Run workflow** shows the main questions as a form. It renders the tfvars
with placeholder IDs and has Terraform check them, so you can try answers without touching Azure.
The form is generated from the schema (`./nerdio form --write`), and CI fails if they drift.
Plan and apply will join it with the deploy workflow.
