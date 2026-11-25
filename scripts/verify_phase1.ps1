<#
.SYNOPSIS
  PgGuardian - Verificación local de la Fase 1 (T-08 / RNF-05 / Requirement 7).

.DESCRIPTION
  1. Precondiciones: .env local con JWT_SECRET no vacío (R7.1).
  2. Crea el directorio de datos de sandbox_db (./.data/sandbox o SANDBOX_DATA_DIR)
     porque create_host_path: false impide que Docker lo cree (R7.2, R7.3).
  3. docker compose -f docker-compose.prod.yml up -d --build y espera hasta 120 s
     a que los cinco servicios estén running/healthy (R7.4).
  4. Llama al health-check con timeout de 5 s (R7.5).
  5. Evalúa CA-09 a CA-14 e imprime una línea JSON por criterio (R7.6).
  6. Sale con código distinto de 0 si algo falla (R7.7). El resumen Markdown del
     final se pega en la plantilla de PR (.github/PULL_REQUEST_TEMPLATE/fase1.md, R7.8).

  Equivalente funcional de scripts/verify_phase1.sh. No modifica el archivo .env.

  Notas de entorno local:
  - Se usa el nombre de proyecto "pgguardian-prod" para no recrear los
    contenedores del compose de desarrollo, que comparte nombres de servicio.
  - APP_DOMAIN se fuerza a ":80" solo en el entorno de este proceso: en local no
    hay certificado de Let's Encrypt y las comprobaciones van por http://localhost.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\verify_phase1.ps1
#>

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Root        = Split-Path -Parent $PSScriptRoot
$ComposeFile = 'docker-compose.prod.yml'
$Project     = 'pgguardian-prod'
$BaseUrl     = 'http://localhost'
$Services    = @('proxy', 'frontend', 'api', 'app_db', 'sandbox_db')
$WaitSeconds = 120

Set-Location -LiteralPath $Root

# ---------------------------------------------------------------- utilidades
$script:Results = New-Object System.Collections.ArrayList

function Add-Result([string]$Criterio, [string]$Requisito, [bool]$Ok, [string]$Detalle) {
    $estado = if ($Ok) { 'aprobado' } else { 'no_aprobado' }
    $obj = [ordered]@{ criterio = $Criterio; requisito = $Requisito; estado = $estado; detalle = $Detalle }
    [void]$script:Results.Add($obj)
    Write-Output (ConvertTo-Json -InputObject $obj -Compress)
}

function Get-DotEnvValue([string]$Path, [string]$Key) {
    # Devuelve $null si la clave no está; si aparece varias veces gana la última (como Compose).
    $value = $null
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match ('^\s*(export\s+)?' + [regex]::Escape($Key) + '\s*=(.*)$')) {
            $v = $Matches[2].Trim()
            if ($v.Length -ge 2 -and (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'")))) {
                $v = $v.Substring(1, $v.Length - 2)
            }
            $value = $v
        }
    }
    return $value
}

function Invoke-Compose {
    # Ejecuta docker compose con el proyecto y archivo de producción.
    & docker compose -p $Project -f $ComposeFile @args
}

function Get-ContainerId([string]$Service) {
    $id = (Invoke-Compose ps -a -q $Service 2>$null | Select-Object -First 1)
    if ($id) { return $id.Trim() } else { return $null }
}

function Get-Inspect([string]$Id) {
    # JSON completo de docker inspect. Se evita pasar plantillas Go con comillas
    # dobles porque PowerShell 5.1 las elimina al invocar ejecutables nativos.
    $raw = (& docker inspect $Id 2>$null) -join "`n"
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    return @($raw | ConvertFrom-Json)[0]
}

function Get-HttpResponse([string]$Url) {
    # curl.exe (no el alias de Invoke-WebRequest) para leer las cabeceras crudas,
    # incluidas las repetidas. Timeout de 5 s (R7.5).
    $hdrFile  = [System.IO.Path]::GetTempFileName()
    $bodyFile = [System.IO.Path]::GetTempFileName()
    $meta = & curl.exe -sS --max-time 5 -D $hdrFile -o $bodyFile -w '%{http_code} %{time_total}' $Url 2>&1
    $code = $LASTEXITCODE
    $headers = @(Get-Content -LiteralPath $hdrFile -Encoding UTF8 | ForEach-Object { $_.TrimEnd("`r") })
    $body = [System.IO.File]::ReadAllText($bodyFile)
    Remove-Item -LiteralPath $hdrFile, $bodyFile -Force -ErrorAction SilentlyContinue
    $status = 0; $time = [double]::NaN
    if ($code -eq 0) {
        $parts = ("$meta").Trim().Split(' ')
        $status = [int]$parts[0]
        $time = [double]::Parse($parts[1], [System.Globalization.CultureInfo]::InvariantCulture)
    }
    return [pscustomobject]@{ CurlExit = $code; Error = "$meta"; Status = $status; Time = $time; Headers = $headers; Body = $body }
}

# ------------------------------------------------------- 0. precondiciones (R7.1)
Write-Host '== PgGuardian - verificación local de la Fase 1 (T-08) =='

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: no se encontró el comando docker. Instala Docker Desktop y vuelve a ejecutar.' -ForegroundColor Red
    exit 1
}
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: no se encontró curl.exe (incluido en Windows 10+). Instálalo y vuelve a ejecutar.' -ForegroundColor Red
    exit 1
}

$EnvFile = Join-Path $Root '.env'
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    Write-Host "ERROR: falta el archivo .env en $Root." -ForegroundColor Red
    Write-Host '  Corrección: copia .env.prod.example a .env (Copy-Item .env.prod.example .env),'
    Write-Host '  define JWT_SECRET con un valor aleatorio y elimina SANDBOX_DATA_DIR para el entorno local.'
    exit 1
}

$jwt = Get-DotEnvValue $EnvFile 'JWT_SECRET'
if ($null -eq $jwt -or $jwt.Trim() -eq '') {
    $que = if ($null -eq $jwt) { 'no está definido' } else { 'está vacío' }
    Write-Host "ERROR: JWT_SECRET $que en .env." -ForegroundColor Red
    Write-Host '  Corrección: agrega en .env una línea JWT_SECRET=<valor aleatorio>, por ejemplo con:'
    Write-Host '  -join ((1..32) | ForEach-Object { ''{0:x2}'' -f (Get-Random -Maximum 256) })'
    exit 1
}
Write-Host 'OK: .env presente y JWT_SECRET definido.'

# -------------------------------------- 0b. directorio de datos del sandbox (R7.2, R7.3)
$dataDir = Get-DotEnvValue $EnvFile 'SANDBOX_DATA_DIR'
if ($null -eq $dataDir -or $dataDir.Trim() -eq '') { $dataDir = './.data/sandbox' }

if ($dataDir.StartsWith('/')) {
    Write-Host "ERROR: no se puede crear el directorio de datos de sandbox_db: $dataDir" -ForegroundColor Red
    Write-Host '  Causa: es una ruta Linux (la de la EC2); en Windows Docker Desktop la resolvería dentro de su VM.'
    Write-Host '  Corrección: elimina SANDBOX_DATA_DIR del .env local para usar ./.data/sandbox.'
    exit 1
}
$dataDirAbs = if ([System.IO.Path]::IsPathRooted($dataDir)) { $dataDir } else { Join-Path $Root $dataDir }
$dataDirAbs = [System.IO.Path]::GetFullPath($dataDirAbs)
if (-not (Test-Path -LiteralPath $dataDirAbs -PathType Container)) {
    try {
        New-Item -ItemType Directory -Path $dataDirAbs -Force -ErrorAction Stop | Out-Null
        Write-Host "OK: creado el directorio de datos de sandbox_db: $dataDirAbs"
    } catch {
        Write-Host "ERROR: no se pudo crear el directorio de datos de sandbox_db: $dataDirAbs" -ForegroundColor Red
        Write-Host "  Causa: $($_.Exception.Message)"
        exit 1
    }
} else {
    Write-Host "OK: directorio de datos de sandbox_db existente: $dataDirAbs"
}

# Solo para este proceso y sus hijos; el .env no se toca.
$env:APP_DOMAIN = ':80'

# ---------------------------------------------------------- 1. arranque (R7.4)
Write-Host "== docker compose -p $Project -f $ComposeFile up -d --build =="
Invoke-Compose up -d --build
$upExit = $LASTEXITCODE

$ready = $false
$statusLine = ''
if ($upExit -eq 0) {
    Write-Host "Esperando hasta $WaitSeconds s a que los cinco servicios estén running/healthy..."
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        $pending = @()
        $states = @()
        foreach ($svc in $Services) {
            $id = Get-ContainerId $svc
            if (-not $id) { $pending += "$svc=sin contenedor"; $states += "$svc=sin contenedor"; continue }
            $ins = Get-Inspect $id
            if (-not $ins) { $pending += "$svc=sin datos"; $states += "$svc=sin datos"; continue }
            $run = "$($ins.State.Status)"
            $health = if ($ins.State.Health) { "$($ins.State.Health.Status)" } else { '' }
            $label = if ($health) { "$run/$health" } else { $run }
            $states += "$svc=$label"
            # Con healthcheck se exige healthy (sandbox_db y app_db); sin él, running.
            if ($run -ne 'running' -or ($health -and $health -ne 'healthy')) { $pending += "$svc=$label" }
        }
        $statusLine = $states -join ', '
        if ($pending.Count -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
}

if ($ready) {
    Add-Result 'arranque' 'R7' $true "Cinco servicios listos: $statusLine"
} elseif ($upExit -ne 0) {
    Add-Result 'arranque' 'R7' $false "docker compose up terminó con código $upExit"
} else {
    Add-Result 'arranque' 'R7' $false "Servicios no listos en $WaitSeconds s: $statusLine. Revisa: docker compose -p $Project -f $ComposeFile logs <servicio>"
}

# ------------------------------------------------------------------- CA-09 (R1)
# JWT_SECRET vacío solo en el entorno del proceso hijo. En PowerShell, $env:X = ''
# borra la variable (y Compose usaría la del .env), por eso se usa ProcessStartInfo,
# que sí admite una variable definida con valor vacío.
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'docker'
$psi.Arguments = "compose -p $Project -f $ComposeFile config"
$psi.WorkingDirectory = $Root
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.EnvironmentVariables['JWT_SECRET'] = ''
$proc = [System.Diagnostics.Process]::Start($psi)
$outTask = $proc.StandardOutput.ReadToEndAsync()
$errText = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()
$null = $outTask.Result
$ca09Exit = $proc.ExitCode
$ca09Ok = ($ca09Exit -ne 0) -and ($errText -match 'falta JWT_SECRET')
Add-Result 'CA-09' 'R1' $ca09Ok ("config con JWT_SECRET vacío: código $ca09Exit; mensaje 'falta JWT_SECRET' " + $(if ($errText -match 'falta JWT_SECRET') { 'presente' } else { 'ausente' }))

# ------------------------------------------------------------------- CA-10 (R2)
$bad = @()
foreach ($svc in $Services) {
    $id = Get-ContainerId $svc
    if (-not $id) { $bad += "$svc=sin contenedor"; continue }
    $ins = Get-Inspect $id
    if (-not $ins) { $bad += "$svc=sin datos"; continue }
    $logCfg = $ins.HostConfig.LogConfig
    $lc = "$($logCfg.Type) $($logCfg.Config.'max-size') $($logCfg.Config.'max-file')".Trim()
    if ($lc -ne 'json-file 10m 3') { $bad += "$svc=[$lc]" }
}
if ($bad.Count -eq 0) {
    Add-Result 'CA-10' 'R2' $true 'Los cinco contenedores usan json-file, max-size 10m, max-file 3'
} else {
    Add-Result 'CA-10' 'R2' $false ("Servicios no conformes: " + ($bad -join ', '))
}

# ------------------------------------------------------------------- CA-11 (R3)
$expectedMem = [ordered]@{ api = 536870912; app_db = 402653184; sandbox_db = 536870912 }
$bad = @(); $got = @()
foreach ($svc in $expectedMem.Keys) {
    $id = Get-ContainerId $svc
    if (-not $id) { $bad += "$svc=sin contenedor"; continue }
    $ins = Get-Inspect $id
    $mem = if ($ins) { "$($ins.HostConfig.Memory)" } else { '0' }
    $got += "$svc=$([math]::Round([double]$mem / 1MB))MiB"
    if ($mem -ne [string]$expectedMem[$svc]) { $bad += "$svc=$mem bytes" }
}
if ($bad.Count -eq 0) {
    Add-Result 'CA-11' 'R3' $true ("Límites: " + ($got -join ', ') + ' (suma 1408 MiB)')
} else {
    Add-Result 'CA-11' 'R3' $false ("Límites incorrectos: " + ($bad -join ', ') + '; esperado api=512, app_db=384, sandbox_db=512 MiB')
}

# ------------------------------------------------------------------- CA-12 (R4)
$problems = @()
$cfgRaw = (& docker compose -p $Project -f $ComposeFile config --format json 2>$null) -join "`n"
if ($LASTEXITCODE -ne 0 -or -not $cfgRaw) {
    $problems += 'docker compose config --format json falló'
} else {
    $cfg = $cfgRaw | ConvertFrom-Json
    $vols = @($cfg.services.sandbox_db.volumes)
    $dataVol = $vols | Where-Object { $_.target -eq '/var/lib/postgresql/data' } | Select-Object -First 1
    if (-not $dataVol) {
        $problems += 'sandbox_db no monta /var/lib/postgresql/data'
    } else {
        if ($dataVol.type -ne 'bind') { $problems += "tipo de montaje '$($dataVol.type)' (se esperaba bind)" }
        # Compose omite create_host_path cuando es false; true aparecería explícito.
        if ($dataVol.bind -and $dataVol.bind.create_host_path -eq $true) { $problems += 'create_host_path resuelto como true' }
        $srcNorm = ("$($dataVol.source)").TrimEnd('\', '/').ToLowerInvariant()
        $expNorm = ([System.IO.Path]::GetFullPath($dataDirAbs)).TrimEnd('\', '/').ToLowerInvariant()
        if ($srcNorm -ne $expNorm) { $problems += "origen del bind '$($dataVol.source)' distinto de '$dataDirAbs'" }
    }
    $usesNamed = $cfgRaw -match '"sandbox_data"'
    if ($usesNamed) { $problems += 'el volumen sandbox_data sigue declarado' }
}
$composeText = [System.IO.File]::ReadAllText((Join-Path $Root $ComposeFile))
if ($composeText -notmatch 'create_host_path:\s*false') { $problems += 'docker-compose.prod.yml no declara create_host_path: false' }

$sbId = Get-ContainerId 'sandbox_db'
if (-not $sbId) {
    $problems += 'sandbox_db sin contenedor'
} else {
    $ins = Get-Inspect $sbId
    $h = if ($ins -and $ins.State.Health) { "$($ins.State.Health.Status)" } else { 'sin healthcheck' }
    if ($h -ne 'healthy') { $problems += "sandbox_db no está healthy ($h); posible problema de permisos del bind mount en Docker Desktop/NTFS" }
    $mt = ''
    if ($ins) { $mt = "$(@($ins.Mounts | Where-Object { $_.Destination -eq '/var/lib/postgresql/data' } | Select-Object -First 1).Type)" }
    if ($mt -ne 'bind') { $problems += "el contenedor monta los datos como '$mt' (se esperaba bind)" }
}
if ($problems.Count -eq 0) {
    Add-Result 'CA-12' 'R4' $true "sandbox_db healthy con bind mount en $dataDirAbs, create_host_path false, sin volumen sandbox_data"
} else {
    Add-Result 'CA-12' 'R4' $false ($problems -join '; ')
}

# ------------------------------------------------------------------- CA-13 (R5)
$expectedHeaders = [ordered]@{
    'Strict-Transport-Security' = 'max-age=31536000; includeSubDomains'
    'X-Content-Type-Options'    = 'nosniff'
    'X-Frame-Options'           = 'DENY'
    'Referrer-Policy'           = 'strict-origin-when-cross-origin'
    'Content-Security-Policy'   = $null   # solo presencia; el valor lo fija T-06
}
$problems = @()
foreach ($path in @('/', '/api/health-check')) {
    $r = Get-HttpResponse ($BaseUrl + $path)
    if ($r.CurlExit -ne 0) { $problems += "${path}: sin respuesta ($($r.Error.Trim()))"; continue }
    foreach ($name in $expectedHeaders.Keys) {
        $lines = @($r.Headers | Where-Object { $_ -match ('^' + [regex]::Escape($name) + ':') })
        if ($lines.Count -ne 1) { $problems += "${path}: $name aparece $($lines.Count) veces"; continue }
        $val = $lines[0].Substring($name.Length + 1).Trim()
        $exp = $expectedHeaders[$name]
        if ($null -ne $exp -and $val -ne $exp) { $problems += "${path}: $name='$val'" }
        if ($name -eq 'Content-Security-Policy' -and -not $val.StartsWith("default-src 'self'")) { $problems += "${path}: CSP inesperada '$val'" }
    }
    $srv = @($r.Headers | Where-Object { $_ -match '^Server:' })
    if ($srv.Count -ne 0) { $problems += "${path}: cabecera Server presente" }
}
if ($problems.Count -eq 0) {
    Add-Result 'CA-13' 'R5' $true 'Cinco cabeceras exactamente una vez y 0 Server en / y /api/health-check'
} else {
    Add-Result 'CA-13' 'R5' $false ($problems -join '; ')
}

# ------------------------------------------------------------- CA-14 (R6, R7.5)
$r = Get-HttpResponse ($BaseUrl + '/api/health-check')
if ($r.CurlExit -ne 0) {
    Add-Result 'CA-14' 'R6' $false "health-check sin respuesta en 5 s: $($r.Error.Trim())"
} else {
    $bodyCompact = ($r.Body -replace '\s', '')
    $ok = ($r.Status -eq 200) -and ($bodyCompact -eq '{"status":"ok"}') -and ($r.Time -le 3)
    $t = $r.Time.ToString('0.000', [System.Globalization.CultureInfo]::InvariantCulture)
    Add-Result 'CA-14' 'R6' $ok "GET /api/health-check -> HTTP $($r.Status) en $t s, cuerpo $bodyCompact"
}

# ---------------------------------------------------------- resumen (R7.7, R7.8)
$failed = @($script:Results | Where-Object { $_.estado -ne 'aprobado' })

Write-Host ''
Write-Host '== Resumen para la descripción del PR (pegar en .github/PULL_REQUEST_TEMPLATE/fase1.md) =='
Write-Host '| Criterio | Requisito | Estado | Detalle |'
Write-Host '| --- | --- | --- | --- |'
foreach ($res in $script:Results) {
    Write-Host ("| {0} | {1} | {2} | {3} |" -f $res.criterio, $res.requisito, $res.estado, ($res.detalle -replace '\|', '\|'))
}
Write-Host ''
Write-Host "Los contenedores siguen en ejecución. Para detenerlos: docker compose -p $Project -f $ComposeFile down"

if ($failed.Count -gt 0) {
    Write-Host ("RESULTADO: NO APROBADO ({0} fallo(s): {1}). No abras el PR; corrige y repite la verificación completa." -f $failed.Count, (($failed | ForEach-Object { $_.criterio }) -join ', ')) -ForegroundColor Red
    exit 1
}
Write-Host 'RESULTADO: APROBADO. CA-09 a CA-14 aprobados; puedes abrir el PR de la Fase 1.' -ForegroundColor Green
exit 0
