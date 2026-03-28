param(
    [int]$Port = 8501
)

$ErrorActionPreference = 'Stop'
$serverHost = '127.0.0.1'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Resolve-Python {
    $candidates = @(
        'C:\Users\allen.ferreira\AppData\Local\anaconda3\python.exe',
        (Get-Command python -ErrorAction SilentlyContinue).Source,
        (Get-Command py -ErrorAction SilentlyContinue).Source
    ) | Where-Object { $_ } | Select-Object -Unique

    foreach ($c in $candidates) {
        if (-not (Test-Path $c)) { continue }
        try {
            & $c -c "import streamlit" 2>$null | Out-Null
            return $c
        } catch {}
    }
    return $null
}

$python = Resolve-Python
if (-not $python) {
    throw "Python com Streamlit nao encontrado. Instale com: pip install streamlit"
}

function Test-PortInUse {
    param([int]$PortToCheck)
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    return ($listeners.Port -contains $PortToCheck)
}

while (Test-PortInUse -PortToCheck $Port) {
    $Port++
}

$url = "http://$serverHost`:$Port"
Write-Host "Iniciando dashboard em $url"
Write-Host "Mantenha este terminal aberto para o dashboard continuar online."
Write-Host "Para abrir manualmente no navegador: Start-Process '$url'"

function Test-PortOpen {
    param([string]$HostName, [int]$PortToCheck)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $PortToCheck, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne(250)) {
            $client.EndConnect($async)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

$logOut = Join-Path $root 'streamlit_stdout.log'
$logErr = Join-Path $root 'streamlit_stderr.log'
$args = @(
    '-m', 'streamlit', 'run', 'dashboard_app.py',
    '--server.address', $serverHost,
    '--server.port', $Port
)

$proc = Start-Process -FilePath $python -ArgumentList $args -PassThru -RedirectStandardOutput $logOut -RedirectStandardError $logErr

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    if (Test-PortOpen -HostName $serverHost -PortToCheck $Port) {
        try { Start-Process -FilePath $url | Out-Null } catch {}
        break
    }
    Start-Sleep -Milliseconds 500
}

Write-Host "Logs: $logOut"
Write-Host "Logs: $logErr"

Wait-Process -Id $proc.Id
