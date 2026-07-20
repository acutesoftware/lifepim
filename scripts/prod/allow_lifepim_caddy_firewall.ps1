# Run from an elevated PowerShell prompt.
$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "This script must be run from an elevated PowerShell prompt."
}

$rules = @(
    @{ Name = "LifePIM Caddy HTTP LAN"; Port = 80 },
    @{ Name = "LifePIM Caddy HTTPS LAN"; Port = 443 }
)

foreach ($rule in $rules) {
    Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule `
        -DisplayName $rule.Name `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $rule.Port `
        -Profile Private,Public `
        -RemoteAddress LocalSubnet | Out-Null
}

Get-NetFirewallRule -DisplayName "LifePIM Caddy * LAN" |
    Select-Object DisplayName,Enabled,Profile,Direction,Action
