package com.egi.app.data

import com.egi.app.mesh.RecordEnvelope
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Animal record (plan-28 Missing Animals) mappers: the AnimalEntity <-> /sync JSON
 * and <-> mesh [RecordEnvelope] round-trips, plus the casing contract. Mirrors the
 * person tests because animals are a PARALLEL mesh track that carries `hop_count`
 * the same way persons do (they relay across the human chain).
 */
class AnimalEnvelopeTest {

    // TEST DATA — NOT REAL
    private fun sampleAnimal(
        createdAt: String = "2026-06-26T12:00:00.000Z",
        updatedAt: String = "2026-06-26T12:30:00.000Z",
        originDevice: String? = "device-test-01",
        hopCount: Int = 2,
    ): AnimalEntity = AnimalEntity(
        id = "egi-animal-test-0001",
        disasterId = "disaster-test",
        status = "missing",
        species = "dog",
        breed = "mestizo de prueba",
        name = "Firulais de prueba",
        sex = "male",
        size = "medium",
        color = "marrón",
        distinguishingMarks = "mancha blanca en el pecho",
        microchip = "CHIP-TEST-0001",
        photoUrl = "https://example.test/firulais.jpg",
        photos = "[\"https://example.test/firulais.jpg\"]",
        lastSeenLocation = "Refugio de prueba",
        lastSeenAt = "2026-06-25T08:00:00.000Z",
        lat = 10.6011,
        lon = -66.9320,
        ownerName = "María de prueba",
        ownerContact = "test@example.test",
        reporterId = "reporter-test-01",
        reporterName = "Juan de prueba",
        notes = "Responde a su nombre",
        source = "mesh",
        reviewed = 0,
        shelterId = "shelter-test-01",
        intakeAt = "2026-06-26T09:00:00.000Z",
        conditionNote = "Sano",
        originDevice = originDevice,
        hopCount = hopCount,
        createdAt = createdAt,
        updatedAt = updatedAt,
    )

    // --- Casing contract ------------------------------------------------------

    @Test
    fun toSyncJsonUsesCamelCaseTimestampsAndSnakeCaseHopCount() {
        val json = sampleAnimal().toSyncJson()

        // createdAt/updatedAt stay camelCase; snake_case variants must be absent.
        assertTrue(json.has("createdAt"))
        assertTrue(json.has("updatedAt"))
        assertFalse(json.has("created_at"))
        assertFalse(json.has("updated_at"))
        // hop_count is snake_case; record_type tags the parallel track.
        assertTrue(json.has("hop_count"))
        assertEquals(2, json.getInt("hop_count"))
        assertEquals(RecordEnvelope.TYPE_ANIMAL, json.getString("record_type"))
        assertEquals("dog", json.getString("species"))
        assertEquals("CHIP-TEST-0001", json.getString("microchip"))
    }

    // --- Sync JSON round-trip -------------------------------------------------

    @Test
    fun animalSyncJsonRoundTrip() {
        val original = sampleAnimal()

        val restored = animalFromSyncJson(original.toSyncJson())

        assertEquals(original.id, restored.id)
        assertEquals(original.status, restored.status)
        assertEquals(original.species, restored.species)
        assertEquals(original.breed, restored.breed)
        assertEquals(original.name, restored.name)
        assertEquals(original.microchip, restored.microchip)
        assertEquals(original.photos, restored.photos)
        assertEquals(original.lat!!, restored.lat!!, 0.0)
        assertEquals(original.lon!!, restored.lon!!, 0.0)
        assertEquals(original.shelterId, restored.shelterId)
        assertEquals(original.reviewed, restored.reviewed)
        assertEquals(original.originDevice, restored.originDevice)
        assertEquals(original.hopCount, restored.hopCount)
        assertEquals(original.createdAt, restored.createdAt)
        assertEquals(original.updatedAt, restored.updatedAt)
    }

    // --- Envelope round-trip --------------------------------------------------

    @Test
    fun animalEnvelopeRoundTrip() {
        val original = sampleAnimal()

        val env = original.toEnvelope()
        val restored = animalEntityFromEnvelope(env)

        assertEquals(RecordEnvelope.TYPE_ANIMAL, env.recordType)
        assertEquals(original.id, restored.id)
        assertEquals(original.name, restored.name)
        assertEquals(original.species, restored.species)
        assertEquals(original.createdAt, restored.createdAt)
        assertEquals(original.updatedAt, restored.updatedAt)
        assertEquals(original.hopCount, restored.hopCount)
    }

    @Test
    fun envelopeHopCountIsAuthoritative() {
        // Payload says hop_count=2, but the envelope transport says 7.
        val original = sampleAnimal(hopCount = 2)
        val env = original.toEnvelope().copy(hopCount = 7)

        val restored = animalEntityFromEnvelope(env)

        assertEquals(7, restored.hopCount)
    }

    @Test
    fun animalEnvelopeFallsBackToEnvelopeOriginDevice() {
        // Payload omits origin_device; the envelope's provenance should fill it in.
        val original = sampleAnimal(originDevice = null)
        val env = original.toEnvelope().copy(originDevice = "device-test-relay")

        val restored = animalEntityFromEnvelope(env)

        assertEquals("device-test-relay", restored.originDevice)
    }

    @Test
    fun relayIncrementsHopCountOnMerge() {
        // Simulate the relay step done in MeshRepository.mergeAnimalEnvelope: the
        // stored copy's hop_count becomes env.hopCount + 1 so the next hop sees an
        // accurate distance.
        val original = sampleAnimal(hopCount = 1)
        val env = original.toEnvelope() // hopCount = 1

        val relayedStore = animalEntityFromEnvelope(env).copy(hopCount = env.hopCount + 1)

        assertEquals(1, env.hopCount)
        assertEquals(2, relayedStore.hopCount)
    }
}
