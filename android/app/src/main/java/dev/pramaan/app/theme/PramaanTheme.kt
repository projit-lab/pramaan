package dev.pramaan.app.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * Pramaan Design Tokens from PRAMAAN_BRAND_KIT.md (Part C).
 * Light theme only.
 */
val Primary = Color(0xFF0B57D0)
val OnPrimary = Color(0xFFFFFFFF)
val PrimaryDeep = Color(0xFF062E6F)
val PrimaryContainer = Color(0xFFD3E3FD)
val OnPrimaryContainer = Color(0xFF041E49)
val SecondaryContainer = Color(0xFFC2E7FF)
val OnSecondaryContainer = Color(0xFF001D35)
val Background = Color(0xFFFFFFFF)
val Surface = Color(0xFFFFFFFF)
val SurfaceContainer = Color(0xFFF0F4F9)
val SurfaceContainerHigh = Color(0xFFE9EEF6)

// State and band tokens
val BandRest = Color(0xFFC2DBFF)
val BandHeld = Color(0xFFFFE2AE)
val BandReleased = Color(0xFFC8EED2)
val BandBlocked = Color(0xFFFFD9D4)

// Status tokens
val Held = Color(0xFF7A4100)
val HeldSoft = Color(0xFFFFEFD6)
val Released = Color(0xFF146C2E)
val ReleasedSoft = Color(0xFFE6F4EA)
val Blocked = Color(0xFFB3261E)
val BlockedSoft = Color(0xFFFCE8E6)
val OnBlocked = Color(0xFFFFFFFF)
val NeutralSoft = Color(0xFFE9EEF6)
val TierHigh = Color(0xFF8E3A00)
val TierHighSoft = Color(0xFFFFDBC8)

// Neutral text & lines
val Ink = Color(0xFF1F1F1F)
val InkMuted = Color(0xFF444746)
val Line = Color(0xFFE1E3E1)
val LineStrong = Color(0xFF747775)
val GeminiViolet = Color(0xFF6B4FA0)

@Immutable
data class PramaanColors(
    val primary: Color = Primary,
    val onPrimary: Color = OnPrimary,
    val primaryDeep: Color = PrimaryDeep,
    val primaryContainer: Color = PrimaryContainer,
    val onPrimaryContainer: Color = OnPrimaryContainer,
    val secondaryContainer: Color = SecondaryContainer,
    val onSecondaryContainer: Color = OnSecondaryContainer,
    val background: Color = Background,
    val surface: Color = Surface,
    val surfaceContainer: Color = SurfaceContainer,
    val surfaceContainerHigh: Color = SurfaceContainerHigh,
    val bandRest: Color = BandRest,
    val bandHeld: Color = BandHeld,
    val bandReleased: Color = BandReleased,
    val bandBlocked: Color = BandBlocked,
    val held: Color = Held,
    val heldSoft: Color = HeldSoft,
    val released: Color = Released,
    val releasedSoft: Color = ReleasedSoft,
    val blocked: Color = Blocked,
    val blockedSoft: Color = BlockedSoft,
    val onBlocked: Color = OnBlocked,
    val neutralSoft: Color = NeutralSoft,
    val tierHigh: Color = TierHigh,
    val tierHighSoft: Color = TierHighSoft,
    val ink: Color = Ink,
    val inkMuted: Color = InkMuted,
    val line: Color = Line,
    val lineStrong: Color = LineStrong,
    val geminiViolet: Color = GeminiViolet,
)

val LocalPramaanColors = staticCompositionLocalOf { PramaanColors() }

val PramaanLightColorScheme = lightColorScheme(
    primary = Primary,
    onPrimary = OnPrimary,
    primaryContainer = PrimaryContainer,
    onPrimaryContainer = OnPrimaryContainer,
    secondaryContainer = SecondaryContainer,
    onSecondaryContainer = OnSecondaryContainer,
    background = Background,
    onBackground = Ink,
    surface = Surface,
    onSurface = Ink,
    surfaceVariant = SurfaceContainer,
    onSurfaceVariant = InkMuted,
    outline = Line,
    outlineVariant = LineStrong,
    error = Blocked,
    onError = OnBlocked,
    errorContainer = BlockedSoft,
    onErrorContainer = Blocked,
)

object PramaanTheme {
    val colors: PramaanColors
        @Composable
        get() = LocalPramaanColors.current
}

@Composable
fun PramaanTheme(
    colors: PramaanColors = PramaanColors(),
    content: @Composable () -> Unit,
) {
    CompositionLocalProvider(LocalPramaanColors provides colors) {
        MaterialTheme(
            colorScheme = PramaanLightColorScheme,
            content = content,
        )
    }
}
