---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0009. Prefer Azure, GitHub, HashiCorp and open-source tooling

## Context and Problem Statement

Third-party services keep coming up as options: CDN and DNS providers such as Cloudflare, hosted
scanners, paid SaaS dashboards. Each one adds an account to create, a bill and a credential for
every community user, and another dependency the kit has to document and test. None of the
roadmap needs one: Nerdio Manager runs on Azure App Service behind Azure's own endpoints, AVD
traffic goes through Microsoft's gateway, and the kit uses Azure DNS and private endpoints.
Which tools and services should the kit reach for?

## Considered Options

- A fixed preference order: Azure, then GitHub, then HashiCorp/HCL, then open source
- Best tool per job, including third-party SaaS

## Decision Outcome

Chosen option: "A fixed preference order", because every extra service is a cost for every
community user. Prefer, in this order:

1. Azure-native services and Microsoft tooling (Azure DNS, private endpoints, Defender for Cloud,
   Microsoft Learn).
2. GitHub (Actions, Pages, issues, secret scanning).
3. HashiCorp tooling in HCL (Terraform, Packer, and Vault where a secret store is needed).
4. Open-source tools (for example Checkov or Trivy for IaC scanning, Playwright).

A third-party service is added only when it is truly needed and nothing in that list covers the
need. Its record must say why the list fell short.

### Consequences

- Good, because a community user needs only an Azure tenant and a GitHub account to run the kit.
  Optional paid tiers such as HCP Packer stay optional.
- Neutral, because Cloudflare and similar services are out. A community docs site, if one is ever
  wanted, uses GitHub Pages.
- This matches earlier calls: no Ansible ([0006](0006-no-ansible.md)), GitHub Actions forms as
  the button UX ([0007](0007-button-ux.md)), and the IBM tools dropped from the
  [roadmap](../stack-options.md#tool-verdicts).
