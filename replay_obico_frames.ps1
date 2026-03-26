param(
    [string]$FrameDir,
    [string]$OutputJson = ".\\obico_replay_results.json"
)

$ErrorActionPreference = "Stop"

if (-not $FrameDir) {
    throw "FrameDir is required."
}

$frames = Get-ChildItem -Path $FrameDir -Filter "*.jpg" | Sort-Object Name
$results = @()

foreach ($frame in $frames) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($frame.FullName)
        $body = @{ img = [Convert]::ToBase64String($bytes) } | ConvertTo-Json -Compress
        $response = Invoke-RestMethod -Uri "http://192.168.0.130:3333/detect/" -Method Post -Headers @{ Authorization = "obico" } -ContentType "application/json" -Body $body -TimeoutSec 60
        $detections = @($response.detections)
        $results += [pscustomobject]@{
            file = $frame.Name
            detection_count = $detections.Count
            detections = $detections
        }
    } catch {
        $results += [pscustomobject]@{
            file = $frame.Name
            error = $_.Exception.Message
        }
    }
}

$results | ConvertTo-Json -Depth 8 | Set-Content -Path $OutputJson -Encoding UTF8
