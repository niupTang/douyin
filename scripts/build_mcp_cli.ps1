$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding

$repoRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $repoRoot "release-cli"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

Push-Location $repoRoot
try {
    py -m build --wheel --no-isolation --outdir $outputDirectory
} finally {
    Pop-Location
}
