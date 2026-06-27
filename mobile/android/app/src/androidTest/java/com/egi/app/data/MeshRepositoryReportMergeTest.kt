package com.egi.app.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test for the report path through [MeshRepository.mergeEnvelope]:
 * a report envelope must upsert into the `reports` table and apply last-write-wins
 * (newer `updated_at` wins, older is skipped) — the mirror of the person merge the
 * JVM RecordMappers tests cover, but exercising real Room storage on a device.
 *
 * Uses an in-memory Room database so it leaves no on-device state behind.
 */
@RunWith(AndroidJUnit4::class)
class MeshRepositoryReportMergeTest {

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
    private fun report(id: String, note: String, updatedAt: String): ReportEntity =
        ReportEntity(
            id = id,
            personId = "egi-test-person-0001",
            authorName = "Reportero de prueba",
            status = "safe",
            note = note,
            location = "Refugio de prueba",
            source = "mesh",
            originDevice = "device-test-9999",
            createdAt = "2026-06-26T10:00:00Z",
            updatedAt = updatedAt,
        )

    @Test
    fun reportEnvelopeIsUpsertedIntoReportsTable() = runBlocking {
        val incoming = report("egi-test-rpt-0001", "primer aviso", "2026-06-26T12:00:00Z")

        val changed = repo.mergeEnvelope(incoming.toEnvelope())

        assertTrue("a brand-new report should be stored", changed)
        val stored = db.reportDao().byId(incoming.id)
        assertNotNull("report row should exist after merge", stored)
        assertEquals("egi-test-person-0001", stored!!.personId)
        assertEquals("primer aviso", stored.note)
    }

    @Test
    fun newerReportWinsAndOlderIsSkipped() = runBlocking {
        val id = "egi-test-rpt-0002"
        repo.mergeEnvelope(report(id, "v1", "2026-06-26T12:00:00Z").toEnvelope())

        // Newer updated_at → applied.
        val newerApplied = repo.mergeEnvelope(report(id, "v2-newer", "2026-06-26T13:00:00Z").toEnvelope())
        assertTrue("newer report should overwrite", newerApplied)
        assertEquals("v2-newer", db.reportDao().byId(id)!!.note)

        // Older updated_at → skipped (LWW), stored copy unchanged.
        val olderApplied = repo.mergeEnvelope(report(id, "v0-stale", "2026-06-26T11:00:00Z").toEnvelope())
        assertFalse("older report should be skipped", olderApplied)
        assertEquals("v2-newer", db.reportDao().byId(id)!!.note)
    }
}
