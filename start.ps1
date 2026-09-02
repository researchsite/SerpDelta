$port = 8501
$dir  = $PSScriptRoot

# Kill anything on the port first
$conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        Write-Host "Freeing port $port (PID $p)..." -ForegroundColor Yellow
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

Write-Host "Starting SERP Delta on http://localhost:$port ..." -ForegroundColor Cyan
Start-Process -FilePath "py" `
    -ArgumentList "-m streamlit run app.py --server.port $port --server.headless true" `
    -WorkingDirectory $dir `
    -WindowStyle Hidden

Start-Sleep -Seconds 5
Start-Process "http://localhost:$port"
Write-Host "Live at http://localhost:$port  |  Run .\stop.ps1 to shut down." -ForegroundColor Green
