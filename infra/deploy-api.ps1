# ==============================================================================
# Pramaan - Cloud Run API Deployment Script
# Service : api
# Project : pramaan-dev-515306
# Region  : asia-south1 (Mumbai)
#
# Idempotent build via Cloud Build and deployment to Cloud Run.
# Configures service account, environment variables, instance limits,
# and grants roles/run.invoker to pramaan-agent.
# ==============================================================================

[CmdletBinding()]
param (
    [string]$Project = "pramaan-dev-515306",
    [string]$Region = "asia-south1",
    [string]$ServiceName = "api",
    [string]$RepoName = "pramaan",
    [string]$Env = "dev"
)

# Ensure Google Cloud SDK is in PATH
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    $sdkBin = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin"
    if (Test-Path $sdkBin) {
        $env:Path = "$sdkBin;$env:Path"
    }
}

function Invoke-Cli {
    param (
        [string]$CommandLine,
        [switch]$IgnoreError
    )
    $output = cmd /c "$CommandLine 2>&1"
    $exitCode = $LASTEXITCODE
    if (-not $IgnoreError -and $exitCode -ne 0) {
        throw "Command failed (Exit code $exitCode): $CommandLine`nOutput: $($output -join "`n")"
    }
    return @{
        Output   = ($output -join "`n").Trim()
        ExitCode = $exitCode
        Success  = ($exitCode -eq 0)
    }
}

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Pramaan API Deployment - Cloud Run ($ServiceName)" -ForegroundColor Cyan
Write-Host "  Project : $Project | Region: $Region" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

$serviceAccount = "pramaan-api@${Project}.iam.gserviceaccount.com"
$agentServiceAccount = "pramaan-agent@${Project}.iam.gserviceaccount.com"
$imageTag = "${Region}-docker.pkg.dev/${Project}/${RepoName}/${ServiceName}:latest"
$kmsKey = "projects/${Project}/locations/${Region}/keyRings/pramaan/cryptoKeys/mandate-signer"

# 1. Build container image with Cloud Build
Write-Host "`n[1/4] Building container image via Cloud Build: $imageTag..." -ForegroundColor Yellow
$rootDir = (Get-Item $PSScriptRoot).Parent.FullName
$apiDir = Join-Path $rootDir "services\api"
Invoke-Cli "gcloud builds submit `"$apiDir`" --tag `"$imageTag`" --project $Project" | Out-Null
Write-Host "  [OK] Container image built and pushed to Artifact Registry." -ForegroundColor Green

# 2. Deploy Cloud Run service
Write-Host "`n[2/4] Deploying Cloud Run service '$ServiceName' in $Region..." -ForegroundColor Yellow
$deployCmd = "gcloud run deploy $ServiceName " +
    "--image `"$imageTag`" " +
    "--region $Region " +
    "--project $Project " +
    "--service-account `"$serviceAccount`" " +
    "--set-env-vars ""ENV=$Env,GCP_PROJECT=$Project,REGION=$Region,KMS_KEY=$kmsKey"" " +
    "--min-instances 0 " +
    "--max-instances 3 " +
    "--allow-unauthenticated"

Invoke-Cli $deployCmd | Out-Null
Write-Host "  [OK] Cloud Run service '$ServiceName' deployed." -ForegroundColor Green

# 3. Grant pramaan-agent roles/run.invoker
Write-Host "`n[3/4] Granting roles/run.invoker to $agentServiceAccount on '$ServiceName'..." -ForegroundColor Yellow
$iamCmd = "gcloud run services add-iam-policy-binding $ServiceName " +
    "--region $Region " +
    "--project $Project " +
    "--member=""serviceAccount:$agentServiceAccount"" " +
    "--role=""roles/run.invoker"""

Invoke-Cli $iamCmd | Out-Null
Write-Host "  [OK] IAM invoker role bound for pramaan-agent." -ForegroundColor Green

# 4. Verification
Write-Host "`n[4/4] Verifying deployed service health endpoint..." -ForegroundColor Yellow
$urlRes = Invoke-Cli "gcloud run services describe $ServiceName --region $Region --project $Project --format=""value(status.url)"""
$serviceUrl = $urlRes.Output

Write-Host "  Service URL: $serviceUrl" -ForegroundColor Cyan
$healthUrl = "$serviceUrl/v1/health"
Write-Host "  Querying $healthUrl..." -ForegroundColor Gray

try {
    $healthRes = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 15
    Write-Host "  Health Response:" -ForegroundColor Green
    $healthRes | ConvertTo-Json | Write-Host
} catch {
    Write-Host "  Failed to query health endpoint directly: $_" -ForegroundColor Red
}

Write-Host "`n===========================================================" -ForegroundColor Green
Write-Host "  Deployment Completed Successfully!" -ForegroundColor Green
Write-Host "  API Endpoint : $serviceUrl" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
