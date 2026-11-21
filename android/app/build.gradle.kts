plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Firebase config for Gemini Live, read from app/google-services.json when it is
// present (it is git-ignored and never committed). Read here instead of through the
// google-services Gradle plugin so the build does not depend on that plugin's AGP
// support. Without the file the voice step falls back to the typed keypad.
@Suppress("UNCHECKED_CAST")
val firebaseConfig: Map<String, String> = run {
    val f = file("google-services.json")
    if (!f.exists()) return@run emptyMap()
    val root = groovy.json.JsonSlurper().parse(f) as Map<String, Any?>
    val project = root["project_info"] as Map<String, Any?>
    val client = (root["client"] as List<Map<String, Any?>>).firstOrNull {
        val info = it["client_info"] as Map<String, Any?>
        (info["android_client_info"] as Map<String, Any?>)["package_name"] == "dev.pramaan.app"
    } ?: return@run emptyMap()
    mapOf(
        "appId" to (client["client_info"] as Map<String, Any?>)["mobilesdk_app_id"].toString(),
        "apiKey" to (client["api_key"] as List<Map<String, Any?>>).first()["current_key"].toString(),
        "projectId" to project["project_id"].toString(),
    )
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
        buildConfigField("String", "FIREBASE_APP_ID", "\"${firebaseConfig["appId"] ?: ""}\"")
        buildConfigField("String", "FIREBASE_API_KEY", "\"${firebaseConfig["apiKey"] ?: ""}\"")
        buildConfigField("String", "FIREBASE_PROJECT_ID", "\"${firebaseConfig["projectId"] ?: ""}\"")
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
    implementation(project(":core-crypto"))
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
