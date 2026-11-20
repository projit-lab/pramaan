# ==============================================================================
# Pramaan - Google Cloud Foundation Bootstrap Script
# Project ID : pramaan-dev-515306
# Region     : asia-south1 (Mumbai)
#
# Idempotent setup for APIs, Artifact Registry, Firestore, BigQuery, Pub/Sub,
# Cloud KMS (HSM), Service Accounts, and Least-Privilege IAM Bindings.
#
# IAM Role Reference:
# - roles/cloudkms.signerVerifier        : Sign & verify with KMS asymmetric key
# - roles/datastore.user                 : Read/write access to Firestore data
# - roles/bigquery.dataEditor            : Edit/read data in BigQuery dataset (Schema DCL)
# - roles/bigquery.jobUser               : Run queries/jobs in BigQuery
# - roles/pubsub.publisher               : Publish messages to Pub/Sub topics
# - roles/pubsub.subscriber              : Pull/consume messages from Pub/Sub
# - roles/secretmanager.secretAccessor   : Access secret payloads in Secret Manager
# - roles/aiplatform.user                : Access Vertex AI / Gemini models & predictions
# - roles/modelarmor.user                : Call Model Armor prompt/response sanitization
# ==============================================================================

[CmdletBinding()]
param (
    [string]$ExpectedProject = "pramaan-dev-515306",
    [string]$Region = "asia-south1"
)

# Ensure Google Cloud SDK is in PATH
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    $sdkBin = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin"
    if (Test-Path $sdkBin) {
        $env:Path = "$sdkBin;$env:Path"
    }
}

# Track summary of all resources
$Summary = [System.Collections.Generic.List[PSCustomObject]]::new()

function Add-SummaryRecord {
    param (
        [string]$ResourceType,
        [string]$ResourceName,
        [string]$Scope,
        [string]$Status,
        [string]$Notes = ""
    )
    $Summary.Add([PSCustomObject]@{
        ResourceType = $ResourceType
        ResourceName = $ResourceName
        Scope        = $Scope
        Status       = $Status
        Notes        = $Notes
    })
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
Write-Host "  Pramaan Cloud Infrastructure Bootstrap - $ExpectedProject" -ForegroundColor Cyan
Write-Host "  Target Region: $Region" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. Project & Billing Verification
# ------------------------------------------------------------------------------
Write-Host "`n[1/9] Checking active gcloud project and billing status..." -ForegroundColor Yellow

$projRes = Invoke-Cli "gcloud config get-value project"
$currentProject = $projRes.Output
if (-not $currentProject -or $currentProject -eq "(unset)") {
    throw "No active gcloud project set. Please run 'gcloud config set project $ExpectedProject' first."
}

if ($currentProject -ne $ExpectedProject) {
    throw "Active gcloud project is '$currentProject', but expected '$ExpectedProject'. Set it using: gcloud config set project $ExpectedProject"
}
Write-Host "  [OK] Active project confirmed: $currentProject" -ForegroundColor Green

$billingRes = Invoke-Cli "gcloud billing projects describe $ExpectedProject --format=""value(billingEnabled)"""
if ($billingRes.Output -ne "True" -and $billingRes.Output -ne "true") {
    throw "Billing is NOT enabled on project '$ExpectedProject'. Please link an active billing account before bootstrapping."
}
Write-Host "  [OK] Billing is active on project: $ExpectedProject" -ForegroundColor Green

Add-SummaryRecord -ResourceType "Project" -ResourceName $ExpectedProject -Scope "Global" -Status "Verified" -Notes "Active & Billing Enabled"

# ------------------------------------------------------------------------------
# 2. Enable Required APIs
# ------------------------------------------------------------------------------
Write-Host "`n[2/9] Checking and enabling required Google Cloud APIs..." -ForegroundColor Yellow

$requiredApis = @(
    "run.googleapis.com",             # Cloud Run
    "artifactregistry.googleapis.com",# Artifact Registry
    "cloudbuild.googleapis.com",      # Cloud Build
    "pubsub.googleapis.com",          # Cloud Pub/Sub
    "firestore.googleapis.com",       # Firestore
    "bigquery.googleapis.com",        # BigQuery
    "cloudkms.googleapis.com",        # Cloud Key Management Service (KMS)
    "secretmanager.googleapis.com",   # Secret Manager
    "alloydb.googleapis.com",         # AlloyDB API (API only, no running clusters)
    "aiplatform.googleapis.com",      # Vertex AI / Agent Platform
    "modelarmor.googleapis.com",      # Model Armor
    "firebase.googleapis.com",        # Firebase Management
    "fcm.googleapis.com",             # Firebase Cloud Messaging
    "playintegrity.googleapis.com",   # Google Play Integrity API
    "iam.googleapis.com"              # Identity and Access Management
)

Write-Host "  Fetching list of currently enabled services..." -ForegroundColor Gray
$servicesRes = Invoke-Cli "gcloud services list --enabled --format=""value(config.name)"""
$enabledApis = $servicesRes.Output -split "[\r\n]+"

$apisToEnable = @()
foreach ($api in $requiredApis) {
    if ($enabledApis -contains $api) {
        Write-Host "  - $api : Already enabled" -ForegroundColor Gray
        Add-SummaryRecord -ResourceType "API" -ResourceName $api -Scope "Project" -Status "Already Enabled"
    } else {
        $apisToEnable += $api
    }
}

if ($apisToEnable.Count -gt 0) {
    $apiListStr = $apisToEnable -join " "
    Write-Host "  Enabling $($apisToEnable.Count) missing APIs: $apiListStr..." -ForegroundColor Cyan
    Invoke-Cli "gcloud services enable $apiListStr" | Out-Null
    foreach ($api in $apisToEnable) {
        Add-SummaryRecord -ResourceType "API" -ResourceName $api -Scope "Project" -Status "Enabled"
    }
}
Write-Host "  [OK] All required APIs are enabled." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 3. Artifact Registry Docker Repository
# ------------------------------------------------------------------------------
Write-Host "`n[3/9] Checking Artifact Registry repository 'pramaan' in $Region..." -ForegroundColor Yellow

$arCheck = Invoke-Cli "gcloud artifacts repositories describe pramaan --location=$Region --format=""value(name)""" -IgnoreError
if ($arCheck.Success -and $arCheck.Output) {
    Write-Host "  - Repository 'pramaan': Already exists in $Region" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "Artifact Registry" -ResourceName "pramaan" -Scope $Region -Status "Already Exists" -Notes "Format: Docker"
} else {
    Write-Host "  Creating Artifact Registry Docker repository 'pramaan' in $Region..." -ForegroundColor Cyan
    Invoke-Cli "gcloud artifacts repositories create pramaan --repository-format=docker --location=$Region --description=""Pramaan Docker repository""" | Out-Null
    Add-SummaryRecord -ResourceType "Artifact Registry" -ResourceName "pramaan" -Scope $Region -Status "Created" -Notes "Format: Docker"
}
Write-Host "  [OK] Artifact Registry repository ready." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 4. Firestore Database (Native mode)
# ------------------------------------------------------------------------------
Write-Host "`n[4/9] Checking Firestore database in $Region..." -ForegroundColor Yellow

$fsCheck = Invoke-Cli "gcloud firestore databases list --format=""value(name)""" -IgnoreError
$defaultDbExists = $false
if ($fsCheck.Success -and $fsCheck.Output) {
    $dbs = $fsCheck.Output -split "[\r\n]+"
    foreach ($db in $dbs) {
        if ($db -match "\(default\)" -or $db -match "projects/$ExpectedProject/databases/\(default\)") {
            $defaultDbExists = $true
            break
        }
    }
}

if ($defaultDbExists) {
    Write-Host "  - Firestore (default) database: Already exists" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "Firestore DB" -ResourceName "(default)" -Scope $Region -Status "Already Exists" -Notes "Mode: Native"
} else {
    Write-Host "  Creating Firestore database '(default)' in Native mode in $Region..." -ForegroundColor Cyan
    Invoke-Cli "gcloud firestore databases create --location=$Region --type=firestore-native" | Out-Null
    Add-SummaryRecord -ResourceType "Firestore DB" -ResourceName "(default)" -Scope $Region -Status "Created" -Notes "Mode: Native"
}
Write-Host "  [OK] Firestore database ready." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 5. BigQuery Dataset
# ------------------------------------------------------------------------------
Write-Host "`n[5/9] Checking BigQuery dataset 'pramaan_ledger' in $Region..." -ForegroundColor Yellow

$bqCheck = Invoke-Cli "bq show --dataset ${ExpectedProject}:pramaan_ledger" -IgnoreError
if ($bqCheck.Success) {
    Write-Host "  - BigQuery dataset 'pramaan_ledger': Already exists in $Region" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "BigQuery Dataset" -ResourceName "pramaan_ledger" -Scope $Region -Status "Already Exists" -Notes "No tables created yet"
} else {
    Write-Host "  Creating BigQuery dataset 'pramaan_ledger' in $Region..." -ForegroundColor Cyan
    Invoke-Cli "bq mk --location=$Region --dataset ${ExpectedProject}:pramaan_ledger" | Out-Null
    Add-SummaryRecord -ResourceType "BigQuery Dataset" -ResourceName "pramaan_ledger" -Scope $Region -Status "Created" -Notes "No tables created yet"
}
Write-Host "  [OK] BigQuery dataset ready." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 6. Pub/Sub Topics
# ------------------------------------------------------------------------------
Write-Host "`n[6/9] Checking Pub/Sub topics..." -ForegroundColor Yellow

$pubsubTopics = @(
    "intent-created",
    "intent-decided",
    "approval-signed",
    "mandate-issued",
    "payment-released",
    "payment-blocked",
    "device-enrolled"
)

foreach ($topic in $pubsubTopics) {
    $topicCheck = Invoke-Cli "gcloud pubsub topics describe $topic --format=""value(name)""" -IgnoreError
    if ($topicCheck.Success -and $topicCheck.Output) {
        Write-Host "  - Topic '$topic': Already exists" -ForegroundColor Gray
        Add-SummaryRecord -ResourceType "Pub/Sub Topic" -ResourceName $topic -Scope "Global/Project" -Status "Already Exists"
    } else {
        Write-Host "  Creating Pub/Sub topic '$topic'..." -ForegroundColor Cyan
        Invoke-Cli "gcloud pubsub topics create $topic" | Out-Null
        Add-SummaryRecord -ResourceType "Pub/Sub Topic" -ResourceName $topic -Scope "Global/Project" -Status "Created"
    }
}
Write-Host "  [OK] All $($pubsubTopics.Count) Pub/Sub topics ready." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 7. Cloud KMS Key Ring & HSM Asymmetric Signing Key
# ------------------------------------------------------------------------------
Write-Host "`n[7/9] Checking Cloud KMS key ring 'pramaan' and HSM key 'mandate-signer' in $Region..." -ForegroundColor Yellow

$krCheck = Invoke-Cli "gcloud kms keyrings describe pramaan --location=$Region --format=""value(name)""" -IgnoreError
if ($krCheck.Success -and $krCheck.Output) {
    Write-Host "  - Key Ring 'pramaan': Already exists in $Region" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "KMS Key Ring" -ResourceName "pramaan" -Scope $Region -Status "Already Exists"
} else {
    Write-Host "  Creating Cloud KMS key ring 'pramaan' in $Region..." -ForegroundColor Cyan
    Invoke-Cli "gcloud kms keyrings create pramaan --location=$Region" | Out-Null
    Add-SummaryRecord -ResourceType "KMS Key Ring" -ResourceName "pramaan" -Scope $Region -Status "Created"
}

$keyCheck = Invoke-Cli "gcloud kms keys describe mandate-signer --location=$Region --keyring=pramaan --format=""value(name)""" -IgnoreError
if ($keyCheck.Success -and $keyCheck.Output) {
    Write-Host "  - Asymmetric Signing Key 'mandate-signer': Already exists in key ring 'pramaan'" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "KMS Key (HSM)" -ResourceName "mandate-signer" -Scope "$Region/pramaan" -Status "Already Exists" -Notes "Alg: EC_SIGN_P256_SHA256, Protection: HSM"
} else {
    Write-Host "  Creating asymmetric signing key 'mandate-signer' (EC_SIGN_P256_SHA256, HSM) in $Region..." -ForegroundColor Cyan

    # Run key creation. If HSM fails or is unavailable, STOP immediately and NEVER fall back to software.
    $keyCreateCmd = "gcloud kms keys create mandate-signer --location=$Region --keyring=pramaan --purpose=asymmetric-signing --default-algorithm=ec-sign-p256-sha256 --protection-level=hsm"
    $keyCreateRes = Invoke-Cli $keyCreateCmd -IgnoreError

    if (-not $keyCreateRes.Success) {
        Write-Host "Error Output: $($keyCreateRes.Output)" -ForegroundColor Red
        throw "CRITICAL: Cloud KMS HSM key creation failed in $Region. HSM may not be available or permitted. Per security policy, we will NOT fall back to software keys."
    }
    Add-SummaryRecord -ResourceType "KMS Key (HSM)" -ResourceName "mandate-signer" -Scope "$Region/pramaan" -Status "Created" -Notes "Alg: EC_SIGN_P256_SHA256, Protection: HSM"
}
Write-Host "  [OK] Cloud KMS HSM signing key ready." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 8. Service Accounts & Least-Privilege IAM Roles
# ------------------------------------------------------------------------------
Write-Host "`n[8/9] Checking service accounts and assigning least-privilege IAM roles..." -ForegroundColor Yellow

$apiSaName = "pramaan-api"
$apiSaEmail = "${apiSaName}@${ExpectedProject}.iam.gserviceaccount.com"

$agentSaName = "pramaan-agent"
$agentSaEmail = "${agentSaName}@${ExpectedProject}.iam.gserviceaccount.com"

# --- 8a. Service Account: pramaan-api ---
$apiSaCheck = Invoke-Cli "gcloud iam service-accounts describe $apiSaEmail" -IgnoreError
if ($apiSaCheck.Success) {
    Write-Host "  - Service Account '$apiSaName': Already exists" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "Service Account" -ResourceName $apiSaName -Scope "IAM" -Status "Already Exists" -Notes $apiSaEmail
} else {
    Write-Host "  Creating service account '$apiSaName'..." -ForegroundColor Cyan
    Invoke-Cli "gcloud iam service-accounts create $apiSaName --display-name=""Pramaan Backend API Service Account"" --description=""Service account for Pramaan FastAPI Cloud Run service with narrow resource access""" | Out-Null
    Add-SummaryRecord -ResourceType "Service Account" -ResourceName $apiSaName -Scope "IAM" -Status "Created" -Notes $apiSaEmail
}

# --- 8b. Service Account: pramaan-agent ---
$agentSaCheck = Invoke-Cli "gcloud iam service-accounts describe $agentSaEmail" -IgnoreError
if ($agentSaCheck.Success) {
    Write-Host "  - Service Account '$agentSaName': Already exists" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "Service Account" -ResourceName $agentSaName -Scope "IAM" -Status "Already Exists" -Notes $agentSaEmail
} else {
    Write-Host "  Creating service account '$agentSaName'..." -ForegroundColor Cyan
    Invoke-Cli "gcloud iam service-accounts create $agentSaName --display-name=""Pramaan AI Agent Service Account"" --description=""Service account for Pramaan AI Agent (Vertex AI & Model Armor access only)""" | Out-Null
    Add-SummaryRecord -ResourceType "Service Account" -ResourceName $agentSaName -Scope "IAM" -Status "Created" -Notes $agentSaEmail
}

# --- 8c. IAM Bindings for pramaan-api ---
Write-Host "  Configuring least-privilege IAM bindings for '$apiSaName'..." -ForegroundColor Cyan

# 1. KMS Key Level: signer/verifier on ONLY the mandate-signer key
Write-Host "    -> Cloud KMS key binding: roles/cloudkms.signerVerifier on key 'mandate-signer'..." -ForegroundColor Gray
Invoke-Cli "gcloud kms keys add-iam-policy-binding mandate-signer --location=$Region --keyring=pramaan --member=""serviceAccount:$apiSaEmail"" --role=""roles/cloudkms.signerVerifier""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "KMS Key: mandate-signer" -Status "Bound" -Notes "roles/cloudkms.signerVerifier"

# 2. Firestore: Read/write Firestore
Write-Host "    -> Firestore binding: roles/datastore.user..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$apiSaEmail"" --role=""roles/datastore.user""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "Project: Firestore" -Status "Bound" -Notes "roles/datastore.user"

# 3. BigQuery: edit data in pramaan_ledger dataset via BigQuery DCL
Write-Host "    -> BigQuery dataset binding: roles/bigquery.dataEditor on 'pramaan_ledger'..." -ForegroundColor Gray
$dsJsonRaw = cmd /c "bq show --format=prettyjson ${ExpectedProject}:pramaan_ledger 2>nul"
$hasDatasetAccess = $false
if ($LASTEXITCODE -eq 0 -and $dsJsonRaw) {
    try {
        $dsObj = ($dsJsonRaw -join "`n") | ConvertFrom-Json
        $entry = $dsObj.access | Where-Object { $_.userByEmail -eq $apiSaEmail }
        if ($entry -and ($entry.role -eq "WRITER" -or $entry.role -eq "roles/bigquery.dataEditor")) {
            $hasDatasetAccess = $true
        }
    } catch {}
}

if ($hasDatasetAccess) {
    Write-Host "      - Already granted on dataset 'pramaan_ledger'" -ForegroundColor Gray
    Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "BigQuery Dataset: pramaan_ledger" -Status "Already Bound" -Notes "roles/bigquery.dataEditor (WRITER)"
} else {
    $grantFile = Join-Path $env:TEMP "bq_grant_$([System.Guid]::NewGuid().ToString('N')).sql"
    try {
        $sql = "GRANT ``roles/bigquery.dataEditor`` ON SCHEMA `${ExpectedProject}.pramaan_ledger` TO ""serviceAccount:$apiSaEmail"";"
        [System.IO.File]::WriteAllText($grantFile, $sql, [System.Text.Encoding]::ASCII)
        Invoke-Cli "bq query --nouse_legacy_sql --location=$Region < `"$grantFile`"" | Out-Null
        Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "BigQuery Dataset: pramaan_ledger" -Status "Bound" -Notes "roles/bigquery.dataEditor"
    } finally {
        if (Test-Path $grantFile) { Remove-Item -Path $grantFile -Force -ErrorAction SilentlyContinue }
    }
}

# 4. BigQuery: run BigQuery jobs (project-level role)
Write-Host "    -> BigQuery job user: roles/bigquery.jobUser..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$apiSaEmail"" --role=""roles/bigquery.jobUser""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "Project: BigQuery Jobs" -Status "Bound" -Notes "roles/bigquery.jobUser"

# 5. Pub/Sub: publish to each topic at topic-level
Write-Host "    -> Pub/Sub publisher bindings on all 7 topics (narrow topic level)..." -ForegroundColor Gray
foreach ($topic in $pubsubTopics) {
    Invoke-Cli "gcloud pubsub topics add-iam-policy-binding $topic --member=""serviceAccount:$apiSaEmail"" --role=""roles/pubsub.publisher""" | Out-Null
    Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "Pub/Sub Topic: $topic" -Status "Bound" -Notes "roles/pubsub.publisher"
}

# 6. Pub/Sub: subscribe to subscriptions
Write-Host "    -> Pub/Sub subscriber binding: roles/pubsub.subscriber..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$apiSaEmail"" --role=""roles/pubsub.subscriber""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "Project: Pub/Sub Subscriptions" -Status "Bound" -Notes "roles/pubsub.subscriber"

# 7. Secret Manager: read secrets
Write-Host "    -> Secret Manager binding: roles/secretmanager.secretAccessor..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$apiSaEmail"" --role=""roles/secretmanager.secretAccessor""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "Project: Secret Manager" -Status "Bound" -Notes "roles/secretmanager.secretAccessor"

# 8. Vertex AI: call Vertex AI / Gemini models
Write-Host "    -> Vertex AI binding: roles/aiplatform.user..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$apiSaEmail"" --role=""roles/aiplatform.user""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $apiSaName -Scope "Project: Vertex AI" -Status "Bound" -Notes "roles/aiplatform.user"

# --- 8d. IAM Bindings for pramaan-agent ---
Write-Host "  Configuring narrow IAM bindings for '$agentSaName'..." -ForegroundColor Cyan

# 1. Vertex AI: call Vertex AI / Gemini models
Write-Host "    -> Vertex AI binding: roles/aiplatform.user..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$agentSaEmail"" --role=""roles/aiplatform.user""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $agentSaName -Scope "Project: Vertex AI" -Status "Bound" -Notes "roles/aiplatform.user"

# 2. Model Armor: call Model Armor sanitization
Write-Host "    -> Model Armor binding: roles/modelarmor.user..." -ForegroundColor Gray
Invoke-Cli "gcloud projects add-iam-policy-binding $ExpectedProject --member=""serviceAccount:$agentSaEmail"" --role=""roles/modelarmor.user""" | Out-Null
Add-SummaryRecord -ResourceType "IAM Binding" -ResourceName $agentSaName -Scope "Project: Model Armor" -Status "Bound" -Notes "roles/modelarmor.user"

Write-Host "  [OK] Service accounts and IAM bindings configured." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 9. Summary Table
# ------------------------------------------------------------------------------
Write-Host "`n[9/9] Bootstrap summary:" -ForegroundColor Yellow
$Summary | Format-Table -Property ResourceType, ResourceName, Scope, Status, Notes -AutoSize

Write-Host "`n===========================================================" -ForegroundColor Green
Write-Host "  Pramaan Cloud Infrastructure Bootstrap Completed Successfully!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
