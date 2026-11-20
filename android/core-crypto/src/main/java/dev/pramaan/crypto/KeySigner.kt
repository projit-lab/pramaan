package dev.pramaan.crypto

interface KeySigner {
    /** Creates the hardware-bound key with the server nonce as attestation challenge. */
    suspend fun enrol(challenge: ByteArray): EnrolResult
    /** Signs exactly these bytes after a strong biometric; returns DER ECDSA P-256. */
    suspend fun sign(data: ByteArray): ByteArray
    /** Public key as X.509 SubjectPublicKeyInfo DER, or null if not enrolled. */
    fun publicKey(): ByteArray?
}

data class EnrolResult(
    val certificateChain: List<ByteArray>,   // DER, leaf first
    val securityLevel: SecurityLevel,
    val keyAlias: String
)

enum class SecurityLevel { STRONGBOX, TEE, SOFTWARE }
