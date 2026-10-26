# `modules/windows-365`

Manages Windows 365 Enterprise Cloud PC resources through Microsoft Graph (`microsoft/msgraph`)
alongside Nerdio Manager:

- **Azure Network Connection (`onPremisesConnections`)** linking Cloud PCs to the AVD spoke VNet and subnet.
- **Provisioning Policy (`provisioningPolicies`)** with Entra Join (`azureADJoin`) or Hybrid Join (`hybridAzureADJoin`) and Single Sign-On.
- **User Settings (`userSettings`)** governing local admin rights, self-service reset, and restore points.
- **Group Assignments** for target Entra ID security groups.
