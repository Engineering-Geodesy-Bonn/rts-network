package de.unibonn.igg.rtsdashboard.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import de.unibonn.igg.rtsdashboard.R
import de.unibonn.igg.rtsdashboard.Status

private data class Message(val title: String, val text: String, val busy: Boolean)

@Composable
private fun describe(status: Status): Message = when (status) {
    Status.NotConfigured -> Message(stringResource(R.string.status_not_configured_title), stringResource(R.string.status_not_configured), false)
    Status.NeedsPermission -> Message(stringResource(R.string.status_permission_title), stringResource(R.string.status_permission), false)
    Status.PermissionDenied -> Message(stringResource(R.string.status_permission_denied_title), stringResource(R.string.status_permission_denied), false)
    is Status.Connecting -> Message(stringResource(R.string.status_connecting_title, status.ssid), stringResource(R.string.status_connecting), true)
    is Status.Lost -> Message(stringResource(R.string.status_lost_title, status.ssid), stringResource(R.string.status_lost), true)
    is Status.Unavailable -> Message(stringResource(R.string.status_unavailable_title, status.ssid), stringResource(R.string.status_unavailable), false)
    is Status.Loading -> Message(stringResource(R.string.status_loading_title), status.url, true)
    is Status.Unreachable -> Message(stringResource(R.string.status_unreachable_title), stringResource(R.string.status_unreachable, status.url, status.error), false)
    Status.Ready -> Message("", "", false)
}

@Composable
fun StatusScreen(status: Status, onRetry: () -> Unit, onSettings: () -> Unit, onAppSettings: () -> Unit) {
    val message = describe(status)
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 32.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Image(painterResource(R.drawable.logo), contentDescription = null, modifier = Modifier.height(104.dp))
        Spacer(Modifier.height(40.dp))

        if (message.busy) {
            CircularProgressIndicator(Modifier.size(36.dp), strokeWidth = 3.dp)
            Spacer(Modifier.height(24.dp))
        }
        Text(
            message.title,
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            message.text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.widthIn(max = 420.dp),
        )
        Spacer(Modifier.height(32.dp))

        val buttonWidth = Modifier.widthIn(min = 200.dp)
        when {
            status == Status.NotConfigured -> Button(onClick = onSettings, modifier = buttonWidth) {
                ButtonIcon(R.drawable.ic_tune)
                Text(stringResource(R.string.settings_title))
            }

            status == Status.PermissionDenied -> {
                Button(onClick = onAppSettings, modifier = buttonWidth) { Text(stringResource(R.string.open_app_settings)) }
                TextButton(onClick = onRetry, modifier = buttonWidth) { Text(stringResource(R.string.retry)) }
            }

            else -> {
                if (!message.busy) {
                    Button(onClick = onRetry, modifier = buttonWidth) {
                        ButtonIcon(R.drawable.ic_refresh)
                        Text(stringResource(R.string.retry))
                    }
                    Spacer(Modifier.height(8.dp))
                }
                OutlinedButton(onClick = onSettings, modifier = buttonWidth) {
                    ButtonIcon(R.drawable.ic_tune)
                    Text(stringResource(R.string.settings_title))
                }
            }
        }
    }
}

@Composable
private fun ButtonIcon(id: Int) {
    Icon(painterResource(id), contentDescription = null, modifier = Modifier.size(ButtonDefaults.IconSize))
    Spacer(Modifier.size(ButtonDefaults.IconSpacing))
}
