# Optional Evergreen (EUCPilots/evergreen-module) and VcRedist (EUCPilots/vcredist) installer step.
# The app list and flags live in HCL (variables.pkr.hcl); Packer writes C:\Windows\Temp\evergreen-settings.json
# and this thin bootstrap installs the requested runtimes and Evergreen packages.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$settingsPath = 'C:\Windows\Temp\evergreen-settings.json'
if (-not (Test-Path $settingsPath)) {
    Write-Host 'No evergreen-settings.json found; skipping Evergreen/VcRedist step'
    exit 0
}

$settings = Get-Content -Raw -Path $settingsPath | ConvertFrom-Json
$apps = @($settings.evergreen_apps)

if (-not $settings.install_vcredist -and $apps.Count -eq 0) {
    Write-Host 'Skipping Evergreen and VcRedist (disabled in HCL)'
    Remove-Item $settingsPath -Force -ErrorAction SilentlyContinue
    exit 0
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force | Out-Null
Set-PSRepository -Name PSGallery -InstallationPolicy Trusted

$workDir = 'C:\Windows\Temp\evergreen-work'
New-Item -Path $workDir -ItemType Directory -Force | Out-Null

if ($settings.install_vcredist) {
    Write-Host 'Installing VcRedist module from PSGallery'
    Install-Module -Name VcRedist -Force -Scope AllUsers -AllowClobber
    Import-Module VcRedist
    $vcPath = Join-Path $workDir 'vcredist'
    New-Item -Path $vcPath -ItemType Directory -Force | Out-Null
    $vcList = Get-VcList | Save-VcRedist -Path $vcPath
    Install-VcRedist -VcList $vcList -Silent | Out-Null
    Write-Host 'VcRedist installation complete'
}

if ($apps.Count -gt 0) {
    Write-Host 'Installing Evergreen module from PSGallery'
    Install-Module -Name Evergreen -Force -Scope AllUsers -AllowClobber
    Import-Module Evergreen

    foreach ($app in $apps) {
        Write-Host "Resolving Evergreen app: $($app.name)"
        $candidates = @(Get-EvergreenApp -Name $app.name)
        if ($app.architecture) {
            $filtered = @($candidates | Where-Object { -not $_.PSObject.Properties['Architecture'] -or $_.Architecture -eq $app.architecture })
            if ($filtered.Count -gt 0) { $candidates = $filtered }
        }
        if ($app.channel) {
            $filtered = @($candidates | Where-Object { $_.PSObject.Properties['Channel'] -and $_.Channel -eq $app.channel })
            if ($filtered.Count -gt 0) { $candidates = $filtered }
        }
        if ($app.ring) {
            $filtered = @($candidates | Where-Object { $_.PSObject.Properties['Ring'] -and $_.Ring -eq $app.ring })
            if ($filtered.Count -gt 0) { $candidates = $filtered }
        }
        if ($app.type) {
            $filtered = @($candidates | Where-Object { $_.PSObject.Properties['Type'] -and $_.Type -eq $app.type })
            if ($filtered.Count -gt 0) { $candidates = $filtered }
        }

        $selected = $candidates | Select-Object -First 1
        if (-not $selected) {
            throw "Evergreen app '$($app.name)' returned no matching installer"
        }

        $appDir = Join-Path $workDir $app.name
        $saved = $selected | Save-EvergreenApp -Path $appDir -Force | Select-Object -First 1
        $installer = $saved.FullName
        Write-Host "Installing $($app.name) $($selected.Version) from $installer"

        $ext = [IO.Path]::GetExtension($installer).ToLowerInvariant()
        $argsList = if ($app.install_args) { $app.install_args } else { '/quiet /norestart' }

        if ($ext -eq '.msi') {
            $proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList "/i `"$installer`" $argsList" -Wait -PassThru
        } elseif ($ext -eq '.msix' -or $ext -eq '.appx' -or $ext -eq '.msixbundle') {
            Add-AppxProvisionedPackage -Online -PackagePath $installer -SkipLicense | Out-Null
            $proc = [pscustomobject]@{ ExitCode = 0 }
        } else {
            $proc = Start-Process -FilePath $installer -ArgumentList $argsList -Wait -PassThru
        }

        if ($proc.ExitCode -notin @(0, 3010)) {
            throw "Evergreen app '$($app.name)' exited with code $($proc.ExitCode)"
        }
    }
}

Remove-Item $workDir, $settingsPath -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Evergreen step complete'
