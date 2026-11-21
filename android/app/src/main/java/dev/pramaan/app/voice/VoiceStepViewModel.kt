package dev.pramaan.app.voice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** The live audio side, so the view model can be tested without Gemini. */
interface VoiceConversation {
    suspend fun start(language: VoiceLanguage, payeeName: String, amountInWords: String, onDigits: (String) -> Unit)
    suspend fun stop()
}

sealed interface VoiceUiState {
    data object Idle : VoiceUiState
    data object Starting : VoiceUiState

    /** The code is on screen and Gemini is listening. */
    data class CodeShown(val code: String, val expiresAt: String, val attemptsLeft: Int) : VoiceUiState {
        override fun toString() = "CodeShown(attemptsLeft=$attemptsLeft)" // never log the code
    }

    /** Digits heard; the approver checks them before anything is sent. */
    data class ReadBack(val code: String, val heard: String, val expiresAt: String, val attemptsLeft: Int) : VoiceUiState {
        override fun toString() = "ReadBack(attemptsLeft=$attemptsLeft)"
    }

    data object Submitting : VoiceUiState
    data class Retry(val code: String, val expiresAt: String, val attemptsLeft: Int) : VoiceUiState {
        override fun toString() = "Retry(attemptsLeft=$attemptsLeft)"
    }

    data object Expired : VoiceUiState
    data object Passed : VoiceUiState

    /** Three wrong tries (or too many codes): finance calls the approver back. */
    data object Fallback : VoiceUiState
    data class Error(val message: String) : VoiceUiState
}

/**
 * Tier 2 voice step. Shown only after the Tier 1 fingerprint signature has been
 * verified by the server; the server enforces that too.
 */
class VoiceStepViewModel(
    private val approvalId: String,
    private val payeeName: String,
    private val amountInWords: String,
    private val api: VoiceStepApi,
    private val conversation: VoiceConversation,
) : ViewModel() {

    private val _state = MutableStateFlow<VoiceUiState>(VoiceUiState.Idle)
    val state: StateFlow<VoiceUiState> = _state.asStateFlow()

    private var language: VoiceLanguage = VoiceLanguage.ENGLISH
    private var voiceId: String? = null

    /** Requires RECORD_AUDIO to have been granted by the screen. */
    fun start(chosen: VoiceLanguage) {
        language = chosen
        _state.value = VoiceUiState.Starting
        viewModelScope.launch {
            try {
                val s = api.start(approvalId, chosen)
                when (s.status) {
                    VoiceStepState.Status.FALLBACK_CALLBACK -> fallback()
                    else -> {
                        val code = requireNotNull(s.code) { "server sent no code" }
                        voiceId = s.voiceId
                        _state.value = VoiceUiState.CodeShown(code, s.expiresAt, s.attemptsRemaining)
                        listen()
                    }
                }
            } catch (p: VoiceStepProblem) {
                if (p.slug == "voice-finished") fallback() else _state.value = VoiceUiState.Error(p.message)
            } catch (e: Exception) {
                android.util.Log.e("PramaanVoice", "start failed", e)
                _state.value = VoiceUiState.Error(
                    "Could not start the spoken check. Check your connection. " +
                        "(${e.javaClass.simpleName}: ${e.message?.take(160)})",
                )
            }
        }
    }

    private suspend fun listen() {
        conversation.start(language, payeeName, amountInWords) { heard -> onHeard(heard) }
    }

    private fun onHeard(heard: String) {
        val s = _state.value
        _state.value = when (s) {
            is VoiceUiState.CodeShown -> VoiceUiState.ReadBack(s.code, heard, s.expiresAt, s.attemptsLeft)
            is VoiceUiState.Retry -> VoiceUiState.ReadBack(s.code, heard, s.expiresAt, s.attemptsLeft)
            else -> s // ignore late calls once we've moved on
        }
    }

    /** Approver confirms the read-back; only now do the digits go to the server. */
    fun confirmReadBack() {
        val s = _state.value as? VoiceUiState.ReadBack ?: return
        val id = voiceId ?: return
        _state.value = VoiceUiState.Submitting
        viewModelScope.launch {
            try {
                val r = api.complete(approvalId, id, s.heard)
                when (r.status) {
                    VoiceStepState.Status.PASSED -> _state.value = VoiceUiState.Passed
                    VoiceStepState.Status.RETRY -> _state.value = VoiceUiState.Retry(s.code, s.expiresAt, r.attemptsRemaining)
                    VoiceStepState.Status.EXPIRED -> expired()
                    VoiceStepState.Status.FALLBACK_CALLBACK -> fallback()
                    VoiceStepState.Status.AWAITING_CODE -> _state.value = VoiceUiState.CodeShown(s.code, s.expiresAt, r.attemptsRemaining)
                }
            } catch (p: VoiceStepProblem) {
                when (p.slug) {
                    "voice-finished" -> fallback()
                    "no-active-code" -> expired()
                    else -> _state.value = VoiceUiState.Error(p.message)
                }
            } catch (e: Exception) {
                _state.value = VoiceUiState.Error("Could not send the code. Check your connection.")
            }
        }
    }

    /** "That's not what I said": back to listening, no try used. */
    fun rejectReadBack() {
        val s = _state.value as? VoiceUiState.ReadBack ?: return
        relisten(VoiceUiState.CodeShown(s.code, s.expiresAt, s.attemptsLeft))
    }

    fun tryAgain() {
        val s = _state.value as? VoiceUiState.Retry ?: return
        relisten(VoiceUiState.CodeShown(s.code, s.expiresAt, s.attemptsLeft))
    }

    /** The model has already used its one function call, so start a fresh Live session. */
    private fun relisten(next: VoiceUiState.CodeShown) {
        _state.value = next
        viewModelScope.launch {
            try {
                conversation.stop()
                listen()
            } catch (e: Exception) {
                _state.value = VoiceUiState.Error("Could not restart listening. Check your connection.")
            }
        }
    }

    fun newCode() = start(language)

    fun finish() {
        viewModelScope.launch { conversation.stop() }
    }

    private suspend fun expired() {
        conversation.stop()
        _state.value = VoiceUiState.Expired
    }

    private suspend fun fallback() {
        conversation.stop()
        _state.value = VoiceUiState.Fallback
    }

    override fun onCleared() {
        // viewModelScope is already cancelled here; stop on a fresh scope.
        kotlinx.coroutines.MainScope().launch { conversation.stop() }
    }
}
