[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$developmentPorts = @(8000, 5173)
$windowTitles = @(
    'research-agent-backend*',
    'research-agent-frontend*'
)

$listenersBefore = @(
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in $developmentPorts }
)

foreach ($windowTitle in $windowTitles) {
    # dev-start.bat assigns these unique titles to the two project terminals.
    # /T also stops the Uvicorn reload worker and the Vite child process.
    & taskkill.exe /FI "WINDOWTITLE eq $windowTitle" /T /F 2>$null | Out-Null
}

Start-Sleep -Milliseconds 500

$remaining = @(
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in $developmentPorts }
)

if ($remaining.Count -gt 0) {
    $details = $remaining | ForEach-Object { "port $($_.LocalPort) (PID $($_.OwningProcess))" }
    Write-Error (
        'The project windows were closed, but some development ports are still in use: ' +
        ($details -join ', ') +
        '. They may belong to programs that were not started with dev-start.bat.'
    )
}

if ($listenersBefore.Count -gt 0) {
    Write-Host 'Research Assistant has been stopped.' -ForegroundColor Green
}
else {
    Write-Host 'Research Assistant is already stopped.' -ForegroundColor Green
}
