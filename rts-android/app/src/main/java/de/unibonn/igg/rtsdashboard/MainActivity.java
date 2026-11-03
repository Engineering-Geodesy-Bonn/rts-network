package de.unibonn.igg.rtsdashboard;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.Uri;
import android.net.wifi.WifiNetworkSpecifier;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Connects to the field router as a local-only ("IoT") Wi-Fi network and shows the dashboard.
 *
 * The router has no internet access, so the network is requested via WifiNetworkSpecifier:
 * it is only used by this app (the process is bound to it), and the phone keeps using
 * mobile data for everything else.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "settings";
    private static final String KEY_SSID = "ssid";
    private static final String KEY_PASSPHRASE = "passphrase";
    private static final String KEY_URL = "url";
    private static final String KEY_CONNECT_WIFI = "connect_wifi";
    private static final String DEFAULT_URL = "http://192.168.0.101:8050";
    private static final int WIFI_TIMEOUT_MS = 60_000;

    private SharedPreferences prefs;
    private ConnectivityManager connectivityManager;
    private ConnectivityManager.NetworkCallback networkCallback;

    private WebView webView;
    private View statusPanel;
    private TextView statusText;
    private ProgressBar statusProgress;
    private Button retryButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        connectivityManager = getSystemService(ConnectivityManager.class);

        webView = findViewById(R.id.web_view);
        statusPanel = findViewById(R.id.status_panel);
        statusText = findViewById(R.id.status_text);
        statusProgress = findViewById(R.id.status_progress);
        retryButton = findViewById(R.id.retry_button);
        retryButton.setOnClickListener(v -> connect());
        findViewById(R.id.settings_button).setOnClickListener(v -> showSettings());

        setUpWebView();

        if (prefs.getBoolean(KEY_CONNECT_WIFI, true) && ssid().isEmpty()) {
            showStatus(getString(R.string.status_not_configured), false);
            showSettings();
        } else {
            connect();
        }
    }

    @Override
    protected void onDestroy() {
        releaseNetwork();
        webView.destroy();
        super.onDestroy();
    }

    @Override
    @SuppressWarnings("deprecation") // still delivered for targetSdk 34 without OnBackInvokedCallback
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
            return;
        }
        new AlertDialog.Builder(this)
                .setItems(R.array.menu_items, (dialog, which) -> {
                    if (which == 0) {
                        loadDashboard();
                    } else if (which == 1) {
                        showSettings();
                    } else {
                        finish();
                    }
                })
                .show();
    }

    private void setUpWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true); // session and API URL are kept in localStorage

        // Enables the default alert/confirm dialogs used by the dashboard.
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    showStatus(getString(R.string.status_dashboard_unreachable, dashboardUrl(), error.getDescription()), false);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (statusProgress.getVisibility() == View.VISIBLE) {
                    statusPanel.setVisibility(View.GONE);
                }
            }
        });
        webView.addJavascriptInterface(new DownloadBridge(), "RTSAndroid");
    }

    private void connect() {
        releaseNetwork();

        if (!prefs.getBoolean(KEY_CONNECT_WIFI, true)) {
            loadDashboard();
            return;
        }

        showStatus(getString(R.string.status_connecting, ssid()), true);

        WifiNetworkSpecifier.Builder specifier = new WifiNetworkSpecifier.Builder().setSsid(ssid());
        String passphrase = prefs.getString(KEY_PASSPHRASE, "");
        if (!passphrase.isEmpty()) {
            specifier.setWpa2Passphrase(passphrase);
        }
        NetworkRequest request = new NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .setNetworkSpecifier(specifier.build())
                .build();

        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                // Route all traffic of this app (including the WebView) through the router.
                connectivityManager.bindProcessToNetwork(network);
                runOnUiThread(MainActivity.this::loadDashboard);
            }

            @Override
            public void onLost(Network network) {
                connectivityManager.bindProcessToNetwork(null);
                runOnUiThread(() -> showStatus(getString(R.string.status_lost, ssid()), false));
            }

            @Override
            public void onUnavailable() {
                networkCallback = null;
                runOnUiThread(() -> showStatus(getString(R.string.status_unavailable, ssid()), false));
            }
        };
        connectivityManager.requestNetwork(request, networkCallback, WIFI_TIMEOUT_MS);
    }

    private void releaseNetwork() {
        if (networkCallback != null) {
            connectivityManager.unregisterNetworkCallback(networkCallback);
            networkCallback = null;
        }
        connectivityManager.bindProcessToNetwork(null);
    }

    private void loadDashboard() {
        showStatus(getString(R.string.status_loading, dashboardUrl()), true);
        webView.loadUrl(dashboardUrl());
    }

    private void showStatus(String message, boolean busy) {
        statusText.setText(message);
        statusProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
        retryButton.setVisibility(busy ? View.GONE : View.VISIBLE);
        statusPanel.setVisibility(View.VISIBLE);
    }

    private void showSettings() {
        View form = getLayoutInflater().inflate(R.layout.dialog_settings, null);
        CheckBox connectWifi = form.findViewById(R.id.connect_wifi);
        EditText ssid = form.findViewById(R.id.ssid);
        EditText passphrase = form.findViewById(R.id.passphrase);
        EditText url = form.findViewById(R.id.url);

        connectWifi.setChecked(prefs.getBoolean(KEY_CONNECT_WIFI, true));
        ssid.setText(ssid());
        passphrase.setText(prefs.getString(KEY_PASSPHRASE, ""));
        url.setText(dashboardUrl());

        new AlertDialog.Builder(this)
                .setTitle(R.string.settings_title)
                .setView(form)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.settings_connect, (dialog, which) -> {
                    prefs.edit()
                            .putBoolean(KEY_CONNECT_WIFI, connectWifi.isChecked())
                            .putString(KEY_SSID, ssid.getText().toString().trim())
                            .putString(KEY_PASSPHRASE, passphrase.getText().toString())
                            .putString(KEY_URL, url.getText().toString().trim())
                            .apply();
                    connect();
                })
                .show();
    }

    private String ssid() {
        return prefs.getString(KEY_SSID, "");
    }

    private String dashboardUrl() {
        String url = prefs.getString(KEY_URL, "");
        return url.isEmpty() ? DEFAULT_URL : url;
    }

    /** Saves CSV downloads of the dashboard, since WebView ignores {@code <a download>}. */
    private class DownloadBridge {
        @JavascriptInterface
        public void saveFile(String filename, String content) {
            String name = filename.replaceAll("[\\\\/:*?\"<>|]", "_");
            ContentValues values = new ContentValues();
            values.put(MediaStore.Downloads.DISPLAY_NAME, name);
            values.put(MediaStore.Downloads.MIME_TYPE, "text/csv");
            values.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/RTS");

            ContentResolver resolver = getContentResolver();
            Uri uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            String message;
            if (uri == null) {
                message = getString(R.string.download_failed, name);
            } else {
                try (OutputStream out = resolver.openOutputStream(uri)) {
                    out.write(content.getBytes(StandardCharsets.UTF_8));
                    message = getString(R.string.download_saved, name);
                } catch (Exception e) {
                    resolver.delete(uri, null, null);
                    message = getString(R.string.download_failed, name);
                }
            }
            String toast = message;
            runOnUiThread(() -> Toast.makeText(MainActivity.this, toast, Toast.LENGTH_LONG).show());
        }
    }
}
