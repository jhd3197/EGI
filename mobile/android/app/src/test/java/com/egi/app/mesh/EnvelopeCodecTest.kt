package com.egi.app.mesh

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Record envelope serialization/deserialization: round-trips through the
 * [EnvelopeCodec] for envelopes, index entries, and request id lists.
 */
class EnvelopeCodecTest {

    // TEST DATA — NOT REAL
    private fun samplePayload(): JSONObject = JSONObject().apply {
        put("id", "egi-test-0001")
        put("name", "Juan Pérez de prueba")
        put("cedula", "V-00000000")
        put("status", "missing")
        put("hop_count", 2)
    }

    @Test
    fun envelopeRoundTripPreservesAllFields() {
        // TEST DATA — NOT REAL
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_PERSON,
            recordId = "egi-test-0001",
            originDevice = "device-test-01",
            hopCount = 2,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:30:00.000Z",
            payload = samplePayload(),
        )

        val decoded = EnvelopeCodec.decodeEnvelope(EnvelopeCodec.encodeEnvelope(original))

        assertEquals(original.recordType, decoded.recordType)
        assertEquals(original.recordId, decoded.recordId)
        assertEquals(original.originDevice, decoded.originDevice)
        assertEquals(original.hopCount, decoded.hopCount)
        assertEquals(original.createdAt, decoded.createdAt)
        assertEquals(original.updatedAt, decoded.updatedAt)
        // Payload contents survive the round-trip.
        assertEquals("Juan Pérez de prueba", decoded.payload.getString("name"))
        assertEquals("V-00000000", decoded.payload.getString("cedula"))
        assertEquals(2, decoded.payload.getInt("hop_count"))
    }

    @Test
    fun envelopeRoundTripHandlesNullOriginDevice() {
        // TEST DATA — NOT REAL
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_REPORT,
            recordId = "egi-test-0002",
            originDevice = null,
            hopCount = 0,
            createdAt = null,
            updatedAt = null,
            payload = JSONObject().put("id", "egi-test-0002"),
        )

        val decoded = EnvelopeCodec.decodeEnvelope(EnvelopeCodec.encodeEnvelope(original))

        assertNull(decoded.originDevice)
        assertNull(decoded.createdAt)
        assertNull(decoded.updatedAt)
        assertEquals(RecordEnvelope.TYPE_REPORT, decoded.recordType)
        assertEquals(0, decoded.hopCount)
    }

    @Test
    fun fromJsonDefaultsRecordTypeToPersonWhenAbsent() {
        // TEST DATA — NOT REAL: payload with no record_type key.
        val obj = JSONObject().apply {
            put("record_id", "egi-test-0003")
            put("payload", JSONObject().put("id", "egi-test-0003"))
        }

        val env = RecordEnvelope.fromJson(obj)

        assertEquals(RecordEnvelope.TYPE_PERSON, env.recordType)
        assertEquals(0, env.hopCount)
        assertNull(env.originDevice)
    }

    @Test
    fun relayedIncrementsHopCount() {
        // TEST DATA — NOT REAL
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_PERSON,
            recordId = "egi-test-0004",
            originDevice = "device-test-02",
            hopCount = 3,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:00:00.000Z",
            payload = samplePayload(),
        )

        val relayed = original.relayed()

        assertEquals(4, relayed.hopCount)
        // Other fields untouched.
        assertEquals(original.recordId, relayed.recordId)
        assertEquals(original.originDevice, relayed.originDevice)
    }

    @Test
    fun indexRoundTripPreservesEntries() {
        // TEST DATA — NOT REAL
        val entries = listOf(
            IndexEntry(recordId = "egi-test-0001", updatedAt = "2026-06-26T12:00:00.000Z", hopCount = 1),
            IndexEntry(recordId = "egi-test-0002", updatedAt = null, hopCount = 0),
        )

        val decoded = EnvelopeCodec.decodeIndex(EnvelopeCodec.encodeIndex(entries))

        assertEquals(entries.size, decoded.size)
        assertEquals("egi-test-0001", decoded[0].recordId)
        assertEquals("2026-06-26T12:00:00.000Z", decoded[0].updatedAt)
        assertEquals(1, decoded[0].hopCount)
        assertEquals("egi-test-0002", decoded[1].recordId)
        assertNull(decoded[1].updatedAt)
        assertEquals(0, decoded[1].hopCount)
    }

    @Test
    fun requestRoundTripPreservesIds() {
        // TEST DATA — NOT REAL
        val ids = listOf("egi-test-0001", "egi-test-0002", "egi-test-0003")

        val decoded = EnvelopeCodec.decodeRequest(EnvelopeCodec.encodeRequest(ids))

        assertEquals(ids, decoded)
        assertTrue(decoded.contains("egi-test-0002"))
        assertFalse(decoded.contains("egi-test-9999"))
    }
}
