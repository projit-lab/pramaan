package dev.pramaan.app.voice

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HttpAndKeypadTest {

    @Test
    fun parsesStartResponse() {
        val s = HttpVoiceStepApi.parseState(
            """{"approval_id":"ap_1","voice_id":"vs_1","status":"awaiting_code","matched":false,"language":"ta",
               "attempts_remaining":3,"expires_at":"2026-11-21T11:44:07+05:30","code":"482913"}"""
        )
        assertEquals(VoiceStepState.Status.AWAITING_CODE, s.status)
        assertEquals(false, s.matched)
        assertEquals(VoiceLanguage.TAMIL, s.language)
        assertEquals(3, s.attemptsRemaining)
        assertEquals("482913", s.code)
    }

    @Test
    fun parsesCompleteResponseWithoutCode() {
        val s = HttpVoiceStepApi.parseState(
            """{"approval_id":"ap_1","voice_id":"vs_1","status":"fallback_callback","matched":false,"language":"hi",
               "attempts_remaining":0,"expires_at":"2026-11-21T11:44:07+05:30"}"""
        )
        assertEquals(VoiceStepState.Status.FALLBACK_CALLBACK, s.status)
        assertEquals(0, s.attemptsRemaining)
        assertNull(s.code)
    }

    @Test
    fun parsesPassedResponse() {
        val s = HttpVoiceStepApi.parseState(
            """{"approval_id":"ap_1","voice_id":"vs_1","status":"passed","matched":true,"language":"en",
               "attempts_remaining":2,"expires_at":"2026-11-21T11:44:07+05:30"}"""
        )
        assertEquals(true, s.matched)
        assertEquals(2, s.attemptsRemaining)
    }

    @Test
    fun parsesProblemDetails() {
        val p = HttpVoiceStepApi.problem(
            409,
            """{"type":"https://pramaan.example/problems/tier1-not-verified","title":"Tier 1 signature required first","status":409,"detail":"Sign first."}""",
        )
        assertEquals("tier1-not-verified", p.slug)
        assertEquals("Sign first.", p.message)
    }

    @Test
    fun problemWithNonJsonBodyStillWorks() {
        val p = HttpVoiceStepApi.problem(502, "Bad gateway")
        assertEquals(502, p.status)
        assertEquals("Request failed (502)", p.message)
    }

    @Test
    fun keypadHandsOverSixDigitsOncePerConversation() = runTest {
        val k = KeypadVoiceConversation()
        val got = mutableListOf<String>()
        k.start(VoiceLanguage.ENGLISH, "payee", "amount") { got += it }
        k.say("12345") // too short: ignored
        k.say("482 913")
        k.say("111111") // second call in the same conversation: ignored
        assertEquals(listOf("482913"), got)
        assertEquals(false, k.listening.value)
    }
}
