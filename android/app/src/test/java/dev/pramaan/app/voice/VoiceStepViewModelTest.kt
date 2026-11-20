package dev.pramaan.app.voice

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class VoiceStepViewModelTest {

    private class FakeApi : VoiceStepApi {
        val completes = mutableListOf<String>()
        var startStatus = VoiceStepState.Status.AWAITING_CODE
        var startProblem: VoiceStepProblem? = null
        val completeQueue = ArrayDeque<VoiceStepState.Status>()
        var completeProblem: VoiceStepProblem? = null
        var attemptsLeft = 3
        var starts = 0

        private fun state(status: VoiceStepState.Status, code: String? = null) =
            VoiceStepState(
                "ap_1", "vs_1", status, status == VoiceStepState.Status.PASSED, VoiceLanguage.TAMIL,
                attemptsLeft, "2026-11-21T11:44:07+05:30", code,
            )

        override suspend fun start(approvalId: String, language: VoiceLanguage): VoiceStepState {
            starts++
            startProblem?.let { throw it }
            return state(startStatus, if (startStatus == VoiceStepState.Status.AWAITING_CODE) "482913" else null)
        }

        override suspend fun complete(approvalId: String, voiceId: String, digits: String): VoiceStepState {
            completes += digits
            completeProblem?.let { throw it }
            val s = completeQueue.removeFirst()
            if (s == VoiceStepState.Status.RETRY) attemptsLeft--
            if (s == VoiceStepState.Status.FALLBACK_CALLBACK) attemptsLeft = 0
            return state(s)
        }
    }

    private class FakeConversation : VoiceConversation {
        var starts = 0
        var stops = 0
        var onDigits: ((String) -> Unit)? = null
        var language: VoiceLanguage? = null

        override suspend fun start(language: VoiceLanguage, payeeName: String, amountInWords: String, onDigits: (String) -> Unit) {
            starts++
            this.language = language
            this.onDigits = onDigits
        }

        override suspend fun stop() {
            stops++
            onDigits = null
        }

        fun hear(d: String) = onDigits!!.invoke(d)
    }

    private lateinit var api: FakeApi
    private lateinit var conv: FakeConversation
    private lateinit var vm: VoiceStepViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        api = FakeApi()
        conv = FakeConversation()
        vm = VoiceStepViewModel("ap_1", "Sri Lakshmi Castings", "thirty lakh rupees", api, conv)
    }

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun startShowsCodeAndListensInChosenLanguage() {
        vm.start(VoiceLanguage.TAMIL)
        val s = vm.state.value as VoiceUiState.CodeShown
        assertEquals("482913", s.code)
        assertEquals(3, s.attemptsLeft)
        assertEquals(1, conv.starts)
        assertEquals(VoiceLanguage.TAMIL, conv.language)
    }

    @Test
    fun digitsAreReadBackBeforeAnythingIsSent() {
        vm.start(VoiceLanguage.TAMIL)
        conv.hear("482913")
        val s = vm.state.value as VoiceUiState.ReadBack
        assertEquals("482913", s.heard)
        assertTrue(api.completes.isEmpty())
    }

    @Test
    fun confirmedMatchPasses() {
        api.completeQueue += VoiceStepState.Status.PASSED
        vm.start(VoiceLanguage.HINDI)
        conv.hear("482913")
        vm.confirmReadBack()
        assertEquals(listOf("482913"), api.completes)
        assertEquals(VoiceUiState.Passed, vm.state.value)
    }

    @Test
    fun rejectingReadBackSendsNothingAndListensAgain() {
        vm.start(VoiceLanguage.ENGLISH)
        conv.hear("482918")
        vm.rejectReadBack()
        assertTrue(vm.state.value is VoiceUiState.CodeShown)
        assertTrue(api.completes.isEmpty())
        assertEquals(2, conv.starts)
        assertEquals(1, conv.stops)
    }

    @Test
    fun wrongCodeShowsRetryThenListensAgain() {
        api.completeQueue += VoiceStepState.Status.RETRY
        vm.start(VoiceLanguage.TAMIL)
        conv.hear("111111")
        vm.confirmReadBack()
        val r = vm.state.value as VoiceUiState.Retry
        assertEquals(2, r.attemptsLeft)
        vm.tryAgain()
        assertTrue(vm.state.value is VoiceUiState.CodeShown)
        assertEquals(2, conv.starts)
    }

    @Test
    fun threeWrongTriesFallBackAndStopListening() {
        api.completeQueue += listOf(VoiceStepState.Status.RETRY, VoiceStepState.Status.RETRY, VoiceStepState.Status.FALLBACK_CALLBACK)
        vm.start(VoiceLanguage.TAMIL)
        repeat(3) { i ->
            conv.hear("11111$i")
            vm.confirmReadBack()
            if (i < 2) vm.tryAgain()
        }
        assertEquals(VoiceUiState.Fallback, vm.state.value)
        assertNull(conv.onDigits)
        assertEquals(3, api.completes.size)
    }

    @Test
    fun expiredCodeAsksForANewOne() {
        api.completeQueue += VoiceStepState.Status.EXPIRED
        vm.start(VoiceLanguage.ENGLISH)
        conv.hear("482913")
        vm.confirmReadBack()
        assertEquals(VoiceUiState.Expired, vm.state.value)
        vm.newCode()
        assertEquals(2, api.starts)
        assertTrue(vm.state.value is VoiceUiState.CodeShown)
    }

    @Test
    fun serverFallbackOnStartGoesStraightToCallBack() {
        api.startStatus = VoiceStepState.Status.FALLBACK_CALLBACK
        vm.start(VoiceLanguage.ENGLISH)
        assertEquals(VoiceUiState.Fallback, vm.state.value)
        assertEquals(0, conv.starts)
    }

    @Test
    fun finishedStepOnStartIsFallback() {
        api.startProblem = VoiceStepProblem(409, "voice-finished", "The voice step is fallback_callback.")
        vm.start(VoiceLanguage.ENGLISH)
        assertEquals(VoiceUiState.Fallback, vm.state.value)
    }

    @Test
    fun tier1NotVerifiedShowsError() {
        api.startProblem = VoiceStepProblem(409, "tier1-not-verified", "The voice step runs only after the fingerprint signature is verified.")
        vm.start(VoiceLanguage.ENGLISH)
        val e = vm.state.value as VoiceUiState.Error
        assertTrue(e.message.contains("fingerprint"))
    }

    @Test
    fun networkErrorOnCompleteShowsError() {
        api.completeProblem = null
        vm.start(VoiceLanguage.ENGLISH)
        conv.hear("482913")
        // completeQueue is empty, so the fake throws NoSuchElementException like a broken connection
        vm.confirmReadBack()
        assertTrue(vm.state.value is VoiceUiState.Error)
    }

    @Test
    fun lateDigitsAfterPassAreIgnored() {
        api.completeQueue += VoiceStepState.Status.PASSED
        vm.start(VoiceLanguage.ENGLISH)
        val late = conv.onDigits!!
        conv.hear("482913")
        vm.confirmReadBack()
        late("999999")
        assertEquals(VoiceUiState.Passed, vm.state.value)
    }

    @Test
    fun stateToStringNeverContainsTheCode() {
        vm.start(VoiceLanguage.ENGLISH)
        assertFalse(vm.state.value.toString().contains("482913"))
        conv.hear("482913")
        assertFalse(vm.state.value.toString().contains("482913"))
    }
}
