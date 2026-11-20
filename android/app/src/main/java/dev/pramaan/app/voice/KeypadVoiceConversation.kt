package dev.pramaan.app.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Dev stand-in for Gemini Live when the app has no Firebase config: you type
 * what you would have said. Same contract as the Live session: it hands six
 * digits to the view model once per conversation.
 */
class KeypadVoiceConversation : VoiceConversation {
    private var onDigits: ((String) -> Unit)? = null
    private val _listening = MutableStateFlow(false)
    val listening: StateFlow<Boolean> = _listening.asStateFlow()

    override suspend fun start(language: VoiceLanguage, payeeName: String, amountInWords: String, onDigits: (String) -> Unit) {
        this.onDigits = onDigits
        _listening.value = true
    }

    override suspend fun stop() {
        onDigits = null
        _listening.value = false
    }

    fun say(text: String) {
        val digits = text.filter { it in '0'..'9' }
        if (digits.length != 6) return
        val cb = onDigits ?: return
        onDigits = null // one call per conversation, like the Live session
        _listening.value = false
        cb(digits)
    }
}
