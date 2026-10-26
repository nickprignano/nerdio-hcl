# Targeted Ansible Automation (`ansible/`)

Per [Decision 0028](../docs/knowledge/decisions/0028-targeted-ansible-for-images-and-hybrid.md),
Terraform (`01-platform` and `02-nerdio-config`) and Nerdio Scripted Actions (`nme_scripted_action`)
own the primary Azure/Nerdio control plane and ephemeral host lifecycle hooks. This folder adds
targeted Ansible playbooks for the three enterprise scenarios where declarative playbooks beat
imperative scripts:

1. **Golden image hardening & enterprise agents (`playbooks/avd-image.yml`):** Configures Teams
   WebRTC media optimizations, RDP Shortpath UDP 3390 listener & firewall rules, Microsoft Defender
   exclusions for FSLogix containers, consumer-experience policies, and enterprise root CA
   certificates. Can be run during Packer builds (`run_ansible_playbook = true` in
   `packer/avd-win11`) or standalone.
2. **AD DS `AzFilesHybrid` storage domain join (`playbooks/ad-ds-fslogix-join.yml`):** Runs
   `Join-AzStorageAccount` from a domain-joined Windows management host to join the FSLogix Azure
   Files storage account to on-premises Active Directory Domain Services, then prints the exact
   `./nerdio init --set` flags (`ad_domain_name`, `ad_domain_guid`, `ad_domain_sid`,
   `ad_storage_sid`, `ad_netbios_name`, `ad_forest_name`) for stage 1.
3. **Static & personal host pool day-2 management (`playbooks/session-host-day2.yml` +
   `inventory/azure_rm.yml`):** Discovers persistent session hosts by Azure tag and enforces
   service health (`RDAgentBootLoader`, `TermService`, `frxsvc`) and SMB 445 reachability to the
   FSLogix share.

## Quick start

```bash
ansible-galaxy collection install -r ansible/requirements.yml

# Verify dynamic inventory (uses your current `az login` or ARM_* variables)
ansible-inventory -i ansible/inventory/azure_rm.yml --graph

# Run day-2 checks against static/personal session hosts
ansible-playbook -i ansible/inventory/azure_rm.yml ansible/playbooks/session-host-day2.yml
```
