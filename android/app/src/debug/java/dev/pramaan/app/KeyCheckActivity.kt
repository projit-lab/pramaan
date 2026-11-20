package dev.pramaan.app

import android.os.Bundle
import android.util.Base64
import android.util.Log
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.lifecycleScope
import dev.pramaan.crypto.AndroidKeyStoreSigner
import kotlinx.coroutines.launch
import java.security.KeyFactory
import java.security.SecureRandom
import java.security.Signature
import java.security.spec.X509EncodedKeySpec

class KeyCheckActivity : FragmentActivity() {

    private val signer by lazy {
        AndroidKeyStoreSigner(activityProvider = { this })
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (intent?.getBooleanExtra("auto_enrol", false) == true) {
            lifecycleScope.launch {
                try {
                    val challenge = ByteArray(32).also { SecureRandom().nextBytes(it) }
                    val result = signer.enrol(challenge)
                    val challengeB64 = Base64.encodeToString(challenge, Base64.NO_WRAP)
                    val chainB64List = result.certificateChain.map { Base64.encodeToString(it, Base64.NO_WRAP) }
                    val chainJson = chainB64List.joinToString(separator = ",", prefix = "[", postfix = "]") { "\"$it\"" }
                    val json = "{\"challenge_b64\":\"$challengeB64\",\"security_level\":\"${result.securityLevel.name}\",\"chain_b64\":$chainJson}"
                    try {
                        java.io.File(filesDir, "attestation_real_phone.json").writeText(json)
                    } catch (e: Exception) {
                        Log.e("KeyCheckExport", "Failed to write file", e)
                    }
                    Log.d("KeyCheckExport", json)
                } catch (e: Exception) {
                    Log.e("KeyCheckExport", "Auto-enrol failed", e)
                }
            }
        }

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    var statusText by remember { mutableStateOf("Ready") }
                    val scope = rememberCoroutineScope()

                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text(
                            text = "Pramaan Key Check",
                            style = MaterialTheme.typography.headlineMedium
                        )
                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                scope.launch {
                                    try {
                                        val challenge = ByteArray(32).also { SecureRandom().nextBytes(it) }
                                        statusText = "Enrolling..."
                                        val result = signer.enrol(challenge)
                                        val pubKeyB64 = signer.publicKey()?.let {
                                            Base64.encodeToString(it, Base64.NO_WRAP)
                                        } ?: "null"
                                        val logMsg = "Enrol success: chainLen=${result.certificateChain.size}, secLevel=${result.securityLevel}, pubKey=$pubKeyB64"
                                        Log.d("KeyCheck", logMsg)
                                        statusText = "Enrolled: ${result.securityLevel}\nChain: ${result.certificateChain.size}\nKey: ${pubKeyB64.take(16)}..."
                                    } catch (e: Exception) {
                                        Log.e("KeyCheck", "Enrol failed", e)
                                        statusText = "Enrol failed: ${e.message}"
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Enrol")
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                scope.launch {
                                    try {
                                        statusText = "Signing test data..."
                                        val testBytes = "pramaan-test".toByteArray(Charsets.UTF_8)
                                        val sigDer = signer.sign(testBytes)

                                        val pubKeyDer = signer.publicKey()
                                        if (pubKeyDer == null) {
                                            statusText = "INVALID: Public key is null"
                                            return@launch
                                        }

                                        val kf = KeyFactory.getInstance("EC")
                                        val pubKey = kf.generatePublic(X509EncodedKeySpec(pubKeyDer))
                                        val verifier = Signature.getInstance("SHA256withECDSA")
                                        verifier.initVerify(pubKey)
                                        verifier.update(testBytes)
                                        val valid = verifier.verify(sigDer)

                                        val resultString = if (valid) "VALID" else "INVALID"
                                        Log.d("KeyCheck", "Signature verification: $resultString")
                                        statusText = resultString
                                    } catch (e: Exception) {
                                        Log.e("KeyCheck", "Sign failed", e)
                                        statusText = "Sign failed: ${e.message}"
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Sign test")
                        }

                        Spacer(modifier = Modifier.height(24.dp))
                        Text(
                            text = statusText,
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
            }
        }
    }
}
