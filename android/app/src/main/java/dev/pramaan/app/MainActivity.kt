package dev.pramaan.app

import android.os.Bundle
import androidx.fragment.app.FragmentActivity
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
import dev.pramaan.app.theme.PramaanTheme
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

/**
 * M4 dev harness: runs the voice step against services/api/dev_main.py for the
 * seeded Tier 2 approval. With a google-services.json the real Gemini Live
 * session is used; without one you type the digits you would have spoken.
 */
class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val hasFirebase = FirebaseApp.initializeApp(this) != null || FirebaseApp.getApps(this).isNotEmpty()
        setContent {
            PramaanTheme {
                Surface(Modifier.fillMaxSize()) {
                    Box(Modifier.safeDrawingPadding()) { Harness(hasFirebase) }
                }
            }
        }
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
        else -> VoiceHarness(id, hasFirebase, onDone = { round++ })
    }
}

@Composable
private fun VoiceHarness(approvalId: String, hasFirebase: Boolean, onDone: () -> Unit) {
    val keypad = remember { KeypadVoiceConversation() }
    val conversation: VoiceConversation = remember { if (hasFirebase) GeminiLiveVoiceSession() else keypad }
    val api = remember {
        HttpVoiceStepApi(BuildConfig.API_BASE) { mapOf("X-Demo-Uid" to BuildConfig.DEMO_UID) }
    }
    val vm = viewModel(key = approvalId) {
        VoiceStepViewModel(
            approvalId = approvalId,
            payeeName = "Sri Lakshmi Castings",
            amountInWords = "thirty lakh rupees",
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
