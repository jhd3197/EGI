package com.egi.app.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.egi.app.mesh.BleConstants
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test for the hop-limit / anti-circulation rules added in plan-23
 * Phase 1 ([MeshRepository.mergePersonEnvelope] + the relayable-index gate):
 *
 *  - A record arriving just under the limit is stored AND stays advertised (relayed).
 *  - A record arriving AT the limit is stored for the local user but withheld from
 *    the advertised index, so the mesh stops forwarding it.
 *  - A record arriving past the limit is rejected outright and counted as dropped.
 *
 * Uses an in-memory Room DB so it leaves no on-device state behind.
 */
@RunWith(AndroidJUnit4::class)
class MeshRepositoryHopLimitTest {

    private lateinit var db: EgiDatabase
    private lateinit var repo: MeshRepository

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, EgiDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        repo = MeshRepository(db, "device-test-0001") // TEST DATA — NOT REAL
    }

    @After
    fun tearDown() {
        db.close()
    }

    // TEST DATA — NOT REAL
    private fun person(id: String, hopCount: Int): PersonEntity = PersonEntity(
        id = id,
        disasterId = "disaster-test",
        name = "Persona de prueba $id",
        status = "missing",
        age = 30,
        location = "Refugio de prueba",
        cedula = "V-00000000",
        originDevice = "device-test-9999",
        hopCount = hopCount,
        createdAt = "2026-06-26T10:00:00Z",
        updatedAt = "2026-06-26T12:00:00Z",
    )

    /** Build a person envelope carrying the given transport hop_count. */
    private fun envelopeAtHop(id: String, hopCount: Int) =
        person(id, hopCount).toEnvelope().copy(hopCount = hopCount)

    @Test
    fun recordJustUnderLimitIsStoredAndRelayed() = runBlocking {
        val id = "egi-test-hop-09"
        val changed = repo.mergeEnvelope(envelopeAtHop(id, BleConstants.MAX_HOPS - 1))

        assertTrue("a hop-${BleConstants.MAX_HOPS - 1} record should be stored", changed)
        val stored = db.personDao().byId(id)
        assertNotNull("record should exist locally", stored)
        // Stored hop_count is the relayed value (env + 1) == MAX_HOPS.
        assertEquals(BleConstants.MAX_HOPS, stored!!.hopCount)
        // Still within the relay budget → advertised to peers.
        assertTrue("record should still be advertised/relayed", repo.localRecordIds().contains(id))
    }

    @Test
    fun recordAtLimitIsStoredButNotRelayed() = runBlocking {
        val id = "egi-test-hop-10"
        val changed = repo.mergeEnvelope(envelopeAtHop(id, BleConstants.MAX_HOPS))

        assertTrue("a hop-${BleConstants.MAX_HOPS} record is still stored locally", changed)
        val stored = db.personDao().byId(id)
        assertNotNull("record should exist locally for the user", stored)
        // Stored hop_count == MAX_HOPS + 1, past the relay budget.
        assertEquals(BleConstants.MAX_HOPS + 1, stored!!.hopCount)
        assertFalse(
            "a maxed-out record must NOT be re-advertised/relayed",
            repo.localRecordIds().contains(id),
        )
        assertFalse(
            "a maxed-out record must NOT appear in the relay index",
            repo.localRecordIndex().any { it.recordId == id },
        )
    }

    @Test
    fun recordPastLimitIsRejected() = runBlocking {
        val id = "egi-test-hop-11"
        val before = repo.droppedAtMaxHopsCount()

        val changed = repo.mergeEnvelope(envelopeAtHop(id, BleConstants.MAX_HOPS + 1))

        assertFalse("a record past the hop limit must be rejected", changed)
        assertNull("a rejected record must not be stored", db.personDao().byId(id))
        assertEquals(
            "the dropped-at-max-hops counter should advance",
            before + 1,
            repo.droppedAtMaxHopsCount(),
        )
    }
}
