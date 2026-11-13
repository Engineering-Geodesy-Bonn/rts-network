package de.unibonn.igg.rtsdashboard.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.provider.Settings as AndroidSettings
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import de.unibonn.igg.rtsdashboard.DashboardViewModel
import de.unibonn.igg.rtsdashboard.DownloadBridge
import de.unibonn.igg.rtsdashboard.Status

@Composable
fun App(viewModel: DashboardViewModel, onExit: () -> Unit) {
    val status by viewModel.status.collectAsStateWithLifecycle()
    val settings by viewModel.settings.collectAsStateWithLifecycle()
    var showSettings by rememberSaveable { mutableStateOf(settings.incomplete) }
    var showMenu by rememberSaveable { mutableStateOf(false) }
    val context = LocalContext.current

    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission(), viewModel::onPermissionResult)
    LaunchedEffect(status) {
        if (status == Status.NeedsPermission) permission.launch(DashboardViewModel.PERMISSION_LOCAL_NETWORK)
    }

    val webView = rememberDashboardWebView(viewModel)
    LaunchedEffect(status) {
        (status as? Status.Loading)?.let { webView.loadUrl(it.url) }
    }
    LaunchedEffect(webView) {
        // a new WebView (activity recreated) is empty
        if (viewModel.status.value == Status.Ready) viewModel.reload()
    }

    BackHandler(enabled = !showSettings) {
        if (status == Status.Ready && webView.canGoBack()) webView.goBack() else showMenu = true
    }

    // The bar color of the dashboard behind the status and navigation bars
    Box(Modifier.fillMaxSize().background(LocalBarColors.current.background)) {
        Box(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing)) {
            AndroidView(factory = { webView }, modifier = Modifier.fillMaxSize())
            AnimatedVisibility(visible = status != Status.Ready, enter = fadeIn(), exit = fadeOut()) {
                StatusScreen(
                    status = status,
                    onRetry = viewModel::connect,
                    onSettings = { showSettings = true },
                    onAppSettings = {
                        context.startActivity(
                            Intent(AndroidSettings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", context.packageName, null)),
                        )
                    },
                )
            }
        }

        AnimatedVisibility(
            visible = showSettings,
            enter = slideInVertically { it / 8 } + fadeIn(),
            exit = slideOutVertically { it / 8 } + fadeOut(),
        ) {
            SettingsScreen(
                initial = settings,
                canClose = !settings.incomplete,
                onSave = {
                    showSettings = false
                    viewModel.saveSettings(it)
                },
                onClose = { showSettings = false },
            )
        }
    }

    if (showMenu) {
        MenuSheet(
            onDismiss = { showMenu = false },
            onReload = {
                showMenu = false
                if (status is Status.Ready || status is Status.Unreachable) viewModel.reload() else viewModel.connect()
            },
            onSettings = {
                showMenu = false
                showSettings = true
            },
            onExit = onExit,
        )
    }
}

@SuppressLint("SetJavaScriptEnabled") // the dashboard is a JavaScript app on our own Raspberry Pi
@Composable
private fun rememberDashboardWebView(viewModel: DashboardViewModel): WebView {
    val context = LocalContext.current
    val background = MaterialTheme.colorScheme.background.toArgb()
    val webView = remember {
        WebView(context).apply {
            setBackgroundColor(background)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true // session and API URL are kept in localStorage
            webChromeClient = WebChromeClient() // alert/confirm dialogs of the dashboard
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String?) = viewModel.onPageFinished()

                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) viewModel.onPageError(error.description.toString())
                }
            }
            addJavascriptInterface(DownloadBridge(context.applicationContext), "RTSAndroid")
        }
    }
    DisposableEffect(webView) {
        onDispose { webView.destroy() }
    }
    return webView
}
