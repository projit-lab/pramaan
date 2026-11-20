package dev.pramaan.app.voice

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.net.HttpURLConnection
import java.net.URL

/**
 * Small HTTP client for POST /v1/approvals/{id}/voice.
 *
 * In the real repo, replace this with the generated API client, which sends the
 * Firebase ID token and the App Check token. `authHeaders` stands in for that;
 * against the API in DEMO_MODE it sends X-Demo-Uid.
 */
class HttpVoiceStepApi(
    private val baseUrl: String,
    private val authHeaders: suspend () -> Map<String, String>,
) : VoiceStepApi {

    override suspend fun start(approvalId: String, language: VoiceLanguage): VoiceStepState =
        post(approvalId, buildJsonObject {
            put("action", "start")
            put("language", language.wire)
        })

    override suspend fun complete(approvalId: String, voiceId: String, digits: String): VoiceStepState =
        post(approvalId, buildJsonObject {
            put("action", "complete")
            put("voice_id", voiceId)
            put("digits", digits)
        })

    private suspend fun post(approvalId: String, body: JsonObject): VoiceStepState {
        val headers = authHeaders()
        return withContext(Dispatchers.IO) {
            val conn = URL("$baseUrl/v1/approvals/$approvalId/voice").openConnection() as HttpURLConnection
            try {
                conn.requestMethod = "POST"
                conn.connectTimeout = 10_000
                conn.readTimeout = 10_000
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                headers.forEach { (k, v) -> conn.setRequestProperty(k, v) }
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
                val code = conn.responseCode
                val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()?.use { it.readText() }.orEmpty()
                if (code !in 200..299) throw problem(code, text)
                parseState(text)
            } finally {
                conn.disconnect()
            }
        }
    }

    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        fun parseState(text: String): VoiceStepState {
            val o = json.parseToJsonElement(text).jsonObject
            fun s(k: String) = o[k]?.jsonPrimitive?.content
            return VoiceStepState(
                approvalId = s("approval_id")!!,
                voiceId = s("voice_id")!!,
                status = VoiceStepState.Status.fromWire(s("status")!!),
                matched = s("matched")!!.toBooleanStrict(),
                language = VoiceLanguage.entries.firstOrNull { it.wire == s("language") } ?: VoiceLanguage.ENGLISH,
                attemptsRemaining = s("attempts_remaining")!!.toInt(),
                expiresAt = s("expires_at")!!,
                code = s("code"),
            )
        }

        fun problem(status: Int, text: String): VoiceStepProblem {
            val o = runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull()
            val type = o?.get("type")?.jsonPrimitive?.content.orEmpty()
            val detail = o?.get("detail")?.jsonPrimitive?.content
                ?: o?.get("title")?.jsonPrimitive?.content
                ?: "Request failed ($status)"
            return VoiceStepProblem(status, type.substringAfterLast('/'), detail)
        }
    }
}
