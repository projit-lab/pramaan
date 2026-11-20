plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "dev.pramaan.crypto"
    compileSdk = 36

    defaultConfig {
        minSdk = 30
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(libs.androidx.biometric)
    implementation(libs.kotlinx.coroutines.android)
}
