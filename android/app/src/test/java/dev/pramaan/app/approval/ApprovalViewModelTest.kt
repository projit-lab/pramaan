package dev.pramaan.app.approval

import dev.pramaan.crypto.EnrolResult
import dev.pramaan.crypto.KeySigner
import dev.pramaan.crypto.SecurityLevel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * What these pin: the screen and the signature describe the same payment, a
 * decision can only be made once, and every refusal says which refusal it is.
 *
 * The one that matters most is `refuses to sign when the screen disagrees`.
 * Everything else on this screen is presentation; that test is the product.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ApprovalViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    // The canonical summary as contracts/canonical/vectors.json defines it.
    private val canonical = mapOf(
        "amount_paise" to "98000000",
        "currency" to "INR",
        "expires_at" to "2027-11-21T11:42:07+05:30",
        "initiator" to "human:clerk@acme.example",
        "intent_id" to "pi_01JD2XGENUINE0001",
        "payee_account" to "000123457781",
        "payee_ifsc" to "ABCD0123456",
        "payee_name" to "Sri Lakshmi Castings",
        "payer_account" to "50100004521",
        "purpose" to "INV-2219",
        "v" to "1",
    )

    private fun payment(
        payee: String = "Sri Lakshmi Castings",
        account: String = "000123457781",
        amount: String = "98000000",
        expiresInMillis: Long = 60 * 60 * 1000,
    ) = ApprovalPayment(
        approvalId = "ap_01JD2XCFO0001",
        intentId = "pi_01JD2XGENUINE0001",
        payeeNameAtBank = payee,
        payeeAccountFull = account,
        payeeIfsc = "ABCD0123456",
        amountPaise = amount,
        purposeInvoice = "INV-2219",
        raisedBy = "clerk@acme.example",
        raisedByIsAgent = false,
        tier = 1,
        reasons = listOf(Reason("Amount is above ₹5,00,000", "rule")),
        geminiExplanation = null,
        expiresAtMillis = FIXED_NOW + expiresInMillis,
    )

    private class FakeSigner(
        private val onSign: (ByteArray) -> ByteArray = { byteArrayOf(0x30, 0x44) },
    ) : KeySigner {
        var signedBytes: ByteArray? = null
        override suspend fun enrol(challenge: ByteArray) =
            EnrolResult(emptyList(), SecurityLevel.SOFTWARE, "fake")
        override suspend fun sign(data: ByteArray): ByteArray {
            signedBytes = data
            return onSign(data)
        }
        override fun publicKey(): ByteArray? = byteArrayOf(1)
    }

    private class FakeApi(var outcome: SubmitOutcome = SubmitOutcome.Accepted) : ApprovalApi {
        var submitted: SignedDecision? = null
        var calls = 0
        override suspend fun submit(signed: SignedDecision): SubmitOutcome {
            calls++
            submitted = signed
            return outcome
        }
    }

    private fun vm(
        signer: KeySigner = FakeSigner(),
        api: ApprovalApi = FakeApi(),
    ) = ApprovalViewModel(signer, api) { FIXED_NOW }

    @Test
    fun `starts loading and renders no buttons until it has a payment`() {
        assertEquals(ApprovalState.Loading, vm().state.value)
    }

    @Test
    fun `a loaded payment is ready to approve`() {
        val model = vm()
        model.load(payment(), canonical)
        val state = model.state.value
        assertTrue(state is ApprovalState.Ready)
        assertEquals("₹9,80,000", (state as ApprovalState.Ready).payment.amountFigures)
        assertEquals("nine lakh eighty thousand rupees", state.payment.amountWords)
        assertEquals("•••• 7781", state.payment.payeeAccountMasked)
    }

    @Test
    fun `refuses to sign when the screen shows a different payee from the signed bytes`() {
        val model = vm()
        model.load(payment(payee = "Totally Different Traders"), canonical)
        val error = assertThrows(ApprovalViewModel.ScreenDisagreesWithSignature::class.java) {
            model.approve()
        }
        assertEquals("payee_name", error.field)
    }

    @Test
    fun `refuses to sign when the screen shows a different account from the signed bytes`() {
        val model = vm()
        // The poisoned account from the Kaveri invoice: same last four would not
        // even be needed, any difference at all must stop the signature.
        model.load(payment(account = "000123458117"), canonical)
        val error = assertThrows(ApprovalViewModel.ScreenDisagreesWithSignature::class.java) {
            model.approve()
        }
        assertEquals("payee_account", error.field)
    }

    @Test
    fun `refuses to sign when the screen shows a different amount from the signed bytes`() {
        val model = vm()
        model.load(payment(amount = "9800000"), canonical)
        val error = assertThrows(ApprovalViewModel.ScreenDisagreesWithSignature::class.java) {
            model.approve()
        }
        assertEquals("amount_paise", error.field)
    }

    @Test
    fun `signs the canonical bytes, not the displayed text`() = runTest(dispatcher) {
        val signer = FakeSigner()
        val api = FakeApi()
        val model = ApprovalViewModel(signer, api) { FIXED_NOW }
        model.load(payment(), canonical)
        model.approve()
        dispatcher.scheduler.advanceUntilIdle()

        val signed = String(signer.signedBytes!!, Charsets.UTF_8)
        // Keys sorted, no whitespace, every value a string.
        assertTrue(signed.startsWith("{\"amount_paise\":\"98000000\""))
        assertTrue(signed.contains("\"payee_name\":\"Sri Lakshmi Castings\""))
        assertEquals(ApprovalState.Signed(payment(), Decision.APPROVE), model.state.value)
    }

    @Test
    fun `an accepted approval says Pramaan is countersigning, never that money was sent`() =
        runTest(dispatcher) {
            val model = vm()
            model.load(payment(), canonical)
            model.approve()
            dispatcher.scheduler.advanceUntilIdle()

            val copy = ApprovalCopy.signed(Decision.APPROVE)
            assertTrue(copy.contains("countersigning"))
            assertTrue(!copy.lowercase().contains("payment sent"))
        }

    @Test
    fun `a rejected signature is a rejected signature, never fraud`() = runTest(dispatcher) {
        val api = FakeApi(SubmitOutcome.Rejected)
        val model = ApprovalViewModel(FakeSigner(), api) { FIXED_NOW }
        model.load(payment(), canonical)
        model.approve()
        dispatcher.scheduler.advanceUntilIdle()

        val state = model.state.value as ApprovalState.Failed
        assertEquals(FailureCause.SIGNATURE_REJECTED, state.cause)
        val copy = ApprovalCopy.failure(state.cause)
        assertTrue(!copy.lowercase().contains("fraud"))
        // Never a retry loop on a rejected signature.
        assertTrue(!ApprovalCopy.isRetryable(state.cause))
    }

    @Test
    fun `the word fraud appears only when the approver chose it`() = runTest(dispatcher) {
        val model = vm()
        model.load(payment(), canonical)
        model.reportFraud()
        dispatcher.scheduler.advanceUntilIdle()

        val state = model.state.value as ApprovalState.Signed
        assertEquals(Decision.REPORT_FRAUD, state.decision)
        assertTrue(ApprovalCopy.signed(state.decision).lowercase().contains("fraud"))
    }

    @Test
    fun `a new fingerprint invalidating the key asks for enrolment, not a retry`() =
        runTest(dispatcher) {
            val signer = FakeSigner { throw KeyInvalidated() }
            val model = ApprovalViewModel(signer, FakeApi()) { FIXED_NOW }
            model.load(payment(), canonical)
            model.approve()
            dispatcher.scheduler.advanceUntilIdle()

            val state = model.state.value as ApprovalState.Failed
            assertEquals(FailureCause.KEY_INVALIDATED, state.cause)
            assertTrue(ApprovalCopy.failure(state.cause).contains("enrol again"))
            assertTrue(!ApprovalCopy.isRetryable(state.cause))
        }

    @Test
    fun `a cancelled fingerprint is not an error`() = runTest(dispatcher) {
        val model = vm()
        model.load(payment(), canonical)
        model.biometricCancelled()
        assertTrue(model.state.value is ApprovalState.Ready)
    }

    @Test
    fun `a network failure says the approval was not sent, and can be retried`() =
        runTest(dispatcher) {
            val api = FakeApi(SubmitOutcome.Offline)
            val model = ApprovalViewModel(FakeSigner(), api) { FIXED_NOW }
            model.load(payment(), canonical)
            model.approve()
            dispatcher.scheduler.advanceUntilIdle()

            val state = model.state.value as ApprovalState.Failed
            assertEquals(FailureCause.NETWORK, state.cause)
            assertTrue(ApprovalCopy.failure(state.cause).contains("was not sent"))
            assertTrue(ApprovalCopy.isRetryable(state.cause))
        }

    @Test
    fun `an expired approval offers no Approve at all`() {
        val model = vm()
        model.load(payment(expiresInMillis = -1), canonical, expiredAtIst = "11:42 am")
        val state = model.state.value as ApprovalState.CannotApprove
        assertEquals(Blocker.EXPIRED, state.blocker)
        assertTrue(ApprovalCopy.blocked(state.blocker, state.expiredAtIst).contains("11:42 am"))
    }

    @Test
    fun `an approval that lapses while the screen is open cannot be signed`() {
        var clock = FIXED_NOW
        val api = FakeApi()
        val model = ApprovalViewModel(FakeSigner(), api) { clock }
        model.load(payment(expiresInMillis = 1000), canonical)
        assertTrue(model.state.value is ApprovalState.Ready)

        clock = FIXED_NOW + 2000 // the thumb was already on its way down
        model.approve()

        assertTrue(model.state.value is ApprovalState.CannotApprove)
        assertEquals(0, api.calls)
    }

    @Test
    fun `a revoked device cannot approve and says who to contact`() {
        val model = vm()
        model.load(payment(), canonical, deviceRevoked = true)
        val state = model.state.value as ApprovalState.CannotApprove
        assertEquals(Blocker.REVOKED, state.blocker)
        assertTrue(ApprovalCopy.blocked(state.blocker).contains("administrator"))
    }

    @Test
    fun `a payment decided elsewhere shows who decided, what and when`() {
        val model = vm()
        model.load(
            payment(),
            canonical,
            alreadyDecided = Triple("md@acme.example", Decision.DECLINE, "18 Nov 2026, 03:20 pm IST"),
        )
        val state = model.state.value as ApprovalState.CannotApprove
        assertEquals(Blocker.ALREADY_DECIDED, state.blocker)
        assertEquals("md@acme.example", state.decidedBy)
        assertEquals(Decision.DECLINE, state.decidedWhat)
        assertNotNull(state.decidedAtIst)
    }

    @Test
    fun `a second decision cannot be made once signing has begun`() = runTest(dispatcher) {
        val api = FakeApi()
        val model = ApprovalViewModel(FakeSigner(), api) { FIXED_NOW }
        model.load(payment(), canonical)
        model.approve()
        model.approve() // a second tap, before the first finished
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(1, api.calls)
    }

    @Test
    fun `the Gemini label is word for word the console's`() {
        assertEquals(
            "Explanation written by Gemini; rules made the decision",
            ApprovalCopy.GEMINI_LABEL,
        )
    }

    private companion object {
        const val FIXED_NOW = 1_795_000_000_000L
    }
}
