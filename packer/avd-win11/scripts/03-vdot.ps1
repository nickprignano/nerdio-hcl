# Apply the Virtual Desktop Optimization Tool with its default settings.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ($env:RUN_VDOT -ne 'True') {
    Write-Host 'Skipping VDOT'
    exit 0
}

$zip = "$env:TEMP\vdot.zip"
Invoke-WebRequest -Uri 'https://github.com/The-Virtual-Desktop-Team/Virtual-Desktop-Optimization-Tool/archive/refs/heads/main.zip' -OutFile $zip
Expand-Archive $zip -DestinationPath "$env:TEMP\vdot" -Force
$script = Get-ChildItem "$env:TEMP\vdot" -Recurse -Filter 'Windows_VDOT.ps1' | Select-Object -First 1

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
& $script.FullName -Optimizations All -AdvancedOptimizations Edge -AcceptEULA -Verbose

Remove-Item $zip, "$env:TEMP\vdot" -Recurse -Force
