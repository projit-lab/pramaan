package dev.pramaan.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.appcheck.FirebaseAppCheck
import com.google.firebase.appcheck.debug.DebugAppCheckProviderFactory
import dev.pramaan.app.voice.GeminiLiveVoiceSession
import dev.pramaan.app.voice.HttpVoiceStepApi
import dev.pramaan.app.voice.KeypadVoiceConversation
import dev.pramaan.app.voice.VoiceConversation
import dev.pramaan.app.voice.VoiceStepScreen
import dev.pramaan.app.voice.VoiceStepViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.net.URL

/** What the approver screen hands over after a Tier 2 signature verifies. */
data class VoiceHandoff(
    val approvalId: String,
    val approverEmail: String,
    val payeeName: String,
    val amountPaise: String,
)

/**
 * The Tier 2 spoken check. Opened by the approver screen when the server answers a
 * verified signature with `next: "voice"`; the mandate is issued only after the
 * spoken code matches. Launched on its own it runs the seeded demo approval.
 * With Firebase config (google-services.json at build time) Gemini Live runs the
 * conversation; without it you type the digits you would have spoken.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val hasFirebase = initFirebase()
        val handoff = intent?.getStringExtra(EXTRA_APPROVAL_ID)?.let { id ->
            VoiceHandoff(
                approvalId = id,
                approverEmail = intent.getStringExtra(EXTRA_APPROVER) ?: "cfo@acme.example",
                payeeName = intent.getStringExtra(EXTRA_PAYEE) ?: "the payee",
                amountPaise = intent.getStringExtra(EXTRA_AMOUNT_PAISE) ?: "0",
            )
        }
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    Box(Modifier.safeDrawingPadding()) {
                        if (handoff != null) {
                            VoiceHarness(
                                approvalId = handoff.approvalId,
                                hasFirebase = hasFirebase,
                                payeeName = handoff.payeeName,
                                amountInWords = amountInWords(handoff.amountPaise),
                                headers = mapOf("X-Dev-User" to handoff.approverEmail),
                                onDone = { finish() },
                            )
                        } else {
                            Harness(hasFirebase)
                        }
                    }
                }
            }
        }
    }

    private fun initFirebase(): Boolean {
        val ok = when {
            FirebaseApp.getApps(this).isNotEmpty() -> true
            FirebaseApp.initializeApp(this) != null -> true
            BuildConfig.FIREBASE_APP_ID.isBlank() -> false
            else -> runCatching {
                val options = FirebaseOptions.Builder()
                    .setApplicationId(BuildConfig.FIREBASE_APP_ID)
                    .setApiKey(BuildConfig.FIREBASE_API_KEY)
                    .setProjectId(BuildConfig.FIREBASE_PROJECT_ID)
                    .build()
                FirebaseApp.initializeApp(this, options)
            }.isSuccess
        }
        if (ok) {
            // Firebase AI Logic enforces App Check. A sideloaded demo build uses the debug
            // provider: it logs a token (tag DebugAppCheckProvider) that is registered once
            // in the Firebase console. A store build would use Play Integrity instead.
            FirebaseAppCheck.getInstance()
                .installAppCheckProviderFactory(DebugAppCheckProviderFactory.getInstance())
        }
        return ok
    }

    companion object {
        const val EXTRA_APPROVAL_ID = "approval_id"
        const val EXTRA_APPROVER = "approver_email"
        const val EXTRA_PAYEE = "payee_name"
        const val EXTRA_AMOUNT_PAISE = "amount_paise"
    }
}

/** "thirty lakh rupees" style wording, in digits, for the spoken prompt. */
fun amountInWords(paise: String): String {
    val rupees = (paise.toLongOrNull() ?: 0L) / 100
    fun trim(x: Double) = if (x % 1.0 == 0.0) x.toLong().toString() else "%.2f".format(x).trimEnd('0').trimEnd('.')
    return when {
        rupees >= 10_000_000 -> "${trim(rupees / 10_000_000.0)} crore rupees"
        rupees >= 100_000 -> "${trim(rupees / 100_000.0)} lakh rupees"
        else -> "$rupees rupees"
    }
}

@Composable
private fun Harness(hasFirebase: Boolean) {
    var approvalId by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var round by remember { mutableStateOf(0) }

    LaunchedEffect(round) {
        approvalId = null
        error = null
        runCatching { fetchSeededApproval() }
            .onSuccess { approvalId = it }
            .onFailure { error = "Can't reach the dev server at ${BuildConfig.API_BASE}. Start it with DEMO_MODE=true." }
    }

    val id = approvalId
    when {
        error != null -> Column(Modifier.padding(24.dp)) {
            Text(error!!)
            Button(onClick = { round++ }) { Text("Retry") }
        }
        id == null -> Text("Loading approval…", Modifier.padding(24.dp))
        else -> VoiceHarness(
            approvalId = id,
            hasFirebase = hasFirebase,
            payeeName = "Sri Lakshmi Castings",
            amountInWords = "thirty lakh rupees",
            headers = mapOf("X-Demo-Uid" to BuildConfig.DEMO_UID),
            onDone = { round++ },
        )
    }
}

@Composable
private fun VoiceHarness(
    approvalId: String,
    hasFirebase: Boolean,
    payeeName: String,
    amountInWords: String,
    headers: Map<String, String>,
    onDone: () -> Unit,
) {
    val keypad = remember { KeypadVoiceConversation() }
    val conversation: VoiceConversation = remember { if (hasFirebase) GeminiLiveVoiceSession() else keypad }
    val api = remember {
        HttpVoiceStepApi(BuildConfig.API_BASE) { headers }
    }
    val vm = viewModel(key = approvalId) {
        VoiceStepViewModel(
            approvalId = approvalId,
            payeeName = payeeName,
            amountInWords = amountInWords,
            api = api,
            conversation = conversation,
        )
    }
    Column {
        VoiceStepScreen(vm, onDone)
        if (!hasFirebase) {
            val listening by keypad.listening.collectAsState()
            if (listening) KeypadInput(keypad::say)
        }
    }
}

@Composable
private fun KeypadInput(onSay: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    Column(Modifier.padding(horizontal = 24.dp)) {
        Text("Dev mode (no Firebase config): type what you'd say", style = MaterialTheme.typography.labelMedium)
        OutlinedTextField(
            value = text,
            onValueChange = { text = it.filter(Char::isDigit).take(6) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = { onSay(text); text = "" }, enabled = text.length == 6) { Text("Say it") }
    }
}

private suspend fun fetchSeededApproval(): String = withContext(Dispatchers.IO) {
    val text = URL("${BuildConfig.API_BASE}/_demo/voice/approvals").readText()
    Json.parseToJsonElement(text).jsonObject["tier2"]!!.jsonPrimitive.content
}
