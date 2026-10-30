# Jalankan bot tanpa Docker. Otomatis restart kalau crash. Stop: Ctrl+C.
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

while ($true) {
    .\.venv\Scripts\python.exe -m handover_bot
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 2) { break }
    Write-Host "Bot berhenti (exit $LASTEXITCODE). Restart dalam 10 detik..."
    Start-Sleep -Seconds 10
}
