plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "de.unibonn.igg.rtsdashboard"
    compileSdk = 37

    defaultConfig {
        applicationId = "de.unibonn.igg.rtsdashboard"
        minSdk = 29 // WifiNetworkSpecifier (local-only Wi-Fi) needs Android 10
        targetSdk = 37
        versionCode = 3
        versionName = "2.0"
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
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName(if (releaseKeystore != null) "release" else "debug")
        }
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.11.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.11.0")
}
