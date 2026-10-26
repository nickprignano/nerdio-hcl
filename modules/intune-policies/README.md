# `modules/intune-policies`

Manages Microsoft Intune configuration policies for Entra-joined and Hybrid-joined AVD session
hosts using `microsoft/msgraph`:

- **Windows Update for Business Ring** (`windowsUpdateForBusinessConfiguration`) with driver
  exclusions and scheduled Sunday maintenance window.
- **Settings Catalog Policy** (`configurationPolicies`) for Microsoft Defender AV exclusions on
  FSLogix (`.vhd`, `.vhdx`) and App Attach (`.cim`) containers.
- **Device Group Assignments** targeting the AVD session host Entra security group.
