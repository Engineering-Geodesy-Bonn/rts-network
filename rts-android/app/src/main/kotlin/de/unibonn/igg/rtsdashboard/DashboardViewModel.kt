package de.unibonn.igg.rtsdashboard

import android.app.Application
import android.content.pm.PackageManager
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** What the app shows instead of (or until) the dashboard. */
sealed interface Status {
    /** The router Wi-Fi has not been entered yet */
    data object NotConfigured : Status

    /** Android 17+: waiting for the user to allow access to the local network */
    data object NeedsPermission : Status
    data object PermissionDenied : Status

    data class Connecting(val ssid: String) : Status
    data class Lost(val ssid: String) : Status
    data class Unavailable(val ssid: String) : Status

    /** The WebView loads [url]; [attempt] makes every reload a new state */
    data class Loading(val url: String, val attempt: Long = System.nanoTime()) : Status
    data class Unreachable(val url: String, val error: String) : Status

    /** The dashboard is shown */
    data object Ready : Status
}

class DashboardViewModel(application: Application) : AndroidViewModel(application) {
    private val store = SettingsStore(application)
    private val wifi = RouterWifi(application)

    private val _settings = MutableStateFlow(store.load())
    val settings: StateFlow<Settings> = _settings.asStateFlow()

    private val _status = MutableStateFlow<Status>(Status.NotConfigured)
    val status: StateFlow<Status> = _status.asStateFlow()

    /** The current page load failed; its onPageFinished must not show the dashboard */
    private var loadFailed = false

    init {
        if (!_settings.value.incomplete) connect()
    }

    fun saveSettings(settings: Settings) {
        store.save(settings)
        _settings.value = store.load()
        connect()
    }

    fun connect() {
        wifi.release()
        val settings = _settings.value
        when {
            settings.incomplete -> _status.value = Status.NotConfigured
            needsLocalNetworkPermission() -> _status.value = Status.NeedsPermission
            !settings.connectWifi -> reload()
            else -> {
                _status.value = Status.Connecting(settings.ssid)
                wifi.connect(settings.ssid, settings.passphrase, object : RouterWifi.Listener {
                    override fun onConnected() = reload()
                    override fun onLost() = _status.update { Status.Lost(settings.ssid) }
                    override fun onUnavailable() = _status.update { Status.Unavailable(settings.ssid) }
                })
            }
        }
    }

    fun onPermissionResult(granted: Boolean) {
        if (granted) connect() else _status.value = Status.PermissionDenied
    }

    fun reload() {
        loadFailed = false
        _status.value = Status.Loading(_settings.value.url)
    }

    fun onPageFinished() {
        if (!loadFailed) _status.update { if (it is Status.Loading) Status.Ready else it }
    }

    fun onPageError(error: String) {
        loadFailed = true
        _status.value = Status.Unreachable(_settings.value.url, error)
    }

    /** Android 17 blocks traffic to local network addresses without this runtime permission. */
    private fun needsLocalNetworkPermission(): Boolean =
        Build.VERSION.SDK_INT >= ANDROID_17 &&
            getApplication<Application>().checkSelfPermission(PERMISSION_LOCAL_NETWORK) != PackageManager.PERMISSION_GRANTED

    override fun onCleared() {
        wifi.release()
    }

    companion object {
        const val ANDROID_17 = 37
        const val PERMISSION_LOCAL_NETWORK = "android.permission.ACCESS_LOCAL_NETWORK"
    }
}
