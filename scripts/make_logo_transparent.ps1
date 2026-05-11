# Strips the dark navy background from the UAP Explorer logo PNG using .NET.
# Pixels darker than $threshold become fully transparent; a small feather band
# fades to partial alpha to avoid hard edges.

param(
    [string]$Path = "$PSScriptRoot\..\frontend\public\uap-explorer-logo.png",
    [int]$Threshold = 55,
    [int]$Feather = 25
)

Add-Type -AssemblyName System.Drawing

$full = (Resolve-Path $Path).Path
Write-Host "Processing $full"

$src = [System.Drawing.Bitmap]::new($full)
$w = $src.Width
$h = $src.Height
$dst = [System.Drawing.Bitmap]::new($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)

$rect = [System.Drawing.Rectangle]::new(0, 0, $w, $h)
$srcData = $src.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$dstData = $dst.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)

$bytes = $srcData.Stride * $h
$buf = New-Object byte[] $bytes
[System.Runtime.InteropServices.Marshal]::Copy($srcData.Scan0, $buf, 0, $bytes)

$cleared = 0
$feathered = 0
for ($i = 0; $i -lt $bytes; $i += 4) {
    $b = $buf[$i]
    $g = $buf[$i+1]
    $r = $buf[$i+2]
    $a = $buf[$i+3]
    $luma = 0.2126 * $r + 0.7152 * $g + 0.0722 * $b
    if ($luma -lt $Threshold) {
        $buf[$i+3] = 0
        $cleared++
    } elseif ($luma -lt ($Threshold + $Feather)) {
        $t = ($luma - $Threshold) / $Feather
        $buf[$i+3] = [byte]([math]::Round($a * $t))
        $feathered++
    }
}

[System.Runtime.InteropServices.Marshal]::Copy($buf, 0, $dstData.Scan0, $bytes)
$src.UnlockBits($srcData)
$dst.UnlockBits($dstData)
$src.Dispose()

$dst.Save($full, [System.Drawing.Imaging.ImageFormat]::Png)
$dst.Dispose()

$total = $w * $h
Write-Host ("Saved {0}" -f $full)
Write-Host ("  size: {0}x{1} ({2} px)" -f $w, $h, $total)
Write-Host ("  fully transparent: {0} ({1:N1}%)" -f $cleared, ($cleared * 100.0 / $total))
Write-Host ("  feathered:         {0} ({1:N1}%)" -f $feathered, ($feathered * 100.0 / $total))
