plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "dev.pramaan.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.pramaan.app"
        minSdk = 30 // keys that need a strong biometric on every use
        targetSdk = 36
        versionCode = 1
        versionName = "0.4.0-m4"

        // services/api running with DEMO_MODE=true. 10.0.2.2 is the host machine as
        // seen from the Android emulator; pass -PapiBase=... for a real phone.
        buildConfigField("String", "API_BASE", "\"${project.findProperty("apiBase") ?: "http://10.0.2.2:8765"}\"")
        buildConfigField("String", "DEMO_UID", "\"uid_cfo\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.ai)
    debugImplementation(libs.androidx.ui.tooling)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}
