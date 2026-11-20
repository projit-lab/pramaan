package dev.pramaan.crypto

import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/**
 * Software P-256 key implementation of [KeySigner] for screen development only.
 *
 * This class uses an in-memory software key from java.security without biometric
 * authentication and reports [SecurityLevel.SOFTWARE]. The server rejects SOFTWARE
 * keys; this class must never be used in production or release builds.
 */
class FakeKeySigner(
    private val keyAlias: String = "fake_software_key"
) : KeySigner {

    private var keyPair: KeyPair? = null

    override suspend fun enrol(challenge: ByteArray): EnrolResult {
        val kpg = KeyPairGenerator.getInstance("EC")
        kpg.initialize(ECGenParameterSpec("secp256r1"))
        val pair = kpg.generateKeyPair()
        keyPair = pair
        return EnrolResult(
            certificateChain = emptyList(),
            securityLevel = SecurityLevel.SOFTWARE,
            keyAlias = keyAlias
        )
    }

    override suspend fun sign(data: ByteArray): ByteArray {
        val pair = keyPair ?: run {
            enrol(ByteArray(0))
            keyPair!!
        }
        val ecdsa = Signature.getInstance("SHA256withECDSA")
        ecdsa.initSign(pair.private)
        ecdsa.update(data)
        return ecdsa.sign()
    }

    override fun publicKey(): ByteArray? {
        return keyPair?.public?.encoded
    }
}
