# Demo: three routine Tier 1 payments land in the batch lane, the window closes,
# and the batch goes to the approver whose phone is on stage (ENV=local API only).
#   .\services\api\scripts\demo_batch.ps1 -Api http://192.168.10.190:8765
param(
    [string]$Api = "http://localhost:8765",
    [string]$Approver = "cfo@acme.example"
)
$v1 = "$Api/v1"
$clerk = @{ "X-Dev-User" = "clerk" }
$amounts = @("60000000", "70000000", "80000000")   # Rs 6, 7 and 8 lakh: Tier 1
$n = 0
foreach ($a in $amounts) {
    $n++
    $body = @{
        payee_vendor_id     = "vd_sri_lakshmi"
        amount_paise        = $a
        purpose             = "INV-BATCH-$n"
        instruction_channel = "portal"
        entry_route         = "erp"
        initiator           = @{ type = "human"; id = "clerk@acme.example" }
    } | ConvertTo-Json -Compress
    $r = Invoke-RestMethod -Method Post -Uri "$v1/intents" -Headers $clerk -ContentType "application/json" -Body $body
    Write-Host "intent $($r.intent_id)  status=$($r.status)  tier=$($r.tier)"
}
$at = (Get-Date).ToUniversalTime().AddDays(1).ToString("yyyy-MM-ddTHH:mm:ssZ")
$closed = Invoke-RestMethod -Method Post -Uri "$v1/_local/jobs/close-batches" -Headers $clerk -ContentType "application/json" -Body (@{ at = $at } | ConvertTo-Json)
foreach ($b in $closed.batches) {
    Invoke-RestMethod -Method Post -Uri "$v1/_local/batches/$($b.batch_id)/assign" -Headers $clerk -ContentType "application/json" -Body (@{ approver_email = $Approver } | ConvertTo-Json) | Out-Null
    Write-Host "batch $($b.batch_id): $($b.lines) payments, assigned to $Approver"
}
Write-Host "On the phone: Load batch -> Approve batch (one fingerprint)."
