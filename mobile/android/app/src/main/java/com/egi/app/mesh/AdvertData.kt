package com.egi.app.mesh

/**
 * Pure (Android-free) codec for the EGI advertisement service data, so the wire
 * format can be unit-tested off-device (plan-23 Phase 2/8).
 *
 * Layout (new): `[version][flags][bloom…]` where flags bit 0 is the gateway flag.
 * Layout (legacy): `[version][bloom…]` — emitted by older app versions that had no
 * flags byte; parsed as a non-gateway for backward compatibility.
 *
 * [BleAdvertiser] builds the bytes with [encode]; [BleScanner] reads them with
 * [parse]. Centralising the format here keeps the two sides in lock-step.
 */
object AdvertData {

    /** Build `[version][flags][bloom]` service data from a raw bloom payload. */
    fun encode(bloom: ByteArray, gateway: Boolean): ByteArray {
        val out = ByteArray(2 + bloom.size)
        out[0] = BleConstants.PROTOCOL_VERSION
        out[1] = if (gateway) BleConstants.GATEWAY_FLAG.toByte() else 0
        System.arraycopy(bloom, 0, out, 2, bloom.size)
        return out
    }

    /** Parsed advert: the bloom bytes (always [BleConstants.ADVERT_BLOOM_BYTES]) and the gateway flag. */
    data class Parsed(val bloomBytes: ByteArray, val isGateway: Boolean) {
        // value-style equality on the byte array (data classes compare arrays by reference).
        override fun equals(other: Any?): Boolean =
            other is Parsed && isGateway == other.isGateway && bloomBytes.contentEquals(other.bloomBytes)

        override fun hashCode(): Int = 31 * bloomBytes.contentHashCode() + isGateway.hashCode()
    }

    /**
     * Parse service data, accepting both the new flagged layout and the legacy
     * unflagged one. Returns null when the version byte mismatches or the length is
     * not a recognised bloom size, so callers can ignore foreign/incompatible adverts.
     */
    fun parse(raw: ByteArray): Parsed? {
        if (raw.isEmpty() || raw[0] != BleConstants.PROTOCOL_VERSION) return null
        val n = BleConstants.ADVERT_BLOOM_BYTES
        return when (raw.size) {
            2 + n -> Parsed(raw.copyOfRange(2, raw.size), (raw[1].toInt() and BleConstants.GATEWAY_FLAG) != 0)
            1 + n -> Parsed(raw.copyOfRange(1, raw.size), false) // legacy, no flags byte
            else -> null
        }
    }
}
