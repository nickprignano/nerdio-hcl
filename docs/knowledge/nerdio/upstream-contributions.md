# Upstream contribution candidates (`nerdio/nme`)

Things this project could contribute to [Nerdio's Terraform provider](https://github.com/Get-Nerdio/NME-Terraform-Provider),
if Nerdio accepts outside contributions. Each entry has the evidence behind it so it can become
an issue or PR without re-research. Checked against commit `65e547f` (2026-09-21).

**Status values:** *candidate* (found, not raised) · *raised* (issue/PR link) · *merged* · *dropped* (say why).

## Before contributing anything

- **No license file.** The repo has no `LICENSE`, so by default nobody else has rights to reuse
  or modify the code, and there's no `CONTRIBUTING` guide. Ask Nerdio which license applies and
  whether they take outside PRs (and under what CLA, if any) before writing code for it.
- Nerdio already tracks its own gaps in
  [AVD-COVERAGE.md](https://github.com/Get-Nerdio/NME-Terraform-Provider/blob/main/AVD-COVERAGE.md).
  Line up with that matrix so a contribution fills a gap they've acknowledged.
- They state that imperative actions (power, reimage, drain, run script, log off, convert, clone)
  are out of scope for the provider by design. Don't propose those.

## Feature gaps

| Gap | Evidence | Why it matters for the kit | Status |
|---|---|---|---|
| App groups and app group assignments | AVD-COVERAGE 3.1 "Manage app groups" and 3.4 "Assign / unassign users & groups to app groups": ❌ | Users can't be granted desktops as code; the kit has to stop at the host pool. | candidate |
| Session host lifecycle (create, delete, list) | AVD-COVERAGE 3.2: ❌, no data source | Host counts on static pools can't be declared. | candidate |
| Host pool data sources | AVD-COVERAGE §4 "No host pool data sources" | Other stacks can't reference pools the kit didn't create. Likely the smallest useful first PR. | candidate |
| RemoteApps and MSIX app attach | AVD-COVERAGE 3.4: ❌ | RemoteApp deployments need console work. | candidate |
| Reimage and script-execution schedules | AVD-COVERAGE 3.4: ❌ | Image rollout cadence isn't reviewable as code. | candidate |
| Personal host-to-user assignment | AVD-COVERAGE 3.2: 🟡 (`nme_user_assignment` is RBAC only) | Personal-desktop pools need manual assignment. | candidate |
| Per-host-pool auto-scale override profiles | AVD-COVERAGE 3.3: ❌ | | candidate |
| In-place update for `workspace`, `linked_resource_group`, `linked_network` | AVD-COVERAGE §4: no update operation in the NME API, so changes force replacement | Replacing a linked network under live pools is disruptive. Needs a Nerdio API change first, so it's a request, not a PR. | candidate |

## Docs and packaging

| Item | Evidence | Suggested fix | Status |
|---|---|---|---|
| Not on the Terraform Registry | README installs from GitHub release zips via `dev_overrides`, and notes `terraform init` "can therefore fail". | Publish to the public registry. Until then, document a `filesystem_mirror` install, which keeps `terraform init` and lock files working (see [restricted-networks.md](../terraform/restricted-networks.md#workaround-filesystem-mirror)). | candidate |
| Examples pin an old version | `examples/main/main.tf` and `examples/provider/provider.tf` use `version = "0.0.1"`; README says `0.1.0`. | Bump the examples to the current release. | candidate |
| README references missing CI | README's layout table lists `.github/workflows`, but the public repo has no `.github` folder. | Publish the workflows, or drop the row. | candidate |
| Linux and Windows amd64 builds only | README: "packages the provider for Linux amd64 and Windows amd64". | Add darwin/arm64 and linux/arm64 to the release matrix. | candidate |
| REST API client tag is ambiguous | Nerdio's REST API article doesn't make clear which app ID goes in `NMW_REST_API_CLIENT:<app-id>`. *Unverified* until tested. | Once confirmed, suggest a provider docs page that walks through auth setup end to end. | candidate |

## Adding an entry

Add a row with the gap, a link or quote as evidence, why it matters, and *candidate*. When it's
raised upstream, replace the status with the issue or PR link.

_Last reviewed: 2026-10-16_
