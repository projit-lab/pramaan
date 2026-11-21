package dev.pramaan.crypto

import java.text.Normalizer

object Canonical {

    fun canonicalBytes(fields: Map<String, String>): ByteArray {
        // 1. NFC-normalise every key and value
        val normalized = fields.map { (k, v) ->
            Normalizer.normalize(k, Normalizer.Form.NFC) to Normalizer.normalize(v, Normalizer.Form.NFC)
        }

        // 2. Sort keys by Unicode code point
        val sorted = normalized.sortedWith { (k1, _), (k2, _) ->
            compareCodePoints(k1, k2)
        }

        // 3. Build JSON object with no whitespace and escaping matching Python json.dumps(ensure_ascii=False)
        val sb = StringBuilder()
        sb.append('{')
        for (i in sorted.indices) {
            val (k, v) = sorted[i]
            if (i > 0) {
                sb.append(',')
            }
            sb.append('"')
            escapeJsonString(k, sb)
            sb.append("\":\"")
            escapeJsonString(v, sb)
            sb.append('"')
        }
        sb.append('}')

        return sb.toString().toByteArray(Charsets.UTF_8)
    }

    private fun compareCodePoints(a: String, b: String): Int {
        val aPoints = a.codePoints().toArray()
        val bPoints = b.codePoints().toArray()
        val minLen = minOf(aPoints.size, bPoints.size)
        for (i in 0 until minLen) {
            val cmp = aPoints[i].compareTo(bPoints[i])
            if (cmp != 0) return cmp
        }
        return aPoints.size.compareTo(bPoints.size)
    }

    private fun escapeJsonString(s: String, sb: StringBuilder) {
        for (ch in s) {
            when (ch) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                '\b' -> sb.append("\\b")
                '\u000c' -> sb.append("\\f")
                else -> {
                    val code = ch.code
                    if (code < 0x20) {
                        sb.append(String.format("\\u%04x", code))
                    } else {
                        sb.append(ch)
                    }
                }
            }
        }
    }
}
