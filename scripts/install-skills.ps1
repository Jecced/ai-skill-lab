[CmdletBinding()]
param(
    [ValidateSet("Install", "Remove")]
    [string] $Action = "Install",

    [ValidateSet("Link", "Copy")]
    [string] $Mode = "Link",

    [string[]] $Targets = @("Codex", "Claude"),

    [switch] $ReplaceUnmanaged,

    [switch] $NoPause
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Wait-BeforeExit {
    param([int] $ExitCode)
    if (-not $NoPause) {
        Write-Host ""
        Read-Host "Press Enter to exit"
    }
    exit $ExitCode
}

try {
    $scriptRoot = Split-Path -Parent $PSCommandPath
    $repoRoot = Split-Path -Parent $scriptRoot
    $syncScript = Join-Path $scriptRoot "sync-installed-skills.ps1"

    if (-not (Test-Path -LiteralPath $syncScript)) {
        throw "Missing sync script: $syncScript"
    }

    if ($Action -eq "Remove") {
        Write-Host "Removing ai-skill-lab skills"
    } else {
        Write-Host "Installing ai-skill-lab skills"
    }
    Write-Host "Repo:    $repoRoot"
    Write-Host "Action:  $Action"
    Write-Host "Mode:    $Mode"
    Write-Host "Targets: $($Targets -join ', ')"
    Write-Host ""

    $syncArgs = @{
        Action = $Action
        Mode = $Mode
        Targets = $Targets
        Apply = $true
    }

    if ($ReplaceUnmanaged) {
        $syncArgs.ReplaceUnmanaged = $true
    }

    & $syncScript @syncArgs

    Write-Host ""
    if ($Action -eq "Remove") {
        Write-Host "Remove complete. Restart Codex and start a new Claude Code session to reload skills."
    } else {
        Write-Host "Install complete. Restart Codex and start a new Claude Code session to reload skills."
    }
    Wait-BeforeExit 0
} catch {
    Write-Host ""
    Write-Host "$Action failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    if ($Action -eq "Install") {
        Write-Host "If an existing same-name skill was installed manually, review it first. Then run with -ReplaceUnmanaged to move the old path aside instead of overwriting it."
    } else {
        Write-Host "Remove only deletes links/copies managed by this repo. Unmanaged same-name directories are left in place."
    }
    Wait-BeforeExit 1
}
