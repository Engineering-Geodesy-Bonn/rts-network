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
- **Android Studio:** open the `rts-android` folder and run the app, or build with `gradle assembleRelease` (Gradle 8.9+ and JDK 17).

Both builds are signed with the committed `app/debug.keystore`, so APKs from different machines can be installed over each other. It is a debug key and not meant for publishing the app in an app store.
