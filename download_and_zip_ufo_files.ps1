param(
    [string]$CsvPath = ".\uap-csv.csv",
    [string]$OutDir = ".\ufo_release_01_files",
    [string]$ZipPath = ".\war_gov_ufo_release_01_documents.zip",
    [string]$ManifestPath = ".\ufo_release_01_download_manifest.csv",
    [int]$Retries = 3,
    [int]$ThrottleSeconds = 1
)

$ErrorActionPreference = "Stop"
$UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UFO release downloader/1.0"

function Get-SafeFileNameFromUrl([string]$Url) {
    $uri = [System.Uri]$Url
    $name = [System.Uri]::UnescapeDataString([System.IO.Path]::GetFileName($uri.AbsolutePath))
    foreach ($c in [System.IO.Path]::GetInvalidFileNameChars()) {
        $name = $name.Replace($c, '_')
    }
    return $name
}

if (!(Test-Path $CsvPath)) { throw "CSV not found: $CsvPath" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$rows = Import-Csv -Path $CsvPath
$links = $rows | ForEach-Object { $_.'PDF | Image Link' } | Where-Object { $_ -and $_.Trim() -ne "" } | ForEach-Object { $_.Trim() } | Sort-Object -Unique
Write-Host "Found $($links.Count) unique downloadable links."

$manifest = New-Object System.Collections.Generic.List[object]
$i = 0
foreach ($url in $links) {
    $i++
    $fileName = Get-SafeFileNameFromUrl $url
    $outFile = Join-Path $OutDir $fileName
    Write-Host "[$i/$($links.Count)] $fileName"

    $status = "failed"
    $size = $null
    $errorMsg = ""

    if ((Test-Path $outFile) -and ((Get-Item $outFile).Length -gt 0)) {
        $status = "skipped_existing"
        $size = (Get-Item $outFile).Length
    } else {
        for ($attempt = 1; $attempt -le $Retries; $attempt++) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $outFile -Headers @{ "User-Agent" = $UserAgent } -TimeoutSec 600
                $status = "downloaded"
                $size = (Get-Item $outFile).Length
                Start-Sleep -Seconds $ThrottleSeconds
                break
            } catch {
                $errorMsg = "attempt ${attempt}: $($_.Exception.Message)"
                if (Test-Path $outFile) { Remove-Item $outFile -Force -ErrorAction SilentlyContinue }
                Start-Sleep -Seconds ([Math]::Min(10, $attempt * 2))
            }
        }
    }

    $manifest.Add([pscustomobject]@{
        index = $i
        url = $url
        filename = $fileName
        status = $status
        size_bytes = $size
        error = $errorMsg
    })
}

$manifest | Export-Csv -Path $ManifestPath -NoTypeInformation
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $ZipPath -Force
Write-Host "Done. ZIP written to $ZipPath"
Write-Host "Manifest written to $ManifestPath"
