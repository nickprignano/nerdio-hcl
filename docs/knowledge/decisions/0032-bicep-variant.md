---
status: accepted
date: 2026-11-10
decision-makers: [maintainers]
---

# 0032. A Bicep variant of the kit lives in `bicep/`, shares the schema and answers, and hands Nerdio configuration to stage 2

## Context and Problem Statement

Some Azure teams standardise on Bicep and won't take a Terraform dependency. The maintainer asked
for "the same install, idea and design as nerdio-hcl, but native Bicep". The kit is built HCL first
([guardrail 2](../../guardrails.md), [decision 0011](0011-terraform-native-install.md)), and its
stage 2 is written against Nerdio's own Terraform provider `nerdio/nme`
([decision 0001](0001-build-on-nerdio-provider.md)), which Bicep can't use. Where should a Bicep
variant live, how does it square with HCL first, and what does it do about stage 2?

## Considered Options

Where it lives:

- A. A `bicep/` folder in this repository, reading the same `schema/parameters.json` answers
- B. A separate repository with its own schema, docs and knowledge base

How Nerdio configuration (stage 2: workspaces, linked networks, host pools, auto-scale, FSLogix
profiles) is applied:

- S1. Bicep owns the Azure side (stage 1); stage 2 stays the existing Terraform root on `nerdio/nme`
- S2. Bicep `deploymentScripts` call the Nerdio Manager REST API from a container in the tenant
- S3. A Nerdio-published Bicep extension (Bicep extensibility), asked of Nerdio upstream
- S4. Bicep for Azure only, Nerdio objects set in the Nerdio console

## Decision Outcome

Chosen options: **A** and **S1 now, S3 as the upstream ask**, because they give Bicep teams a
native Azure deployment without forking the parts that make the kit turnkey.

**A over B.** The schema is what makes the kit one product: the chat, `./nerdio init` and the
Actions form all render one answers file. `bicep/environments/<env>/platform.bicepparam` reads the
same `environments/<env>/01-platform/setup.auto.tfvars.json` with `loadJsonContent()`, so one
interview drives either engine, and preflight, the knowledge base, decisions, guardrails and CI are
shared instead of copied. A separate repository would need its own copy of every one of those and
would drift. `bicep/` takes no content from other projects.

**HCL first, restated.** Terraform stays the reference implementation and the default. Bicep is an
opt-in variant for the Azure side only: same names, same resource layout, same inputs, and a
parity table in [bicep/README.md](../../../bicep/README.md). A change to stage 1 lands in Terraform
first; the Bicep side follows or is marked "not ported". Scripts are still thin glue in both
engines. Guardrail 2 gains one sentence pointing here.

**S1 over S2.** Stage 2 isn't Azure infrastructure; it is Nerdio's API, and `nerdio/nme` already
models it with state, plan and drift. A `deploymentScripts` port (S2) would:

- re-implement the provider in a script (create, update, delete, idempotency), with no plan or drift
  detection, which `what-if` can't see into
- put the REST API client secret inside a script container, against [decision 0015](0015-secrets-key-vault-default-openbao-optional.md)
  (the provider reads it ephemerally from Key Vault or OpenBao)
- add a storage account and container instance per run, and private networking work when public
  access is off ([decision 0030](0030-enterprise-guardrails-locks-and-gitops.md))
- risk adapting `nerdio/nme` code, which is unlicensed ([decision 0013](0013-unlicensed-code-reference-only.md))

S2 stays the fallback if the maintainer decides a Bicep user must never run Terraform at all; then
it gets its own decision. S4 is rejected (no portal click-paths).

**S3** is the clean end state: a Nerdio Bicep extension would make stage 2 native the way the
Microsoft Graph extension made Entra native. It's recorded as an upstream ask, not sent
([guardrail 8](../../guardrails.md)).

### What Bicep can and can't do in stage 1 (checked 2026-11-10)

| Need | Bicep answer |
|---|---|
| Plan before apply | `az deployment sub what-if`; deployment stacks also have what-if |
| State, delete of removed resources, drift | Deployment stacks (`az stack sub`) with `actionOnUnmanage` and deny settings |
| Entra app, service principal, app roles, admin consent | Microsoft Graph Bicep extension (v1.0): `applications`, `servicePrincipals`, `appRoleAssignedTo`, `oauth2PermissionGrants`, `federatedIdentityCredentials`; `keyCredentials` only (no passwords, which suits the kit's certificate sign-in) |
| Graph resources inside a stack or what-if | **Not supported.** Graph resources must deploy as a separate, plain subscription deployment, and their changes can't be previewed |
| Nerdio app code deploy (`azapi` starts an Automation job in Terraform) | `Microsoft.Automation/automationAccounts/jobs` is an ARM resource, so Bicep can start the same runbook natively (to verify live) |
| Runs from Cloud Shell on an iPad | Yes: `az` ships Bicep; no installs |

### Consequences

- Good, because a Bicep shop gets the same landing zone from the same interview, with no second
  schema, and the knowledge base keeps one voice.
- Good, because stage 2 keeps plan, drift and ephemeral secrets.
- Bad, because a Bicep user still runs Terraform for stage 2 until Nerdio ships an extension.
- Bad, because two engines double the stage 1 test surface; CI compiles and lints Bicep on every PR,
  but only Terraform has mocked tests.
- Bad, because Graph resources sit outside the stack, so the identity part has no preview and no
  stack-managed delete; it needs its own deployment and a documented teardown.

### First slice (this PR)

Landing zone only: resource groups, Log Analytics, regional spoke networks, private DNS (own or
hub), vWAN connection, FSLogix storage with locks, Compute Gallery. Not ported: Nerdio install
(`nerdio-core`), identity, hardening, secrets, ANF and the optional modules. Next slices, in order:
identity (Graph extension), `nerdio-core`, hardening.

The secrets slice keeps decision 0015's Key Vault hand-off. Because the Graph extension can't create
passwords, the REST API client secret is the one step done by a thin script
(`bicep/rest-client-secret.sh`), which pipes it from Entra into Key Vault unseen; the vault and its
access stay in Bicep.

## More Information

- [Microsoft Graph Bicep limitations](https://learn.microsoft.com/graph/templates/bicep/limitations)
  (no what-if, no stacks, no passwords, no role-assignable groups)
- [Deployment stacks known issues](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks-known-issues)
- [Deployment stack what-if](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks-what-if)
- [loadJsonContent](https://learn.microsoft.com/azure/azure-resource-manager/bicep/bicep-functions-files#loadjsoncontent)
- Accepted by the maintainer on 2026-11-10, choosing the mix (Bicep stage 1, Terraform stage 2)
  over REST API scripts or waiting for Nerdio. Revisit when Nerdio answers the Bicep extension ask
  or stage 1 parity passes a live sandbox run.
