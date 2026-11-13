package de.unibonn.igg.rtsdashboard.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

// The colors of the dashboard (rts-dashboard/src/app.css), so that app and dashboard look alike.

/** Header and bottom navigation of the dashboard; also behind the system bars */
data class BarColors(val background: Color, val content: Color, val muted: Color)

private val LightBar = BarColors(Color(0xFF1A1F26), Color(0xFFE9ECEF), Color(0xFF98A2AD))
private val DarkBar = BarColors(Color(0xFF090B0E), Color(0xFFE6E9ED), Color(0xFF8A949F))

val LocalBarColors = staticCompositionLocalOf { DarkBar }

private val Light = lightColorScheme(
    primary = Color(0xFF1D5FC9),
    onPrimary = Color(0xFFFFFFFF),
    background = Color(0xFFECEEF1),
    onBackground = Color(0xFF14181D),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF14181D),
    surfaceVariant = Color(0xFFF5F6F8),
    onSurfaceVariant = Color(0xFF5A6470),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFFFFFFF),
    surfaceContainer = Color(0xFFF5F6F8),
    surfaceContainerHigh = Color(0xFFF5F6F8),
    surfaceContainerHighest = Color(0xFFECEEF1),
    outline = Color(0xFFC3C9D1),
    outlineVariant = Color(0xFFD8DCE2),
    error = Color(0xFFC0261A),
    errorContainer = Color(0xFFFBE6E3),
    onErrorContainer = Color(0xFFC0261A),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF5B9BFF),
    onPrimary = Color(0xFF0D1014),
    background = Color(0xFF0D1014),
    onBackground = Color(0xFFE6E9ED),
    surface = Color(0xFF151A20),
    onSurface = Color(0xFFE6E9ED),
    surfaceVariant = Color(0xFF1B2128),
    onSurfaceVariant = Color(0xFF98A2AD),
    surfaceContainerLowest = Color(0xFF0D1014),
    surfaceContainerLow = Color(0xFF151A20),
    surfaceContainer = Color(0xFF151A20),
    surfaceContainerHigh = Color(0xFF1B2128),
    surfaceContainerHighest = Color(0xFF222A33),
    outline = Color(0xFF36404B),
    outlineVariant = Color(0xFF283039),
    error = Color(0xFFF1675A),
    errorContainer = Color(0xFF2F1512),
    onErrorContainer = Color(0xFFF1675A),
)

@Composable
fun RtsTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    androidx.compose.runtime.CompositionLocalProvider(LocalBarColors provides if (dark) DarkBar else LightBar) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, content = content)
    }
}
