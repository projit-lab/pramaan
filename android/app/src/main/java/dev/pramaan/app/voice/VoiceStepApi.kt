package dev.pramaan.app.voice

/**
 * POST /v1/approvals/{id}/voice (contracts/voice.openapi.yaml).
 *
 * Implement this with the app's generated API client, which already adds the
 * Firebase ID token and the App Check token (X-Firebase-AppCheck).
 */
interface VoiceStepApi {
    suspend fun start(approvalId: String, language: VoiceLanguage): VoiceStepState
    suspend fun complete(approvalId: String, voiceId: String, digits: String): VoiceStepState
}

/** Server state of the voice step: VoiceStepState in contracts/openapi.yaml. */
data class VoiceStepState(
    val approvalId: String,
    val voiceId: String,
    val status: Status,
    val matched: Boolean,
    val language: VoiceLanguage,
    val attemptsRemaining: Int,
    val expiresAt: String,
    /** Only present in the answer to `start`. Shown on screen, never logged. */
    val code: String? = null,
) {
    enum class Status(val wire: String) {
        AWAITING_CODE("awaiting_code"),
        PASSED("passed"),
        RETRY("retry"),
        EXPIRED("expired"),
        FALLBACK_CALLBACK("fallback_callback");

        companion object {
            fun fromWire(s: String) = entries.first { it.wire == s }
        }
    }

    override fun toString() =
        "VoiceStepState(approvalId=$approvalId, voiceId=$voiceId, status=$status, attemptsRemaining=$attemptsRemaining)"
}

/** Problem-details error from the API (RFC 9457). */
class VoiceStepProblem(val status: Int, val slug: String, override val message: String) : Exception(message)

enum class VoiceLanguage(val wire: String, val bcp47: String, val displayName: String) {
    TAMIL("ta", "ta-IN", "தமிழ்"),
    HINDI("hi", "hi-IN", "हिन्दी"),
    ENGLISH("en", "en-IN", "English"),
}
