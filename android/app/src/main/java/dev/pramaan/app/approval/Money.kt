package dev.pramaan.app.approval

import java.math.BigInteger

/**
 * Money on the approval screen.
 *
 * A deliberate port of web/shared/src/format/money.ts, kept word for word
 * identical in its output. The approver sees this on the phone and the finance
 * team sees the console; if the two ever phrase an amount differently, one of
 * them is wrong and nobody can tell which. MoneyTest pins the same cases the
 * web tests pin.
 *
 * Amounts are integer paise held as a string, never a Double. A Double cannot
 * hold 184000000 paise exactly once arithmetic touches it, and this is the one
 * number a person is about to sign.
 */
object Money {

    class InvalidPaise(value: String) : IllegalArgumentException("Not an integer paise string: $value")

    private val DIGITS_ONLY = Regex("^[0-9]+$")

    private val ONES = listOf(
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen",
    )

    private val TENS = listOf(
        "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    )

    private val TEN_MILLION = BigInteger.valueOf(10_000_000L)
    private val HUNDRED_THOUSAND = BigInteger.valueOf(100_000L)
    private val THOUSAND = BigInteger.valueOf(1_000L)
    private val HUNDRED = BigInteger.valueOf(100L)

    private fun assertPaise(paise: String) {
        if (!DIGITS_ONLY.matches(paise)) throw InvalidPaise(paise)
    }

    /** Rupees and the leftover paise, exactly. */
    fun split(paise: String): Pair<BigInteger, Int> {
        assertPaise(paise)
        val value = BigInteger(paise)
        return value.divide(HUNDRED) to value.mod(HUNDRED).toInt()
    }

    /** 2,34,56,789 — last three, then twos. */
    fun groupIndian(digits: String): String {
        assertPaise(digits)
        val trimmed = digits.trimStart('0').ifEmpty { "0" }
        if (trimmed.length <= 3) return trimmed
        val last3 = trimmed.takeLast(3)
        val rest = trimmed.dropLast(3)
        val groups = ArrayDeque<String>()
        var end = rest.length
        while (end > 0) {
            groups.addFirst(rest.substring(maxOf(0, end - 2), end))
            end -= 2
        }
        return groups.joinToString(",") + "," + last3
    }

    /** formatRupees("465000000") == "₹46,50,000" */
    fun formatRupees(paise: String, symbol: Boolean = true): String {
        val (rupees, remainder) = split(paise)
        val head = groupIndian(rupees.toString())
        val body = if (remainder == 0) head else "$head.%02d".format(remainder)
        return if (symbol) "₹$body" else body
    }

    /** Words for 0-99. */
    private fun underHundred(n: Int): String {
        if (n < 20) return ONES[n]
        val tens = TENS[n / 10]
        val ones = n % 10
        return if (ones == 0) tens else "$tens-${ONES[ones]}"
    }

    /** Words for 0-999. */
    private fun underThousand(n: Int): String {
        if (n < 100) return underHundred(n)
        val head = "${ONES[n / 100]} hundred"
        val rest = n % 100
        return if (rest == 0) head else "$head ${underHundred(rest)}"
    }

    /** A crore count can itself run past 999, so it is spelled on the same scale. */
    private fun croreCountInWords(count: BigInteger): String {
        val parts = mutableListOf<String>()
        var remaining = count
        val thousands = remaining.divide(THOUSAND)
        remaining = remaining.mod(THOUSAND)
        if (thousands > BigInteger.ZERO) parts.add("${underThousand(thousands.toInt())} thousand")
        val rest = remaining.toInt()
        if (rest > 0) parts.add(underThousand(rest))
        return if (parts.isEmpty()) "zero" else parts.joinToString(" ")
    }

    /**
     * The amount in Indian words. This is the digit-transposition catch, and the
     * spec calls it not optional: 46,50,000 and 4,65,000 look alike at a glance
     * and read nothing alike.
     *
     * amountInWords("465000000") == "forty-six lakh fifty thousand rupees"
     */
    fun amountInWords(paise: String): String {
        val (rupees, remainderPaise) = split(paise)

        val parts = mutableListOf<String>()
        var remaining = rupees

        val crore = remaining.divide(TEN_MILLION)
        remaining = remaining.mod(TEN_MILLION)
        val lakh = remaining.divide(HUNDRED_THOUSAND)
        remaining = remaining.mod(HUNDRED_THOUSAND)
        val thousand = remaining.divide(THOUSAND)
        remaining = remaining.mod(THOUSAND)
        val rest = remaining.toInt()

        if (crore > BigInteger.ZERO) parts.add("${croreCountInWords(crore)} crore")
        if (lakh > BigInteger.ZERO) parts.add("${underHundred(lakh.toInt())} lakh")
        if (thousand > BigInteger.ZERO) parts.add("${underHundred(thousand.toInt())} thousand")
        if (rest > 0) parts.add(underThousand(rest))

        val rupeeWords = if (parts.isEmpty()) "zero rupees" else parts.joinToString(" ") + " rupees"
        return if (remainderPaise == 0) rupeeWords
        else "$rupeeWords and ${underHundred(remainderPaise)} paise"
    }

    /**
     * The last four of an account number, masked. The signature covers the full
     * number; the screen shows four. Anything that is not a plain account number
     * returns a dash rather than a guess.
     */
    fun maskAccount(account: String?): String {
        if (account == null || account.length < 4 || !DIGITS_ONLY.matches(account)) return "—"
        return "•••• ${account.takeLast(4)}"
    }
}
