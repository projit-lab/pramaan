package dev.pramaan.app.voice

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat

// Placeholder tokens until Shoaib's Stitch design lands. Colours carry meaning only.
private val Held = Color(0xFFB26A00)
private val Released = Color(0xFF1E7A3C)
private val Blocked = Color(0xFFB3261E)

/**
 * Voice-step screens: language choice, code shown + listening, read-back, retry,
 * expired, passed and call-back fallback.
 */
@Composable
fun VoiceStepScreen(vm: VoiceStepViewModel, onDone: () -> Unit) {
    val state by vm.state.collectAsState()
    val context = LocalContext.current
    var pending by remember { mutableStateOf<VoiceLanguage?>(null) }
    var micDenied by remember { mutableStateOf(false) }
    val askMic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val lang = pending
        if (granted && lang != null) vm.start(lang) else micDenied = true
    }

    fun begin(lang: VoiceLanguage) {
        val has = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        if (has) vm.start(lang) else {
            pending = lang
            askMic.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    Column(
        Modifier.fillMaxWidth().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Spoken confirmation", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Your fingerprint approval is signed. This payment also needs you to speak a one-time code. " +
                "Nothing is recorded or stored.",
            style = MaterialTheme.typography.bodyMedium,
        )
        when (val s = state) {
            VoiceUiState.Idle -> LanguagePicker(micDenied, ::begin)
            VoiceUiState.Starting, VoiceUiState.Submitting -> Busy()
            is VoiceUiState.CodeShown -> {
                CodeCard(s.code)
                Listening()
                AttemptsLeft(s.attemptsLeft)
            }
            is VoiceUiState.ReadBack -> ReadBack(s.code, s.heard, onYes = vm::confirmReadBack, onNo = vm::rejectReadBack)
            is VoiceUiState.Retry -> {
                StatusLine("That code didn't match.", Held)
                AttemptsLeft(s.attemptsLeft)
                Button(onClick = vm::tryAgain, Modifier.fillMaxWidth()) { Text("Say the code again") }
            }
            VoiceUiState.Expired -> {
                StatusLine("The code expired after two minutes.", Held)
                Button(onClick = vm::newCode, Modifier.fillMaxWidth()) { Text("Get a new code") }
            }
            VoiceUiState.Passed -> {
                StatusLine("Spoken check passed.", Released)
                Text("Gemini will now ask you to say the payee and the amount. If they don't match, decline the payment.")
                Button(onClick = { vm.finish(); onDone() }, Modifier.fillMaxWidth()) { Text("Done") }
            }
            VoiceUiState.Fallback -> {
                StatusLine("Spoken check not completed.", Blocked)
                Text("The payment stays held. Your finance team will call you back on your number on record to confirm it.")
                Button(onClick = { vm.finish(); onDone() }, Modifier.fillMaxWidth()) { Text("OK") }
            }
            is VoiceUiState.Error -> {
                StatusLine(s.message, Blocked)
                OutlinedButton(onClick = vm::newCode, Modifier.fillMaxWidth()) { Text("Try again") }
            }
        }
    }
}

@Composable
private fun LanguagePicker(micDenied: Boolean, onPick: (VoiceLanguage) -> Unit) {
    Text("Choose the language you'll speak in", style = MaterialTheme.typography.titleMedium)
    VoiceLanguage.entries.forEach { lang ->
        OutlinedButton(onClick = { onPick(lang) }, Modifier.fillMaxWidth()) { Text(lang.displayName) }
    }
    if (micDenied) {
        StatusLine("Microphone permission is needed for the spoken check. Allow it in Settings, or ask finance for a call-back.", Blocked)
    }
}

@Composable
private fun CodeCard(code: String) {
    val spaced = code.chunked(3).joinToString("  ")
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Say this code", style = MaterialTheme.typography.labelLarge)
        Text(
            spaced,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 44.sp,
            modifier = Modifier.semantics { contentDescription = "Code " + code.toCharArray().joinToString(" ") },
        )
        Text("Valid for two minutes, once", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun Listening() {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        Text("Listening…", style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun ReadBack(code: String, heard: String, onYes: () -> Unit, onNo: () -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Column {
            Text("Your code", style = MaterialTheme.typography.labelLarge)
            Text(code.chunked(3).joinToString(" "), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 30.sp)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text("We heard", style = MaterialTheme.typography.labelLarge)
            Text(heard.chunked(3).joinToString(" "), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 30.sp)
        }
    }
    Text("Is what we heard the same as your code?")
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Button(onClick = onYes, Modifier.weight(1f)) { Text("Yes, send it") }
        OutlinedButton(onClick = onNo, Modifier.weight(1f)) { Text("No, say again") }
    }
}

@Composable
private fun AttemptsLeft(n: Int) {
    Text(if (n == 1) "1 try left" else "$n tries left", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun StatusLine(text: String, color: Color) {
    Text(text, color = color, style = MaterialTheme.typography.titleMedium)
}

@Composable
private fun Busy() {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) { CircularProgressIndicator() }
}
