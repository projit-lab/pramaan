package dev.pramaan.app

import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.util.Log
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.fragment.app.FragmentActivity
import dev.pramaan.crypto.AndroidKeyStoreSigner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class ApproverCheckActivity : FragmentActivity() {

    private val signer by lazy {
        AndroidKeyStoreSigner(activityProvider = { this })
    }

    private val apiBase: String
        get() = BuildConfig.API_BASE.trimEnd('/')

    private val approverEmail = "cfo@acme.example"

    companion object {
        private const val TAG = "ApproverCheck"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    var statusMessage by remember { mutableStateOf("Ready. API: $apiBase") }
                    var selectedApprovalId by remember { mutableStateOf("") }
                    var responseLog by remember { mutableStateOf("") }
                    var pendingCount by remember { mutableStateOf(0) }
                    val scope = rememberCoroutineScope()
                    val scrollState = rememberScrollState()

                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                            .verticalScroll(scrollState),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "Pramaan Approver Check",
                            style = MaterialTheme.typography.headlineMedium
                        )
                        Text(
                            text = "Approver: $approverEmail\nAPI Base: $apiBase",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.secondaryContainer
                            ),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(
                                    text = "Status: $statusMessage",
                                    style = MaterialTheme.typography.bodyMedium
                                )
                                if (selectedApprovalId.isNotEmpty()) {
                                    Text(
                                        text = "Target Approval: $selectedApprovalId",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }
                        }

                        // Button 1: Enrol with server
                        Button(
                            onClick = {
                                scope.launch {
                                    statusMessage = "Enrolling with server..."
                                    responseLog = "Requesting enrolment challenge...\n"
                                    try {
                                        // 1. Request challenge
                                        val (chCode, chBody) = httpPost(
                                            urlStr = "$apiBase/v1/devices/enrol/challenge",
                                            userHeader = approverEmail,
                                            jsonBody = "{}"
                                        )
                                        responseLog += "Challenge HTTP $chCode:\n$chBody\n\n"
                                        if (chCode !in 200..299) {
                                            statusMessage = "Failed challenge: HTTP $chCode"
                                            return@launch
                                        }

                                        val chJson = JSONObject(chBody)
                                        val challengeB64 = chJson.optString("nonce").ifEmpty {
                                            chJson.getString("challenge_b64")
                                        }
                                        val challengeBytes = Base64.decode(challengeB64, Base64.NO_WRAP)

                                        // 2. Enrol key in hardware KeyStore
                                        responseLog += "Creating hardware key in KeyStore...\n"
                                        val enrolResult = signer.enrol(challengeBytes)
                                        responseLog += "Key generated: ${enrolResult.securityLevel}, chainLen=${enrolResult.certificateChain.size}\n\n"

                                        // 3. Post attestation chain to server
                                        val chainArray = JSONArray()
                                        for (certBytes in enrolResult.certificateChain) {
                                            chainArray.put(Base64.encodeToString(certBytes, Base64.NO_WRAP))
                                        }

                                        val enrolReq = JSONObject().apply {
                                            put("chain_b64", chainArray)
                                            put("nonce", challengeB64)
                                            put("phone_model", "${Build.MANUFACTURER} ${Build.MODEL}")
                                        }

                                        val (enrolCode, enrolBody) = httpPost(
                                            urlStr = "$apiBase/v1/devices/enrol",
                                            userHeader = approverEmail,
                                            jsonBody = enrolReq.toString()
                                        )
                                        responseLog += "Enrol HTTP $enrolCode:\n$enrolBody\n"
                                        if (enrolCode in 200..299) {
                                            val respJson = JSONObject(enrolBody)
                                            val devId = respJson.optString("device_id")
                                            val secLevel = respJson.optString("key_security_level")
                                            statusMessage = "Enrolled successfully! Device: $devId ($secLevel)"
                                        } else {
                                            statusMessage = "Enrol failed: HTTP $enrolCode"
                                        }
                                    } catch (e: Exception) {
                                        Log.e(TAG, "Enrol error", e)
                                        statusMessage = "Enrol error: ${e.message}"
                                        responseLog += "Exception: ${e.stackTraceToString()}\n"
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Enrol with server")
                        }

                        // Button 2: Load pending
                        Button(
                            onClick = {
                                scope.launch {
                                    statusMessage = "Loading pending approvals..."
                                    responseLog = "Fetching pending approvals...\n"
                                    try {
                                        val (code, body) = httpGet(
                                            urlStr = "$apiBase/v1/approvals?status=pending",
                                            userHeader = approverEmail
                                        )
                                        responseLog += "Pending approvals HTTP $code:\n$body\n"
                                        if (code in 200..299) {
                                            val json = JSONObject(body)
                                            val list = json.optJSONArray("approvals") ?: JSONArray()
                                            pendingCount = list.length()
                                            if (list.length() > 0) {
                                                val first = list.getJSONObject(0)
                                                selectedApprovalId = first.getString("approval_id")
                                                val amount = first.optString("amount_paise")
                                                val payee = first.optString("payee_name_at_bank")
                                                val tier = first.optInt("tier")
                                                statusMessage = "Found ${list.length()} pending. Selected: $selectedApprovalId (Tier $tier, Rs ${amount}p to $payee)"
                                            } else {
                                                selectedApprovalId = ""
                                                statusMessage = "No pending approvals found for $approverEmail."
                                            }
                                        } else {
                                            statusMessage = "Load pending failed: HTTP $code"
                                        }
                                    } catch (e: Exception) {
                                        Log.e(TAG, "Load pending error", e)
                                        statusMessage = "Load error: ${e.message}"
                                        responseLog += "Exception: ${e.stackTraceToString()}\n"
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Load pending (${pendingCount})")
                        }

                        OutlinedTextField(
                            value = selectedApprovalId,
                            onValueChange = { selectedApprovalId = it },
                            label = { Text("Approval ID to Decide") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )

                        Row(modifier = Modifier.fillMaxWidth()) {
                            // Button 3: Approve
                            Button(
                                onClick = {
                                    scope.launch {
                                        if (selectedApprovalId.isBlank()) {
                                            statusMessage = "Please load or enter an Approval ID first"
                                            return@launch
                                        }
                                        statusMessage = "Fetching approval $selectedApprovalId..."
                                        responseLog = "GET /v1/approvals/$selectedApprovalId...\n"
                                        try {
                                            // 1. GET approval detail
                                            val (code, body) = httpGet(
                                                urlStr = "$apiBase/v1/approvals/$selectedApprovalId",
                                                userHeader = approverEmail
                                            )
                                            responseLog += "HTTP $code:\n$body\n\n"
                                            if (code !in 200..299) {
                                                statusMessage = "Failed fetching approval: HTTP $code"
                                                return@launch
                                            }

                                            val apprJson = JSONObject(body)
                                            val canonicalB64 = apprJson.getString("canonical_b64")
                                            val canonicalBytes = Base64.decode(canonicalB64, Base64.NO_WRAP)

                                            // 2. Sign canonical bytes with biometric prompt
                                            statusMessage = "Please confirm with fingerprint..."
                                            responseLog += "Prompting for biometric signature over canonical bytes...\n"
                                            val sigDer = signer.sign(canonicalBytes)
                                            val sigB64 = Base64.encodeToString(sigDer, Base64.NO_WRAP)
                                            responseLog += "Signature generated (${sigDer.size} bytes DER)\n\n"

                                            // 3. POST decision
                                            statusMessage = "Sending approval decision to server..."
                                            val decReq = JSONObject().apply {
                                                put("decision", "approve")
                                                put("signature", sigB64)
                                            }
                                            val (postCode, postBody) = httpPost(
                                                urlStr = "$apiBase/v1/approvals/$selectedApprovalId/decision",
                                                userHeader = approverEmail,
                                                jsonBody = decReq.toString()
                                            )
                                            responseLog += "POST decision HTTP $postCode:\n$postBody\n"
                                            if (postCode in 200..299) {
                                                val decJson = JSONObject(postBody)
                                                val mandateId = decJson.optString("mandate_id")
                                                statusMessage = "APPROVED! Mandate: $mandateId (Verified: true)"
                                            } else {
                                                statusMessage = "Decision failed: HTTP $postCode"
                                            }
                                        } catch (e: Exception) {
                                            Log.e(TAG, "Approve error", e)
                                            statusMessage = "Approve error: ${e.message}"
                                            responseLog += "Exception: ${e.stackTraceToString()}\n"
                                        }
                                    }
                                },
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("Approve")
                            }

                            Spacer(modifier = Modifier.width(8.dp))

                            // Button 4: Decline
                            Button(
                                onClick = {
                                    scope.launch {
                                        if (selectedApprovalId.isBlank()) {
                                            statusMessage = "Please load or enter an Approval ID first"
                                            return@launch
                                        }
                                        statusMessage = "Fetching approval $selectedApprovalId..."
                                        responseLog = "GET /v1/approvals/$selectedApprovalId...\n"
                                        try {
                                            val (code, body) = httpGet(
                                                urlStr = "$apiBase/v1/approvals/$selectedApprovalId",
                                                userHeader = approverEmail
                                            )
                                            responseLog += "HTTP $code:\n$body\n\n"
                                            if (code !in 200..299) {
                                                statusMessage = "Failed fetching approval: HTTP $code"
                                                return@launch
                                            }

                                            val apprJson = JSONObject(body)
                                            val canonicalB64 = apprJson.getString("canonical_b64")
                                            val canonicalBytes = Base64.decode(canonicalB64, Base64.NO_WRAP)

                                            statusMessage = "Please confirm decline with fingerprint..."
                                            val sigDer = signer.sign(canonicalBytes)
                                            val sigB64 = Base64.encodeToString(sigDer, Base64.NO_WRAP)

                                            val decReq = JSONObject().apply {
                                                put("decision", "decline")
                                                put("signature", sigB64)
                                            }
                                            val (postCode, postBody) = httpPost(
                                                urlStr = "$apiBase/v1/approvals/$selectedApprovalId/decision",
                                                userHeader = approverEmail,
                                                jsonBody = decReq.toString()
                                            )
                                            responseLog += "POST decision HTTP $postCode:\n$postBody\n"
                                            if (postCode in 200..299) {
                                                statusMessage = "DECLINED successfully."
                                            } else {
                                                statusMessage = "Decline failed: HTTP $postCode"
                                            }
                                        } catch (e: Exception) {
                                            Log.e(TAG, "Decline error", e)
                                            statusMessage = "Decline error: ${e.message}"
                                            responseLog += "Exception: ${e.stackTraceToString()}\n"
                                        }
                                    }
                                },
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("Decline")
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Text("Server Response Log:", style = MaterialTheme.typography.titleSmall)
                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.surfaceVariant
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(220.dp)
                        ) {
                            Text(
                                text = responseLog.ifEmpty { "No responses yet." },
                                modifier = Modifier
                                    .fillMaxSize()
                                    .padding(8.dp)
                                    .verticalScroll(rememberScrollState()),
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                }
            }
        }
    }

    private suspend fun httpGet(urlStr: String, userHeader: String): Pair<Int, String> =
        withContext(Dispatchers.IO) {
            val url = URL(urlStr)
            val conn = url.openConnection() as HttpURLConnection
            try {
                conn.requestMethod = "GET"
                conn.setRequestProperty("X-Dev-User", userHeader)
                conn.setRequestProperty("Accept", "application/json")
                conn.connectTimeout = 10000
                conn.readTimeout = 10000
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream ?: conn.inputStream
                val body = stream.bufferedReader().use { it.readText() }
                Pair(code, body)
            } finally {
                conn.disconnect()
            }
        }

    private suspend fun httpPost(urlStr: String, userHeader: String, jsonBody: String): Pair<Int, String> =
        withContext(Dispatchers.IO) {
            val url = URL(urlStr)
            val conn = url.openConnection() as HttpURLConnection
            try {
                conn.requestMethod = "POST"
                conn.setRequestProperty("X-Dev-User", userHeader)
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                conn.setRequestProperty("Accept", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 10000
                conn.readTimeout = 10000
                conn.outputStream.use { os ->
                    os.write(jsonBody.toByteArray(Charsets.UTF_8))
                }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream ?: conn.inputStream
                val body = stream.bufferedReader().use { it.readText() }
                Pair(code, body)
            } finally {
                conn.disconnect()
            }
        }
}
