package com.egi.app.mesh

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Wire-format tests for the advertisement service data + gateway flag (plan-23
 * Phase 2/8): encode/parse round-trips, the gateway bit, and backward compatibility
 * with the legacy unflagged layout that older app versions emit.
 */
class AdvertDataTest {

    private fun bloom(): ByteArray =
        ByteArray(BleConstants.ADVERT_BLOOM_BYTES) { (it * 7 + 1).toByte() }

    @Test
    fun encodesVersionFlagsBloom() {
        val data = AdvertData.encode(bloom(), gateway = true)
        assertEquals(2 + BleConstants.ADVERT_BLOOM_BYTES, data.size)
        assertEquals(BleConstants.PROTOCOL_VERSION, data[0])
        assertEquals(BleConstants.GATEWAY_FLAG.toByte(), data[1])
    }

    @Test
    fun nonGatewayLeavesFlagBitClear() {
        val data = AdvertData.encode(bloom(), gateway = false)
        assertEquals(0.toByte(), data[1])
        val parsed = AdvertData.parse(data)!!
        assertFalse(parsed.isGateway)
    }

    @Test
    fun gatewayRoundTrips() {
        val b = bloom()
        val parsed = AdvertData.parse(AdvertData.encode(b, gateway = true))!!
        assertTrue(parsed.isGateway)
        assertArrayEquals(b, parsed.bloomBytes)
    }

    @Test
    fun legacyUnflaggedFormatParsesAsNonGateway() {
        // Old layout: [version][bloom16], no flags byte.
        val b = bloom()
        val legacy = ByteArray(1 + b.size).also {
            it[0] = BleConstants.PROTOCOL_VERSION
            System.arraycopy(b, 0, it, 1, b.size)
        }
        val parsed = AdvertData.parse(legacy)!!
        assertFalse("a peer with no flags byte must look like a non-gateway", parsed.isGateway)
        assertArrayEquals(b, parsed.bloomBytes)
    }

    @Test
    fun wrongVersionIsRejected() {
        val data = AdvertData.encode(bloom(), gateway = false)
        data[0] = (BleConstants.PROTOCOL_VERSION + 1).toByte()
        assertNull(AdvertData.parse(data))
    }

    @Test
    fun wrongLengthIsRejected() {
        assertNull(AdvertData.parse(ByteArray(0)))
        assertNull(AdvertData.parse(byteArrayOf(BleConstants.PROTOCOL_VERSION)))
        // version + flags but a truncated bloom.
        assertNull(AdvertData.parse(byteArrayOf(BleConstants.PROTOCOL_VERSION, 0, 1, 2, 3)))
    }
}
