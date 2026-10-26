---
status: accepted
date: 2026-10-26
decision-makers: [maintainers]
---

# 0028. Targeted Ansible for image provisioning, hybrid AD DS storage joins and static host day-2 configuration

## Context and Problem Statement

[Decision 0006](0006-no-ansible.md) originally kept Ansible out of the kit because Nerdio's dynamic
auto-scale continuously creates and destroys session hosts, and `nme_scripted_action` covers most
in-guest runtime scripts. However, full enterprise automation across every Nerdio scenario hits
three places where Terraform and Nerdio Scripted Actions alone fall short:

1. **Golden image hardening and enterprise agent baking (`packer/avd-win11`):** Enterprises often
   maintain existing declarative Ansible roles (`ansible.windows`, `community.windows`) for CIS
   benchmarks, EDR/AV agents, root certificates and line-of-business prerequisites that are cleaner
   and more idempotent in Ansible than imperative PowerShell scripts.
2. **AD DS `AzFilesHybrid` domain join for FSLogix Azure Files shares:** Joining an Azure Storage
   account to on-premises Active Directory Domain Services requires running `AzFilesHybrid`
   (`Join-AzStorageAccount`) from a domain-joined Windows management host with AD credentials, then
   collecting the resulting `domain_guid`, `domain_sid` and `storage_sid` for stage 1's
   `azurerm_storage_account`.
3. **Static and personal host pools (`nme_static_host_pool`) and OpenBao VM day-2 management:**
   Unlike pooled dynamic host pools that re-image frequently, persistent personal desktops and
   static host pools live long enough to need idempotent day-2 configuration management discovered
   by Azure tags (`azure.azcollection.azure_rm`).

## Considered Options

- Keep [0006](0006-no-ansible.md) strictly ("No Ansible") and write imperative PowerShell for all
  three gaps
- Use Ansible everywhere, replacing `nme_scripted_action`
- Add targeted, optional Ansible (`ansible/`) for golden image provisioning, `AzFilesHybrid`
  storage domain join, and tag-driven day-2 management of static/personal hosts while keeping
  Terraform + Nerdio Scripted Actions as the default for dynamic host pools

## Decision Outcome

Chosen option: "Targeted, optional Ansible (`ansible/`)", superseding [0006](0006-no-ansible.md).

- **Terraform (`azurerm`, `azuread`, `azapi`, `nerdio/nme`, `vault`, `restapi`)** remains the primary
  control plane for all Azure, Entra, Vault/OpenBao and Nerdio Manager resources.
- **Nerdio Scripted Actions (`nme_scripted_action`, `nme_scripted_action_group`,
  `nme_scripted_action_profile`)** remain the primary mechanism for runtime lifecycle hooks
  (`on_vm_create`, `on_host_create`, `on_start`, `on_stop`, `on_remove`) on auto-scaled dynamic host
  pools.
- **Ansible (`ansible/`)** provides:
  1. `ansible/playbooks/avd-image.yml`: idempotent Windows 11 multi-session golden image
     customization (enterprise root certificates, CIS baseline registry hardening, Defender AVD
     exclusions, FSLogix/Teams/OneDrive per-machine preparation) invoked during Packer builds or
     standalone image maintenance.
  2. `ansible/playbooks/ad-ds-fslogix-join.yml`: automated `AzFilesHybrid` domain join for Azure
     Files FSLogix storage accounts from a domain-joined management host, emitting the exact
     `active_directory` block (`domain_name`, `domain_guid`, `domain_sid`, `netbios_domain_name`,
     `forest_name`, `storage_sid`) consumed by `01-platform`.
  3. `ansible/playbooks/session-host-day2.yml` + `ansible/inventory/azure_rm.yml`: dynamic Azure
     tag-based inventory and day-2 state enforcement for static/personal host pools and the OpenBao
     server.

### Consequences

- Good, because enterprises with existing Ansible roles and hybrid AD DS estates get complete
  end-to-end automation without manual PowerShell runbooks.
- Good, because Ansible remains optional: default Entra-joined deployments in Azure Cloud Shell
  still need only Terraform and Python standard library.
- Neutral, because maintainers keep a clear boundary: use `nme_scripted_action` for ephemeral
  auto-scaled host lifecycle hooks, and Ansible for image baking, hybrid AD DS domain joins and
  persistent hosts.
