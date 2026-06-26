package com.egi.app.mesh

/**
 * Tiny fixed-size bloom filter used in the BLE advertisement so a passing peer
 * can cheaply guess "do you already have everything I hold?" and skip a costly
 * GATT connection when the answer is almost certainly yes.
 *
 * Membership is probabilistic: [mightContain] may return true for an absent item
 * (false positive) but never false for a present one. That bias is exactly what
 * we want — a false positive only risks skipping a sync we'd have done anyway,
 * never corrupting data.
 *
 * Backed by [BleConstants.ADVERT_BLOOM_BYTES] bytes with `k` hash probes derived
 * via double hashing (Kirsch–Mitzenmacher) from a single 64-bit FNV-1a hash.
 */
class BloomFilter(
    private val bits: ByteArray = ByteArray(BleConstants.ADVERT_BLOOM_BYTES),
    private val hashes: Int = DEFAULT_HASHES,
) {
    private val bitCount: Int = bits.size * 8

    fun add(value: String) {
        forEachBit(value) { index -> bits[index ushr 3] = (bits[index ushr 3].toInt() or (1 shl (index and 7))).toByte() }
    }

    fun mightContain(value: String): Boolean {
        var present = true
        forEachBit(value) { index ->
            if (bits[index ushr 3].toInt() and (1 shl (index and 7)) == 0) present = false
        }
        return present
    }

    fun toBytes(): ByteArray = bits.copyOf()

    private inline fun forEachBit(value: String, action: (Int) -> Unit) {
        val h = fnv1a64(value)
        val h1 = (h and 0xFFFFFFFFL).toInt()
        val h2 = (h ushr 32).toInt() or 1 // odd step keeps probes well distributed
        for (i in 0 until hashes) {
            val combined = (h1 + i * h2)
            val index = (combined and 0x7FFFFFFF) % bitCount
            action(index)
        }
    }

    companion object {
        const val DEFAULT_HASHES = 4

        fun fromBytes(bytes: ByteArray, hashes: Int = DEFAULT_HASHES): BloomFilter =
            BloomFilter(bytes.copyOf(), hashes)

        /** Build a filter populated from a set of record IDs. */
        fun of(recordIds: Collection<String>): BloomFilter {
            val filter = BloomFilter()
            recordIds.forEach { filter.add(it) }
            return filter
        }

        private fun fnv1a64(value: String): Long {
            var hash = -0x340d631b7bdddcdbL // 14695981039346656037 (FNV offset basis)
            for (b in value.toByteArray(Charsets.UTF_8)) {
                hash = hash xor (b.toLong() and 0xFF)
                hash *= 0x100000001b3L // FNV prime
            }
            return hash
        }
    }
}
