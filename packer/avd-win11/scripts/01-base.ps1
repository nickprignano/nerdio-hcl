# Base configuration for an AVD multi-session image.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host "Setting time zone to $env:TIMEZONE"
Set-TimeZone -Id $env:TIMEZONE

# Let session hosts redirect the time zone from the client.
New-Item -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -Force | Out-Null
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -Name fEnableTimeZoneRedirection -Value 1 -Type DWord

# Disable Storage Sense; FSLogix profiles shouldn't be cleaned up by the OS.
New-Item -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\StorageSense' -Force | Out-Null
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\StorageSense' -Name AllowStorageSenseGlobal -Value 0 -Type DWord

# Microsoft 365 Apps: shared computer activation and no automatic updates in the image.
New-Item -Path 'HKLM:\SOFTWARE\Policies\Microsoft\office\16.0\common\officeupdate' -Force | Out-Null
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\office\16.0\common\officeupdate' -Name hideupdatenotifications -Value 1 -Type DWord
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\office\16.0\common\officeupdate' -Name hideenabledisableupdates -Value 1 -Type DWord

# FSLogix ships in the multi-session images; Nerdio's FSLogix profiles configure it per host pool.
if (-not (Test-Path 'C:\Program Files\FSLogix\Apps\frx.exe')) {
    Write-Host 'FSLogix not found, installing latest'
    $zip = "$env:TEMP\fslogix.zip"
    Invoke-WebRequest -Uri 'https://aka.ms/fslogix_download' -OutFile $zip
    Expand-Archive $zip -DestinationPath "$env:TEMP\fslogix" -Force
    Start-Process "$env:TEMP\fslogix\x64\Release\FSLogixAppsSetup.exe" -ArgumentList '/install /quiet /norestart' -Wait
}

if ($env:GPU_PRESET -eq 'True') {
    Write-Host 'Applying GPU hardware acceleration and H.264/HEVC encoding policies'
    $tsPath = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services'
    Set-ItemProperty -Path $tsPath -Name bEnumerateHWBeforeSW -Value 1 -Type DWord
    Set-ItemProperty -Path $tsPath -Name AVC444ModePreferred -Value 1 -Type DWord
    Set-ItemProperty -Path $tsPath -Name AVCHardwareEncodePreferred -Value 1 -Type DWord
    Set-ItemProperty -Path $tsPath -Name MaxCompressionLevel -Value 1 -Type DWord
}

Write-Host 'Base configuration complete'
