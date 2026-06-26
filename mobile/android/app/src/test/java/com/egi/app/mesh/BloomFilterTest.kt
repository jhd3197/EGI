package com.egi.app.mesh

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * BLE advertisement parser coverage for the bloom filter carried in the advert.
 *
 * Invariant under test: no false negatives — every added id MUST report
 * [BloomFilter.mightContain] == true. Absent ids may false-positive, so we only
 * assert membership for added ids, plus that serialization preserves membership.
 */
class BloomFilterTest {

    // TEST DATA — NOT REAL
    private val ids = listOf(
        "egi-test-0001",
        "egi-test-0002",
        "egi-test-0003",
        "egi-test-0004",
        "egi-test-0005",
    )

    @Test
    fun addedIdsHaveNoFalseNegatives() {
        val filter = BloomFilter()
        ids.forEach { filter.add(it) }

        ids.forEach { id ->
            assertTrue("added id should be present: $id", filter.mightContain(id))
        }
    }

    @Test
    fun ofBuildsEquivalentFilter() {
        val manual = BloomFilter()
        ids.forEach { manual.add(it) }

        val built = BloomFilter.of(ids)

        // Same backing bytes => identical membership behaviour.
        assertEquals(
            manual.toBytes().toList(),
            built.toBytes().toList(),
        )
        ids.forEach { id ->
            assertTrue(built.mightContain(id))
        }
    }

    @Test
    fun toBytesFromBytesRoundTripPreservesMembership() {
        val filter = BloomFilter.of(ids)

        val restored = BloomFilter.fromBytes(filter.toBytes())

        assertEquals(filter.toBytes().toList(), restored.toBytes().toList())
        ids.forEach { id ->
            assertTrue("membership must survive serialization: $id", restored.mightContain(id))
        }
    }

    @Test
    fun toBytesHasExpectedAdvertSize() {
        val filter = BloomFilter.of(ids)
        assertEquals(BleConstants.ADVERT_BLOOM_BYTES, filter.toBytes().size)
    }

    @Test
    fun absentIdReportsNotPresentWhenNoBitsCollide() {
        // An empty filter cannot false-positive: nothing has been added, so an
        // unseen id must report absent. Guards the membership read path.
        // TEST DATA — NOT REAL
        val empty = BloomFilter()
        assertEquals(false, empty.mightContain("egi-test-9999"))
    }
}
