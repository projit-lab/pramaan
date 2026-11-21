package dev.pramaan.app

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import dev.pramaan.app.approval.ApprovalApi
import dev.pramaan.app.approval.ApprovalPayment
import dev.pramaan.app.approval.ApprovalScreen
import dev.pramaan.app.approval.ApprovalViewModel
import dev.pramaan.app.approval.ApproverHomeScreen
import dev.pramaan.app.approval.Reason
import dev.pramaan.app.approval.SignedDecision
import dev.pramaan.app.approval.SubmitOutcome
import dev.pramaan.app.theme.PramaanTheme
import dev.pramaan.crypto.FakeKeySigner

/**
 * Debug-only launcher activity that starts directly into the seeded
 * Kaveri Steel Traders approval screen, powered by FakeKeySigner.
 */
class ApprovalPreviewActivity : FragmentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val signer = FakeKeySigner()
        val api = object : ApprovalApi {
            override suspend fun submit(signed: SignedDecision): SubmitOutcome {
                return SubmitOutcome.Accepted
            }
        }

        val kaveriPayment = ApprovalPayment(
            approvalId = "ap_01JD2XKAVERI0001",
            intentId = "pi_01JD2XKAVERI0001",
            payeeNameAtBank = "Kaveri Steel Traders",
            payeeAccountFull = "000123458117",
            payeeIfsc = "EFGH0005540",
            amountPaise = "184000000", // ₹18,40,000
            purposeInvoice = "INV-2026-4471",
            raisedBy = "clerk@acme.example",
            raisedByIsAgent = false,
            tier = 2,
            reasons = listOf(
                Reason(
                    text = "Bank account changed",
                    source = "rule",
                    changedFrom = "••5540",
                    changedTo = "••8117",
                ),
                Reason(text = "Unusual time", source = "rule"),
                Reason(text = "First time payee", source = "rule"),
            ),
            geminiExplanation = "This invoice asks you to pay a new account added two days ago, and the amount is four times what Acme usually pays this vendor. Call the vendor on the number in your records before approving.",
            expiresAtMillis = System.currentTimeMillis() + 60 * 60 * 1000,
        )

        val canonical = mapOf(
            "amount_paise" to "184000000",
            "currency" to "INR",
            "expires_at" to "2027-11-21T11:42:07+05:30",
            "initiator" to "human:clerk@acme.example",
            "intent_id" to "pi_01JD2XKAVERI0001",
            "payee_account" to "000123458117",
            "payee_ifsc" to "EFGH0005540",
            "payee_name" to "Kaveri Steel Traders",
            "payer_account" to "50100004521",
            "purpose" to "INV-2026-4471",
            "v" to "1",
        )

        val viewModel = ApprovalViewModel(signer, api)
        viewModel.load(kaveriPayment, canonical)

        setContent {
            PramaanTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    var currentScreen by remember { mutableStateOf("approval") }
                    val state by viewModel.state.collectAsState()

                    if (currentScreen == "approval") {
                        ApprovalScreen(
                            state = state,
                            onApprove = { viewModel.approve() },
                            onDecline = { viewModel.decline() },
                            onReportFraud = { viewModel.reportFraud() },
                            onRetry = { viewModel.approve() },
                            minutesRemaining = { 54 },
                            onBack = { currentScreen = "home" },
                        )
                    } else {
                        ApproverHomeScreen(
                            approverName = "Prajit",
                            onOpenPayment = { currentScreen = "approval" },
                        )
                    }
                }
            }
        }
    }
}
