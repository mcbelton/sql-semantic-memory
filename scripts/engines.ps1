<#
.SYNOPSIS
  Portable database servers for the cross-engine tests on Windows: no admin rights, no Docker.

.DESCRIPTION
  start   Downloads PostgreSQL and MariaDB once (to -Root), initializes data folders, starts both servers on
          127.0.0.1 (ports 54329 and 33069) plus SQL Server LocalDB, waits until they accept connections and
          prints the environment variables the tests read.
  env     Prints the environment variable assignments (pipe to Invoke-Expression to apply them).
  status  Shows which servers are running.
  stop    Stops everything that 'start' started.

  On Linux/macOS (or with Docker on Windows) use compose.yaml instead; it exposes the same ports.

.EXAMPLE
  .\scripts\engines.ps1 start
  .\scripts\engines.ps1 env | Invoke-Expression
  python scripts\verify.py --require-engines
  .\scripts\engines.ps1 stop
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'env')]
    [string]$Action = 'status',
    [string]$Root = (Join-Path $env:LOCALAPPDATA 'sqlmem-engines'),
    [switch]$NoLocalDb
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$PgVersion = '18.6.0'
$PgPort = 54329
$PgUrl = "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/$PgVersion/embedded-postgres-binaries-windows-amd64-$PgVersion.jar"
$MariaVersion = '11.4.5'
$MariaPort = 33069
$MariaUrl = "https://archive.mariadb.org/mariadb-$MariaVersion/winx64-packages/mariadb-$MariaVersion-winx64.zip"
$LocalDbInstance = 'MSSQLLocalDB'

$PgHome = Join-Path $Root "postgresql-$PgVersion"
$PgData = Join-Path $Root 'pgdata'
$MariaHome = Join-Path $Root "mariadb-$MariaVersion-winx64"
$MariaData = Join-Path $Root 'mariadata'
$StateFile = Join-Path $Root 'pids.json'

function Get-Python {
    $venv = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
    if (Test-Path $venv) { return (Resolve-Path $venv).Path }
    return 'python'
}

function Test-Port([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.ConnectAsync('127.0.0.1', $Port).Wait(500) -and $client.Connected
    } catch {
        $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port([int]$Port, [string]$Name, [int]$Seconds = 90) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not start listening on port $Port within $Seconds s (see logs in $Root)"
}

function Get-OdbcDriverName {
    foreach ($name in 'ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server') {
        if (Get-OdbcDriver -Name $name -ErrorAction SilentlyContinue) { return $name }
    }
    return $null
}

function Install-PostgreSql {
    if (Test-Path (Join-Path $PgHome 'bin\postgres.exe')) { return }
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    $jar = Join-Path $Root "postgres-$PgVersion.jar"
    Write-Host "Downloading PostgreSQL $PgVersion ..."
    curl.exe -fsSL -o $jar $PgUrl
    if ($LASTEXITCODE) { throw "download failed: $PgUrl" }
    # The jar holds a .txz archive; Python's tarfile reads xz without extra tools.
    $extract = "import io, sys, tarfile, zipfile; z = zipfile.ZipFile(sys.argv[1]); " +
        "n = next(n for n in z.namelist() if n.endswith('.txz')); " +
        "tarfile.open(fileobj=io.BytesIO(z.read(n)), mode='r:xz').extractall(sys.argv[2], filter='data')"
    & (Get-Python) -c $extract $jar $PgHome
    if ($LASTEXITCODE) { throw 'extracting PostgreSQL failed' }
    Remove-Item $jar
}

function Install-MariaDb {
    if (Test-Path (Join-Path $MariaHome 'bin\mariadbd.exe')) { return }
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    $zip = Join-Path $Root "mariadb-$MariaVersion.zip"
    Write-Host "Downloading MariaDB $MariaVersion ..."
    curl.exe -fsSL -o $zip $MariaUrl
    if ($LASTEXITCODE) { throw "download failed: $MariaUrl" }
    tar.exe -xf $zip -C $Root
    if ($LASTEXITCODE) { throw 'extracting MariaDB failed' }
    Remove-Item $zip
}

function Read-State {
    if (Test-Path $StateFile) { return Get-Content $StateFile -Raw | ConvertFrom-Json }
    return [pscustomobject]@{ postgresql = $null; mariadb = $null; localdb = $false }
}

function Start-Engines {
    Install-PostgreSql
    Install-MariaDb
    $state = Read-State

    if (Test-Port $PgPort) {
        Write-Host "PostgreSQL already listening on $PgPort"
    } else {
        if (-not (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
            & (Join-Path $PgHome 'bin\initdb.exe') -D $PgData -U postgres -A trust -E UTF8 *> (Join-Path $Root 'initdb.log')
            if ($LASTEXITCODE) { throw "initdb failed, see $Root\initdb.log" }
        }
        $pgArgs = @('-D', "`"$PgData`"", '-p', $PgPort, '-h', '127.0.0.1', '-c', 'logging_collector=on',
            '-c', "log_directory=`"$($Root -replace '\\', '/')/pglog`"")
        $proc = Start-Process -FilePath (Join-Path $PgHome 'bin\postgres.exe') -ArgumentList $pgArgs -WindowStyle Hidden -PassThru
        $state.postgresql = $proc.Id
        Wait-Port $PgPort 'PostgreSQL'
        Write-Host "PostgreSQL $PgVersion listening on 127.0.0.1:$PgPort (pid $($proc.Id))"
    }

    if (Test-Port $MariaPort) {
        Write-Host "MariaDB already listening on $MariaPort"
    } else {
        $ini = Join-Path $MariaData 'my.ini'
        if (-not (Test-Path $ini)) {
            & (Join-Path $MariaHome 'bin\mariadb-install-db.exe') "--datadir=$MariaData" "--port=$MariaPort" *> (Join-Path $Root 'mariadb-install.log')
            if ($LASTEXITCODE) { throw "mariadb-install-db failed, see $Root\mariadb-install.log" }
        }
        $mArgs = @("--defaults-file=`"$ini`"", '--bind-address=127.0.0.1', "--port=$MariaPort")
        $proc = Start-Process -FilePath (Join-Path $MariaHome 'bin\mariadbd.exe') -ArgumentList $mArgs -WindowStyle Hidden -PassThru
        $state.mariadb = $proc.Id
        Wait-Port $MariaPort 'MariaDB'
        Write-Host "MariaDB $MariaVersion listening on 127.0.0.1:$MariaPort (pid $($proc.Id))"
    }

    if (-not $NoLocalDb -and (Get-Command sqllocaldb.exe -ErrorAction SilentlyContinue)) {
        sqllocaldb.exe start $LocalDbInstance | Out-Null
        $state.localdb = $true
        Write-Host "SQL Server LocalDB instance '$LocalDbInstance' started"
    } elseif (-not $NoLocalDb) {
        Write-Warning 'sqllocaldb.exe not found: SQL Server tests will be skipped (install SQL Server Express LocalDB).'
    }
    $state | ConvertTo-Json | Set-Content -Path $StateFile -Encoding utf8
    Write-Host "`nApply the test settings to this session with:  .\scripts\engines.ps1 env | Invoke-Expression"
}

function Get-EnvAssignments {
    $urls = @("postgresql+psycopg://postgres@127.0.0.1:$PgPort/postgres", "mysql+pymysql://root@127.0.0.1:$MariaPort/mysql")
    $lines = @()
    $driver = Get-OdbcDriverName
    $state = Read-State
    if ($state.localdb -and $driver) {
        $odbc = "Driver={$driver};Server=(localdb)\$LocalDbInstance;Trusted_Connection=yes;"
        $urls += 'mssql+pyodbc:///?odbc_connect=' + [uri]::EscapeDataString("${odbc}Database=tempdb;")
        $lines += "`$env:SQLMEM_MSSQL_ODBC = '$odbc'"
    }
    $lines = @("`$env:SQLMEM_TEST_URLS = '$($urls -join ' ')'") + $lines
    return $lines
}

function Get-OwnProcess([object]$ProcessId, [string]$Executable) {
    # pids.json can outlive a crash or reboot, and Windows reuses process ids: only return the process when it
    # still runs the expected executable.
    if (-not $ProcessId) { return $null }
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { return $null }
    $path = $null
    try { $path = $proc.Path } catch { $path = $null }
    if ($path -and [string]::Equals([IO.Path]::GetFullPath($path), [IO.Path]::GetFullPath($Executable),
            [StringComparison]::OrdinalIgnoreCase)) {
        return $proc
    }
    Write-Warning "Process $ProcessId is now '$($proc.ProcessName)', not $(Split-Path -Leaf $Executable); leaving it alone."
    return $null
}

function Stop-OwnProcess([object]$ProcessId, [string]$Executable, [string]$Name, [scriptblock]$Shutdown) {
    $proc = Get-OwnProcess $ProcessId $Executable
    if (-not $proc) { return }
    & $Shutdown
    if (-not $proc.WaitForExit(15000)) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "$Name stopped"
}

function Stop-Engines {
    $state = Read-State
    try {
        Stop-OwnProcess $state.postgresql (Join-Path $PgHome 'bin\postgres.exe') 'PostgreSQL' {
            & (Join-Path $PgHome 'bin\pg_ctl.exe') stop -D $PgData -m fast *> $null
        }
        Stop-OwnProcess $state.mariadb (Join-Path $MariaHome 'bin\mariadbd.exe') 'MariaDB' {
            & (Join-Path $MariaHome 'bin\mariadb-admin.exe') -u root -h 127.0.0.1 -P $MariaPort shutdown *> $null
        }
        if ($state.localdb -and (Get-Command sqllocaldb.exe -ErrorAction SilentlyContinue)) {
            sqllocaldb.exe stop $LocalDbInstance | Out-Null
            Write-Host "SQL Server LocalDB instance '$LocalDbInstance' stopped"
        }
    } finally {
        if (Test-Path $StateFile) { Remove-Item $StateFile }
    }
}

function Show-Status {
    $state = Read-State
    [pscustomobject]@{ Engine = 'PostgreSQL'; Port = $PgPort; Listening = (Test-Port $PgPort); Pid = $state.postgresql }
    [pscustomobject]@{ Engine = 'MariaDB'; Port = $MariaPort; Listening = (Test-Port $MariaPort); Pid = $state.mariadb }
    [pscustomobject]@{ Engine = 'SQL Server LocalDB'; Port = '-'; Listening = [bool]$state.localdb; Pid = '-' }
}

switch ($Action) {
    'start' { Start-Engines; Get-EnvAssignments }
    'env' { Get-EnvAssignments }
    'status' { Show-Status | Format-Table -AutoSize }
    'stop' { Stop-Engines }
}
