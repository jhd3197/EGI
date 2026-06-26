package com.egi.app.sms

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * JVM unit tests for the pure [SmsCheckin] parser. These mirror the cases the
 * server parser ([server/modules/sms.py] parse_checkin) covers so both sides
 * decode the same wire format identically.
 */
class SmsCheckinTest {

    @Test
    fun parsesCommaSeparatedForm() {
        val fields = SmsCheckin.parse("EGI CHECKIN V-12345678, Juan Pérez, Refugio Norte")

        assertEquals("V-12345678", fields?.cedula)
        assertEquals("Juan Pérez", fields?.name)
        assertEquals("Refugio Norte", fields?.location)
    }

    @Test
    fun parsesWhitespaceForm() {
        // First token = cédula, last = location, middle joined = name.
        val fields = SmsCheckin.parse("EGI CHECKIN V-12345678 Juan Pérez Refugio")

        assertEquals("V-12345678", fields?.cedula)
        assertEquals("Juan Pérez", fields?.name)
        assertEquals("Refugio", fields?.location)
    }

    @Test
    fun isCaseInsensitiveOnKeyword() {
        val fields = SmsCheckin.parse("egi checkin V-99999999, María, Albergue Sur")

        assertEquals("V-99999999", fields?.cedula)
        assertEquals("María", fields?.name)
        assertEquals("Albergue Sur", fields?.location)
    }

    @Test
    fun missingKeywordReturnsNull() {
        assertNull(SmsCheckin.parse("HELLO V-12345678, Juan, Refugio"))
    }

    @Test
    fun missingCedulaReturnsNull() {
        // Keyword present but no fields after it → no cédula.
        assertNull(SmsCheckin.parse("EGI CHECKIN"))
        assertNull(SmsCheckin.parse("EGI CHECKIN   "))
        // Comma form whose first field is empty → no cédula.
        assertNull(SmsCheckin.parse("EGI CHECKIN , Juan, Refugio"))
    }

    @Test
    fun nullOrBlankBodyReturnsNull() {
        assertNull(SmsCheckin.parse(null))
        assertNull(SmsCheckin.parse(""))
        assertNull(SmsCheckin.parse("   "))
    }

    @Test
    fun whitespaceFormWithTwoTokensHasEmptyLocation() {
        val fields = SmsCheckin.parse("EGI CHECKIN V-12345678 Juan")

        assertEquals("V-12345678", fields?.cedula)
        assertEquals("Juan", fields?.name)
        assertEquals("", fields?.location)
    }

    @Test
    fun whitespaceFormWithOnlyCedula() {
        val fields = SmsCheckin.parse("EGI CHECKIN V-12345678")

        assertEquals("V-12345678", fields?.cedula)
        assertEquals("", fields?.name)
        assertEquals("", fields?.location)
    }
}
