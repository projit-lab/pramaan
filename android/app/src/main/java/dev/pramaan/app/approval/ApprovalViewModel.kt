package dev.pramaan.app.approval

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.pramaan.crypto.Canonical
import dev.pramaan.crypto.KeySigner
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** What the phone sends once the approver has signed. */
data class SignedDecision(
    val approvalId: String,
    val decision: Decision,
    /** DER ECDSA P-256 over the canonical summary bytes. */
    val signatureDer: ByteArray,
    /** Base64 of the exact bytes signed, so the server checks the same thing. */
    val summaryB64: String,
)

/** The server side of the decision. Implemented over HTTP; faked in tests. */
interface ApprovalApi {
    suspend fun submit(signed: SignedDecision): SubmitOutcome
}

sealed interface SubmitOutcome {
    data object Accepted : SubmitOutcome
    data object Rejected : SubmitOutcome
    data object Offline : SubmitOutcome
    data class AlreadyDecided(val by: String, val what: Decision, val atIst: String) : SubmitOutcome
}

/** Raised by a signer when a new fingerprint invalidated the key. */
class KeyInvalidated : Exception("The signing key is no longer valid")

/** Raised when the biometric did not match. */
class BiometricNotRecognised : Exception("Fingerprint not recognised")

/**
 * The approval screen's state machine.
 *
 * The rule this class exists to enforce: **the screen and the signature must
 * describe the same payment.** The phone signs the canonical summary bytes the
 * server sent, and shows fields taken from that same map. Before it will sign,
 * it checks that what the approver is looking at is what the bytes say. If they
 * disagree it refuses, because a screen that shows one payee while signing
 * another is the exact attack Pramaan exists to stop.
 */
class ApprovalViewModel(
    private val signer: KeySigner,
    private val api: ApprovalApi,
    private val now: () -> Long = System::currentTimeMillis,
) : ViewModel() {

    private val _state = MutableStateFlow<ApprovalState>(ApprovalState.Loading)
    val state: StateFlow<ApprovalState> = _state.asStateFlow()

    /** The canonical summary the server sent, exactly as it will be signed. */
    private var canonicalFields: Map<String, String> = emptyMap()

    class ScreenDisagreesWithSignature(val field: String) : IllegalStateException(
        "The screen shows a different $field from the bytes that would be signed"
    )

    /**
     * Hand the screen a payment and the canonical fields that go with it.
     *
     * [deviceRevoked] and [alreadyDecided] come from the same server response,
     * so the screen never offers Approve on a payment it cannot approve.
     */
    fun load(
        payment: ApprovalPayment,
        canonical: Map<String, String>,
        deviceRevoked: Boolean = false,
        alreadyDecided: Triple<String, Decision, String>? = null,
        expiredAtIst: String? = null,
    ) {
        canonicalFields = canonical

        if (deviceRevoked) {
            _state.value = ApprovalState.CannotApprove(payment, Blocker.REVOKED)
            return
        }
        if (alreadyDecided != null) {
            _state.value = ApprovalState.CannotApprove(
                payment,
                Blocker.ALREADY_DECIDED,
                decidedBy = alreadyDecided.first,
                decidedWhat = alreadyDecided.second,
                decidedAtIst = alreadyDecided.third,
            )
            return
        }
        if (payment.expiresAtMillis <= now()) {
            _state.value = ApprovalState.CannotApprove(
                payment,
                Blocker.EXPIRED,
                expiredAtIst = expiredAtIst,
            )
            return
        }
        _state.value = ApprovalState.Ready(payment)
    }

    /**
     * The guard. Throws rather than returning false, because there is no sensible
     * way to carry on: a mismatch here means the approver cannot trust the screen.
     */
    internal fun assertScreenMatchesBytes(payment: ApprovalPayment) {
        fun check(field: String, shown: String) {
            val signed = canonicalFields[field]
                ?: throw ScreenDisagreesWithSignature(field)
            if (signed != shown) throw ScreenDisagreesWithSignature(field)
        }
        check("payee_name", payment.payeeNameAtBank)
        check("payee_account", payment.payeeAccountFull)
        check("payee_ifsc", payment.payeeIfsc)
        check("amount_paise", payment.amountPaise)
    }

    fun approve() = decide(Decision.APPROVE)
    fun decline() = decide(Decision.DECLINE)
    fun reportFraud() = decide(Decision.REPORT_FRAUD)

    /** The approver dismissed the fingerprint prompt: no error, back to Ready. */
    fun biometricCancelled() {
        val payment = currentPayment() ?: return
        _state.value = ApprovalState.Ready(payment)
    }

    fun retry() {
        val payment = currentPayment() ?: return
        _state.value = ApprovalState.Ready(payment)
    }

    private fun currentPayment(): ApprovalPayment? = when (val s = _state.value) {
        is ApprovalState.Ready -> s.payment
        is ApprovalState.WaitingForFingerprint -> s.payment
        is ApprovalState.Signing -> s.payment
        is ApprovalState.Failed -> s.payment
        is ApprovalState.Signed -> s.payment
        is ApprovalState.CannotApprove -> s.payment
        ApprovalState.Loading -> null
    }

    private fun decide(decision: Decision) {
        val payment = (_state.value as? ApprovalState.Ready)?.payment ?: return

        // Checked again at the moment of deciding, not only at load: an approval
        // can lapse while the screen is open and a thumb is on its way down.
        if (payment.expiresAtMillis <= now()) {
            _state.value = ApprovalState.CannotApprove(payment, Blocker.EXPIRED)
            return
        }

        assertScreenMatchesBytes(payment)

        val bytes = Canonical.canonicalBytes(canonicalFields)
        _state.value = ApprovalState.WaitingForFingerprint(payment)

        viewModelScope.launch {
            val signature = try {
                signer.sign(bytes)
            } catch (e: BiometricNotRecognised) {
                _state.value = ApprovalState.Failed(payment, FailureCause.BIOMETRIC_NOT_RECOGNISED)
                return@launch
            } catch (e: KeyInvalidated) {
                _state.value = ApprovalState.Failed(payment, FailureCause.KEY_INVALIDATED)
                return@launch
            }

            _state.value = ApprovalState.Signing(payment)

            val signed = SignedDecision(
                approvalId = payment.approvalId,
                decision = decision,
                signatureDer = signature,
                summaryB64 = base64(bytes),
            )

            _state.value = when (val outcome = api.submit(signed)) {
                SubmitOutcome.Accepted -> ApprovalState.Signed(payment, decision)
                SubmitOutcome.Rejected ->
                    ApprovalState.Failed(payment, FailureCause.SIGNATURE_REJECTED)
                SubmitOutcome.Offline ->
                    ApprovalState.Failed(payment, FailureCause.NETWORK)
                is SubmitOutcome.AlreadyDecided -> ApprovalState.CannotApprove(
                    payment,
                    Blocker.ALREADY_DECIDED,
                    decidedBy = outcome.by,
                    decidedWhat = outcome.what,
                    decidedAtIst = outcome.atIst,
                )
            }
        }
    }

    private fun base64(bytes: ByteArray): String =
        java.util.Base64.getEncoder().encodeToString(bytes)
}
