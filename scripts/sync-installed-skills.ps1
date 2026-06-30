[CmdletBinding()]
param(
    [ValidateSet("Install", "Remove")]
    [string] $Action = "Install",

    [ValidateSet("Link", "Copy")]
    [string] $Mode = "Link",

    [string[]] $Targets = @("Codex", "Claude"),

    [string] $CodexHome = $env:CODEX_HOME,

    [string] $ClaudeHome = $env:CLAUDE_HOME,

    [switch] $Apply,

    [switch] $ReplaceUnmanaged
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$ManifestName = ".ai-skill-lab-install.manifest"
$MarkerName = ".ai-skill-lab-managed"
$ManagedByLine = "managed-by=ai-skill-lab"

function ConvertTo-AbsolutePath {
    param([Parameter(Mandatory = $true)][string] $Path)
    return [System.IO.Path]::GetFullPath(
        $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    )
}

function Normalize-PathForCompare {
    param([Parameter(Mandatory = $true)][string] $Path)
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd("\", "/")
    if ($env:OS -eq "Windows_NT") {
        return $full.Replace("/", "\")
    }
    return $full
}

function Test-SamePath {
    param(
        [Parameter(Mandatory = $true)][string] $Left,
        [Parameter(Mandatory = $true)][string] $Right
    )
    $comparison = if ($env:OS -eq "Windows_NT") {
        [System.StringComparison]::OrdinalIgnoreCase
    } else {
        [System.StringComparison]::Ordinal
    }
    return [string]::Equals(
        (Normalize-PathForCompare $Left),
        (Normalize-PathForCompare $Right),
        $comparison
    )
}

function Test-PathUnder {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Root
    )
    $comparison = if ($env:OS -eq "Windows_NT") {
        [System.StringComparison]::OrdinalIgnoreCase
    } else {
        [System.StringComparison]::Ordinal
    }
    $pathValue = Normalize-PathForCompare $Path
    $rootValue = Normalize-PathForCompare $Root
    if ([string]::Equals($pathValue, $rootValue, $comparison)) {
        return $true
    }
    return $pathValue.StartsWith($rootValue + [System.IO.Path]::DirectorySeparatorChar, $comparison)
}

function Invoke-PlannedAction {
    param(
        [Parameter(Mandatory = $true)][string] $Message,
        [Parameter(Mandatory = $true)][scriptblock] $Action
    )
    if ($Apply) {
        Write-Host "APPLY: $Message"
        & $Action
    } else {
        Write-Host "DRY-RUN: $Message"
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string] $Path)
    if (Test-Path -LiteralPath $Path) {
        return
    }
    Invoke-PlannedAction "create directory $Path" {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Get-ReparseTarget {
    param([Parameter(Mandatory = $true)][string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq [System.IO.FileAttributes]::ReparsePoint)) {
        return $null
    }
    foreach ($propertyName in @("Target", "LinkTarget")) {
        $property = $item.PSObject.Properties[$propertyName]
        if ($null -eq $property) {
            continue
        }
        $value = $property.Value
        if ($value -is [array]) {
            $value = $value | Select-Object -First 1
        }
        if (-not [string]::IsNullOrWhiteSpace([string] $value)) {
            return [string] $value
        }
    }
    return $null
}

function Test-ManagedCopy {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $RepoRoot
    )
    $markerPath = Join-Path $Path $MarkerName
    if (-not (Test-Path -LiteralPath $markerPath)) {
        return $false
    }
    $lines = Get-Content -LiteralPath $markerPath -Encoding UTF8
    if ($lines -notcontains $ManagedByLine) {
        return $false
    }
    $repoLine = $lines | Where-Object { $_ -like "repo_root=*" } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($repoLine)) {
        return $false
    }
    return Test-SamePath ($repoLine.Substring("repo_root=".Length)) $RepoRoot
}

function Read-Manifest {
    param([Parameter(Mandatory = $true)][string] $InstallHome)
    $manifest = @{
        RepoRoot = $null
        Mode = $null
        Skills = @()
        HasVendorTools = $false
    }
    $manifestPath = Join-Path $InstallHome $ManifestName
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        return $manifest
    }
    foreach ($line in Get-Content -LiteralPath $manifestPath -Encoding UTF8) {
        if ($line -like "repo_root=*") {
            $manifest.RepoRoot = $line.Substring("repo_root=".Length)
        } elseif ($line -like "mode=*") {
            $manifest.Mode = $line.Substring("mode=".Length)
        } elseif ($line -like "skill=*") {
            $manifest.Skills += $line.Substring("skill=".Length)
        } elseif ($line -eq "vendor_tools=vendor-tools") {
            $manifest.HasVendorTools = $true
        }
    }
    return $manifest
}

function Write-Manifest {
    param(
        [Parameter(Mandatory = $true)][string] $InstallHome,
        [Parameter(Mandatory = $true)][string] $RepoRoot,
        [Parameter(Mandatory = $true)][string] $Mode,
        [Parameter(Mandatory = $true)][string[]] $SkillNames
    )
    $manifestPath = Join-Path $InstallHome $ManifestName
    $lines = @(
        "# ai-skill-lab managed install manifest v1",
        "repo_root=$RepoRoot",
        "mode=$Mode",
        "updated_at=$((Get-Date).ToUniversalTime().ToString("o"))"
    )
    foreach ($skillName in $SkillNames) {
        $lines += "skill=$skillName"
    }
    $lines += "vendor_tools=vendor-tools"

    Invoke-PlannedAction "write manifest $manifestPath" {
        Set-Content -LiteralPath $manifestPath -Encoding UTF8 -Value $lines
    }
}

function Remove-Manifest {
    param(
        [Parameter(Mandatory = $true)][string] $InstallHome,
        [Parameter(Mandatory = $true)][string] $RepoRoot
    )
    $manifestPath = Join-Path $InstallHome $ManifestName
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        return
    }
    $manifest = Read-Manifest $InstallHome
    if ([string]::IsNullOrWhiteSpace($manifest.RepoRoot) -or -not (Test-SamePath $manifest.RepoRoot $RepoRoot)) {
        Write-Host "SKIP: manifest is not managed by this repo: $manifestPath"
        return
    }
    Invoke-PlannedAction "remove manifest $manifestPath" {
        Remove-Item -LiteralPath $manifestPath -Force
    }
}

function Write-ManagedMarker {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $RepoRoot
    )
    $markerPath = Join-Path $Path $MarkerName
    $lines = @(
        $ManagedByLine,
        "repo_root=$RepoRoot",
        "updated_at=$((Get-Date).ToUniversalTime().ToString("o"))"
    )
    Set-Content -LiteralPath $markerPath -Encoding UTF8 -Value $lines
}

function Move-UnmanagedAside {
    param([Parameter(Mandatory = $true)][string] $Path)
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "$Path.unmanaged-backup-$stamp"
    $index = 1
    while (Test-Path -LiteralPath $backupPath) {
        $backupPath = "$Path.unmanaged-backup-$stamp-$index"
        $index += 1
    }
    Invoke-PlannedAction "move unmanaged path $Path to $backupPath" {
        Move-Item -LiteralPath $Path -Destination $backupPath
    }
}

function Remove-ManagedPath {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $RepoRoot,
        [switch] $SkipUnmanaged
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $linkTarget = Get-ReparseTarget $Path
    if ($null -ne $linkTarget) {
        if (-not (Test-PathUnder $linkTarget $RepoRoot)) {
            if ($SkipUnmanaged) {
                Write-Host "SKIP: unmanaged link $Path -> $linkTarget"
                return
            }
            throw "Refusing to remove link outside this repo: $Path -> $linkTarget"
        }
        Invoke-PlannedAction "remove managed link $Path" {
            $item = Get-Item -LiteralPath $Path -Force
            if ($item.PSIsContainer) {
                [System.IO.Directory]::Delete($Path)
            } else {
                [System.IO.File]::Delete($Path)
            }
        }
        return
    }
    if (Test-ManagedCopy $Path $RepoRoot) {
        Invoke-PlannedAction "remove managed copy $Path" {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
        return
    }
    if ($SkipUnmanaged) {
        Write-Host "SKIP: unmanaged path $Path"
        return
    }
    throw "Refusing to remove unmanaged path: $Path"
}

function Remove-ManagedInstall {
    param(
        [Parameter(Mandatory = $true)][string] $TargetHome,
        [Parameter(Mandatory = $true)][string] $RepoRoot,
        [Parameter(Mandatory = $true)][string[]] $CurrentSkillNames,
        [Parameter(Mandatory = $true)] $Manifest
    )

    $targetSkillsRoot = Join-Path $TargetHome "skills"
    $targetVendorTools = Join-Path $TargetHome "vendor-tools"
    $removeSkillNames = New-Object System.Collections.Generic.List[string]

    foreach ($skillName in $CurrentSkillNames) {
        $removeSkillNames.Add($skillName)
    }

    if (-not [string]::IsNullOrWhiteSpace($Manifest.RepoRoot) -and (Test-SamePath $Manifest.RepoRoot $RepoRoot)) {
        foreach ($skillName in $Manifest.Skills) {
            $removeSkillNames.Add($skillName)
        }
    } elseif (-not [string]::IsNullOrWhiteSpace($Manifest.RepoRoot)) {
        Write-Warning "Existing manifest belongs to another repo; uninstall will only remove links/copies that point to this repo: $($Manifest.RepoRoot)"
    }

    foreach ($skillName in ($removeSkillNames.ToArray() | Select-Object -Unique)) {
        Remove-ManagedPath (Join-Path $targetSkillsRoot $skillName) $RepoRoot -SkipUnmanaged
    }

    Remove-ManagedPath $targetVendorTools $RepoRoot -SkipUnmanaged
    Remove-Manifest $TargetHome $RepoRoot
}

function New-ManagedLink {
    param(
        [Parameter(Mandatory = $true)][string] $Source,
        [Parameter(Mandatory = $true)][string] $Destination
    )
    Invoke-PlannedAction "create junction $Destination -> $Source" {
        New-Item -ItemType Junction -Path $Destination -Target $Source | Out-Null
    }
}

function Copy-ManagedDirectory {
    param(
        [Parameter(Mandatory = $true)][string] $Source,
        [Parameter(Mandatory = $true)][string] $Destination,
        [Parameter(Mandatory = $true)][string] $RepoRoot
    )
    Invoke-PlannedAction "copy $Source to $Destination" {
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
        Write-ManagedMarker $Destination $RepoRoot
    }
}

function Ensure-ManagedEntry {
    param(
        [Parameter(Mandatory = $true)][string] $Source,
        [Parameter(Mandatory = $true)][string] $Destination,
        [Parameter(Mandatory = $true)][string] $RepoRoot
    )

    $parent = Split-Path -Parent $Destination
    Ensure-Directory $parent

    if (Test-Path -LiteralPath $Destination) {
        $linkTarget = Get-ReparseTarget $Destination
        if ($null -ne $linkTarget) {
            if (Test-SamePath $linkTarget $Source) {
                Write-Host "OK: $Destination already points to $Source"
                return
            }
            if (-not (Test-PathUnder $linkTarget $RepoRoot)) {
                if (-not $ReplaceUnmanaged) {
                    throw "Refusing to replace unmanaged link: $Destination -> $linkTarget"
                }
                Move-UnmanagedAside $Destination
            } else {
                Remove-ManagedPath $Destination $RepoRoot
            }
        } elseif (Test-ManagedCopy $Destination $RepoRoot) {
            Remove-ManagedPath $Destination $RepoRoot
        } else {
            if (-not $ReplaceUnmanaged) {
                throw "Destination exists and is not managed by ai-skill-lab: $Destination"
            }
            Move-UnmanagedAside $Destination
        }
    }

    if ($Mode -eq "Link") {
        New-ManagedLink $Source $Destination
    } else {
        Copy-ManagedDirectory $Source $Destination $RepoRoot
    }
}

function Split-TargetNames {
    param([Parameter(Mandatory = $true)][string[]] $RawTargets)
    $names = New-Object System.Collections.Generic.List[string]
    foreach ($rawTarget in $RawTargets) {
        foreach ($part in ($rawTarget -split ",")) {
            $name = $part.Trim().ToLowerInvariant()
            if ($name.Length -gt 0) {
                $names.Add($name)
            }
        }
    }
    return $names.ToArray() | Select-Object -Unique
}

function Get-TargetHome {
    param([Parameter(Mandatory = $true)][string] $TargetName)
    switch ($TargetName) {
        "codex" {
            if ([string]::IsNullOrWhiteSpace($CodexHome)) {
                return ConvertTo-AbsolutePath (Join-Path $HOME ".codex")
            }
            return ConvertTo-AbsolutePath $CodexHome
        }
        "claude" {
            if ([string]::IsNullOrWhiteSpace($ClaudeHome)) {
                return ConvertTo-AbsolutePath (Join-Path $HOME ".claude")
            }
            return ConvertTo-AbsolutePath $ClaudeHome
        }
        default {
            throw "Unknown target '$TargetName'. Use Codex, Claude, or both."
        }
    }
}

$scriptRoot = Split-Path -Parent $PSCommandPath
$repoRoot = ConvertTo-AbsolutePath (Join-Path $scriptRoot "..")
$skillsRoot = Join-Path $repoRoot "skills"
$vendorToolsRoot = Join-Path $repoRoot "vendor-tools"

if (-not (Test-Path -LiteralPath $skillsRoot)) {
    throw "Missing source skills directory: $skillsRoot"
}
if (-not (Test-Path -LiteralPath $vendorToolsRoot)) {
    throw "Missing source vendor-tools directory: $vendorToolsRoot"
}

$sourceSkills = Get-ChildItem -LiteralPath $skillsRoot -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") } |
    Sort-Object Name

if ($sourceSkills.Count -eq 0 -and $Action -eq "Install") {
    throw "No skills found under $skillsRoot"
}

$skillNames = @($sourceSkills | Select-Object -ExpandProperty Name)
$targetNames = Split-TargetNames $Targets

if (-not $Apply) {
    Write-Host "Dry run only. Re-run with -Apply to modify target directories."
}

foreach ($targetName in $targetNames) {
    $targetHome = Get-TargetHome $targetName
    $targetSkillsRoot = Join-Path $targetHome "skills"
    $targetVendorTools = Join-Path $targetHome "vendor-tools"
    $manifest = Read-Manifest $targetHome
    $manifestBelongsToThisRepo = $false

    if (-not [string]::IsNullOrWhiteSpace($manifest.RepoRoot)) {
        $manifestBelongsToThisRepo = Test-SamePath $manifest.RepoRoot $repoRoot
    }

    Write-Host ""
    Write-Host "Target: $targetName"
    Write-Host "Home:   $targetHome"
    Write-Host "Action: $Action"
    Write-Host "Mode:   $Mode"

    if ($Action -eq "Remove") {
        Remove-ManagedInstall `
            -TargetHome $targetHome `
            -RepoRoot $repoRoot `
            -CurrentSkillNames $skillNames `
            -Manifest $manifest
        continue
    }

    Ensure-Directory $targetHome
    Ensure-Directory $targetSkillsRoot

    if ($manifestBelongsToThisRepo) {
        foreach ($oldSkillName in $manifest.Skills) {
            if ($skillNames -notcontains $oldSkillName) {
                Remove-ManagedPath (Join-Path $targetSkillsRoot $oldSkillName) $repoRoot
            }
        }
    } elseif (-not [string]::IsNullOrWhiteSpace($manifest.RepoRoot)) {
        Write-Warning "Existing manifest belongs to another repo; stale cleanup is skipped: $($manifest.RepoRoot)"
    }

    foreach ($sourceSkill in $sourceSkills) {
        Ensure-ManagedEntry `
            -Source $sourceSkill.FullName `
            -Destination (Join-Path $targetSkillsRoot $sourceSkill.Name) `
            -RepoRoot $repoRoot
    }

    Ensure-ManagedEntry `
        -Source $vendorToolsRoot `
        -Destination $targetVendorTools `
        -RepoRoot $repoRoot

    Write-Manifest $targetHome $repoRoot $Mode $skillNames
}
