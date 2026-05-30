# tests/stress/run_baseline.ps1
# Corre la prueba baseline y guarda resultados en tests/stress/results/
# Uso: .\tests\stress\run_baseline.ps1 -Label "antes_gzip"

param(
    [string]$Label = "baseline",
    [int]$Users = 10,
    [int]$SpawnRate = 2,
    [string]$RunTime = "60s",
    [string]$Host = "http://127.0.0.1:8000"
)

$ResultsDir = "tests\stress\results"
if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Path $ResultsDir | Out-Null
}

Write-Host "Corriendo prueba: $Label con $Users usuarios por $RunTime"
Write-Host "Resultados en: $ResultsDir\$Label"

locust -f tests/stress/locustfile.py `
       --host=$Host `
       --users=$Users `
       --spawn-rate=$SpawnRate `
       --run-time=$RunTime `
       --headless `
       --csv="$ResultsDir\$Label"

Write-Host "`nPrueba terminada. Archivos generados:"
Get-ChildItem "$ResultsDir\$Label*"