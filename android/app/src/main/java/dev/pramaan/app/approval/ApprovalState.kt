package dev.pramaan.app.approval

/**
 * What the approval screen can be, and what it is allowed to say in each state.
 *
 * The states are the nine in docs/android-approval-screen-spec.md. They are a
 * sealed hierarchy rather than a set of booleans so that "signing" and "expired"
 * cannot both be true, and so that the Approve button exists in exactly the
 * states where approving is possible.
 */

/** One reason the payment was held. A rule wrote it, or Gemini explained it. */
data class Reason(
    val text: String,
    /** "rule", "gemini" or "model_armor". Shown to the approver, never inferred. */
    val source: String,
    /** Set only on a reason that records a change, e.g. an account that moved. */
    val changedFrom: String? = null,
    val changedTo: String? = null,
)

/**
 * The payment, as the phone was told it. `payeeAccountFull` is what the
 * signature covers; the screen shows only its last four until the approver taps
 * to reveal. If these two ever disagree the screen is lying about what is being
 * signed, so both live in one object and the screen derives the masked form.
 */
data class ApprovalPayment(
    val approvalId: String,
    val intentId: String,
    val payeeNameAtBank: String,
    val payeeAccountFull: String,
    val payeeIfsc: String,
    val amountPaise: String,
    val purposeInvoice: String?,
    /** A work email, or an agent id when a machine raised it. */
    val raisedBy: String,
    val raisedByIsAgent: Boolean,
    val tier: Int,
    val reasons: List<Reason>,
    /** One to three sentences, always labelled as Gemini's. Null when absent. */
    val geminiExplanation: String?,
    /** Epoch millis. The countdown is derived, never stored as text. */
    val expiresAtMillis: Long,
) {
    val payeeAccountMasked: String get() = Money.maskAccount(payeeAccountFull)
    val amountFigures: String get() = Money.formatRupees(amountPaise)
    val amountWords: String get() = Money.amountInWords(amountPaise)
}

/** Why the approver cannot approve. A disabled Approve always says which. */
enum class Blocker { EXPIRED, REVOKED, ALREADY_DECIDED, OFFLINE }

/** Why a signing attempt failed. Each needs a different action from the person. */
enum class FailureCause {
    BIOMETRIC_NOT_RECOGNISED,
    KEY_INVALIDATED,
    SIGNATURE_REJECTED,
    NETWORK,
}

sealed interface ApprovalState {

    /** 1. Skeleton in the shape of the final layout. No buttons are rendered. */
    data object Loading : ApprovalState

    /** 2. The normal state: everything shown, Approve enabled, countdown live. */
    data class Ready(val payment: ApprovalPayment) : ApprovalState

    /** 3. The platform BiometricPrompt is up; payee and amount stay visible. */
    data class WaitingForFingerprint(val payment: ApprovalPayment) : ApprovalState

    /** 4. Signature computed and sent. Every button disabled; a second tap impossible. */
    data class Signing(val payment: ApprovalPayment) : ApprovalState

    /** 5. Signed. Says what was signed, and what happens next, honestly. */
    data class Signed(
        val payment: ApprovalPayment,
        val decision: Decision,
    ) : ApprovalState

    /** 6. A signing attempt failed. Never the word fraud. */
    data class Failed(
        val payment: ApprovalPayment,
        val cause: FailureCause,
    ) : ApprovalState

    /** 7, 8, 9. Approving is off the table; the screen says why, and offers no Approve. */
    data class CannotApprove(
        val payment: ApprovalPayment,
        val blocker: Blocker,
        /** Set for ALREADY_DECIDED: who decided, what, and when. */
        val decidedBy: String? = null,
        val decidedWhat: Decision? = null,
        val decidedAtIst: String? = null,
        /** Set for EXPIRED: the time it lapsed, in IST. */
        val expiredAtIst: String? = null,
    ) : ApprovalState
}

enum class Decision { APPROVE, DECLINE, REPORT_FRAUD }

/**
 * The copy for every state that says something to the approver.
 *
 * It lives here rather than in the composable so the tests can assert on the
 * exact words. The honesty rules are load-bearing: Pramaan does not move money,
 * so a signed approval never says "Payment sent"; and a signature that did not
 * verify is never called fraud.
 */
object ApprovalCopy {

    const val SIGNING = "Sending your signed approval"

    const val SIGNED_APPROVE =
        "Approved. Pramaan is countersigning this and the payment will be released to the bank."

    const val SIGNED_DECLINE = "Declined. No money will move."

    const val SIGNED_REPORT_FRAUD =
        "Reported as fraud. The payment is blocked and your security team has been alerted."

    fun signed(decision: Decision): String = when (decision) {
        Decision.APPROVE -> SIGNED_APPROVE
        Decision.DECLINE -> SIGNED_DECLINE
        Decision.REPORT_FRAUD -> SIGNED_REPORT_FRAUD
    }

    fun failure(cause: FailureCause): String = when (cause) {
        FailureCause.BIOMETRIC_NOT_RECOGNISED ->
            "That fingerprint wasn't recognised."
        FailureCause.KEY_INVALIDATED ->
            "This phone's signing key is no longer valid, because a new fingerprint was " +
                "added. You'll need to enrol again."
        FailureCause.SIGNATURE_REJECTED ->
            "Pramaan could not verify this signature. The payment has not been approved."
        FailureCause.NETWORK ->
            "Couldn't reach Pramaan. Your approval was not sent."
    }

    /** Whether offering "try again" helps, or just loops the person. */
    fun isRetryable(cause: FailureCause): Boolean = when (cause) {
        FailureCause.BIOMETRIC_NOT_RECOGNISED, FailureCause.NETWORK -> true
        FailureCause.KEY_INVALIDATED, FailureCause.SIGNATURE_REJECTED -> false
    }

    fun blocked(blocker: Blocker, expiredAtIst: String? = null): String = when (blocker) {
        Blocker.EXPIRED ->
            "This approval expired at ${expiredAtIst ?: "an earlier time"}. " +
                "Ask the accounts team to raise it again."
        Blocker.REVOKED ->
            "This phone can no longer approve payments. Contact your administrator."
        Blocker.ALREADY_DECIDED ->
            "This payment was already decided."
        Blocker.OFFLINE ->
            "Couldn't reach Pramaan to check this approval is still open."
    }

    /** Word for word the console's label, so the two never drift. */
    const val GEMINI_LABEL = "AI summary · Gemini"
}
