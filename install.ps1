# Autopsy installer (Windows) - copies skills into ~/.claude/skills/

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsDir = Join-Path $ScriptDir "skills"
$TargetDir = Join-Path $HOME ".claude\skills"

$Installed = 0
foreach ($dir in Get-ChildItem -Path $SkillsDir -Directory) {
    $src = Join-Path $dir.FullName "SKILL.md"
    if (-not (Test-Path $src)) { continue }
    $dest = Join-Path $TargetDir $dir.Name
    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    Copy-Item $src (Join-Path $dest "SKILL.md") -Force
    Write-Host "  Installed: $($dir.Name) -> $dest\SKILL.md"
    $Installed++
}

if ($Installed -eq 0) {
    Write-Host "No skills found under $SkillsDir\*\SKILL.md - nothing installed."
    exit 1
}

# Don't trust Get-Command alone: Windows ships a python3 stub that resolves on PATH
# and only advertises the Microsoft Store. Run the interpreter and see what answers.
$Probe = 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)'
$Py = ""
foreach ($candidate in @("python", "python3")) {
    try {
        & $candidate -c $Probe
        if ($LASTEXITCODE -eq 0) { $Py = $candidate; break }
    } catch {}
}
if (-not $Py) {
    Write-Host "Warning: no working Python 3.8+ interpreter found on PATH."
    $Py = "python"
}

Write-Host ""
Write-Host "Installed $Installed skill(s) to $TargetDir"
Write-Host "Scripts are at: $ScriptDir\scripts\"
Write-Host "You can now use /autopsy in Claude Code."
Write-Host ""
Write-Host "Quick test:"
Write-Host "  $Py $ScriptDir\scripts\autopsy\run.py --days 7"
