<#
Deploys a Nerdio Manager package to the web app, signed in as the Automation account's managed
identity. Terraform starts it once to install Nerdio (with packageVersion), and Nerdio's in-app
updater starts it by name (with sourceUri, a package URL from Nerdio's maintenance service).

Reads the subscriptionId, resourceGroupName and webAppName Automation variables. Uses Entra tokens
for the SCM site, so the web app can keep basic publishing credentials disabled.

Part of github.com/nickprignano/nerdio-hcl (modules/nerdio-core). Our own code, written from
documented behavior; it doesn't contain or copy Nerdio's runbook. It prints no secrets or IDs.
#>
param
(
    [Parameter(Mandatory = $false)]
    [string] $sourceUri = '',
    [Parameter(Mandatory = $false)]
    [string] $azureEnv = 'AzureCloud',
    # Accepted for compatibility with Nerdio's updater. This runbook always uses the managed identity.
    [Parameter(Mandatory = $false)]
    [string] $authType = 'ManagedIdentity',
    [Parameter(Mandatory = $false)]
    [string] $packageVersion = 'latest',
    [Parameter(Mandatory = $false)]
    [string] $maintenanceUri = 'https://nwp-web-app.azurewebsites.net'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$subscriptionId = Get-AutomationVariable -Name 'subscriptionId'
$resourceGroupName = Get-AutomationVariable -Name 'resourceGroupName'
$webAppName = Get-AutomationVariable -Name 'webAppName'

$scmSuffix = '.scm.azurewebsites.net'
if ($azureEnv -eq 'AzureUSGovernment') { $scmSuffix = '.scm.azurewebsites.us' }
$scmUri = "https://$webAppName$scmSuffix/api"

if ($authType -ne 'ManagedIdentity') {
    Write-Output "authType '$authType' requested; using the managed identity."
}
Connect-AzAccount -Identity -Subscription $subscriptionId -Environment $azureEnv | Out-Null

function Get-ScmHeaders {
    $token = (Get-AzAccessToken).Token
    if ($token -is [System.Security.SecureString]) {
        $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
        try { $token = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
        finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }
    return @{ Authorization = "Bearer $token" }
}

function Invoke-WithRetry {
    param([string] $Name, [scriptblock] $Script, [int] $Tries = 5, [int] $SleepSeconds = 30)
    for ($i = 1; $i -le $Tries; $i++) {
        try { return & $Script }
        catch {
            Write-Output "$Name attempt $i of $Tries failed: $($_.Exception.Message)"
            if ($i -eq $Tries) { throw }
            Start-Sleep -Seconds $SleepSeconds
        }
    }
}

# --- Package URL ---------------------------------------------------------------------------------
if ([string]::IsNullOrWhiteSpace($sourceUri)) {
    $version = $packageVersion
    if ($version -eq 'latest') {
        $packages = Invoke-RestMethod -Uri "$maintenanceUri/api/package" -Method Get
        # status 2 is general availability.
        $version = ($packages | Where-Object { $_.status -eq 2 -and $_.version } |
            Sort-Object { [version]$_.version } -Descending | Select-Object -First 1).version
        if (-not $version) { throw 'No generally available package from the maintenance service.' }
    }
    Write-Output "Installing Nerdio Manager $version"
    $link = Invoke-RestMethod -Uri "$maintenanceUri/api/package/$version/link?standalone=false" -Method Post -ContentType 'application/json'
    $sourceUri = $link.packageUri
    if ([string]::IsNullOrWhiteSpace($sourceUri)) { throw "The maintenance service returned no package URL for $version." }
}

# --- Download and unpack -------------------------------------------------------------------------
$work = Join-Path $env:TEMP ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $work | Out-Null
$packageZip = Join-Path $work 'package.zip'
Invoke-WithRetry -Name 'Download package' -Script { Invoke-WebRequest -Uri $sourceUri -OutFile $packageZip -UseBasicParsing }
Expand-Archive -Path $packageZip -DestinationPath $work -Force
$appZip = Join-Path $work 'app.zip'
if (-not (Test-Path $appZip)) { throw 'The package has no app.zip.' }
$versionFile = Join-Path $work 'version.txt'
if (Test-Path $versionFile) { Get-Content $versionFile | Write-Output }

# Nerdio ships pre- and post-publish hooks in the package; run them when present.
$hooks = Join-Path $work 'nwm-scripts.psm1'
if (Test-Path $hooks) { Import-Module $hooks }
if (Get-Command NWM-Before-Publish -ErrorAction SilentlyContinue) { NWM-Before-Publish -rg $resourceGroupName -appName $webAppName }

# --- Publish -------------------------------------------------------------------------------------
try { Invoke-RestMethod -Uri "$scmUri/jobs/continuous/provision/stop" -Headers (Get-ScmHeaders) -Method Post | Out-Null }
catch { Write-Output "Provision web job not stopped (normal on a first install): $($_.Exception.Message)" }

Invoke-WithRetry -Name 'Stop web app' -Script { Stop-AzWebApp -ResourceGroupName $resourceGroupName -Name $webAppName | Out-Null }

Invoke-WithRetry -Name 'Publish' -Script {
    Invoke-RestMethod -Uri "$scmUri/publish?type=zip&clean=true" -Headers (Get-ScmHeaders) -Method Post `
        -InFile $appZip -ContentType 'application/zip' -TimeoutSec 900 | Out-Null
}
Write-Output 'Published app.zip'

Invoke-WithRetry -Name 'Start web app' -Script { Start-AzWebApp -ResourceGroupName $resourceGroupName -Name $webAppName | Out-Null }

Invoke-WithRetry -Name 'Start provision web job' -Tries 10 -Script {
    Invoke-RestMethod -Uri "$scmUri/jobs/continuous/provision/start" -Headers (Get-ScmHeaders) -Method Post | Out-Null
}

if (Get-Command NWM-After-Publish -ErrorAction SilentlyContinue) { NWM-After-Publish -rg $resourceGroupName -appName $webAppName }

Remove-Item -Path $work -Recurse -Force -ErrorAction SilentlyContinue
Write-Output "Nerdio Manager deployed to $webAppName"
