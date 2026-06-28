package com.egi.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Exact-dedup normalization parity with the server
 * (`server/modules/duplicates.py`). Every expected value below is the literal
 * output of the corresponding Python function so the mesh client clusters records
 * identically to the gateway (plan-27 Phase 6).
 */
class DedupNormalizeTest {

    // --- normalizeCedula ------------------------------------------------------

    @Test
    fun cedulaVariantsCollapse() {
        // V-12.345.678 keeps its prefix letter + digits; v12345678 matches it.
        assertEquals("V12345678", DedupNormalize.normalizeCedula("V-12.345.678"))
        assertEquals("V12345678", DedupNormalize.normalizeCedula("v12345678"))
        // No prefix -> digits only (server keeps the letter optional).
        assertEquals("12345678", DedupNormalize.normalizeCedula("12.345.678"))
    }

    @Test
    fun cedulaPrefixOnlyKeptBeforeDigits() {
        // A letter after the first digit is not a nationality prefix — dropped.
        assertEquals("12345", DedupNormalize.normalizeCedula("123V45"))
    }

    @Test
    fun cedulaNoDigitsIsEmpty() {
        assertEquals("", DedupNormalize.normalizeCedula("abc"))
        assertEquals("", DedupNormalize.normalizeCedula(""))
        assertEquals("", DedupNormalize.normalizeCedula(null))
    }

    // --- normalizePhone -------------------------------------------------------

    @Test
    fun phoneVariantsCollapseToLastTen() {
        // +58 412-555-1234 -> digits 584125551234 -> last 10; 04125551234 -> last 10.
        assertEquals("4125551234", DedupNormalize.normalizePhone("+58 412-555-1234"))
        assertEquals("4125551234", DedupNormalize.normalizePhone("04125551234"))
        assertEquals(
            DedupNormalize.normalizePhone("+58 412-555-1234"),
            DedupNormalize.normalizePhone("04125551234"),
        )
    }

    @Test
    fun phoneTooShortIsEmpty() {
        assertEquals("", DedupNormalize.normalizePhone("12345")) // 5 digits < 7
        assertEquals("", DedupNormalize.normalizePhone("123-456")) // 6 digits < 7
        assertEquals("", DedupNormalize.normalizePhone(null))
    }

    @Test
    fun phoneExactlySevenDigitsKept() {
        assertEquals("1234567", DedupNormalize.normalizePhone("123-4567"))
    }

    // --- normalizeName --------------------------------------------------------

    @Test
    fun nameAccentsStrippedAndLowercasedAndCollapsed() {
        assertEquals("jose nunez", DedupNormalize.normalizeName("José  Núñez"))
        assertEquals("maria perez", DedupNormalize.normalizeName("  MARÍA   Pérez  "))
        assertEquals("", DedupNormalize.normalizeName(null))
        assertEquals("", DedupNormalize.normalizeName("   "))
    }

    // --- exactKey precedence --------------------------------------------------

    @Test
    fun exactKeyCedulaBeatsPhoneName() {
        // With a cédula present, the phone+name pair is ignored (cédula wins).
        assertEquals(
            "cedula:V12345678",
            DedupNormalize.exactKey("V-12.345.678", "+58 412-555-1234", "José Núñez"),
        )
    }

    @Test
    fun exactKeyPhoneNameWhenNoCedula() {
        assertEquals(
            "phonename:4125551234|jose nunez",
            DedupNormalize.exactKey(null, "+58 412-555-1234", "José Núñez"),
        )
    }

    @Test
    fun exactKeyNullWhenNeither() {
        // No cédula, phone too short -> no exact key.
        assertNull(DedupNormalize.exactKey(null, "12345", "José Núñez"))
        // Phone present but no name -> no phone+name key.
        assertNull(DedupNormalize.exactKey(null, "+58 412-555-1234", null))
        // Nothing at all.
        assertNull(DedupNormalize.exactKey(null, null, null))
    }

    @Test
    fun exactKeyMatchesAcrossFormatVariants() {
        // Two formattings of the same identity yield the same key.
        val a = DedupNormalize.exactKey(null, "+58 412-555-1234", "José Núñez")
        val b = DedupNormalize.exactKey(null, "0412 555 1234", "jose nunez")
        assertEquals(a, b)
    }
}
