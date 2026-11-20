package dev.pramaan.crypto

import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyInfo
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.security.keystore.StrongBoxUnavailableException
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class AndroidKeyStoreSigner(
    private val activityProvider: () -> FragmentActivity,
    private val promptTitle: String = "Confirm with your fingerprint",
    private val keyAlias: String = DEFAULT_KEY_ALIAS,
) : KeySigner {

    companion object {
        const val DEFAULT_KEY_ALIAS = "pramaan_approver_key"
        private const val ANDROID_KEY_STORE = "AndroidKeyStore"
        private const val SIGNATURE_ALGORITHM = "SHA256withECDSA"
        private const val EC_CURVE = "secp256r1"
    }

    private fun getKeyStore(): KeyStore {
        return KeyStore.getInstance(ANDROID_KEY_STORE).apply { load(null) }
    }

    override suspend fun enrol(challenge: ByteArray): EnrolResult = withContext(Dispatchers.IO) {
        val keyStore = getKeyStore()
        if (keyStore.containsAlias(keyAlias)) {
            keyStore.deleteEntry(keyAlias)
        }

        fun createSpec(strongBox: Boolean): KeyGenParameterSpec {
            val builder = KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_SIGN)
                .setAlgorithmParameterSpec(ECGenParameterSpec(EC_CURVE))
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setUserAuthenticationRequired(true)
                .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
                .setInvalidatedByBiometricEnrollment(true)
                .setAttestationChallenge(challenge)

            if (strongBox) {
                builder.setIsStrongBoxBacked(true)
            }
            return builder.build()
        }

        var isStrongBox = false
        try {
            val kpg = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, ANDROID_KEY_STORE)
            kpg.initialize(createSpec(strongBox = true))
            kpg.generateKeyPair()
            isStrongBox = true
        } catch (e: Exception) {
            if (e is StrongBoxUnavailableException || e.cause is StrongBoxUnavailableException) {
                // Retry without StrongBox (fallback to TEE)
                val kpg = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, ANDROID_KEY_STORE)
                kpg.initialize(createSpec(strongBox = false))
                kpg.generateKeyPair()
                isStrongBox = false
            } else {
                throw e
            }
        }

        val securityLevel: SecurityLevel
        if (isStrongBox) {
            securityLevel = SecurityLevel.STRONGBOX
        } else {
            val privateKey = keyStore.getKey(keyAlias, null) as? PrivateKey
                ?: throw IllegalStateException("Generated private key not found in KeyStore")

            val factory = KeyFactory.getInstance(KeyProperties.KEY_ALGORITHM_EC, ANDROID_KEY_STORE)
            val keyInfo = factory.getKeySpec(privateKey, KeyInfo::class.java)

            val isSecure: Boolean
            val level: SecurityLevel
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                when (keyInfo.securityLevel) {
                    KeyProperties.SECURITY_LEVEL_STRONGBOX -> {
                        isSecure = true
                        level = SecurityLevel.STRONGBOX
                    }
                    KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT -> {
                        isSecure = true
                        level = SecurityLevel.TEE
                    }
                    else -> {
                        isSecure = false
                        level = SecurityLevel.SOFTWARE
                    }
                }
            } else {
                @Suppress("DEPRECATION")
                isSecure = keyInfo.isInsideSecureHardware
                level = if (isSecure) SecurityLevel.TEE else SecurityLevel.SOFTWARE
            }

            if (!isSecure || level == SecurityLevel.SOFTWARE) {
                if (keyStore.containsAlias(keyAlias)) {
                    keyStore.deleteEntry(keyAlias)
                }
                throw InsecureKeyException("Key is not inside secure hardware (level: $level)")
            }
            securityLevel = level
        }

        val certificateChain = keyStore.getCertificateChain(keyAlias)
            ?: throw IllegalStateException("Certificate chain missing for alias $keyAlias")

        EnrolResult(
            certificateChain = certificateChain.map { it.encoded },
            securityLevel = securityLevel,
            keyAlias = keyAlias,
        )
    }

    override suspend fun sign(data: ByteArray): ByteArray {
        val keyStore = getKeyStore()
        if (!keyStore.containsAlias(keyAlias)) {
            throw KeyNotEnrolledException("Key '$keyAlias' is not enrolled in AndroidKeyStore")
        }

        val privateKey = keyStore.getKey(keyAlias, null) as? PrivateKey
            ?: throw KeyNotEnrolledException("Private key for '$keyAlias' not found in AndroidKeyStore")

        val signature = Signature.getInstance(SIGNATURE_ALGORITHM)
        try {
            signature.initSign(privateKey)
        } catch (e: KeyPermanentlyInvalidatedException) {
            throw KeyInvalidatedException("Key permanently invalidated by biometric changes", e)
        }

        val cryptoObject = BiometricPrompt.CryptoObject(signature)

        return withContext(Dispatchers.Main) {
            val activity = activityProvider()
            val executor = ContextCompat.getMainExecutor(activity)

            val promptInfo = BiometricPrompt.PromptInfo.Builder()
                .setTitle(promptTitle)
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                .setNegativeButtonText("Cancel")
                .build()

            suspendCancellableCoroutine { continuation ->
                val callback = object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                        try {
                            val authenticatedSignature = result.cryptoObject?.signature
                                ?: throw IllegalStateException("Signature missing from CryptoObject")
                            authenticatedSignature.update(data)
                            val derSignature = authenticatedSignature.sign()
                            continuation.resume(derSignature)
                        } catch (t: Throwable) {
                            continuation.resumeWithException(t)
                        }
                    }

                    override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                        when (errorCode) {
                            BiometricPrompt.ERROR_USER_CANCELED,
                            BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                            BiometricPrompt.ERROR_CANCELED -> {
                                continuation.resumeWithException(
                                    BiometricCancelledException(errString.toString())
                                )
                            }
                            else -> {
                                continuation.resumeWithException(
                                    BiometricFailedException(errorCode, errString.toString())
                                )
                            }
                        }
                    }
                }

                val biometricPrompt = BiometricPrompt(activity, executor, callback)
                biometricPrompt.authenticate(promptInfo, cryptoObject)

                continuation.invokeOnCancellation {
                    biometricPrompt.cancelAuthentication()
                }
            }
        }
    }

    override fun publicKey(): ByteArray? {
        val keyStore = getKeyStore()
        val cert = keyStore.getCertificate(keyAlias) ?: return null
        return cert.publicKey.encoded
    }
}
