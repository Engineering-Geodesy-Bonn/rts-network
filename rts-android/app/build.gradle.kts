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

    // Release key from the environment (GitHub secrets in CI). It must never be committed:
    // anyone who has it can publish APKs that install as updates of this app.
    val releaseKeystore = System.getenv("RTS_KEYSTORE_FILE")

    signingConfigs {
        // Debug key for local test builds only (it is public, as the repository is)
        getByName("debug") {
            storeFile = file("debug.keystore")
        }
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = System.getenv("RTS_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("RTS_KEY_ALIAS")
                keyPassword = System.getenv("RTS_KEY_PASSWORD") ?: System.getenv("RTS_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName(if (releaseKeystore != null) "release" else "debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
