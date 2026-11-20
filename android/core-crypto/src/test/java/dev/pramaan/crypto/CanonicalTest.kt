package dev.pramaan.crypto

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class CanonicalTest {

    private fun findVectorsFile(): File {
        val candidates = listOf(
            File("../../contracts/canonical/vectors.json"),
            File("../contracts/canonical/vectors.json"),
            File("contracts/canonical/vectors.json"),
            File(System.getProperty("user.dir"), "../../contracts/canonical/vectors.json"),
            File(System.getProperty("user.dir"), "../contracts/canonical/vectors.json"),
            File(System.getProperty("user.dir"), "contracts/canonical/vectors.json"),
        )
        return candidates.firstOrNull { it.exists() }
            ?: error("contracts/canonical/vectors.json not found in candidates: ${candidates.map { it.absolutePath }}")
    }

    private fun sha256Hex(bytes: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
        return digest.joinToString("") { "%02x".format(it) }
    }

    @Test
    fun testSharedVectors() {
        val file = findVectorsFile()
        val jsonText = file.readText(Charsets.UTF_8)
        val array = Json.parseToJsonElement(jsonText).jsonArray

        println("Running ${array.size} canonical test vectors from ${file.canonicalPath}:")

        for (element in array) {
            val obj = element.jsonObject
            val name = obj["name"]!!.jsonPrimitive.content
            val expectedCanonical = obj["canonical"]!!.jsonPrimitive.content
            val expectedBytesLen = obj["canonical_utf8_bytes"]!!.jsonPrimitive.content.toInt()
            val expectedSha256 = obj["sha256"]!!.jsonPrimitive.content

            val paymentObj = obj["payment"]!!.jsonObject
            val paymentMap = paymentObj.mapValues { (_, v) -> v.jsonPrimitive.content }

            val actualBytes = Canonical.canonicalBytes(paymentMap)
            val actualBytesLen = actualBytes.size
            val actualSha256 = sha256Hex(actualBytes)
            val expectedBytes = expectedCanonical.toByteArray(Charsets.UTF_8)

            println("  Vector: $name")
            assertArrayEquals("Canonical bytes mismatch for $name", expectedBytes, actualBytes)
            assertEquals("Byte length mismatch for $name", expectedBytesLen, actualBytesLen)
            assertEquals("SHA-256 mismatch for $name", expectedSha256, actualSha256)
        }
    }
}
