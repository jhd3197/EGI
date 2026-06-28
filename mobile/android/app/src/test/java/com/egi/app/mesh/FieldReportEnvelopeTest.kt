package com.egi.app.mesh

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

/**
 * SAR field report (plan-26 Phase 4) transport: a `field_report` envelope must
 * round-trip through [EnvelopeCodec] — both the plaintext and the encrypted
 * variants — with `recordType == "field_report"` and every payload key intact,
 * proving the codec carries it opaquely exactly like a person/report record.
 */
class FieldReportEnvelopeTest {

    // TEST DATA — NOT REAL: mirrors the body the PWA POSTs to
    // /sar/operations/{id}/field-reports.
    private fun sampleFieldReport(): JSONObject = JSONObject().apply {
        put("id", "egi-fr-test-0001")
        put("type", "sighting")
        put("operation_id", "op-test-laguaira")
        put("sector_id", "sector-test-07")
        put("person_id", "egi-test-0001")
        put("note", "Persona vista cerca del refugio de prueba")
        put("lat", 10.6011)
        put("lon", -66.9320)
        put("reporter_alias", "brigada-prueba")
        put("origin_device", "device-test-01")
        put("created_at", "2026-06-26T12:00:00.000Z")
        put("updated_at", "2026-06-26T12:30:00.000Z")
    }

    private fun assertPayloadIntact(payload: JSONObject) {
        assertEquals("egi-fr-test-0001", payload.getString("id"))
        assertEquals("sighting", payload.getString("type"))
        assertEquals("op-test-laguaira", payload.getString("operation_id"))
        assertEquals("sector-test-07", payload.getString("sector_id"))
        assertEquals("egi-test-0001", payload.getString("person_id"))
        assertEquals("Persona vista cerca del refugio de prueba", payload.getString("note"))
        assertEquals(10.6011, payload.getDouble("lat"), 0.0)
        assertEquals(-66.9320, payload.getDouble("lon"), 0.0)
        assertEquals("brigada-prueba", payload.getString("reporter_alias"))
        assertEquals("device-test-01", payload.getString("origin_device"))
    }

    @Test
    fun fieldReportEnvelopeRoundTripsPlaintext() {
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_FIELD_REPORT,
            recordId = "egi-fr-test-0001",
            originDevice = "device-test-01",
            hopCount = 1,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:30:00.000Z",
            payload = sampleFieldReport(),
        )

        val decoded = EnvelopeCodec.decodeEnvelope(EnvelopeCodec.encodeEnvelope(original))

        assertEquals(RecordEnvelope.TYPE_FIELD_REPORT, decoded.recordType)
        assertEquals("field_report", decoded.recordType)
        assertEquals(original.recordId, decoded.recordId)
        assertEquals(original.originDevice, decoded.originDevice)
        assertEquals(original.hopCount, decoded.hopCount)
        assertEquals(original.createdAt, decoded.createdAt)
        assertEquals(original.updatedAt, decoded.updatedAt)
        assertPayloadIntact(decoded.payload)
    }

    @Test
    fun fieldReportProducerBuildsFieldReportEnvelope() {
        // The producer side a future field-report UI/bridge would call.
        val env = com.egi.app.data.fieldReportEnvelope(sampleFieldReport())

        assertEquals(RecordEnvelope.TYPE_FIELD_REPORT, env.recordType)
        assertEquals("egi-fr-test-0001", env.recordId)
        assertEquals("device-test-01", env.originDevice)
        assertEquals(0, env.hopCount)
        assertEquals("2026-06-26T12:00:00.000Z", env.createdAt)
        assertEquals("2026-06-26T12:30:00.000Z", env.updatedAt)

        val decoded = EnvelopeCodec.decodeEnvelope(EnvelopeCodec.encodeEnvelope(env))
        assertEquals("field_report", decoded.recordType)
        assertPayloadIntact(decoded.payload)
    }

    @Test
    fun fieldReportEnvelopeRoundTripsEncrypted() {
        val key = freshSessionKey()
        val original = RecordEnvelope(
            recordType = RecordEnvelope.TYPE_FIELD_REPORT,
            recordId = "egi-fr-test-0001",
            originDevice = "device-test-01",
            hopCount = 0,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:30:00.000Z",
            payload = sampleFieldReport(),
        )

        val encoded = EnvelopeCodec.encodeEnvelopeEncrypted(original, key)
        // The note (free-text PII) must NOT appear in the encoded bytes.
        val wire = String(encoded, Charsets.UTF_8)
        assertFalse(wire.contains("Persona vista cerca del refugio de prueba"))
        // Header fields stay readable so last-write-wins works without decrypting.
        assertEquals(true, wire.contains("egi-fr-test-0001"))
        assertEquals(true, wire.contains("field_report"))

        val decoded = EnvelopeCodec.decodeEnvelopeEncrypted(encoded, key)
        assertEquals(RecordEnvelope.TYPE_FIELD_REPORT, decoded.recordType)
        assertEquals("field_report", decoded.recordType)
        assertEquals(original.recordId, decoded.recordId)
        assertEquals(original.originDevice, decoded.originDevice)
        assertEquals(original.hopCount, decoded.hopCount)
        assertEquals(original.createdAt, decoded.createdAt)
        assertEquals(original.updatedAt, decoded.updatedAt)
        assertPayloadIntact(decoded.payload)
    }

    /** A fresh session key derived through a full ECDH exchange between two parties. */
    private fun freshSessionKey(): ByteArray {
        val alice = MeshCrypto.generateKeyPair()
        val bob = MeshCrypto.generateKeyPair()
        return MeshCrypto.deriveSessionKey(alice.private, MeshCrypto.publicKeyBytes(bob.public))
    }
}
