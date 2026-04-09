$HostName = "com.polyglot.aijdk"
$ScriptDir = Split-Path -Parent (Resolve-Path $MyInvocation.MyCommand.Path)
$HostPath = Join-Path $ScriptDir "native_host.py"
# NOTE: Replace 'your-extension-id-here' with your extension's actual ID
# (found at chrome://extensions after loading the extension, then update this
#  file and re-run it so the manifest and registry entries are refreshed).
$ManifestPath = Join-Path $ScriptDir "native_host_manifest.json"

$manifest = @{
    name = $HostName
    description = "AllInOnePolyglotAIJDK Native Messaging Host"
    path = $HostPath
    type = "stdio"
    allowed_origins = @("chrome-extension://your-extension-id-here/")
}

$manifest | ConvertTo-Json -Depth 10 | Out-File -Encoding UTF8 $ManifestPath

# Register for Chrome and Edge
$regPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\$HostName"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "(Default)" -Value $ManifestPath

$regPathEdge = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\$HostName"
New-Item -Path $regPathEdge -Force | Out-Null
Set-ItemProperty -Path $regPathEdge -Name "(Default)" -Value $ManifestPath

Write-Host "Native Messaging Host registered successfully!" -ForegroundColor Green
