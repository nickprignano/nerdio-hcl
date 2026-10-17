<#
Activates eligible Entra directory roles through PIM with Microsoft Graph PowerShell.

./nerdio fix roles calls this when the az CLI's Graph token can't read PIM (it isn't granted the
RoleManagement scopes). Graph PowerShell asks for those scopes itself, signing in with a device
code, which works from Cloud Shell in any browser. The caller has already shown the plan and
had the person type yes.

Part of github.com/nickprignano/nerdio-hcl (scripts/nerdio). Prints no IDs or tokens.
#>
param(
    [Parameter(Mandatory = $true)] [string[]] $Roles,
    [string] $Fallback = 'Global Administrator',
    [int] $Hours = 4
)
$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable Microsoft.Graph.Identity.Governance)) {
    Write-Output 'Microsoft Graph PowerShell is not installed here; Azure Cloud Shell has it.'
    exit 2
}
Import-Module Microsoft.Graph.Identity.Governance, Microsoft.Graph.Users
Connect-MgGraph -UseDeviceCode -NoWelcome -Scopes 'RoleEligibilitySchedule.Read.Directory', 'RoleAssignmentSchedule.ReadWrite.Directory', 'User.Read'

$me = (Get-MgUser -UserId (Get-MgContext).Account -Property Id).Id
$eligible = @{}
Get-MgRoleManagementDirectoryRoleEligibilityScheduleInstance -Filter "principalId eq '$me'" -ExpandProperty RoleDefinition -All |
    Where-Object { $_.DirectoryScopeId -eq '/' } |
    ForEach-Object { $eligible[$_.RoleDefinition.DisplayName] = $_.RoleDefinitionId }

$plan = @($Roles | Where-Object { $eligible.ContainsKey($_) })
if ($plan.Count -lt $Roles.Count -and $eligible.ContainsKey($Fallback)) { $plan = @($Fallback) }
if ($plan.Count -eq 0) {
    Write-Output ('None of these roles is eligible for you in PIM: ' + ($Roles -join ', ') + '. A Global Administrator has to assign one.')
    exit 3
}

$failed = 0
foreach ($role in $plan) {
    try {
        New-MgRoleManagementDirectoryRoleAssignmentScheduleRequest -BodyParameter @{
            action           = 'selfActivate'
            principalId      = $me
            roleDefinitionId = $eligible[$role]
            directoryScopeId = '/'
            justification    = 'Deploying Nerdio Manager with the nerdio-hcl kit'
            scheduleInfo     = @{
                startDateTime = (Get-Date).ToUniversalTime().ToString('o')
                expiration    = @{ type = 'AfterDuration'; duration = "PT$($Hours)H" }
            }
        } | Out-Null
        Write-Output "  activated $role"
    }
    catch {
        Write-Output "  ${role}: $($_.Exception.Message)"
        $failed++
    }
}
Disconnect-MgGraph | Out-Null
exit ([int]($failed -gt 0))
