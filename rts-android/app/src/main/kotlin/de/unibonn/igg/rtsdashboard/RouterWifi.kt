package de.unibonn.igg.rtsdashboard

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier

/**
 * The field router as a local-only ("IoT") Wi-Fi network.
 *
 * The router has no internet access, so it is requested via WifiNetworkSpecifier: only this app
 * uses it (the process is bound to it, including the WebView), and the phone keeps using mobile
 * data for everything else. Android asks once to confirm the connection; while the request is
 * active it reconnects by itself when the router is back in range.
 */
class RouterWifi(context: Context) {
    private val connectivity = context.getSystemService(ConnectivityManager::class.java)
    private var callback: ConnectivityManager.NetworkCallback? = null

    interface Listener {
        fun onConnected()
        fun onLost()
        fun onUnavailable()
    }

    fun connect(ssid: String, passphrase: String, listener: Listener) {
        release()
        val specifier = WifiNetworkSpecifier.Builder().setSsid(ssid).apply {
            if (passphrase.isNotEmpty()) setWpa2Passphrase(passphrase)
        }.build()
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(specifier)
            .build()

        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                connectivity.bindProcessToNetwork(network)
                listener.onConnected()
            }

            override fun onLost(network: Network) {
                connectivity.bindProcessToNetwork(null)
                listener.onLost()
            }

            override fun onUnavailable() {
                this@RouterWifi.callback = null
                listener.onUnavailable()
            }
        }
        this.callback = callback
        connectivity.requestNetwork(request, callback, TIMEOUT_MS)
    }

    fun release() {
        callback?.let { connectivity.unregisterNetworkCallback(it) }
        callback = null
        connectivity.bindProcessToNetwork(null)
    }

    private companion object {
        const val TIMEOUT_MS = 60_000
    }
}
