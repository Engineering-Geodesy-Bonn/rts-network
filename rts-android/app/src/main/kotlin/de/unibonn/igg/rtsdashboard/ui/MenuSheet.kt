package de.unibonn.igg.rtsdashboard.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import de.unibonn.igg.rtsdashboard.R

/** Opened with the back gesture when the dashboard cannot go back any further. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MenuSheet(onDismiss: () -> Unit, onReload: () -> Unit, onSettings: () -> Unit, onExit: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface) {
        Item(R.drawable.ic_refresh, R.string.menu_reload, onReload)
        Item(R.drawable.ic_tune, R.string.settings_title, onSettings)
        Item(R.drawable.ic_exit, R.string.menu_exit, onExit)
    }
}

@Composable
private fun Item(icon: Int, label: Int, onClick: () -> Unit) {
    ListItem(
        headlineContent = { Text(stringResource(label)) },
        leadingContent = { Icon(painterResource(icon), contentDescription = null) },
        colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.clickable(onClick = onClick).padding(horizontal = 8.dp),
    )
}
