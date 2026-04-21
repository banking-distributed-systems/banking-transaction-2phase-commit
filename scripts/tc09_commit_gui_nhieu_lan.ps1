param(
    [string]$BaseApi = "http://localhost:8666/api",
    [string]$FromAccount = "102938475612",
    [string]$ToAccount = "203847569801",
    [double]$Amount = 10000,
    [string]$Description = "TC09 - Commit gui nhieu lan",
    [int]$Repeat = 6,
    [int]$StatusPollMax = 20,
    [int]$StatusPollSleepMs = 500
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-AccountNumber {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    return (($Value -replace "\s+", "").Trim())
}

function Parse-JsonSafe {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
    try {
        return $Text | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-ObjectPropertyValue {
    param(
        [object]$Object,
        [string]$PropertyName,
        [object]$Default = $null
    )

    if ($null -eq $Object) {
        return $Default
    }

    $prop = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $prop) {
        return $Default
    }

    return $prop.Value
}

function Invoke-ApiJson {
    param(
        [string]$Method,
        [string]$Url,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )

    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 10
    }

    $invokeParams = @{
        Method      = $Method
        Uri         = $Url
        Headers     = $Headers
        ContentType = "application/json"
        UseBasicParsing = $true
        TimeoutSec  = 15
    }

    if ($null -ne $jsonBody) {
        $invokeParams["Body"] = $jsonBody
    }

    try {
        $res = Invoke-WebRequest @invokeParams
        return [pscustomobject]@{
            HttpStatus = [int]$res.StatusCode
            Json       = Parse-JsonSafe -Text $res.Content
            Raw        = $res.Content
            Error      = $null
        }
    }
    catch {
        $status = 0
        $raw = ""
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $raw = $reader.ReadToEnd()
                $reader.Close()
            }
            catch {
                $raw = ""
            }
        }

        return [pscustomobject]@{
            HttpStatus = $status
            Json       = Parse-JsonSafe -Text $raw
            Raw        = $raw
            Error      = $_.Exception.Message
        }
    }
}

function Get-Accounts {
    param([string]$BaseApiUrl)

    $res = Invoke-ApiJson -Method "GET" -Url "$BaseApiUrl/accounts"
    if ($res.HttpStatus -lt 200 -or $res.HttpStatus -ge 300 -or $null -eq $res.Json) {
        throw "Khong lay duoc danh sach tai khoan. HTTP=$($res.HttpStatus). $($res.Raw)"
    }

    if ($res.Json -is [System.Array]) {
        return $res.Json
    }

    throw "Response /accounts khong dung dinh dang mang."
}

function Get-Balance {
    param(
        [array]$Accounts,
        [string]$AccountNumber
    )

    $normalizedTarget = Normalize-AccountNumber -Value $AccountNumber
    $found = $Accounts | Where-Object {
        (Normalize-AccountNumber -Value $_.account_number) -eq $normalizedTarget
    } | Select-Object -First 1

    if ($null -eq $found) {
        throw "Khong tim thay tai khoan $AccountNumber trong /api/accounts"
    }

    return [double]$found.balance
}

function Poll-TransferStatus {
    param(
        [string]$BaseApiUrl,
        [string]$TxId,
        [int]$MaxAttempts,
        [int]$SleepMs
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $res = Invoke-ApiJson -Method "GET" -Url "$BaseApiUrl/transfer/status/$TxId"
        if ($res.HttpStatus -eq 200 -and $res.Json -and $res.Json.status -eq "success") {
            $phase = [string]$res.Json.data.phase
            if ($phase -in @("COMMITTED", "ABORTED", "COMPENSATED", "TIMEOUT")) {
                return $res
            }
        }
        Start-Sleep -Milliseconds $SleepMs
    }

    return $null
}

$FromAccount = Normalize-AccountNumber -Value $FromAccount
$ToAccount = Normalize-AccountNumber -Value $ToAccount

if ($Repeat -lt 2) {
    throw "Repeat phai >= 2 de test commit gui nhieu lan."
}

$idemKey = "TC09-" + [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() + "-" + (Get-Random -Minimum 1000 -Maximum 9999)

Write-Host "=== TC09 - Commit gui nhieu lan ===" -ForegroundColor Cyan
Write-Host "API: $BaseApi"
Write-Host "From: $FromAccount"
Write-Host "To:   $ToAccount"
Write-Host "Amount: $Amount"
Write-Host "Repeat: $Repeat"
Write-Host "Idempotency-Key: $idemKey"
Write-Host ""

# 1) Health check
$health = Invoke-ApiJson -Method "GET" -Url "$BaseApi/health"
if ($health.HttpStatus -lt 200 -or $health.HttpStatus -ge 300) {
    throw "Backend khong healthy. HTTP=$($health.HttpStatus). Hay chay backend truoc."
}

# 2) Balance truoc test
$accountsBefore = Get-Accounts -BaseApiUrl $BaseApi
$fromBefore = Get-Balance -Accounts $accountsBefore -AccountNumber $FromAccount
$toBefore = Get-Balance -Accounts $accountsBefore -AccountNumber $ToAccount

Write-Host "Balance truoc test:"
Write-Host "- From: $fromBefore"
Write-Host "- To:   $toBefore"
Write-Host ""

$payload = @{
    from_account_number = $FromAccount
    to_account_number   = $ToAccount
    amount              = $Amount
    description         = $Description
}

$headers = @{ "Idempotency-Key" = $idemKey }
$responses = @()
$txId = $null

# 3) Gui cung mot request transfer nhieu lan
for ($i = 1; $i -le $Repeat; $i++) {
    $res = Invoke-ApiJson -Method "POST" -Url "$BaseApi/transfer" -Body $payload -Headers $headers

    $jsonStatus = [string](Get-ObjectPropertyValue -Object $res.Json -PropertyName "status" -Default "")
    $jsonErrorCode = [string](Get-ObjectPropertyValue -Object $res.Json -PropertyName "error_code" -Default "")
    $jsonMessage = [string](Get-ObjectPropertyValue -Object $res.Json -PropertyName "message" -Default $res.Error)
    $jsonTxId = [string](Get-ObjectPropertyValue -Object $res.Json -PropertyName "tx_id" -Default "")
    $jsonReplay = [bool](Get-ObjectPropertyValue -Object $res.Json -PropertyName "idempotent_replay" -Default $false)

    $item = [pscustomobject]@{
        Attempt         = $i
        HttpStatus      = $res.HttpStatus
        Status          = $jsonStatus
        ErrorCode       = $jsonErrorCode
        Message         = $jsonMessage
        TxId            = $jsonTxId
        IdempotentReplay = $jsonReplay
    }

    if (-not [string]::IsNullOrWhiteSpace($item.TxId)) {
        $txId = $item.TxId
    }

    $responses += $item
    Start-Sleep -Milliseconds 80
}

Write-Host "Ket qua moi lan goi /transfer:" -ForegroundColor Yellow
$responses | Format-Table -AutoSize
Write-Host ""

if ([string]::IsNullOrWhiteSpace($txId)) {
    throw "Khong lay duoc tx_id tu cac response transfer."
}

# 4) Kiem tra phase cuoi
$statusRes = Poll-TransferStatus -BaseApiUrl $BaseApi -TxId $txId -MaxAttempts $StatusPollMax -SleepMs $StatusPollSleepMs
if ($null -eq $statusRes) {
    throw "Khong doc duoc trang thai ket thuc cua tx_id=$txId"
}

$finalPhase = [string]$statusRes.Json.data.phase
Write-Host "Trang thai cuoi tx_id=${txId}: $finalPhase" -ForegroundColor Yellow

# 5) Balance sau test
$accountsAfter = Get-Accounts -BaseApiUrl $BaseApi
$fromAfter = Get-Balance -Accounts $accountsAfter -AccountNumber $FromAccount
$toAfter = Get-Balance -Accounts $accountsAfter -AccountNumber $ToAccount

$fromDelta = [math]::Round(($fromAfter - $fromBefore), 2)
$toDelta = [math]::Round(($toAfter - $toBefore), 2)

Write-Host ""
Write-Host "Balance sau test:"
Write-Host "- From: $fromAfter (delta: $fromDelta)"
Write-Host "- To:   $toAfter (delta: $toDelta)"
Write-Host ""

# 6) Assert TC09
$notCrash = ($health.HttpStatus -ge 200 -and $health.HttpStatus -lt 300)
$notDuplicated = ($fromDelta -eq (-1 * $Amount) -and $toDelta -eq $Amount)
$isCommitted = ($finalPhase -eq "COMMITTED")

Write-Host "Danh gia TC09:" -ForegroundColor Cyan
Write-Host "- He thong khong crash: $notCrash"
Write-Host "- Khong nhan doi tien:  $notDuplicated"
Write-Host "- Trang thai COMMITTED: $isCommitted"

if ($notCrash -and $notDuplicated -and $isCommitted) {
    Write-Host "`nPASS TC09" -ForegroundColor Green
    exit 0
}

Write-Host "`nFAIL TC09" -ForegroundColor Red
exit 1
