# RTS Dashboard Android App

Android app (Android 10+) to control measurements from a phone in the field. It connects to the Wi-Fi of the field router (e.g. a TP-Link travel router) that the Raspberry Pi running the RTS API and dashboard is connected to, and shows the dashboard.

## How it works

The router has no internet access. A phone that joins such a network normally may disconnect from it again or keep sending traffic via mobile data. The app therefore requests the router Wi-Fi as a local-only network (`WifiNetworkSpecifier`, sometimes called "IoT Wi-Fi"):

- Android asks once to confirm the connection ("Device to use with RTS Dashboard"). On Android 11+ later connections are approved automatically.
- Only the app uses the router Wi-Fi. All other apps keep using mobile data.
- If the connection is lost, the app reconnects automatically when the router is back in range.
- CSV downloads from the dashboard are saved to `Downloads/RTS`.

Press the back button to reload the dashboard, change the settings, or exit.

## Setup

1. Connect the Raspberry Pi to the router and give it a fixed IP address (DHCP reservation in the router settings). The default dashboard URL is `http://192.168.0.101:8050`.
2. Install the APK on the phone (allow installing from unknown sources).
3. On first start, enter the router Wi-Fi name and password. The dashboard URL can be changed in the same dialog.

If the phone is already connected to the same network as the dashboard (e.g. in the office), uncheck "Connect to router Wi-Fi" in the settings.

## Building

The project uses only the Android platform APIs (no AndroidX), plain Java and the Android Gradle plugin.

- **GitHub Actions:** every push that changes `rts-android/` builds the APK. Download it from the `rts-dashboard-apk` artifact of the workflow run.
- **Android Studio:** open the `rts-android` folder and run the app, or build with `gradle assembleRelease` (Gradle 9.6+ and JDK 17).

### Signing

APKs from GitHub Actions are signed with the private release key of the app, which is stored only in the repository secrets `RTS_KEYSTORE_BASE64` (the PKCS12 file, base64 encoded), `RTS_KEYSTORE_PASSWORD` and `RTS_KEY_ALIAS`. Android only installs updates signed with the same key, so keep a copy of the key outside GitHub: if it is lost, the app has to be uninstalled before a new build can be installed.

Local builds without these environment variables (`RTS_KEYSTORE_FILE`, `RTS_KEYSTORE_PASSWORD`, `RTS_KEY_ALIAS`) are signed with `app/debug.keystore`. That key is public like the repository, so such APKs are for testing only. They cannot update an installed release APK, and Google Play Protect may warn about them.

### Google Play Protect

Play Protect may warn about an app installed from outside the Play Store that it does not know yet. If it does, choose *More details > Install anyway* and send the app for scanning when asked. A newly released version can also be submitted to Google for review via the Play Protect appeals form.
