# Dress rehearsal: the full pilot path in a throwaway sandbox

Run the exact path the first production pilot will use, end to end, in a **personal sandbox**
tenant you can tear down, and write down everything that breaks. The pilot runbook
([pilot.md](pilot.md)) only starts once this rehearsal meets its [exit criteria](#exit-criteria).

Rules for the rehearsal:

- **Personal sandbox only.** Nothing here runs in a governed tenant. The governed pilot has its own
  gate ([pilot.md](pilot.md#phase-0-intake)).
- **Same path as the pilot**: pipeline install, approval gate, the wizard, stage 2, verify, drift.
  Where the pilot will differ (locks on, admin consent by hand), rehearse the pilot's setting.
- **Log every break** in the [run log](#run-log) as you go, with no IDs, domains, emails or names.
  A break that has a cause and a fix also goes into
  [known-errors.yaml](knowledge/troubleshooting/known-errors.yaml).
- **Leave other projects' resources alone.** A sandbox may hold resources that aren't the kit's
  (no `nerdio-kit-role` tag). Don't delete them, and pick an AVD address range that doesn't
  overlap their networks; preflight warns on overlaps.
- **Timebox and cost.** Nerdio's App Service (B3), SQL (S1), the NAT gateway and any session hosts
  bill while they're up. Plan one or two sittings and tear down at the end of the last.

Every command runs in Azure Cloud Shell (Bash, persistent storage) in a browser, iPad included.
If the Cloud Shell prompt starts with `PS`, type `bash` first. You run each step yourself; an
assistant may explain a plan but never applies it.

## What the rehearsal proves

| # | Claim | Proved by step | Live-tested before? |
|---|---|---|---|
| 1 | The pipeline bootstrap creates identities, state and GitHub environments | 3 | No |
| 2 | The setup chat deploys, connects to Claude keylessly and saves answers | 3, 4 | No |
| 3 | The approval gate applies exactly the plan the reviewer saw | 6 | No |
| 4 | The terraform install brings Nerdio Manager to its wizard (Entra-only SQL, Key Vault cert sign-in) | 6, 7 | No |
| 5 | Terraform's consent grants match what the wizard asks for | 8 | No |
| 6 | Stage 2 reaches Nerdio's REST API with the Key Vault secret hand-off | 9 | No |
| 7 | Verify and drift come back clean | 10, 12 | No |
| 8 | Locks, then a clean teardown, leave nothing behind | 15 | Partly (Cloud Shell destroy, 2026-10-17) |
| 9 | Optional: Copilot's resource group and checks; the Bicep stage | 11, 14 | No |

## 0. Before you start

- Cloud Shell in **persistent** mode (`ls ~/clouddrive` works).
- An Entra security group for the chat's admins (the examples use `AVD Admins`).
- A GitHub account with admin on the repository the pipeline will use, and `gh` sign-in from
  Cloud Shell (`gh auth login`, "Login with a web browser").
- For the chat on the Claude API: an admin of your Anthropic organization, for one step.
- Decide now whether you're rehearsing Copilot (step 11): it's an answer at init time.
- Open the [run log](#run-log) and note the date, the kit commit (`git rev-parse --short HEAD`)
  and Cloud Shell's Terraform version.

## 1. Clone and pin the sandbox

```bash
git clone https://github.com/nickprignano/nme-automation ~/nme-automation && cd ~/nme-automation
az account show --query name -o tsv     # the personal sandbox subscription?
./nerdio use sandbox                    # remembers this tenant and subscription as "sandbox"
```

Use the environment name **`sandbox`**: the deploy and drift workflows only offer `sandbox`, `dev`
and `prod` (an environment saved earlier under another name can't be picked in the Actions form).

## 2. Answer and check

```bash
./nerdio init --set environment=sandbox --set enable_resource_locks=true   # pilot setting: locks on
# add --set nerdio_ai=true to rehearse Copilot (step 11)
./nerdio preflight --save ~/rehearsal          # read-only; report in ~/rehearsal (mode 600)
```

Fix what it reports with the `./nerdio fix ...` lines it prints (each asks before sending), and
rerun until it's clean apart from `manual` items. Log anything that preflight missed and the apply
later hit: that's a preflight gap worth a check of its own.

## 3. Bootstrap the pipeline and deploy the chat

```bash
gh auth login
./nerdio assistant --admin-group "AVD Admins" --pipeline
./github/settings.sh apply            # repository ruleset the apply gate trusts; see github/README.md
```

Rehearse the pilot's consent choice: if the pilot will grant admin consent by hand (likely under
PIM), answer `./nerdio init --set grant_admin_consent=false` and, in
`00-pipeline/terraform.tfvars`, set `access = { apply_graph_roles = [...] }` without
*AppRoleAssignment.ReadWrite.All* and *DelegatedPermissionGrant.ReadWrite.All*, before the
bootstrap ([access.md](access.md#making-it-stricter)). An Entra admin then consents once per app
after step 6.

Then connect the chat to the Claude API ([assistant.md](assistant.md#claude-api)):

```bash
./scripts/install-ant-cli.sh
ant auth login --no-browser --profile nerdio-admin --scope org:admin
./nerdio assistant --connect-claude
ant auth logout --profile nerdio-admin
```

Open the chat URL it printed, sign in, and finish **/setup/github** (two clicks).

Log: the bootstrap's duration, any role it said you lacked, whether the chat answered first time,
and any 403 from the Claude API.

## 4. Drive the setup from the chat

Walk the chat through discover, prepare and configure, and let it save the answers to the
pipeline. Compare `./nerdio show` with what the chat saved. If the chat fails, log it and fall back
to `./scripts/pipeline/bootstrap.sh --answers-only` so the rest of the rehearsal can continue.

## 5. Preflight from the pipeline

Actions > **deploy** > environment `sandbox`, stage `preflight`. Its role checks come back
`manual` by design (the apply identity holds those roles). Anything else that differs from your
Cloud Shell preflight goes in the log.

## 6. Platform stage through the gate

Actions > **deploy** > `sandbox`, stage `platform`, **apply** ticked. Read the plan in the run
summary, then approve `sandbox-apply`. Note in the log:

- the plan's resource count and the apply's duration;
- whether the lock resources (`azurerm_management_lock`) applied. Expect a likely failure here:
  the apply identity's default roles (Contributor and Role Based Access Control Administrator)
  can't write locks; see [run log](#run-log) entry R2;
- whether the plan blocked anything as a stateful replace (it shouldn't on a first apply).

## 7. Wait for the install and check it

The apply starts an Automation job that deploys Nerdio's code; allow about 10 minutes. Then run
stage `verify` from the pipeline, or in Cloud Shell:

```bash
./nerdio preflight --stage post-install --save ~/rehearsal
```

Open the `nerdio_url` output. If the wizard doesn't appear, read the job in the
`nmw-app-automation-*` account and log its error lines with IDs blanked.

## 8. Nerdio's setup wizard (manual)

Follow [deployment-runbook.md step 4](deployment-runbook.md#4-setup-wizard-manual). Log:

- whether the console showed any database or connection error (tests the Entra-only SQL design);
- whether the wizard still asked for the second consent or said it was granted;
- how long the wizard took, and every screen you had to decide something on.

## 9. Stage 2 through the gate

Turn on the REST API under **Settings > Integrations** (or first try without it, and log whether
the plan reached Nerdio). Then Actions > **deploy** > `sandbox`, stage `config`, apply, approve.
Log whether the workspace, FSLogix profile, auto-scale profile and host pool appeared, and
whether Nerdio started building a session host.

## 10. Verify

Actions > **deploy** > `sandbox`, stage `verify` (`--stage post-wizard`). Every check should pass
or be `manual` with a reason. Ask the chat to explain the report; log anything it got wrong.

## 11. Optional: Copilot

Only if you answered `nerdio_ai=true`. In Nerdio's console, turn Copilot on with the resource
group and model `ai.copilot` names, then:

```bash
./nerdio preflight --stage post-wizard --features ai --save ~/rehearsal
```

Log the Azure OpenAI quota you needed and whether `ai.copilot` passed.

## 12. Drift

```bash
gh variable set NERDIO_DRIFT_ENVS --body '["sandbox"]'
```

Run Actions > **drift** once. A clean run opens no issue. Then change one setting in Nerdio's
console, run it again, and check the `infra-drift` issue names it; revert and confirm the next
run closes it.

## 13. Optional: golden image

Only if the pilot will use a custom image ([deployment-runbook.md step 7](deployment-runbook.md#7-golden-image)).
Packer builds in Cloud Shell are unverified; log whether it finished inside Cloud Shell's
session limits.

## 14. Teardown, with the optional Bicep stage in the middle

Tear down in this order. Each pipeline destroy is a plan you approve.

1. **Stage 2:** Actions > **deploy** > `sandbox`, stage `config`, **destroy** and apply ticked.
   Delete any session hosts Nerdio built that Terraform doesn't know about first, from Nerdio's
   console.
2. **Stage 1:** stage `platform`, destroy, apply. Terraform removes its own locks first. If the
   Nerdio group won't delete because of the Smart Detection action group, follow
   [known error `smart-detection-action-group-blocks-destroy`](knowledge/troubleshooting/known-errors.yaml).
3. **Optional Bicep stage** (the names are free now; never run both engines on one environment
   at once): set `access = { plan_bicep_whatif = true }` in `00-pipeline` and rerun the bootstrap,
   then stage `bicep` with apply. It deploys only the landing-zone slice
   ([bicep/README.md](../bicep/README.md)). Check the what-if matched, then delete it:
   `az stack sub delete --name nerdio-<prefix>-platform --action-on-unmanage deleteAll` after
   checking what the stack holds.
4. **The chat:** stage `assistant`, destroy, apply. Archive the federation rule and the service
   account in the Claude Console, and uninstall the chat's GitHub App.
5. **The pipeline itself:** there is no bootstrap teardown command yet (log entry R3). In Cloud
   Shell: remove the state account's `CanNotDelete` lock, move `00-pipeline` state back to local
   (`terraform init -migrate-state` without the backend file), then
   `terraform -chdir=environments/example/00-pipeline destroy`. That also removes the GitHub
   environments.
6. **Leftovers:** check nothing tagged `nerdio-kit-role` remains, Entra app registrations are gone
   (they sit in the recycle bin for 30 days), and soft-deleted Key Vaults are listed by
   `az keyvault list-deleted`. Log anything you had to delete by hand.
7. `./nerdio use sandbox --forget` if you won't reuse the profile.

## Exit criteria

The pilot can be scheduled when all of these hold, on one rehearsal run:

- Steps 3 to 10 and 14 completed without editing Terraform by hand mid-run.
- Every break in the log is fixed in `main` (with a known-error entry) or has a written workaround
  the pilot runbook repeats.
- The lock question (R2) and the approver question (R4) are settled for the pilot.
- Teardown left no kit resources behind, so the pilot's own rollback is known to work.
- Elapsed time per stage is recorded, so the pilot's change window can be sized.

## Run log

One row per break, surprise or slow step, written as you go. Severity: **blocker** (stopped the
run), **workaround** (got past it by hand), **paper cut** (worked, but confusing or slow). Never
put IDs, domains, emails or names here; describe the resource by its kit role.

Entries R1 to R4 are predicted from reading the code before the first rehearsal. Confirm or
strike them during the run.

| # | Date | Step | What happened | Severity | Fix or known-error |
|---|---|---|---|---|---|
| R1 | predicted | 1 | The deploy and drift workflows only offer `sandbox`, `dev` and `prod`. An environment pinned under another name (for example from the earlier chat trial) can't be chosen in the Actions form | paper cut | Use `sandbox`; widen the choice list if more names are needed |
| R2 | predicted | 6 | With `enable_resource_locks = true` (the `prod` default) the pipeline's apply identity likely can't create `azurerm_management_lock`: Contributor excludes `Microsoft.Authorization/*/write`, and Role Based Access Control Administrator only covers role assignments | blocker | Give the apply identity a custom role with only `Microsoft.Authorization/locks/*` through `access.apply_roles` ([access.md](access.md#making-it-stricter)); the kit doesn't create one yet |
| R3 | predicted | 14.5 | `scripts/pipeline/bootstrap.sh` has no teardown mode; the pipeline's own state lives in the account being destroyed | workaround | Manual steps in 14.5; candidate for a `--destroy` mode |
| R4 | predicted | 6 | The apply environment has `prevent_self_review = false` hard-coded (a single maintainer approves their own run). A governed pilot may need a second approver | paper cut | Name a second reviewer in `NME_REVIEWERS`; a switch for self-review is a candidate change |
| | | | | | |
