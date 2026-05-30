# verify_gzip.ps1
param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [string]$AreaId = "",
    [string]$BaselineCsv = "tests\stress\results\baseline_stats.csv"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Traffic Engine - GZip Verification  " -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. HEALTH CHECK ──────────────────────────────────────────────────────────
Write-Host "1. Verificando /health..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "$ApiUrl/health" -UseBasicParsing
    if ($health.StatusCode -eq 200) {
        Write-Host "   [PASS] /health responde 200" -ForegroundColor Green
    } else {
        Write-Host "   [FAIL] /health respondio $($health.StatusCode)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   [FAIL] No se pudo conectar a $ApiUrl - Asegurate de que la API este corriendo" -ForegroundColor Red
    exit 1
}

# ── 2. OBTENER AREA_ID ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "2. Obteniendo area_id desde /geographic-areas..." -ForegroundColor Yellow
if ($AreaId -eq "") {
    try {
        $areas = Invoke-RestMethod -Uri "$ApiUrl/geographic-areas" -UseBasicParsing
        if ($areas.Count -gt 0) {
            $AreaId = $areas[0].area_id
            Write-Host "   [INFO] Usando area_id: $AreaId" -ForegroundColor Cyan
        } else {
            Write-Host "   [FAIL] No hay areas geograficas. Corre: python scripts/init_mongo_geodata.py" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "   [FAIL] Error obteniendo areas: $_" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "   [INFO] Usando area_id proporcionado: $AreaId" -ForegroundColor Cyan
}

$topologyUrl = "$ApiUrl/geographic-areas/$AreaId/topology"

# ── 3. VERIFICAR CONTENT-ENCODING: GZIP ─────────────────────────────────────
Write-Host ""
Write-Host "3. Verificando Content-Encoding: gzip en /topology..." -ForegroundColor Yellow
$gzipActive = $false
$reduction = 0
try {
    $withGzip = Invoke-WebRequest -Uri $topologyUrl `
                -Headers @{"Accept-Encoding" = "gzip"} -UseBasicParsing
    $encoding = $withGzip.Headers["Content-Encoding"]

    if ($encoding -eq "gzip") {
        Write-Host "   [PASS] Content-Encoding: gzip detectado" -ForegroundColor Green
        $gzipActive = $true
    } else {
        Write-Host "   [FAIL] Content-Encoding no es gzip (valor actual: '$encoding')" -ForegroundColor Red
        Write-Host "          Verifica que add_middleware(GZipMiddleware) este en create_app()" -ForegroundColor Red
    }
} catch {
    Write-Host "   [FAIL] Error al llamar /topology: $_" -ForegroundColor Red
}

# ── 4. COMPARAR TAMANO DE RESPUESTA ─────────────────────────────────────────
Write-Host ""
Write-Host "4. Comparando tamano de respuesta /topology..." -ForegroundColor Yellow
try {
    $sinGzip = Invoke-WebRequest -Uri $topologyUrl -UseBasicParsing
    $sizeSin = $sinGzip.RawContentLength

    $conGzip = Invoke-WebRequest -Uri $topologyUrl `
               -Headers @{"Accept-Encoding" = "gzip"} -UseBasicParsing
    $sizeCon = $conGzip.RawContentLength

    $reduction = [math]::Round((1 - $sizeCon / $sizeSin) * 100, 1)
    $baselineKb = [math]::Round(402737 / 1024, 1)
    $sinKb      = [math]::Round($sizeSin / 1024, 1)
    $conKb      = [math]::Round($sizeCon / 1024, 1)

    Write-Host ""
    Write-Host "   COMPARACION DE TAMANO /topology" -ForegroundColor White
    Write-Host "   Baseline CSV (sin GZip) : $baselineKb KB" -ForegroundColor White
    Write-Host "   Sin GZip (actual)       : $sinKb KB" -ForegroundColor White
    Write-Host "   Con GZip (actual)       : $conKb KB" -ForegroundColor White
    Write-Host "   Reduccion               : $reduction%" -ForegroundColor White
    Write-Host ""

    if ($reduction -gt 50) {
        Write-Host "   [PASS] Reduccion de $reduction% - GZip funcionando correctamente" -ForegroundColor Green
    } elseif ($reduction -gt 0) {
        Write-Host "   [WARN] Reduccion de solo $reduction% - respuesta puede ser pequena" -ForegroundColor Yellow
    } else {
        Write-Host "   [FAIL] Sin reduccion - verifica el middleware" -ForegroundColor Red
    }
} catch {
    Write-Host "   [FAIL] Error midiendo tamano: $_" -ForegroundColor Red
}

# ── 5. VERIFICAR QUE /health NO SE COMPRIME ──────────────────────────────────
Write-Host ""
Write-Host "5. Verificando que /health no tiene overhead (minimum_size=500)..." -ForegroundColor Yellow
$healthOk = $false
try {
    $healthResp    = Invoke-WebRequest -Uri "$ApiUrl/health" `
                     -Headers @{"Accept-Encoding" = "gzip"} -UseBasicParsing
    $healthSize    = $healthResp.RawContentLength
    $healthEnc     = $healthResp.Headers["Content-Encoding"]

    if ($healthEnc -ne "gzip") {
        Write-Host "   [PASS] /health no esta comprimido (tamano: $healthSize bytes, umbral: 500)" -ForegroundColor Green
        $healthOk = $true
    } else {
        Write-Host "   [WARN] /health se esta comprimiendo ($healthSize bytes) - considera subir minimum_size" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [FAIL] Error verificando /health: $_" -ForegroundColor Red
}

# ── 6. TIEMPOS DE RESPUESTA (5 muestras) ────────────────────────────────────
Write-Host ""
Write-Host "6. Midiendo tiempos de respuesta promedio (5 muestras)..." -ForegroundColor Yellow

function Measure-Endpoint {
    param([string]$Url, [hashtable]$ExtraHeaders = @{}, [int]$Samples = 5)
    $times = @()
    for ($i = 0; $i -lt $Samples; $i++) {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try { Invoke-WebRequest -Uri $Url -Headers $ExtraHeaders -UseBasicParsing | Out-Null } catch {}
        $sw.Stop()
        $times += $sw.ElapsedMilliseconds
    }
    return [math]::Round(($times | Measure-Object -Average).Average, 0)
}

$areasTime    = Measure-Endpoint -Url "$ApiUrl/geographic-areas"
$topologyTime = Measure-Endpoint -Url $topologyUrl -ExtraHeaders @{"Accept-Encoding" = "gzip"}
$healthTime   = Measure-Endpoint -Url "$ApiUrl/health"

$baselineAreas    = 4159
$baselineTopology = 4077
$baselineHealth   = 1651

function Write-CompareRow {
    param([string]$Name, [int]$Baseline, [int]$Actual)
    $diff = $Baseline - $Actual
    $pct  = if ($Baseline -gt 0) { [math]::Round($diff / $Baseline * 100, 1) } else { 0 }
    if ($pct -gt 10) {
        $tag   = "[MEJOR]"
        $color = "Green"
    } elseif ($pct -lt -5) {
        $tag   = "[PEOR] "
        $color = "Red"
    } else {
        $tag   = "[IGUAL]"
        $color = "White"
    }
    Write-Host ("   {0}  {1,-16} baseline={2,6}ms   actual={3,6}ms   diferencia={4,6}%" -f $tag, $Name, $Baseline, $Actual, $pct) -ForegroundColor $color
}

Write-Host ""
Write-Host "   COMPARACION DE TIEMPOS vs BASELINE CSV" -ForegroundColor White
Write-CompareRow "/geographic-areas"  $baselineAreas    $areasTime
Write-CompareRow "/topology (+gzip)"  $baselineTopology $topologyTime
Write-CompareRow "/health"            $baselineHealth   $healthTime

# ── 7. TESTS AUTOMATICOS ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "7. Corriendo suite de tests (test_api_app.py)..." -ForegroundColor Yellow
$testsPassed = $false
try {
    $testOut = & pytest tests/test_api_app.py -v --tb=short 2>&1
    $testOut | ForEach-Object { Write-Host "   $_" }
    $failLine = $testOut | Where-Object { $_ -match "failed|error" } | Select-Object -Last 1
    if (-not $failLine -or $failLine -match "^0 failed") {
        Write-Host "   [PASS] Todos los tests pasaron" -ForegroundColor Green
        $testsPassed = $true
    } else {
        Write-Host "   [FAIL] Hay tests fallando - revisa la salida anterior" -ForegroundColor Red
    }
} catch {
    Write-Host "   [FAIL] Error ejecutando pytest: $_" -ForegroundColor Red
}

# ── 8. RESUMEN FINAL ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "           RESUMEN FINAL               " -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

function Write-StatusLine {
    param([string]$Label, [bool]$Ok, [string]$Extra = "")
    $symbol = if ($Ok) { "[OK]" } else { "[!!]" }
    $color  = if ($Ok) { "Green" } else { "Red" }
    Write-Host ("  {0}  {1,-40} {2}" -f $symbol, $Label, $Extra) -ForegroundColor $color
}

Write-StatusLine "GZip activo en /topology"       $gzipActive    "Content-Encoding: gzip"
Write-StatusLine "Reduccion de tamano mayor 50%"  ($reduction -gt 50)  "$reduction%"
Write-StatusLine "/health sin overhead de GZip"   $healthOk      ""
Write-StatusLine "Tests en verde"                 $testsPassed   ""
Write-Host ""
if ($gzipActive -and ($reduction -gt 50) -and $healthOk -and $testsPassed) {
    Write-Host "  Listo para commit:" -ForegroundColor Green
    Write-Host "  git add src/traffic_engine/api/app.py tests/stress/verify_gzip.ps1" -ForegroundColor Green
    Write-Host '  git commit -m "perf: add GZip middleware to compress large API responses"' -ForegroundColor Green
    Write-Host "  git push" -ForegroundColor Green
} else {
    Write-Host "  Hay elementos pendientes de corregir antes del commit." -ForegroundColor Yellow
}
Write-Host ""