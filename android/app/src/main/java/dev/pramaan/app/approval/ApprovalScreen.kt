package dev.pramaan.app.approval

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.pramaan.app.theme.BandBlocked
import dev.pramaan.app.theme.BandHeld
import dev.pramaan.app.theme.BandReleased
import dev.pramaan.app.theme.Blocked
import dev.pramaan.app.theme.BlockedSoft
import dev.pramaan.app.theme.Held
import dev.pramaan.app.theme.HeldSoft
import dev.pramaan.app.theme.Ink
import dev.pramaan.app.theme.InkMuted
import dev.pramaan.app.theme.Line
import dev.pramaan.app.theme.LineStrong
import dev.pramaan.app.theme.NeutralSoft
import dev.pramaan.app.theme.Primary
import dev.pramaan.app.theme.PrimaryContainer
import dev.pramaan.app.theme.PrimaryDeep
import dev.pramaan.app.theme.Released
import dev.pramaan.app.theme.ReleasedSoft
import dev.pramaan.app.theme.SurfaceContainer
import kotlinx.coroutines.delay

/**
 * The approver's approval screen, built to PRAMAAN_BRAND_KIT.md (Parts C & E).
 *
 * Top half: The state band with seal lines, payee avatar, big 56sp amount, and words.
 * Bottom half: White sheet with ChangedField card, reason chips, AI explanation,
 *              and 1-second Hold-to-Approve button.
 */
@Composable
fun ApprovalScreen(
    state: ApprovalState,
    onApprove: () -> Unit,
    onDecline: () -> Unit,
    onReportFraud: () -> Unit,
    onRetry: () -> Unit,
    minutesRemaining: (ApprovalPayment) -> Long,
    modifier: Modifier = Modifier,
    onBack: () -> Unit = {},
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = Color.White,
    ) {
        when (state) {
            ApprovalState.Loading -> LoadingSkeleton()

            is ApprovalState.Ready -> ReadyApprovalScreen(
                payment = state.payment,
                onApprove = onApprove,
                onDecline = onDecline,
                onReportFraud = onReportFraud,
                onBack = onBack,
                minutesRemaining = minutesRemaining,
                isSigning = false,
            )

            is ApprovalState.WaitingForFingerprint -> ReadyApprovalScreen(
                payment = state.payment,
                onApprove = onApprove,
                onDecline = onDecline,
                onReportFraud = onReportFraud,
                onBack = onBack,
                minutesRemaining = minutesRemaining,
                isSigning = false,
            )

            is ApprovalState.Signing -> ReadyApprovalScreen(
                payment = state.payment,
                onApprove = onApprove,
                onDecline = onDecline,
                onReportFraud = onReportFraud,
                onBack = onBack,
                minutesRemaining = minutesRemaining,
                isSigning = true,
            )

            is ApprovalState.Signed -> {
                when (state.decision) {
                    Decision.APPROVE -> ReleasedScreen(state.payment, onBack)
                    else -> NonApprovedScreen(state.payment, state.decision, onBack)
                }
            }

            is ApprovalState.Failed -> FailedScreen(
                state = state,
                onRetry = onRetry,
                onBack = onBack,
                minutesRemaining = minutesRemaining,
            )

            is ApprovalState.CannotApprove -> CannotApproveScreen(
                state = state,
                onBack = onBack,
                minutesRemaining = minutesRemaining,
            )
        }
    }
}

/**
 * Top state band with cheque-style seal lines (concentric circles + dashed ring).
 */
@Composable
fun StateHeaderBand(
    bandColor: Color,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(bandColor)
    ) {
        // Cheque seal lines ornament in top-right corner
        Canvas(modifier = Modifier.matchParentSize()) {
            val center = Offset(size.width + 40f, -40f)
            val sealColor = Color.White.copy(alpha = 0.40f)
            val dashedColor = Color.White.copy(alpha = 0.75f)

            // Fine concentric rings
            for (r in 40..500 step 26) {
                drawCircle(
                    color = sealColor,
                    radius = r.toFloat(),
                    center = center,
                    style = Stroke(width = 1.5f),
                )
            }

            // Dashed security ring
            drawCircle(
                color = dashedColor,
                radius = 160f,
                center = center,
                style = Stroke(
                    width = 2.5f,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(14f, 10f), 0f),
                ),
            )
        }

        Box(modifier = Modifier.padding(bottom = 20.dp)) {
            content()
        }
    }
}

@Composable
private fun ReadyApprovalScreen(
    payment: ApprovalPayment,
    onApprove: () -> Unit,
    onDecline: () -> Unit,
    onReportFraud: () -> Unit,
    onBack: () -> Unit,
    minutesRemaining: (ApprovalPayment) -> Long,
    isSigning: Boolean,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        // --- TOP HALF: AMBER HELD STATE BAND ---
        StateHeaderBand(bandColor = BandHeld) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                // Top navigation & status chip row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconButton(onClick = onBack, modifier = Modifier.size(40.dp)) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                            tint = Ink,
                        )
                    }

                    // Held · Tier chip on white background
                    Box(
                        modifier = Modifier
                            .background(Color.White, RoundedCornerShape(999.dp))
                            .border(1.dp, Held.copy(alpha = 0.25f), RoundedCornerShape(999.dp))
                            .padding(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            ClockIcon(color = Held, size = 14)
                            Spacer(Modifier.width(6.dp))
                            Text(
                                text = "Held · Tier ${payment.tier}",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Medium,
                                color = Held,
                            )
                        }
                    }
                }

                Spacer(Modifier.height(8.dp))

                // Payee initial avatar circle
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .background(Color.White, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = payment.payeeNameAtBank.take(1).uppercase(),
                        fontSize = 24.sp,
                        fontWeight = FontWeight.Medium,
                        color = Ink,
                    )
                }

                Spacer(Modifier.height(8.dp))

                // "Paying <Payee>"
                Text(
                    text = "Paying",
                    fontSize = 14.sp,
                    color = InkMuted,
                )
                Text(
                    text = payment.payeeNameAtBank,
                    fontSize = 18.sp,
                    lineHeight = 24.sp,
                    fontWeight = FontWeight.Medium,
                    color = Ink,
                    textAlign = TextAlign.Center,
                )

                // Subtext with invoice & initiator
                val initiatorName = if (payment.raisedByIsAgent) "Agent" else payment.raisedBy.substringBefore('@').replaceFirstChar { it.uppercase() }
                val subtext = "${payment.purposeInvoice ?: "Invoice"} · pushed by $initiatorName"
                Text(
                    text = subtext,
                    fontSize = 13.sp,
                    color = InkMuted,
                    textAlign = TextAlign.Center,
                )

                Spacer(Modifier.height(14.dp))

                // Giant 56sp amount
                Text(
                    text = payment.amountFigures,
                    fontSize = 56.sp,
                    lineHeight = 60.sp,
                    fontWeight = FontWeight.Bold,
                    color = Ink,
                    textAlign = TextAlign.Center,
                )

                // Amount in words
                Text(
                    text = payment.amountWords.replaceFirstChar { it.uppercase() },
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    color = InkMuted,
                    textAlign = TextAlign.Center,
                )
            }
        }

        // --- BOTTOM HALF: WHITE SHEET WITH 16dp SIDE PADDING ---
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 20.dp)
        ) {
            // 1. ChangedField card: when reasons record a bank change
            val bankChangeReason = payment.reasons.firstOrNull {
                it.changedFrom != null && it.changedTo != null
            }
            if (bankChangeReason != null) {
                ChangedFieldCard(bankChangeReason)
                Spacer(Modifier.height(14.dp))
            }

            // 2. Other reason chips
            val otherReasons = payment.reasons.filter { it != bankChangeReason }
            if (otherReasons.isNotEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    otherReasons.forEach { reason ->
                        ReasonChipView(reason)
                    }
                }
                Spacer(Modifier.height(14.dp))
            }

            // 3. AI Explanation card
            if (payment.geminiExplanation != null) {
                AiExplanationCard(explanation = payment.geminiExplanation)
                Spacer(Modifier.height(20.dp))
            }

            // Expiry countdown note
            val minutes = minutesRemaining(payment)
            if (minutes > 0) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(bottom = 12.dp)
                ) {
                    ClockIcon(color = Held, size = 14)
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = "Expires in $minutes min",
                        fontSize = 13.sp,
                        color = Held,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }

            // 4. HoldToApprove button
            if (isSigning) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp)
                        .background(Primary, RoundedCornerShape(999.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = ApprovalCopy.SIGNING,
                        color = Color.White,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Medium,
                    )
                }
            } else {
                HoldToApproveButton(
                    amountText = payment.amountFigures,
                    onApproved = onApprove,
                )
            }

            Spacer(Modifier.height(12.dp))

            // 5. Decline button
            OutlinedButton(
                onClick = onDecline,
                enabled = !isSigning,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                shape = RoundedCornerShape(999.dp),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = LineStrong,
                ),
            ) {
                Text(
                    text = "Decline",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium,
                    color = Ink,
                )
            }

            Spacer(Modifier.height(8.dp))

            // Report fraud text button
            TextButton(
                onClick = onReportFraud,
                enabled = !isSigning,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(44.dp),
            ) {
                Text(
                    text = "Report fraud",
                    color = Blocked,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                )
            }
        }
    }
}

/**
 * ChangedField: old value struck through, arrow, new value in red on a soft red card.
 */
@Composable
private fun ChangedFieldCard(reason: Reason) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(BlockedSoft, RoundedCornerShape(12.dp))
            .padding(14.dp)
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Icon(
                imageVector = Icons.Filled.Warning,
                contentDescription = "Warning",
                tint = Blocked,
                modifier = Modifier
                    .size(20.dp)
                    .padding(top = 2.dp),
            )
            Spacer(Modifier.width(10.dp))
            Column {
                Text(
                    text = reason.text,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    color = Blocked,
                )
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = reason.changedFrom ?: "",
                        fontSize = 14.sp,
                        color = InkMuted,
                        textDecoration = TextDecoration.LineThrough,
                    )
                    Text(
                        text = "  →  ",
                        fontSize = 14.sp,
                        color = InkMuted,
                    )
                    Text(
                        text = reason.changedTo ?: "",
                        fontSize = 14.sp,
                        color = Blocked,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
        }
    }
}

/**
 * ReasonChip: soft rounded pill with text and source badge.
 */
@Composable
private fun ReasonChipView(reason: Reason) {
    Box(
        modifier = Modifier
            .background(NeutralSoft, RoundedCornerShape(999.dp))
            .padding(horizontal = 12.dp, vertical = 6.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = reason.text,
                fontSize = 13.sp,
                color = Ink,
            )
        }
    }
}

/**
 * AiExplanation: soft card labelled "AI summary · Gemini" with sparkles.
 */
@Composable
private fun AiExplanationCard(explanation: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrimaryContainer, RoundedCornerShape(12.dp))
            .padding(14.dp)
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SparkleIcon(color = Primary, size = 16)
                Spacer(Modifier.width(6.dp))
                Text(
                    text = ApprovalCopy.GEMINI_LABEL,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    color = Primary,
                )
            }
            Spacer(Modifier.height(6.dp))
            Text(
                text = explanation,
                fontSize = 14.sp,
                lineHeight = 20.sp,
                color = Ink,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Gemini flagged this change. Your signature releases it.",
                fontSize = 12.sp,
                color = InkMuted,
            )
        }
    }
}

/**
 * HoldToApprove: Press-and-hold button filling with primaryDeep over 1 second.
 */
@Composable
fun HoldToApproveButton(
    amountText: String,
    onApproved: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var isHolding by remember { mutableStateOf(false) }
    var holdFraction by remember { mutableFloatStateOf(0f) }
    var triggered by remember { mutableStateOf(false) }

    val animatedFraction by animateFloatAsState(
        targetValue = holdFraction,
        animationSpec = if (isHolding) tween(durationMillis = 50) else tween(durationMillis = 200),
        label = "HoldProgress",
    )

    LaunchedEffect(isHolding) {
        if (isHolding && !triggered) {
            val startTime = System.currentTimeMillis()
            while (isHolding && !triggered) {
                val elapsed = System.currentTimeMillis() - startTime
                val progress = (elapsed / 1000f).coerceIn(0f, 1f)
                holdFraction = progress
                if (progress >= 1.0f) {
                    triggered = true
                    onApproved()
                    break
                }
                delay(30)
            }
        } else if (!isHolding && !triggered) {
            holdFraction = 0f
        }
    }

    Column(modifier = modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
                .clip(RoundedCornerShape(999.dp))
                .background(Primary)
                .pointerInput(triggered) {
                    if (!triggered) {
                        awaitEachGesture {
                            awaitFirstDown(requireUnconsumed = false)
                            isHolding = true
                            waitForUpOrCancellation()
                            isHolding = false
                        }
                    }
                },
            contentAlignment = Alignment.CenterStart,
        ) {
            // Progress fill bar from left to right in primaryDeep
            Box(
                modifier = Modifier
                    .fillMaxWidth(animatedFraction)
                    .fillMaxHeight()
                    .background(PrimaryDeep)
            )

            // Centered content
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                FingerprintIcon(color = Color.White, size = 20)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = when {
                        triggered -> "Signed on this phone"
                        isHolding -> "Keep holding…"
                        else -> "Hold to approve $amountText"
                    },
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium,
                )
            }
        }

        Spacer(Modifier.height(6.dp))
        Text(
            text = "Try it: press and hold for one second",
            fontSize = 12.sp,
            color = InkMuted,
        )
    }
}

/**
 * ReleasedScreen: The green celebration screen after successful signing and release.
 */
@Composable
fun ReleasedScreen(
    payment: ApprovalPayment,
    onBack: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        StateHeaderBand(bandColor = BandReleased) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Row(modifier = Modifier.fillMaxWidth()) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Ink)
                    }
                }

                // Big green tick circle (96dp)
                Box(
                    modifier = Modifier
                        .size(96.dp)
                        .background(ReleasedSoft, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = Icons.Filled.Check,
                        contentDescription = "Released",
                        tint = Released,
                        modifier = Modifier.size(54.dp),
                    )
                }

                Spacer(Modifier.height(16.dp))

                Text(
                    text = "Approved and released",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Medium,
                    color = Ink,
                )

                Spacer(Modifier.height(8.dp))

                Text(
                    text = payment.amountFigures,
                    fontSize = 38.sp,
                    fontWeight = FontWeight.Bold,
                    color = Ink,
                )

                Text(
                    text = "to ${payment.payeeNameAtBank} ••${payment.payeeAccountFull.takeLast(4)}",
                    fontSize = 15.sp,
                    color = InkMuted,
                )

                Spacer(Modifier.height(8.dp))

                // Hardware-backed badge
                Box(
                    modifier = Modifier
                        .background(Color.White, RoundedCornerShape(999.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = "Signed on this phone · StrongBox hardware",
                        fontSize = 13.sp,
                        color = Released,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = ApprovalCopy.SIGNED_APPROVE,
                fontSize = 15.sp,
                lineHeight = 22.sp,
                color = InkMuted,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(32.dp))

            OutlinedButton(
                onClick = onBack,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                shape = RoundedCornerShape(999.dp),
            ) {
                Text("Back to approvals", color = Primary)
            }
        }
    }
}

@Composable
private fun NonApprovedScreen(
    payment: ApprovalPayment,
    decision: Decision,
    onBack: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        StateHeaderBand(bandColor = BandBlocked) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Row(modifier = Modifier.fillMaxWidth()) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Ink)
                    }
                }

                Box(
                    modifier = Modifier
                        .size(80.dp)
                        .background(BlockedSoft, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = Icons.Filled.Warning,
                        contentDescription = "Declined",
                        tint = Blocked,
                        modifier = Modifier.size(44.dp),
                    )
                }

                Spacer(Modifier.height(16.dp))

                Text(
                    text = if (decision == Decision.DECLINE) "Declined" else "Reported as fraud",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Medium,
                    color = Ink,
                )

                Text(
                    text = "${payment.amountFigures} to ${payment.payeeNameAtBank}",
                    fontSize = 15.sp,
                    color = InkMuted,
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = ApprovalCopy.signed(decision),
                fontSize = 15.sp,
                lineHeight = 22.sp,
                color = InkMuted,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(32.dp))

            OutlinedButton(
                onClick = onBack,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                shape = RoundedCornerShape(999.dp),
            ) {
                Text("Back to approvals", color = Primary)
            }
        }
    }
}

@Composable
private fun FailedScreen(
    state: ApprovalState.Failed,
    onRetry: () -> Unit,
    onBack: () -> Unit,
    minutesRemaining: (ApprovalPayment) -> Long,
) {
    ReadyApprovalScreen(
        payment = state.payment,
        onApprove = onRetry,
        onDecline = onBack,
        onReportFraud = {},
        onBack = onBack,
        minutesRemaining = minutesRemaining,
        isSigning = false,
    )
}

@Composable
private fun CannotApproveScreen(
    state: ApprovalState.CannotApprove,
    onBack: () -> Unit,
    minutesRemaining: (ApprovalPayment) -> Long,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        StateHeaderBand(bandColor = BandHeld) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Row(modifier = Modifier.fillMaxWidth()) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Ink)
                    }
                }
                Text(
                    text = state.payment.amountFigures,
                    fontSize = 38.sp,
                    fontWeight = FontWeight.Bold,
                    color = Ink,
                )
                Text(
                    text = "to ${state.payment.payeeNameAtBank}",
                    fontSize = 15.sp,
                    color = InkMuted,
                )
            }
        }

        Column(modifier = Modifier.padding(20.dp)) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(HeldSoft, RoundedCornerShape(12.dp))
                    .padding(14.dp)
            ) {
                Text(
                    text = ApprovalCopy.blocked(state.blocker, state.expiredAtIst),
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    color = Held,
                )
            }

            if (state.decidedBy != null) {
                Spacer(Modifier.height(12.dp))
                Text(
                    text = "Decided by ${state.decidedBy} (${state.decidedWhat ?: ""})" +
                        (state.decidedAtIst?.let { ", $it" } ?: ""),
                    fontSize = 13.sp,
                    color = InkMuted,
                )
            }

            Spacer(Modifier.height(24.dp))

            OutlinedButton(
                onClick = onBack,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                shape = RoundedCornerShape(999.dp),
            ) {
                Text("Back to approvals", color = Primary)
            }
        }
    }
}

@Composable
private fun LoadingSkeleton() {
    Column(
        Modifier
            .fillMaxSize()
            .padding(20.dp)
    ) {
        Box(
            Modifier
                .fillMaxWidth(0.7f)
                .height(32.dp)
                .background(SurfaceContainer, RoundedCornerShape(8.dp))
        )
        Spacer(Modifier.height(16.dp))
        Box(
            Modifier
                .fillMaxWidth(0.5f)
                .height(18.dp)
                .background(SurfaceContainer, RoundedCornerShape(8.dp))
        )
        Spacer(Modifier.height(24.dp))
        Box(
            Modifier
                .fillMaxWidth(0.8f)
                .height(56.dp)
                .background(SurfaceContainer, RoundedCornerShape(8.dp))
        )
        Spacer(Modifier.height(32.dp))
        Box(
            Modifier
                .fillMaxWidth()
                .height(80.dp)
                .background(SurfaceContainer, RoundedCornerShape(12.dp))
        )
    }
}

// ----------------- Custom Vector Icons -----------------

@Composable
fun ClockIcon(color: Color, size: Int = 16) {
    Canvas(modifier = Modifier.size(size.dp)) {
        val r = this.size.minDimension / 2f - 2f
        val c = Offset(this.size.width / 2f, this.size.height / 2f)
        drawCircle(color = color, radius = r, center = c, style = Stroke(width = 1.8f))
        // Hands
        drawLine(
            color = color,
            start = c,
            end = Offset(c.x, c.y - r * 0.55f),
            strokeWidth = 1.8f,
            cap = StrokeCap.Round,
        )
        drawLine(
            color = color,
            start = c,
            end = Offset(c.x + r * 0.45f, c.y),
            strokeWidth = 1.8f,
            cap = StrokeCap.Round,
        )
    }
}

@Composable
fun SparkleIcon(color: Color, size: Int = 16) {
    Canvas(modifier = Modifier.size(size.dp)) {
        val w = this.size.width
        val h = this.size.height
        val path = Path().apply {
            moveTo(w / 2f, 0f)
            quadraticTo(w / 2f, h / 2f, w, h / 2f)
            quadraticTo(w / 2f, h / 2f, w / 2f, h)
            quadraticTo(w / 2f, h / 2f, 0f, h / 2f)
            quadraticTo(w / 2f, h / 2f, w / 2f, 0f)
            close()
        }
        drawPath(path = path, color = color)
    }
}

@Composable
fun FingerprintIcon(color: Color, size: Int = 20) {
    Canvas(modifier = Modifier.size(size.dp)) {
        val c = Offset(this.size.width / 2f, this.size.height / 2f)
        val stroke = Stroke(width = 1.8f, cap = StrokeCap.Round)
        // Concentric fingerprint arches
        drawArc(
            color = color,
            startAngle = 180f,
            sweepAngle = 180f,
            useCenter = false,
            topLeft = Offset(c.x - 3f, c.y - 4f),
            size = androidx.compose.ui.geometry.Size(6f, 8f),
            style = stroke,
        )
        drawArc(
            color = color,
            startAngle = 160f,
            sweepAngle = 220f,
            useCenter = false,
            topLeft = Offset(c.x - 6f, c.y - 7f),
            size = androidx.compose.ui.geometry.Size(12f, 14f),
            style = stroke,
        )
        drawArc(
            color = color,
            startAngle = 150f,
            sweepAngle = 240f,
            useCenter = false,
            topLeft = Offset(c.x - 9f, c.y - 10f),
            size = androidx.compose.ui.geometry.Size(18f, 20f),
            style = stroke,
        )
    }
}
