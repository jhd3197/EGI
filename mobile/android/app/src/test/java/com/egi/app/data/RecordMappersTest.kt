package com.egi.app.data

import com.egi.app.mesh.RecordEnvelope
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Sync index diff logic (the [isNewer] last-write-wins comparator) plus the
 * PersonEntity <-> JSON / envelope mappers, including the casing contract.
 */
class RecordMappersTest {

    // TEST DATA — NOT REAL
    private fun samplePerson(
        createdAt: String = "2026-06-26T12:00:00.000Z",
        updatedAt: String = "2026-06-26T12:30:00.000Z",
        originDevice: String? = "device-test-01",
        hopCount: Int = 2,
    ): PersonEntity = PersonEntity(
        id = "egi-test-0001",
        disasterId = "disaster-test",
        name = "Juan Pérez de prueba",
        status = "missing",
        age = 42,
        location = "Refugio de prueba",
        cedula = "V-00000000",
        originDevice = originDevice,
        hopCount = hopCount,
        createdAt = createdAt,
        updatedAt = updatedAt,
    )

    // --- isNewer --------------------------------------------------------------

    @Test
    fun isNewerNullAIsNeverNewer() {
        assertFalse(isNewer(null, "2026-06-26T12:00:00.000Z"))
    }

    @Test
    fun isNewerRealABeatsNullB() {
        assertTrue(isNewer("2026-06-26T12:00:00.000Z", null))
    }

    @Test
    fun isNewerBothNullIsFalse() {
        assertFalse(isNewer(null, null))
    }

    @Test
    fun isNewerLexicographicCompare() {
        assertTrue(isNewer("2026-06-26T12:30:00.000Z", "2026-06-26T12:00:00.000Z"))
        assertFalse(isNewer("2026-06-26T12:00:00.000Z", "2026-06-26T12:30:00.000Z"))
    }

    @Test
    fun isNewerEqualIsFalse() {
        val ts = "2026-06-26T12:00:00.000Z"
        assertFalse(isNewer(ts, ts))
    }

    // --- Casing contract ------------------------------------------------------

    @Test
    fun toSyncJsonUsesCamelCaseTimestampsAndSnakeCaseHopCount() {
        val json = samplePerson().toSyncJson()

        // createdAt/updatedAt stay camelCase; snake_case variants must be absent.
        assertTrue(json.has("createdAt"))
        assertTrue(json.has("updatedAt"))
        assertFalse(json.has("created_at"))
        assertFalse(json.has("updated_at"))
        // hop_count is snake_case.
        assertTrue(json.has("hop_count"))
        assertEquals(2, json.getInt("hop_count"))
        assertEquals("Juan Pérez de prueba", json.getString("name"))
        assertEquals("V-00000000", json.getString("cedula"))
    }

    // --- Sync JSON round-trip -------------------------------------------------

    @Test
    fun personSyncJsonRoundTrip() {
        val original = samplePerson()

        val restored = personFromSyncJson(original.toSyncJson())

        assertEquals(original.id, restored.id)
        assertEquals(original.name, restored.name)
        assertEquals(original.status, restored.status)
        assertEquals(original.age, restored.age)
        assertEquals(original.cedula, restored.cedula)
        assertEquals(original.originDevice, restored.originDevice)
        assertEquals(original.hopCount, restored.hopCount)
        assertEquals(original.createdAt, restored.createdAt)
        assertEquals(original.updatedAt, restored.updatedAt)
    }

    // --- Envelope round-trip --------------------------------------------------

    @Test
    fun personEnvelopeRoundTrip() {
        val original = samplePerson()

        val env = original.toEnvelope()
        val restored = personEntityFromEnvelope(env)

        assertEquals(original.id, restored.id)
        assertEquals(original.name, restored.name)
        assertEquals(original.createdAt, restored.createdAt)
        assertEquals(original.updatedAt, restored.updatedAt)
        assertEquals(original.hopCount, restored.hopCount)
    }

    @Test
    fun envelopeHopCountIsAuthoritative() {
        // Payload says hop_count=2, but the envelope transport says 7.
        val original = samplePerson(hopCount = 2)
        val env = original.toEnvelope().copy(hopCount = 7)

        val restored = personEntityFromEnvelope(env)

        assertEquals(7, restored.hopCount)
    }

    // --- ReportEntity round-trips ---------------------------------------------

    // TEST DATA — NOT REAL
    private fun sampleReport(
        createdAt: String = "2026-06-26T12:00:00.000Z",
        updatedAt: String = "2026-06-26T12:30:00.000Z",
        originDevice: String? = "device-test-01",
    ): ReportEntity = ReportEntity(
        id = "egi-report-0001",
        personId = "egi-test-0001",
        authorName = "María de prueba",
        authorRelation = "hermana",
        status = "found",
        note = "Vista en el refugio de prueba",
        location = "Refugio de prueba",
        source = "mesh",
        originDevice = originDevice,
        createdAt = createdAt,
        updatedAt = updatedAt,
    )

    @Test
    fun reportSyncJsonRoundTrip() {
        val original = sampleReport()

        val restored = reportFromSyncJson(original.toSyncJson())

        assertEquals(original.id, restored.id)
        assertEquals(original.personId, restored.personId)
        assertEquals(original.authorName, restored.authorName)
        assertEquals(original.authorRelation, restored.authorRelation)
        assertEquals(original.status, restored.status)
        assertEquals(original.note, restored.note)
        assertEquals(original.location, restored.location)
        assertEquals(original.source, restored.source)
        assertEquals(original.originDevice, restored.originDevice)
        assertEquals(original.createdAt, restored.createdAt)
        assertEquals(original.updatedAt, restored.updatedAt)
    }

    @Test
    fun reportSyncJsonUsesCamelCaseTimestamps() {
        val json = sampleReport().toSyncJson()

        // createdAt/updatedAt stay camelCase; snake_case variants must be absent.
        assertTrue(json.has("createdAt"))
        assertTrue(json.has("updatedAt"))
        assertFalse(json.has("created_at"))
        assertFalse(json.has("updated_at"))
        // Other fields are snake_case.
        assertEquals("egi-test-0001", json.getString("person_id"))
        assertEquals("María de prueba", json.getString("author_name"))
    }

    @Test
    fun reportEnvelopeRoundTrip() {
        val original = sampleReport()

        val env = original.toEnvelope()
        val restored = reportEntityFromEnvelope(env)

        assertEquals(RecordEnvelope.TYPE_REPORT, env.recordType)
        // Reports don't track hops over the mesh.
        assertEquals(0, env.hopCount)
        assertEquals(original.id, restored.id)
        assertEquals(original.personId, restored.personId)
        assertEquals(original.note, restored.note)
        assertEquals(original.status, restored.status)
        assertEquals(original.originDevice, restored.originDevice)
        assertEquals(original.createdAt, restored.createdAt)
        assertEquals(original.updatedAt, restored.updatedAt)
    }

    @Test
    fun reportEnvelopeFallsBackToEnvelopeOriginDevice() {
        // Payload omits origin_device; the envelope's provenance should fill it in.
        val original = sampleReport(originDevice = null)
        val env = original.toEnvelope().copy(originDevice = "device-test-relay")

        val restored = reportEntityFromEnvelope(env)

        assertEquals("device-test-relay", restored.originDevice)
    }
}
