<#
.SYNOPSIS
    AutoTrade AI - Windows Logon Auto-Start Launcher.
    Automates startup and health verification of the complete local paper-trading stack:
    1. Fedora WSL2 environment
    2. Redis / Valkey in-memory daemon
    3. Ollama local LLM runtime
    4. FastAPI Operator API
    5. Next.js production monitoring dashboard
    6. Cloudflare Tunnel (trademoniter.reginaldalfret.tech)
    7. Today's live NSE paper-trading session (under strict market-session and duplicate protection rules).
#>

[CmdletBinding()]
param(
    [switch]$ForceSession = $false
)

$ErrorActionPreference = "Continue"

# Core Configuration & Absolute Paths
$ProjectDir = "D:\Trading LLM\MobiTradeAI"
$LogDir = "$ProjectDir\logs"
$RuntimeDir = "$ProjectDir\runtime"
$LogFile = "$LogDir\windows_startup.log"

$OllamaPath = "C:\Users\ASUS\AppData\Local\Programs\Ollama\ollama.exe"
$CloudflaredPath = "C:\Cloudflared\cloudflared.exe"
$CloudflaredConfig = "C:\Users\ASUS\.cloudflared\config.yml"

$WslDistro = "Fedora"
$WslProjectPath = "/root/projects/AutoTradeAI"
$ApiPort = 8008
$DashboardPort = 3000
$PublicUrl = "https://trademoniter.reginaldalfret.tech"

# Ensure directories exist
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
if (-not (Test-Path $RuntimeDir)) { New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null }

function Write-Log {
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [string]$Level = "INFO"
    )
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $logLine = "[$ts] [$Level] $Message"
    Write-Host $logLine
    try {
        Add-Content -Path $LogFile -Value $logLine -Encoding UTF8
    } catch {
        # Ignore write lock contention
    }
}

Write-Log "================================================================="
Write-Log "        AUTOTRADE AI - WINDOWS STARTUP LAUNCHER                  "
Write-Log "================================================================="
Write-Log "Host User: $env:USERDOMAIN\$env:USERNAME | Project: $ProjectDir"

# -------------------------------------------------------------
# STEP 1: Verify WSL2 Fedora Environment
# -------------------------------------------------------------
Write-Log "Verifying WSL2 '$WslDistro' distribution..."
$wslCheck = (wsl.exe -d $WslDistro -- echo ok 2>&1) -join ""
if ($wslCheck -notmatch "ok") {
    Write-Log "WSL2 distribution '$WslDistro' was not accessible! Output: $wslCheck" "FATAL"
    exit 1
}
Write-Log "WSL2 '$WslDistro' verified successfully." "SUCCESS"

# -------------------------------------------------------------
# STEP 2: Verify & Start Redis / Valkey Service in WSL
# -------------------------------------------------------------
Write-Log "Checking Redis / Valkey in-memory service..."
$redisPing = (wsl.exe -d $WslDistro -u root -- redis-cli ping 2>&1) -join ""
if ($redisPing -match "PONG") {
    Write-Log "Redis/Valkey daemon is already running (PONG)." "OK"
} else {
    Write-Log "Starting Valkey server in WSL..." "INFO"
    wsl.exe -d $WslDistro -u root -- /root/projects/AutoTradeAI/scripts/start_wsl_service.sh valkey 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    $redisPing = (wsl.exe -d $WslDistro -u root -- redis-cli ping 2>&1) -join ""
    if ($redisPing -match "PONG") {
        Write-Log "Redis/Valkey service started successfully." "SUCCESS"
    } else {
        Write-Log "Warning: Redis ping returned: $redisPing. System will operate in in-memory fallback mode." "WARN"
    }
}

# -------------------------------------------------------------
# STEP 3: Verify & Start Ollama Runtime on Windows Host
# -------------------------------------------------------------
Write-Log "Checking Ollama local LLM runtime..."
$ollamaOnline = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { $ollamaOnline = $true }
} catch {
    $ollamaOnline = $false
}

if ($ollamaOnline) {
    Write-Log "Ollama service is already online at http://127.0.0.1:11434." "OK"
} else {
    Write-Log "Ollama not responding. Starting Ollama serve daemon..." "INFO"
    if (Test-Path $OllamaPath) {
        Start-Process -FilePath $OllamaPath -ArgumentList "serve" -WindowStyle Hidden
        $retry = 0
        while ($retry -lt 8 -and -not $ollamaOnline) {
            Start-Sleep -Seconds 1
            $retry++
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                if ($resp.StatusCode -eq 200) { $ollamaOnline = $true }
            } catch {}
        }
    } else {
        Write-Log "Ollama executable not found at $OllamaPath." "ERROR"
    }

    if ($ollamaOnline) {
        Write-Log "Ollama started and verified responsive." "SUCCESS"
    } else {
        Write-Log "Ollama did not respond after startup attempt. LLM inference may fail." "WARN"
    }
}

# -------------------------------------------------------------
# STEP 4: Verify & Start FastAPI Operator Backend (Port 8008)
# -------------------------------------------------------------
Write-Log "Checking FastAPI Operator API (port $ApiPort)..."
$apiOnline = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { $apiOnline = $true }
} catch {
    $apiOnline = $false
}

if ($apiOnline) {
    Write-Log "FastAPI backend is already online at http://127.0.0.1:$ApiPort." "OK"
} else {
    Write-Log "Starting FastAPI daemon in WSL..." "INFO"
    wsl.exe -d $WslDistro -u root -- /root/projects/AutoTradeAI/scripts/start_wsl_service.sh api
    $retry = 0
    while ($retry -lt 10 -and -not $apiOnline) {
        Start-Sleep -Seconds 1
        $retry++
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) { $apiOnline = $true }
        } catch {}
    }

    if ($apiOnline) {
        Write-Log "FastAPI backend started and verified responsive." "SUCCESS"
    } else {
        Write-Log "FastAPI backend failed to respond on port $ApiPort." "ERROR"
    }
}

# -------------------------------------------------------------
# STEP 5: Verify & Start Next.js Production Dashboard (Port 3000)
# -------------------------------------------------------------
Write-Log "Checking Next.js dashboard (port $DashboardPort)..."
$dashOnline = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$DashboardPort" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { $dashOnline = $true }
} catch {
    $dashOnline = $false
}

if ($dashOnline) {
    Write-Log "Next.js dashboard is already online at http://127.0.0.1:$DashboardPort." "OK"
} else {
    Write-Log "Starting Next.js dashboard daemon in WSL..." "INFO"
    wsl.exe -d $WslDistro -u root -- /root/projects/AutoTradeAI/scripts/start_wsl_service.sh dashboard
    $retry = 0
    while ($retry -lt 12 -and -not $dashOnline) {
        Start-Sleep -Seconds 1
        $retry++
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$DashboardPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) { $dashOnline = $true }
        } catch {}
    }

    if ($dashOnline) {
        Write-Log "Next.js dashboard started and verified responsive." "SUCCESS"
    } else {
        Write-Log "Next.js dashboard failed to respond on port $DashboardPort." "ERROR"
    }
}

# -------------------------------------------------------------
# STEP 6: Verify & Start Cloudflare Tunnel
# -------------------------------------------------------------
Write-Log "Checking Cloudflare Tunnel for $PublicUrl..."
$cfProc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
if ($cfProc) {
    Write-Log "Cloudflare Tunnel process is already active (PID $($cfProc.Id[0]))." "OK"
} else {
    Write-Log "Starting Cloudflare Tunnel daemon on Windows..." "INFO"
    if (Test-Path $CloudflaredPath) {
        Start-Process -FilePath $CloudflaredPath -ArgumentList "--config $CloudflaredConfig tunnel run dailygurus-pricelist" -WindowStyle Hidden
        Start-Sleep -Seconds 4
        $cfProc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
        if ($cfProc) {
            Write-Log "Cloudflare Tunnel started successfully (PID $($cfProc.Id[0]))." "SUCCESS"
        } else {
            Write-Log "Warning: Cloudflare Tunnel process did not remain running." "WARN"
        }
    } else {
        Write-Log "Cloudflared executable not found at $CloudflaredPath." "ERROR"
    }
}

# -------------------------------------------------------------
# STEP 7: Comprehensive Endpoint & Health Verification
# -------------------------------------------------------------
Write-Log "Performing system health verification..."

$endpoints = @(
    @{ Name = "FastAPI Health";   Url = "http://127.0.0.1:$ApiPort/health" },
    @{ Name = "Runtime Status";   Url = "http://127.0.0.1:$ApiPort/runtime/status" },
    @{ Name = "Activity Feed";    Url = "http://127.0.0.1:$ApiPort/activity?limit=5" },
    @{ Name = "Portfolio State";  Url = "http://127.0.0.1:$ApiPort/portfolio" },
    @{ Name = "Risk Parameters";  Url = "http://127.0.0.1:$ApiPort/risk" },
    @{ Name = "Local Dashboard";  Url = "http://127.0.0.1:$DashboardPort" },
    @{ Name = "Public Dashboard"; Url = $PublicUrl }
)

foreach ($ep in $endpoints) {
    try {
        $r = Invoke-WebRequest -Uri $ep.Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Log " -> [$($ep.Name)] Status: $($r.StatusCode) [OK]" "OK"
    } catch {
        Write-Log " -> [$($ep.Name)] Failed: $($_.Exception.Message)" "WARN"
    }
}

# -------------------------------------------------------------
# STEP 8: Market Session Evaluation & Duplicate Protection
# -------------------------------------------------------------
$utcNow = [DateTime]::UtcNow
$istNow = $utcNow.AddHours(5).AddMinutes(30)
$todayStr = $istNow.ToString("yyyy-MM-dd")
$currentMin = $istNow.Hour * 60 + $istNow.Minute

Write-Log "Current IST Time: $($istNow.ToString('yyyy-MM-dd HH:mm:ss')) IST (Minutes into day: $currentMin)"

$lockFileWindows = "$RuntimeDir\session_$todayStr.lock"
$lockFileWsl = "\\wsl$\Fedora\root\projects\AutoTradeAI\runtime\session_$todayStr.lock"

# Evaluate Duplicate Lock
$alreadyExecuted = $false
foreach ($lf in @($lockFileWindows, $lockFileWsl)) {
    if (Test-Path $lf) {
        try {
            $lockContent = Get-Content -Path $lf -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($lockContent.status -in @("COMPLETED", "RUNNING")) {
                $alreadyExecuted = $true
                Write-Log "Daily session lock detected at '$lf' for $todayStr (Status: $($lockContent.status))." "LOCK"
                break
            }
        } catch {
            Write-Log "Note reading lock file '$lf': $($_.Exception.Message)" "WARN"
        }
    }
}

# Market session time boundaries:
# 09:15 IST = 555 mins
# 15:15 IST = 915 mins
# 15:30 IST = 930 mins

if ($currentMin -lt 555) {
    # Pre-market
    Write-Log "IST Time ($($istNow.ToString('HH:mm'))) is BEFORE market open (09:15 IST)." "MARKET"
    Write-Log "Infrastructure and dashboard are running. Paper trading session will not start early." "DECISION"
}
elseif ($currentMin -ge 555 -and $currentMin -le 915) {
    # Active market trading window
    Write-Log "IST Time ($($istNow.ToString('HH:mm'))) is WITHIN active market session (09:15 to 15:15 IST)." "MARKET"
    if ($alreadyExecuted -and -not $ForceSession) {
        Write-Log "DUPLICATE PROTECTION: Today's session ($todayStr) has already been executed. Refusing duplicate run." "DECISION"
    } else {
        Write-Log "Launching today's autonomous paper-trading session in background..." "START_SESSION"
        $forceArg = if ($ForceSession) { "--force" } else { "" }
        wsl.exe -d $WslDistro -u root -- /root/projects/AutoTradeAI/scripts/start_wsl_service.sh session $forceArg
        Write-Log "Session launched successfully in WSL background. Output logging to $WslProjectPath/logs/today_session.log." "SUCCESS"
    }
}
elseif ($currentMin -gt 915 -and $currentMin -le 930) {
    # Square-off cutoff window
    Write-Log "IST Time ($($istNow.ToString('HH:mm'))) is in mandatory square-off window (15:15 to 15:30 IST)." "MARKET"
    Write-Log "Ensuring infrastructure/dashboard remain available; fresh trading session not initiated." "DECISION"
}
else {
    # Post-market
    Write-Log "IST Time ($($istNow.ToString('HH:mm'))) is AFTER market close (> 15:30 IST)." "MARKET"
    Write-Log "Market session closed for today. Dashboard and reporting services remain available." "DECISION"
}

Write-Log "AutoTrade AI startup launcher finished successfully."
Write-Log "================================================================="
exit 0
