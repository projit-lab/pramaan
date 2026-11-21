package dev.pramaan.app.approval

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.pramaan.app.theme.BandRest
import dev.pramaan.app.theme.Held
import dev.pramaan.app.theme.HeldSoft
import dev.pramaan.app.theme.Ink
import dev.pramaan.app.theme.InkMuted
import dev.pramaan.app.theme.Line
import dev.pramaan.app.theme.NeutralSoft
import dev.pramaan.app.theme.Primary
import dev.pramaan.app.theme.PrimaryContainer
import dev.pramaan.app.theme.SecondaryContainer
import dev.pramaan.app.theme.SurfaceContainer

/**
 * The approver's landing screen, built to PRAMAAN_BRAND_KIT.md Part E (ApproverHome).
 */
@Composable
fun ApproverHomeScreen(
    approverName: String = "Prajit",
    onOpenPayment: (String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = Color.White,
    ) {
        Column(
            modifier = Modifier.fillMaxSize()
        ) {
            // Scrollable main content
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
            ) {
                // Top blue state band (#C2DBFF)
                StateHeaderBand(bandColor = BandRest) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 16.dp)
                    ) {
                        // Search pill + Avatar
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .height(44.dp)
                                    .background(Color.White, RoundedCornerShape(999.dp))
                                    .padding(horizontal = 16.dp),
                                contentAlignment = Alignment.CenterStart,
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Filled.Search,
                                        contentDescription = "Search",
                                        tint = InkMuted,
                                        modifier = Modifier.size(20.dp),
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Text(
                                        text = "Search payments",
                                        fontSize = 15.sp,
                                        color = InkMuted,
                                    )
                                }
                            }

                            Spacer(Modifier.width(12.dp))

                            // Approver avatar circle
                            Box(
                                modifier = Modifier
                                    .size(44.dp)
                                    .background(Color.White, CircleShape),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(
                                    text = approverName.take(1).uppercase(),
                                    fontSize = 18.sp,
                                    fontWeight = FontWeight.Medium,
                                    color = Ink,
                                )
                            }
                        }

                        Spacer(Modifier.height(20.dp))

                        // Greeting & Count hero
                        Text(
                            text = "Good morning, $approverName",
                            fontSize = 15.sp,
                            color = InkMuted,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = "2 payments\nneed you",
                            fontSize = 34.sp,
                            lineHeight = 40.sp,
                            fontWeight = FontWeight.Bold,
                            color = Ink,
                        )

                        Spacer(Modifier.height(14.dp))

                        // Phone key reassurance row
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            FingerprintIcon(color = Primary, size = 18)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = "Your phone key is hardware-protected",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Medium,
                                color = Ink,
                            )
                        }
                    }
                }

                // Main sheet content
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 20.dp)
                ) {
                    // Four ActionTiles
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        ActionTile(
                            label = "Pending\napprovals",
                            count = 2,
                            onClick = { onOpenPayment("kaveri") },
                        )
                        ActionTile(
                            label = "Signed\nmandates",
                            onClick = {},
                        )
                        ActionTile(
                            label = "Hardware\nkey",
                            onClick = {},
                        )
                        ActionTile(
                            label = "Settings",
                            onClick = {},
                        )
                    }

                    Spacer(Modifier.height(28.dp))

                    Text(
                        text = "Waiting for you",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Medium,
                        color = Ink,
                    )

                    Spacer(Modifier.height(12.dp))

                    // Payment row 1: Kaveri Steel Traders
                    PaymentListRow(
                        avatarInitial = "K",
                        payeeName = "Kaveri Steel Traders",
                        subtitle = "Bank account changed ••5540 → ••8117 · 2 min ago",
                        amountText = "₹18,40,000",
                        onClick = { onOpenPayment("kaveri") },
                    )

                    Spacer(Modifier.height(8.dp))

                    // Payment row 2: ACME Corp
                    PaymentListRow(
                        avatarInitial = "A",
                        payeeName = "ACME Corp",
                        subtitle = "First time payee · 5 min ago",
                        amountText = "₹3,20,000",
                        onClick = { onOpenPayment("acme") },
                    )
                }
            }

            // Bottom Navigation Bar
            ApproverBottomNav()
        }
    }
}

@Composable
private fun ActionTile(
    label: String,
    count: Int? = null,
    onClick: () -> Unit,
) {
    Column(
        modifier = Modifier
            .width(76.dp)
            .clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier.size(64.dp),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                modifier = Modifier
                    .size(60.dp)
                    .background(PrimaryContainer, RoundedCornerShape(18.dp)),
                contentAlignment = Alignment.Center,
            ) {
                FingerprintIcon(color = Primary, size = 26)
            }

            if (count != null && count > 0) {
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .background(Held, CircleShape)
                        .border(2.dp, Color.White, CircleShape)
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = "$count",
                        color = Color.White,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        Spacer(Modifier.height(6.dp))

        Text(
            text = label,
            fontSize = 12.sp,
            lineHeight = 15.sp,
            color = Ink,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
    }
}

@Composable
private fun PaymentListRow(
    avatarInitial: String,
    payeeName: String,
    subtitle: String,
    amountText: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceContainer)
            .clickable(onClick = onClick)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(44.dp)
                .background(PrimaryContainer, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = avatarInitial,
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium,
                color = Primary,
            )
        }

        Spacer(Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = payeeName,
                fontSize = 15.sp,
                fontWeight = FontWeight.Medium,
                color = Ink,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                text = subtitle,
                fontSize = 12.sp,
                color = InkMuted,
            )
        }

        Spacer(Modifier.width(8.dp))

        Column(horizontalAlignment = Alignment.End) {
            Text(
                text = amountText,
                fontSize = 15.sp,
                fontWeight = FontWeight.Medium,
                color = Ink,
            )
            Spacer(Modifier.height(4.dp))
            Box(
                modifier = Modifier
                    .background(HeldSoft, RoundedCornerShape(999.dp))
                    .padding(horizontal = 8.dp, vertical = 2.dp)
            ) {
                Text(
                    text = "Held",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium,
                    color = Held,
                )
            }
        }
    }
}

@Composable
private fun ApproverBottomNav() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(SurfaceContainer)
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceAround,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BottomNavItem(label = "Home", isSelected = true)
        BottomNavItem(label = "History", isSelected = false)
        BottomNavItem(label = "Key", isSelected = false)
        BottomNavItem(label = "Profile", isSelected = false)
    }
}

@Composable
private fun BottomNavItem(label: String, isSelected: Boolean) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
    ) {
        Box(
            modifier = Modifier
                .size(width = 54.dp, height = 28.dp)
                .background(
                    if (isSelected) SecondaryContainer else Color.Transparent,
                    RoundedCornerShape(999.dp),
                ),
            contentAlignment = Alignment.Center,
        ) {
            FingerprintIcon(
                color = if (isSelected) Primary else InkMuted,
                size = 18,
            )
        }
        Spacer(Modifier.height(2.dp))
        Text(
            text = label,
            fontSize = 11.sp,
            fontWeight = if (isSelected) FontWeight.Medium else FontWeight.Normal,
            color = if (isSelected) Ink else InkMuted,
        )
    }
}
