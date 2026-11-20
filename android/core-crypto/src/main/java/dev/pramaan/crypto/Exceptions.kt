package dev.pramaan.crypto

open class CryptoException(message: String, cause: Throwable? = null) : Exception(message, cause)

class InsecureKeyException(message: String) : CryptoException(message)

class KeyNotEnrolledException(message: String) : CryptoException(message)

class KeyInvalidatedException(message: String, cause: Throwable? = null) : CryptoException(message, cause)

class BiometricCancelledException(message: String) : CryptoException(message)

class BiometricFailedException(val code: Int, message: String) : CryptoException("[$code] $message")
