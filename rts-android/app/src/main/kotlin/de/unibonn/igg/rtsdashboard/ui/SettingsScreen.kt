package de.unibonn.igg.rtsdashboard.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import de.unibonn.igg.rtsdashboard.R
import de.unibonn.igg.rtsdashboard.Settings

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(initial: Settings, canClose: Boolean, onSave: (Settings) -> Unit, onClose: () -> Unit) {
    var connectWifi by rememberSaveable { mutableStateOf(initial.connectWifi) }
    var ssid by rememberSaveable { mutableStateOf(initial.ssid) }
    var passphrase by rememberSaveable { mutableStateOf(initial.passphrase) }
    var url by rememberSaveable { mutableStateOf(initial.url) }
    var showPassphrase by rememberSaveable { mutableStateOf(false) }

    val settings = Settings(connectWifi, ssid, passphrase, url)
    val valid = !settings.incomplete && url.isNotBlank()
    val bar = LocalBarColors.current

    BackHandler(enabled = canClose, onBack = onClose)

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = {
                    if (canClose) {
                        IconButton(onClick = onClose) {
                            Icon(painterResource(R.drawable.ic_close), contentDescription = stringResource(R.string.close))
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = bar.background,
                    titleContentColor = bar.content,
                    navigationIconContentColor = bar.content,
                ),
            )
        },
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.background) {
                Column {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    Button(
                        onClick = { onSave(settings) },
                        enabled = valid,
                        modifier = Modifier
                            .windowInsetsPadding(WindowInsets.navigationBars.union(WindowInsets.ime))
                            .padding(16.dp)
                            .fillMaxWidth(),
                    ) { Text(stringResource(R.string.settings_connect)) }
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Surface(
                color = MaterialTheme.colorScheme.surface,
                shape = MaterialTheme.shapes.medium,
                onClick = { connectWifi = !connectWifi },
            ) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f).padding(end = 16.dp)) {
                        Text(stringResource(R.string.settings_connect_wifi), style = MaterialTheme.typography.titleMedium)
                        Text(
                            stringResource(R.string.settings_connect_wifi_hint),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = connectWifi, onCheckedChange = { connectWifi = it })
                }
            }

            OutlinedTextField(
                value = ssid,
                onValueChange = { ssid = it },
                enabled = connectWifi,
                label = { Text(stringResource(R.string.settings_ssid)) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = passphrase,
                onValueChange = { passphrase = it },
                enabled = connectWifi,
                label = { Text(stringResource(R.string.settings_passphrase)) },
                singleLine = true,
                visualTransformation = if (showPassphrase) VisualTransformation.None else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Next),
                trailingIcon = {
                    IconButton(onClick = { showPassphrase = !showPassphrase }) {
                        Icon(
                            painterResource(if (showPassphrase) R.drawable.ic_visibility_off else R.drawable.ic_visibility),
                            contentDescription = stringResource(if (showPassphrase) R.string.hide_password else R.string.show_password),
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text(stringResource(R.string.settings_url)) },
                supportingText = { Text(stringResource(R.string.settings_url_hint, Settings.DEFAULT_URL)) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
