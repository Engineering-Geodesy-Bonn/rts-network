plugins {
    id("com.android.application")
}

android {
    namespace = "de.unibonn.igg.rtsdashboard"
    compileSdk = 37

    defaultConfig {
        applicationId = "de.unibonn.igg.rtsdashboard"
        minSdk = 29 // WifiNetworkSpecifier (local-only Wi-Fi) needs Android 10
        targetSdk = 37
        versionCode = 2
        versionName = "1.1"
    }

    signingConfigs {
        // Shared debug key so APKs from CI and local builds can update each other.
        getByName("debug") {
            storeFile = file("debug.keystore")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
