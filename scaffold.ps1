param (
    [string]$ProjectName
)

$BaseDir = "L:\ALLINONEPOLYGLOTAIJDK\sandbox\$ProjectName"
New-Item -ItemType Directory -Path "$BaseDir\src" -Force
New-Item -ItemType Directory -Path "$BaseDir\ui" -Force

# Initialize Cargo
Set-Location $BaseDir
cargo init --bin

# Add Slint dependency
Add-Content -Path "Cargo.toml" -Value 'slint = "1.9.4"'
Add-Content -Path "Cargo.toml" -Value '[build-dependencies]`nslint-build = "1.9.4"'

Write-Host "[AGENT] Project $ProjectName scaffolded in isolated sandbox."
