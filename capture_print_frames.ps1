param(
    [string]$EntityId = "image.a1mini_0300aa5a1600497_camera",
    [int]$IntervalSeconds = 20,
    [string]$OutputRoot = ".\\captures",
    [int]$MaxFrames = 0
)

$ErrorActionPreference = "Stop"

$configBytes = Get-Content -Raw -Encoding Byte ".ha_connection_info.json"
$configText = [System.Text.Encoding]::UTF8.GetString($configBytes).TrimStart([char]0xFEFF)
$config = $configText | ConvertFrom-Json

$baseUrl = $config.ha_api.url.TrimEnd("/")
$headers = @{ Authorization = "Bearer $($config.ha_api.token)" }

$sessionStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionDir = Join-Path $OutputRoot $sessionStamp
$null = New-Item -ItemType Directory -Path $sessionDir -Force
$logPath = Join-Path $sessionDir "capture.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logPath -Value $line
}

Write-Log "capture start entity=$EntityId interval=${IntervalSeconds}s"

$frameCount = 0
while ($true) {
    try {
        $state = Invoke-RestMethod -Uri "$baseUrl/api/states/$EntityId" -Headers $headers -Method Get -TimeoutSec 15
        $picturePath = $state.attributes.entity_picture

        if ([string]::IsNullOrWhiteSpace($picturePath)) {
            Write-Log "skip missing entity_picture"
        } else {
            $imageUrl = if ($picturePath.StartsWith("/")) { "$baseUrl$picturePath" } else { $picturePath }
            $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
            $filePath = Join-Path $sessionDir "$timestamp.jpg"
            Invoke-WebRequest -Uri $imageUrl -Headers $headers -OutFile $filePath -TimeoutSec 20 | Out-Null
            $frameCount += 1
            Write-Log "saved frame=$frameCount file=$filePath"
        }
    } catch {
        Write-Log "error $($_.Exception.Message)"
    }

    if ($MaxFrames -gt 0 -and $frameCount -ge $MaxFrames) {
        Write-Log "capture complete frame_limit=$MaxFrames"
        break
    }

    Start-Sleep -Seconds $IntervalSeconds
}
