param(
    [string]$Url = "http://127.0.0.1:8000/api/health"
)

$ErrorActionPreference = "Stop"
$response = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 5
if ($response.status -ne "ok") {
    throw "Unexpected health response: $($response | ConvertTo-Json -Compress)"
}
$response | ConvertTo-Json -Depth 8
