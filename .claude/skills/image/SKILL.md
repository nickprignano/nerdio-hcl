---
name: image
description: Build and customize Windows 11 multi-session AVD golden images with Packer, VDOT, and optional Ansible playbooks, then link them to Nerdio Manager via Azure Compute Gallery.
---

# Image Skill (`nerdio-hcl`)

Use this skill when building or customizing AVD session host golden images in `packer/avd-win11/`.

## Workflow

1. **Prerequisites**:
   - Ensure `image_gallery_enabled = true` in Stage 1 (`01-platform`) so the Azure Compute Gallery (`azurerm_shared_image_gallery`) and image definition (`win11-24h2-avd-m365`) exist.
2. **Customization Options**:
   - **VDOT (`wdot_profile`)**: `"safe"` (default — disables Appx packages and scheduled tasks while keeping Autologgers, Event Logs, and Edge intact), `"default"`, or `"none"`.
   - **Ansible (`run_ansible_playbook = true`)**: Runs `ansible/playbooks/avd-image.yml` during the Packer build for enterprise LOB agents, certificates, and CIS hardening before Sysprep.
3. **Build Execution**:
   - Gated Pipeline: Run `.github/workflows/image.yml` (`workflow_dispatch`).
   - CLI: `packer init packer/avd-win11 && packer build packer/avd-win11`.
4. **Link to Nerdio Manager**:
   - Stage 1 automatically links the Compute Gallery image definition into Nerdio via `nme_azure_resource_link` (`gallery_image_definition_ids`), and Stage 2 resolves it by name when `image = "win11-24h2-avd-m365"`.
