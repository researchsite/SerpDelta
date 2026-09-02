$port = 8501
$conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host "No process found on port $port." -ForegroundColor Yellow
    exit 0
}
$pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $pids) {
    Write-Host "Stopping PID $p on port $port..." -ForegroundColor Cyan
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
}
Write-Host "SERP Delta stopped." -ForegroundColor Green
