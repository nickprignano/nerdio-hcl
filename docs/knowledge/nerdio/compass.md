---
title: "Nerdio Compass"
summary: "Nerdio's free SaaS VDI discovery and assessment tool: what it is, its lack of an API or Terraform surface, and how it relates to the kit"
topic: nerdio
status: verified
last_reviewed: 2026-11-11
---

# Nerdio Compass

Nerdio Compass is **not** an MSP or partner product (that's Nerdio Manager for MSP). It's a free
discovery and assessment tool for teams planning a move from an existing VDI estate (Citrix today;
Omnissa Horizon and Amazon WorkSpaces on the roadmap) to Windows 365, Azure Virtual Desktop or
both. It reports structure, configuration, workloads, dependencies and costs, and gives migration
readiness scores. No agent and no professional services engagement are needed
([overview](https://nerdiohelp.getnerdio.com/hc/en-us/articles/48062839049229-Nerdio-Compass-Overview),
[announcement](https://getnerdio.com/blog/announcing-nerdio-compass-start-your-vdi-modernization-journey-to-windows-cloud/)).

## How it runs

- **SaaS, signed in with Entra ID.** Onboarding is a four-step web wizard: sign in and accept a
  Microsoft consent screen, pick an Azure region, enter the organization name, accept the terms,
  and Compass creates a workspace. No install, script or app registration is described
  ([onboarding wizard](https://nerdiohelp.getnerdio.com/hc/en-us/articles/48134198794765)).
- **Data comes in two ways:** a direct connection, or an imported snapshot export. For Azure it
  collects Entra ID users and groups, Intune policies and devices, AVD session hosts and Windows
  365 Cloud PCs into snapshots; the raw snapshot is viewable as JSON, and the Entra users and
  groups tabs export to CSV
  ([analyze Azure](https://nerdiohelp.getnerdio.com/hc/en-us/articles/48134205541005)).
- **Permissions aren't spelled out** in the pages above; the consent screen lists them, and a
  separate first-sign-in article covers them. Check it before anyone consents in a governed tenant.
- Its help center is `nerdiohelp.getnerdio.com`, not the Nerdio Manager one (`nmehelp`).

## Automation surface

- **No public API, PowerShell module or Terraform resource** is documented, and Compass isn't in
  the `nerdio/nme` provider (which is a Nerdio Manager REST client). The only "API" on the roadmap
  is Compass *reading* Citrix Monitor APIs
  ([roadmap](https://nerdiohelp.getnerdio.com/hc/en-us/articles/48062860161549-Nerdio-Compass-Roadmap)).
- **Roadmap:** GA in November 2026 (Citrix export proxy, AI assistant, Horizon, WorkSpaces,
  Windows 365 migration). In 2027: AVD and AVD Hybrid support, a trial purchase flow from Nerdio
  Manager, and Compass **replacing Nerdio Manager's Advisor and Modeler tools**.

## How it fits the kit

- **Not on the deploy path.** The kit deploys and configures Nerdio Manager; Compass is a
  pre-sales or planning assessment that runs before that, in Nerdio's SaaS. There is nothing for
  Terraform to manage.
- **Possible use in the *discover* phase:** the setup chat could ask whether a Compass assessment
  exists and use its exported numbers (users, host counts) to suggest sizing answers. That needs a
  stable export format first; today only CSV tabs and the raw snapshot JSON exist.
- **Not a substitute for the readiness preflight** ([readiness.md](readiness.md)): Compass assesses
  the estate you're leaving; preflight checks the tenant you're deploying into.
- **Watch item:** the Advisor and Modeler replacement in 2027 may change what Nerdio Manager
  exposes after install. **Upstream ask, if Nerdio allows:** a documented API or a stable export
  schema so the kit can read an assessment.
