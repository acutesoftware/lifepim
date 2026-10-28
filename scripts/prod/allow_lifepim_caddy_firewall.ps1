# LifePIM Desktop is local-only. Run from an elevated PowerShell prompt to
# remove the two legacy rules that exposed its former Caddy listener.
$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "This script must be run from an elevated PowerShell prompt."
}

$ruleNames = @("LifePIM Caddy HTTP LAN", "LifePIM Caddy HTTPS LAN", "LifePIM Waitress")
foreach ($ruleName in $ruleNames) {
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
}

Write-Host "Removed LifePIM-specific LAN firewall rules. No unrelated Caddy rules were changed."
