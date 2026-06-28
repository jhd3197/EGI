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
    fun envelopeRoundTripPreservesPlan25TrustFieldsInPayload() {
        // Plan-25: the trust signals ride inside payload and must survive relay.
        // TEST DATA — NOT REAL
        val payload = samplePayload().apply {
            put("author_role", "operator")
            put("org_id", "org-cruzroja")
            put("location_id", "loc-la-guaira")
            put("signature", "BASE64SIGNATURETESTONLY==")
            put("trust_tier", "high")
        }
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_PERSON,
            recordId = "egi-test-0001",
            originDevice = "device-test-01",
            hopCount = 1,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:30:00.000Z",
            payload = payload,
        )

        val decoded = EnvelopeCodec.decodeEnvelope(EnvelopeCodec.encodeEnvelope(original))

        assertEquals("operator", decoded.payload.getString("author_role"))
        assertEquals("org-cruzroja", decoded.payload.getString("org_id"))
        assertEquals("loc-la-guaira", decoded.payload.getString("location_id"))
        assertEquals("BASE64SIGNATURETESTONLY==", decoded.payload.getString("signature"))
        assertEquals("high", decoded.payload.getString("trust_tier"))
    }

    @Test
    fun encryptedEnvelopePreservesPlan25TrustFieldsInPayload() {
        val key = freshSessionKey()
        // TEST DATA — NOT REAL
        val payload = samplePayload().apply {
            put("author_role", "commander")
            put("org_id", "org-pc")
            put("location_id", "loc-maiquetia")
            put("signature", "ANOTHERSIGTESTONLY==")
            put("trust_tier", "medium")
        }
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_PERSON,
            recordId = "egi-test-0001",
            originDevice = "device-test-01",
            hopCount = 0,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:30:00.000Z",
            payload = payload,
        )

        val decoded = EnvelopeCodec.decodeEnvelopeEncrypted(
            EnvelopeCodec.encodeEnvelopeEncrypted(original, key), key,
        )

        assertEquals("commander", decoded.payload.getString("author_role"))
        assertEquals("org-pc", decoded.payload.getString("org_id"))
        assertEquals("loc-maiquetia", decoded.payload.getString("location_id"))
        assertEquals("ANOTHERSIGTESTONLY==", decoded.payload.getString("signature"))
        assertEquals("medium", decoded.payload.getString("trust_tier"))
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

    /** A fresh session key derived through a full ECDH exchange between two parties. */
    private fun freshSessionKey(): ByteArray {
        val alice = MeshCrypto.generateKeyPair()
        val bob = MeshCrypto.generateKeyPair()
        return MeshCrypto.deriveSessionKey(alice.private, MeshCrypto.publicKeyBytes(bob.public))
    }

    @Test
    fun encryptedPersonEnvelopeRoundTripsAndHidesPayload() {
        val key = freshSessionKey()
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

        val encoded = EnvelopeCodec.encodeEnvelopeEncrypted(original, key)
        // The name (PII) must NOT appear in the encoded bytes — payload is encrypted.
        val wire = String(encoded, Charsets.UTF_8)
        assertFalse(wire.contains("Juan Pérez de prueba"))
        assertFalse(wire.contains("V-00000000"))
        // Header fields stay readable so last-write-wins works without decrypting.
        assertTrue(wire.contains("egi-test-0001"))
        assertTrue(wire.contains("2026-06-26T12:30:00.000Z"))

        val decoded = EnvelopeCodec.decodeEnvelopeEncrypted(encoded, key)
        assertEquals(original.recordType, decoded.recordType)
        assertEquals(original.recordId, decoded.recordId)
        assertEquals(original.originDevice, decoded.originDevice)
        assertEquals(original.hopCount, decoded.hopCount)
        assertEquals(original.createdAt, decoded.createdAt)
        assertEquals(original.updatedAt, decoded.updatedAt)
        assertEquals("Juan Pérez de prueba", decoded.payload.getString("name"))
        assertEquals("V-00000000", decoded.payload.getString("cedula"))
        assertEquals(2, decoded.payload.getInt("hop_count"))
    }

    @Test
    fun encryptedReportEnvelopeRoundTrips() {
        val key = freshSessionKey()
        // TEST DATA — NOT REAL
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_REPORT,
            recordId = "egi-test-0002",
            originDevice = null,
            hopCount = 0,
            createdAt = null,
            updatedAt = "2026-06-26T13:00:00.000Z",
            payload = JSONObject().apply {
                put("id", "egi-test-0002")
                put("note", "Visto en el refugio de prueba")
            },
        )

        val encoded = EnvelopeCodec.encodeEnvelopeEncrypted(original, key)
        assertFalse(String(encoded, Charsets.UTF_8).contains("Visto en el refugio de prueba"))

        val decoded = EnvelopeCodec.decodeEnvelopeEncrypted(encoded, key)
        assertEquals(RecordEnvelope.TYPE_REPORT, decoded.recordType)
        assertEquals("egi-test-0002", decoded.recordId)
        assertNull(decoded.originDevice)
        assertNull(decoded.createdAt)
        assertEquals("2026-06-26T13:00:00.000Z", decoded.updatedAt)
        assertEquals("Visto en el refugio de prueba", decoded.payload.getString("note"))
    }

    @Test(expected = Exception::class)
    fun encryptedEnvelopeFailsToDecodeWithWrongKey() {
        val key = freshSessionKey()
        val wrongKey = freshSessionKey()
        // TEST DATA — NOT REAL
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_PERSON,
            recordId = "egi-test-0003",
            originDevice = "device-test-03",
            hopCount = 0,
            createdAt = null,
            updatedAt = null,
            payload = samplePayload(),
        )

        val encoded = EnvelopeCodec.encodeEnvelopeEncrypted(original, key)
        EnvelopeCodec.decodeEnvelopeEncrypted(encoded, wrongKey)
    }
}
