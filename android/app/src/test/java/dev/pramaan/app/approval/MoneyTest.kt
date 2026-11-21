package dev.pramaan.app.approval

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

/**
 * The same cases web/shared/src/format/money.test.ts pins, asserted against the
 * Kotlin port. The phone and the console must say an amount the same way; if
 * these two suites ever disagree, one of the two apps is lying to somebody.
 */
class MoneyTest {

    @Test
    fun `groups rupees the Indian way`() {
        assertEquals("₹46,50,000", Money.formatRupees("465000000"))
        assertEquals("₹9,80,000", Money.formatRupees("98000000"))
        assertEquals("₹500", Money.formatRupees("50000"))
        assertEquals("46,50,000", Money.formatRupees("465000000", symbol = false))
    }

    @Test
    fun `shows paise only when there are some`() {
        assertEquals("₹9,80,000.50", Money.formatRupees("98000050"))
        assertEquals("₹0.01", Money.formatRupees("1"))
    }

    @Test
    fun `spells lakhs`() {
        assertEquals("forty-six lakh fifty thousand rupees", Money.amountInWords("465000000"))
        assertEquals("nine lakh eighty thousand rupees", Money.amountInWords("98000000"))
        assertEquals("eighteen lakh forty thousand rupees", Money.amountInWords("184000000"))
        assertEquals("thirty lakh rupees", Money.amountInWords("300000000"))
    }

    @Test
    fun `spells crores`() {
        assertEquals("ten crore forty lakh rupees", Money.amountInWords("10400000000"))
        assertEquals("ten crore rupees", Money.amountInWords("10000000000"))
        assertEquals("one crore rupees", Money.amountInWords("1000000000"))
        assertEquals("one crore one thousand rupees", Money.amountInWords("1000100000"))
    }

    @Test
    fun `spells small amounts`() {
        assertEquals("five hundred rupees", Money.amountInWords("50000"))
        assertEquals("one thousand two hundred thirty-four rupees", Money.amountInWords("123400"))
        assertEquals("nineteen rupees", Money.amountInWords("1900"))
        assertEquals("zero rupees", Money.amountInWords("0"))
    }

    @Test
    fun `spells the paise when they are not zero`() {
        assertEquals("nine lakh eighty thousand rupees and fifty paise", Money.amountInWords("98000050"))
        assertEquals("zero rupees and one paise", Money.amountInWords("1"))
    }

    @Test
    fun `spells past a hundred crore the way a CFO says it`() {
        assertEquals("one thousand two hundred crore rupees", Money.amountInWords("1200000000000"))
    }

    @Test
    fun `refuses anything that is not integer paise, rather than guessing`() {
        assertThrows(Money.InvalidPaise::class.java) { Money.amountInWords("12.5") }
        assertThrows(Money.InvalidPaise::class.java) { Money.amountInWords("-100") }
        assertThrows(Money.InvalidPaise::class.java) { Money.formatRupees("not-a-number") }
    }

    @Test
    fun `masks an account to its last four, and never invents one`() {
        assertEquals("•••• 7781", Money.maskAccount("000123457781"))
        assertEquals("•••• 7781", Money.maskAccount("7781"))
        assertEquals("—", Money.maskAccount(null))
        assertEquals("—", Money.maskAccount("77"))
        assertEquals("—", Money.maskAccount("not-an-account"))
    }
}
