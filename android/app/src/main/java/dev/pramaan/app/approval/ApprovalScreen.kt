package dev.pramaan.app.approval

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * The approver's approval screen.
 *
 * Built to docs/android-approval-screen-spec.md. The one rule it serves: an
 * approver must be able to spot a wrong payment in three seconds. So the order
 * runs payee, account, amount in figures, amount in words, purpose, who raised
 * it, why it was held -- a fraud gets the payee and the amount wrong, and those
 * are at the top.
 *
 * Colours come from web/shared/src/styles/tokens.css so the phone, the console
 * and the ERP speak one language. Colour never carries meaning alone: every
 * state here also carries its word.
 */

// Mirrors of the tokens. When tokens.css changes, these change with it.
private val Held = Color(0xFFB26A00)
private val Released = Color(0xFF1B7F4B)
private val Blocked = Color(0xFFB3261E)
private val Ai = Color(0xFF6B4EFF)
private val Ink = Color(0xFF1B1C1E)
private val InkMuted = Color(0xFF5A6169)
private val SurfaceContainer = Color(0xFFF2F4F7)

@Composable
fun ApprovalScreen(
    state: ApprovalState,
    onApprove: () -> Unit,
    onDecline: () -> Unit,
    onReportFraud: () -> Unit,
    onRetry: () -> Unit,
    minutesRemaining: (ApprovalPayment) -> Long,
    modifier: Modifier = Modifier,
) {
    Surface(modifier = modifier.fillMaxSize()) {
        when (state) {
            ApprovalState.Loading -> LoadingSkeleton()

            is ApprovalState.Ready -> PaymentBody(state.payment, minutesRemaining) {
                Buttons(onApprove, onDecline, onReportFraud, enabled = true)
            }

            // The last look before the finger lands must be at the payment.
            is ApprovalState.WaitingForFingerprint ->
                PaymentBody(state.payment, minutesRemaining) {
                    Buttons(onApprove, onDecline, onReportFraud, enabled = false)
                }

            is ApprovalState.Signing -> PaymentBody(state.payment, minutesRemaining) {
                Text(
                    ApprovalCopy.SIGNING,
                    color = InkMuted,
                    modifier = Modifier.padding(vertical = 16.dp),
                )
            }

            is ApprovalState.Signed -> SignedPanel(state)

            is ApprovalState.Failed -> PaymentBody(state.payment, minutesRemaining) {
                Banner(ApprovalCopy.failure(state.cause), Blocked)
                if (ApprovalCopy.isRetryable(state.cause)) {
                    Spacer(Modifier.height(12.dp))
                    OutlinedButton(onClick = onRetry, modifier = tapTarget()) {
                        Text("Try again")
                    }
                }
            }

            is ApprovalState.CannotApprove -> PaymentBody(state.payment, minutesRemaining) {
                // No Approve button at all, rather than a disabled one.
                Banner(ApprovalCopy.blocked(state.blocker, state.expiredAtIst), Held)
                if (state.decidedBy != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "${state.decidedWhat?.label() ?: "Decided"} by ${state.decidedBy}" +
                            (state.decidedAtIst?.let { ", $it" } ?: ""),
                        color = InkMuted,
                        fontSize = 14.sp,
                    )
                }
            }
        }
    }
}

private fun Decision.label(): String = when (this) {
    Decision.APPROVE -> "Approved"
    Decision.DECLINE -> "Declined"
    Decision.REPORT_FRAUD -> "Reported as fraud"
}

/** A spinner alone on a payment screen reads as "something is happening to the money". */
@Composable
private fun LoadingSkeleton() {
    Column(Modifier.fillMaxSize().padding(20.dp)) {
        SkeletonBar(0.7f, 28.dp)
        Spacer(Modifier.height(12.dp))
        SkeletonBar(0.4f, 16.dp)
        Spacer(Modifier.height(28.dp))
        SkeletonBar(0.6f, 48.dp)
        Spacer(Modifier.height(10.dp))
        SkeletonBar(0.8f, 18.dp)
        Spacer(Modifier.height(28.dp))
        repeat(3) {
            SkeletonBar(0.5f, 28.dp)
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun SkeletonBar(widthFraction: Float, height: androidx.compose.ui.unit.Dp) {
    Box(
        Modifier
            .fillMaxWidth(widthFraction)
            .height(height)
            .background(SurfaceContainer, RoundedCornerShape(8.dp))
    )
}

@Composable
private fun PaymentBody(
    payment: ApprovalPayment,
    minutesRemaining: (ApprovalPayment) -> Long,
    actions: @Composable () -> Unit,
) {
    var revealed by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp)
    ) {
        // 1. Payee, largest on the screen.
        Text(
            payment.payeeNameAtBank,
            fontSize = 26.sp,
            lineHeight = 32.sp,
            fontWeight = FontWeight.Medium,
            color = Ink,
        )

        Spacer(Modifier.height(6.dp))

        // 2. Account and IFSC. Tap reveals the full number; the reveal is logged
        //    server-side by the caller that flips this flag in a real build.
        Text(
            text = if (revealed) {
                "${payment.payeeAccountFull} · ${payment.payeeIfsc}"
            } else {
                "${payment.payeeAccountMasked} · ${payment.payeeIfsc}"
            },
            fontSize = 15.sp,
            color = InkMuted,
            modifier = Modifier
                .heightIn(min = 48.dp)
                .clickable { revealed = !revealed }
                .semantics {
                    contentDescription = if (revealed) {
                        "Account ${payment.payeeAccountFull}, tap to hide"
                    } else {
                        "Account ending ${payment.payeeAccountFull.takeLast(4)}, tap to reveal"
                    }
                },
        )

        Spacer(Modifier.height(20.dp))

        // 3 and 4. Figures and words in one visual block: the transposition catch.
        Text(
            payment.amountFigures,
            fontSize = 44.sp,
            lineHeight = 52.sp,
            fontWeight = FontWeight.Medium,
            color = Ink,
        )
        Text(
            payment.amountWords,
            fontSize = 16.sp,
            lineHeight = 22.sp,
            color = InkMuted,
        )

        Spacer(Modifier.height(20.dp))

        // 5. Purpose.
        payment.purposeInvoice?.let {
            LabelledRow("Invoice", it)
        }

        // 6. Who raised it. A machine must never have to be worked out.
        LabelledRow(
            label = if (payment.raisedByIsAgent) "Raised by an AI agent" else "Raised by",
            value = payment.raisedBy,
            valueColor = if (payment.raisedByIsAgent) Ai else Ink,
        )

        LabelledRow("Tier", "Tier ${payment.tier}")

        Spacer(Modifier.height(16.dp))

        // 7. Every reason, as text. Never an icon alone.
        if (payment.reasons.isNotEmpty()) {
            Text("Why this is waiting", fontSize = 13.sp, color = InkMuted)
            Spacer(Modifier.height(8.dp))
            payment.reasons.forEach { ReasonChip(it) }
        }

        // 8. Anything Gemini wrote, labelled word for word as the console labels it.
        payment.geminiExplanation?.let {
            Spacer(Modifier.height(16.dp))
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFF3F0FF), RoundedCornerShape(12.dp))
                    .padding(12.dp)
            ) {
                Text(ApprovalCopy.GEMINI_LABEL, fontSize = 12.sp, color = Ai)
                Spacer(Modifier.height(4.dp))
                Text(it, fontSize = 14.sp, lineHeight = 20.sp, color = Ink)
            }
        }

        Spacer(Modifier.height(20.dp))

        // 9. The expiry.
        val minutes = minutesRemaining(payment)
        if (minutes > 0) {
            Text("Expires in $minutes min", fontSize = 14.sp, color = Held)
        }

        Spacer(Modifier.height(24.dp))

        actions()

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun LabelledRow(label: String, value: String, valueColor: Color = Ink) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, fontSize = 14.sp, color = InkMuted)
        Text(value, fontSize = 14.sp, color = valueColor, fontWeight = FontWeight.Medium)
    }
}

/**
 * A reason that records a change shows the old value struck through and the new
 * one in red. This is the sentence that saves the money.
 */
@Composable
private fun ReasonChip(reason: Reason) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(bottom = 8.dp)
            .background(SurfaceContainer, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp)
    ) {
        Text(reason.text, fontSize = 14.sp, lineHeight = 20.sp, color = Ink)
        if (reason.changedFrom != null && reason.changedTo != null) {
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    reason.changedFrom,
                    fontSize = 14.sp,
                    color = InkMuted,
                    textDecoration = TextDecoration.LineThrough,
                )
                Text("  →  ", fontSize = 14.sp, color = InkMuted)
                Text(
                    reason.changedTo,
                    fontSize = 14.sp,
                    color = Blocked,
                    fontWeight = FontWeight.Medium,
                )
            }
        }
        Spacer(Modifier.height(4.dp))
        Text(
            when (reason.source) {
                "gemini" -> "AI-written"
                "model_armor" -> "Model Armor"
                else -> "rule"
            },
            fontSize = 11.sp,
            color = if (reason.source == "gemini") Ai else InkMuted,
        )
    }
}

/**
 * Decline sits above Approve on purpose: Approve must not be the easiest reflex
 * target, and the two are far enough apart that one thumb cannot catch both.
 */
@Composable
private fun Buttons(
    onApprove: () -> Unit,
    onDecline: () -> Unit,
    onReportFraud: () -> Unit,
    enabled: Boolean,
) {
    Column(Modifier.fillMaxWidth()) {
        OutlinedButton(
            onClick = onDecline,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth().then(tapTarget()),
        ) { Text("Decline") }

        Spacer(Modifier.height(16.dp))

        Button(
            onClick = onApprove,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth().then(tapTarget()),
            colors = ButtonDefaults.buttonColors(containerColor = Released),
        ) { Text("Approve with fingerprint") }

        Spacer(Modifier.height(12.dp))

        TextButton(
            onClick = onReportFraud,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth().then(tapTarget()),
        ) { Text("Report fraud", color = Blocked) }
    }
}

private fun tapTarget(): Modifier = Modifier.heightIn(min = 48.dp)

/** Says what was signed, not merely that something was. */
@Composable
private fun SignedPanel(state: ApprovalState.Signed) {
    val payment = state.payment
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            state.decision.label(),
            fontSize = 24.sp,
            fontWeight = FontWeight.Medium,
            color = when (state.decision) {
                Decision.APPROVE -> Released
                else -> Blocked
            },
        )
        Spacer(Modifier.height(16.dp))
        Text(payment.payeeNameAtBank, fontSize = 18.sp, color = Ink)
        Text(payment.payeeAccountMasked, fontSize = 14.sp, color = InkMuted)
        Spacer(Modifier.height(8.dp))
        Text(
            payment.amountFigures,
            fontSize = 32.sp,
            fontWeight = FontWeight.Medium,
            color = Ink,
        )
        Text(
            payment.amountWords,
            fontSize = 14.sp,
            color = InkMuted,
            modifier = Modifier.clearAndSetSemantics { },
        )
        Spacer(Modifier.height(24.dp))
        Text(
            ApprovalCopy.signed(state.decision),
            fontSize = 15.sp,
            lineHeight = 22.sp,
            color = InkMuted,
        )
    }
}

@Composable
private fun Banner(text: String, tone: Color) {
    Box(
        Modifier
            .fillMaxWidth()
            .background(tone.copy(alpha = 0.10f), RoundedCornerShape(12.dp))
            .padding(14.dp)
    ) {
        Text(text, fontSize = 14.sp, lineHeight = 20.sp, color = Ink)
    }
}
