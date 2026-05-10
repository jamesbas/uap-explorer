<#
.SYNOPSIS
    Deploy UAP Explorer to Azure Container Apps.

.DESCRIPTION
    End-to-end deploy:
      1. Selects the target subscription and resource group.
      2. Provisions infra (ACR, Log Analytics, Container Apps Environment,
         user-assigned managed identity, two Container Apps with placeholder
         images) via infra/main.bicep.
      3. Reads backend/.env, extracts secret values, and re-runs the Bicep
         deployment with those secrets passed as parameters so they land in
         the backend Container App as ACA secrets / env vars.
      4. Builds the backend and frontend container images in ACR using
         `az acr build` (no local Docker required).
      5. Updates each Container App to the freshly built image tag.
      6. Sets the backend's FRONTEND_URL env var to the frontend's public
         FQDN so CORS works.
      7. Prints the public URL.

    The script is safe to re-run. Each invocation builds new image tags
    based on a timestamp + short git SHA so revisions are versioned in ACR.

.PARAMETER SubscriptionId
    Azure subscription. Default matches the UAP Explorer Azure subscription.

.PARAMETER ResourceGroup
    Resource group. Default matches the UAP Explorer resource group.

.PARAMETER Location
    Azure region. Default 'eastus'.

.PARAMETER NamePrefix
    Short prefix used in resource names (lowercase, 2-12 chars). Default 'uapexplorer'.

.PARAMETER EnvFile
    Path to the backend .env file containing Azure secrets. Defaults to
    backend/.env relative to this script.

.PARAMETER SkipBuild
    If set, skips `az acr build` and only re-runs the Bicep deployment.
    Useful when you just want to rotate secrets or change CPU/memory.

.PARAMETER SkipInfra
    If set, skips Bicep deployment and only rebuilds + updates images.

.EXAMPLE
    pwsh ./infra/deploy.ps1
        Full deploy using defaults.

.EXAMPLE
    pwsh ./infra/deploy.ps1 -SkipInfra
        Just rebuild and push the two images, then roll the apps.
#>
[CmdletBinding()]
param(
    [string]$SubscriptionId  = '9c245e09-df78-44f6-9253-a2a176e6f147',
    [string]$ResourceGroup   = 'rgJabAI-UAPExplorer',
    [string]$Location        = 'eastus',
    [string]$NamePrefix      = 'uapexplorer',
    [string]$EnvFile,
    [switch]$SkipBuild,
    [switch]$SkipInfra
)

$ErrorActionPreference = 'Stop'

# Force UTF-8 so `az acr build` log streaming doesn't crash on Windows cp1252
# when pip output contains non-ASCII characters.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    # Switch the Windows console code page to UTF-8 so colorama (used by az
    # acr build's log streaming) doesn't fall back to cp1252.
    cmd /c "chcp 65001 >nul" 2>$null
} catch { }

# Resolve script directory (fallback if $PSScriptRoot is empty, e.g. dot-sourced)
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RepoRoot = Split-Path -Parent $ScriptDir
$BicepFile = Join-Path $ScriptDir 'main.bicep'
if (-not $EnvFile) { $EnvFile = Join-Path $RepoRoot 'backend/.env' }

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Read-DotEnv([string]$path) {
    if (-not (Test-Path $path)) {
        throw "Env file not found: $path"
    }
    $map = @{}
    foreach ($line in Get-Content $path) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        $eq = $t.IndexOf('=')
        if ($eq -lt 1) { continue }
        $k = $t.Substring(0, $eq).Trim()
        $v = $t.Substring($eq + 1).Trim()
        # Strip optional surrounding quotes
        if ($v.Length -ge 2 -and (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'")))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        $map[$k] = $v
    }
    return $map
}

function Get-EnvOrEmpty([hashtable]$env, [string]$key) {
    if ($env.ContainsKey($key)) { return $env[$key] }
    return ''
}

# -------------------------------------------------------------------------
Write-Step "Verifying Azure CLI"
$null = az version 2>$null
if ($LASTEXITCODE -ne 0) { throw "Azure CLI not found on PATH." }

Write-Step "Setting subscription"
az account set --subscription $SubscriptionId | Out-Null
$account = az account show --output json | ConvertFrom-Json
Write-Host "  Subscription: $($account.name)  ($($account.id))"

Write-Step "Ensuring resource group $ResourceGroup exists in $Location"
az group create --name $ResourceGroup --location $Location --output none

# -------------------------------------------------------------------------
Write-Step "Loading backend secrets from $EnvFile"
$dotenv = Read-DotEnv $EnvFile
$secrets = @{
    adminPassword                  = Get-EnvOrEmpty $dotenv 'ADMIN_PASSWORD'
    azureStorageAccount            = Get-EnvOrEmpty $dotenv 'AZURE_STORAGE_ACCOUNT'
    azureStorageContainer          = (Get-EnvOrEmpty $dotenv 'AZURE_STORAGE_CONTAINER')
    azureStorageConnectionString   = Get-EnvOrEmpty $dotenv 'AZURE_STORAGE_CONNECTION_STRING'
    azureSearchEndpoint            = Get-EnvOrEmpty $dotenv 'AZURE_SEARCH_ENDPOINT'
    azureSearchAdminKey            = Get-EnvOrEmpty $dotenv 'AZURE_SEARCH_ADMIN_KEY'
    azureSearchIndexName           = (Get-EnvOrEmpty $dotenv 'AZURE_SEARCH_INDEX_NAME')
    azureOpenAIEndpoint            = Get-EnvOrEmpty $dotenv 'AZURE_OPENAI_ENDPOINT'
    azureOpenAIKey                 = Get-EnvOrEmpty $dotenv 'AZURE_OPENAI_API_KEY'
    azureOpenAIDeployment          = (Get-EnvOrEmpty $dotenv 'AZURE_OPENAI_DEPLOYMENT')
    azureOpenAIEmbeddingDeployment = (Get-EnvOrEmpty $dotenv 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT')
    azureOpenAIApiVersion          = (Get-EnvOrEmpty $dotenv 'AZURE_OPENAI_API_VERSION')
    azureDocIntelligenceEndpoint   = Get-EnvOrEmpty $dotenv 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
    azureDocIntelligenceKey        = Get-EnvOrEmpty $dotenv 'AZURE_DOCUMENT_INTELLIGENCE_KEY'
}
if (-not $secrets.adminPassword)  { Write-Warning 'ADMIN_PASSWORD is empty.' }
if (-not $secrets.azureSearchAdminKey) { Write-Warning 'AZURE_SEARCH_ADMIN_KEY is empty.' }
if (-not $secrets.azureOpenAIKey) { Write-Warning 'AZURE_OPENAI_API_KEY is empty.' }

# -------------------------------------------------------------------------
function Invoke-BicepDeploy([string]$backendImage, [string]$frontendImage) {
    $deployName = "uapexplorer-$(Get-Date -Format yyyyMMddHHmmss)"
    $params = @(
        "namePrefix=$NamePrefix",
        "location=$Location",
        "backendImage=$backendImage",
        "frontendImage=$frontendImage",
        "adminPassword=$($secrets.adminPassword)",
        "azureStorageAccount=$($secrets.azureStorageAccount)",
        "azureStorageContainer=$($secrets.azureStorageContainer)",
        "azureStorageConnectionString=$($secrets.azureStorageConnectionString)",
        "azureSearchEndpoint=$($secrets.azureSearchEndpoint)",
        "azureSearchAdminKey=$($secrets.azureSearchAdminKey)",
        "azureSearchIndexName=$($secrets.azureSearchIndexName)",
        "azureOpenAIEndpoint=$($secrets.azureOpenAIEndpoint)",
        "azureOpenAIKey=$($secrets.azureOpenAIKey)",
        "azureOpenAIDeployment=$($secrets.azureOpenAIDeployment)",
        "azureOpenAIEmbeddingDeployment=$($secrets.azureOpenAIEmbeddingDeployment)",
        "azureOpenAIApiVersion=$($secrets.azureOpenAIApiVersion)",
        "azureDocIntelligenceEndpoint=$($secrets.azureDocIntelligenceEndpoint)",
        "azureDocIntelligenceKey=$($secrets.azureDocIntelligenceKey)"
    )
    $json = az deployment group create `
        --resource-group $ResourceGroup `
        --name $deployName `
        --template-file $BicepFile `
        --parameters @params `
        --output json
    if ($LASTEXITCODE -ne 0) { throw "Bicep deployment failed." }
    return ($json | ConvertFrom-Json)
}

# -------------------------------------------------------------------------
# 1) First/initial deploy: get ACR + apps stood up with placeholder images.
$placeholder = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

$deploy = $null
if (-not $SkipInfra) {
    Write-Step "Provisioning infra via Bicep (initial deploy)"
    $deploy = Invoke-BicepDeploy -backendImage $placeholder -frontendImage $placeholder
} else {
    Write-Step "Reading existing deployment outputs (SkipInfra)"
    # Look up the actual ACR in the resource group (matches what Bicep created).
    $acrName = az acr list -g $ResourceGroup --query "[0].name" -o tsv
    if (-not $acrName) { throw "No ACR found in $ResourceGroup. Run without -SkipInfra first." }
    $deploy = [pscustomobject]@{ properties = [pscustomobject]@{ outputs = @{
        acrName        = @{ value = $acrName }
        acrLoginServer = @{ value = "$acrName.azurecr.io" }
        backendAppName = @{ value = "ca-$NamePrefix-backend" }
        frontendAppName = @{ value = "ca-$NamePrefix-frontend" }
    } } }
}

$out = $deploy.properties.outputs
$AcrName        = $out.acrName.value
$AcrLogin       = $out.acrLoginServer.value
$BackendAppName = $out.backendAppName.value
$FrontendAppName = $out.frontendAppName.value
Write-Host "  ACR:            $AcrLogin"
Write-Host "  Backend app:    $BackendAppName"
Write-Host "  Frontend app:   $FrontendAppName"

# -------------------------------------------------------------------------
# 2) Build images in ACR
$gitSha = (git -C $RepoRoot rev-parse --short HEAD 2>$null)
if (-not $gitSha) { $gitSha = 'local' }
$Tag = "$(Get-Date -Format yyyyMMdd-HHmmss)-$gitSha"

$backendImage  = "$AcrLogin/uap-backend:$Tag"
$frontendImage = "$AcrLogin/uap-frontend:$Tag"

if (-not $SkipBuild) {
    # NOTE: --no-logs is required on Windows because az's bundled Python
    # uses colorama to write log stream output, which crashes with
    # 'charmap codec can't encode' on cp1252 when pip output contains
    # non-ASCII characters. The build still runs in ACR; we wait for it.

    # Stage the source CSV into the backend build context so the image can
    # bundle it at /app/data/source/uap-csv.csv (matches UAP_CSV_PATH env).
    $csvSrc = Join-Path $RepoRoot 'data/source/uap-csv.csv'
    $csvDstDir = Join-Path $RepoRoot 'backend/data/source'
    if (Test-Path $csvSrc) {
        New-Item -ItemType Directory -Path $csvDstDir -Force | Out-Null
        Copy-Item $csvSrc (Join-Path $csvDstDir 'uap-csv.csv') -Force
    } else {
        throw "Source CSV not found at $csvSrc; cannot stage for backend image."
    }

    Write-Step "Building backend image  ($backendImage)"
    az acr build `
        --registry $AcrName `
        --image "uap-backend:$Tag" `
        --file (Join-Path $RepoRoot 'backend/Dockerfile') `
        --no-logs `
        (Join-Path $RepoRoot 'backend')
    if ($LASTEXITCODE -ne 0) { throw "Backend ACR build failed." }

    Write-Step "Building frontend image ($frontendImage)"
    az acr build `
        --registry $AcrName `
        --image "uap-frontend:$Tag" `
        --file (Join-Path $RepoRoot 'frontend/Dockerfile') `
        --no-logs `
        (Join-Path $RepoRoot 'frontend')
    if ($LASTEXITCODE -ne 0) { throw "Frontend ACR build failed." }
} else {
    Write-Step "SkipBuild set - looking up latest tags in $AcrName"
    $backendTag = az acr repository show-tags --name $AcrName --repository uap-backend --orderby time_desc --top 1 -o tsv 2>$null
    $frontendTag = az acr repository show-tags --name $AcrName --repository uap-frontend --orderby time_desc --top 1 -o tsv 2>$null
    if (-not $backendTag -or -not $frontendTag) { throw "Could not find existing image tags in $AcrName. Run without -SkipBuild first." }
    $backendImage  = "$AcrLogin/uap-backend:$backendTag"
    $frontendImage = "$AcrLogin/uap-frontend:$frontendTag"
    Write-Host "  Using backend  $backendImage"
    Write-Host "  Using frontend $frontendImage"
}

# -------------------------------------------------------------------------
# 3) Re-deploy Bicep with the real image tags so app revisions update.
Write-Step "Updating Container Apps to new image tags via Bicep"
$deploy = Invoke-BicepDeploy -backendImage $backendImage -frontendImage $frontendImage
$out = $deploy.properties.outputs
$FrontendUrl = $out.frontendUrl.value
$BackendInternalFqdn = $out.backendInternalFqdn.value

# -------------------------------------------------------------------------
# 4) Set FRONTEND_URL on the backend so CORS allows the public origin.
Write-Step "Patching backend FRONTEND_URL -> $FrontendUrl"
az containerapp update `
    --name $BackendAppName `
    --resource-group $ResourceGroup `
    --set-env-vars "FRONTEND_URL=$FrontendUrl" `
    --output none
if ($LASTEXITCODE -ne 0) { throw "Failed to patch backend env." }

# -------------------------------------------------------------------------
Write-Step "Done"
Write-Host ""
Write-Host "  Frontend (public):       $FrontendUrl" -ForegroundColor Green
Write-Host "  Backend (internal FQDN): http://$BackendInternalFqdn"
Write-Host ""
Write-Host "Tail backend logs:"
Write-Host "  az containerapp logs show -n $BackendAppName -g $ResourceGroup --follow"
Write-Host "Tail frontend logs:"
Write-Host "  az containerapp logs show -n $FrontendAppName -g $ResourceGroup --follow"
