package de.unibonn.igg.rtsdashboard

import android.content.Context
import androidx.core.content.edit

/** Connection settings, entered once in the field. */
data class Settings(
    /** Request the router Wi-Fi as a local-only network; off when the phone is already in the dashboard's network */
    val connectWifi: Boolean = true,
    val ssid: String = "",
    val passphrase: String = "",
    val url: String = DEFAULT_URL,
) {
    /** The router Wi-Fi has not been entered yet */
    val incomplete: Boolean get() = connectWifi && ssid.isBlank()

    companion object {
        const val DEFAULT_URL = "http://192.168.0.101:8050"
    }
}

class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    fun load() = Settings(
        connectWifi = prefs.getBoolean(KEY_CONNECT_WIFI, true),
        ssid = prefs.getString(KEY_SSID, "").orEmpty(),
        passphrase = prefs.getString(KEY_PASSPHRASE, "").orEmpty(),
        url = prefs.getString(KEY_URL, "").orEmpty().ifBlank { Settings.DEFAULT_URL },
    )

    fun save(settings: Settings) = prefs.edit {
        putBoolean(KEY_CONNECT_WIFI, settings.connectWifi)
        putString(KEY_SSID, settings.ssid.trim())
        putString(KEY_PASSPHRASE, settings.passphrase)
        putString(KEY_URL, settings.url.trim())
    }

    private companion object {
        const val KEY_CONNECT_WIFI = "connect_wifi"
        const val KEY_SSID = "ssid"
        const val KEY_PASSPHRASE = "passphrase"
        const val KEY_URL = "url"
    }
}
