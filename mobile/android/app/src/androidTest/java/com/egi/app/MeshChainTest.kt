package com.egi.app

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.egi.app.data.EgiDatabase
import com.egi.app.data.MeshRepository
import com.egi.app.data.PersonEntity
import com.egi.app.data.toEnvelope
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * End-to-end-ish checks of the human-chain relay rules at the data layer (plan-23
 * Phase 3/8), exercised against real Room storage on a device:
 *
 *  - A record received from a peer over the mesh becomes *pending for the cloud*, so
 *    a gateway that receives it will upload it on its next cloud sync round.
 *  - Each relay hop increments the stored hop_count, so a record that travels the
 *    chain carries an accurate distance — and the value a peer would receive (the
 *    re-emitted envelope) reflects that hop.
 */
@RunWith(AndroidJUnit4::class)
class MeshChainTest {

    private lateinit var db: EgiDatabase
    private lateinit var repo: MeshRepository

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, EgiDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        repo = MeshRepository(db, "device-gateway-test") // TEST DATA — NOT REAL
    }

    @After
    fun tearDown() = db.close()

    // TEST DATA — NOT REAL
    private fun person(id: String, hopCount: Int) = PersonEntity(
        id = id,
        disasterId = "disaster-test",
        name = "Persona de prueba",
        status = "missing",
        age = 25,
        location = "Refugio de prueba",
        cedula = "V-00000000",
        originDevice = "device-offline-peer",
        hopCount = hopCount,
        createdAt = "2026-06-26T10:00:00Z",
        updatedAt = "2026-06-26T12:00:00Z",
    )

    @Test
    fun recordReceivedFromPeerIsPendingForCloudUpload() = runBlocking {
        val id = "egi-test-chain-0001"
        // Simulate receiving an offline peer's record over the mesh.
        val changed = repo.mergeEnvelope(person(id, hopCount = 1).toEnvelope().copy(hopCount = 1))
        assertTrue("a freshly received record should be stored", changed)

        // A gateway uploads everything changed since its last cloud sync.
        val pending = repo.pendingForCloud("1970-01-01T00:00:00Z")
        assertTrue(
            "the record received over the mesh must be queued for the next cloud upload",
            pending.any { it.id == id },
        )
    }

    @Test
    fun relayIncrementsHopCountAndReEmitsIt() = runBlocking {
        val id = "egi-test-chain-0002"
        // Receive at hop 2 → stored as hop 3 (the relayed distance).
        repo.mergeEnvelope(person(id, hopCount = 2).toEnvelope().copy(hopCount = 2))
        assertEquals(3, db.personDao().byId(id)!!.hopCount)

        // The envelope we'd hand the next peer carries that incremented hop, so the
        // chain keeps an accurate, monotonically increasing distance.
        val outbound = repo.envelopesFor(listOf(id))
        assertEquals(1, outbound.size)
        assertEquals(3, outbound.first().hopCount)
    }
}
