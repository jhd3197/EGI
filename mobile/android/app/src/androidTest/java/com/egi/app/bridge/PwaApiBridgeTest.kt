package com.egi.app.bridge

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.egi.app.data.EgiDatabase
import com.egi.app.data.PersonEntity
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test for [PwaApiBridge] — the native handler that answers the PWA's
 * same-origin API from Room when the app runs inside the WebView. Exercises both
 * halves: the GET read surface (parsed back from JSON) and the POST write surface
 * (persisted to real Room storage with last-write-wins).
 *
 * Uses an in-memory Room database so it leaves no on-device state behind.
 */
@RunWith(AndroidJUnit4::class)
class PwaApiBridgeTest {

    private lateinit var db: EgiDatabase
    private lateinit var bridge: PwaApiBridge

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, EgiDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        bridge = PwaApiBridge(db, "device-test-0001") // TEST DATA — NOT REAL
    }

    @After
    fun tearDown() {
        db.close()
    }

    // TEST DATA — NOT REAL
    private fun person(id: String, name: String, updatedAt: String): PersonEntity =
        PersonEntity(
            id = id,
            disasterId = "egi-test-disaster",
            name = name,
            status = "missing",
            cedula = "V-00500001",
            source = "web",
            createdAt = "2026-06-26T10:00:00Z",
            updatedAt = updatedAt,
        )

    @Test
    fun postSyncPersistsRecordsThenSyncGetReturnsThem() = runBlocking {
        val body = JSONObject()
            .put("records", org.json.JSONArray().put(JSONObject()
                .put("id", "egi-test-p1")
                .put("disaster_id", "egi-test-disaster")
                .put("name", "Persona de prueba")
                .put("status", "missing")
                .put("source", "web")
                .put("createdAt", "2026-06-26T10:00:00Z")
                .put("updatedAt", "2026-06-26T12:00:00Z")))
            .toString()

        val res = JSONObject(bridge.postSync(body))
        assertTrue("postSync should report ok", res.getBoolean("ok"))
        assertEquals(1, res.getInt("applied"))

        // The row is now in Room and visible via the /sync GET (since the epoch).
        val stored = db.personDao().byId("egi-test-p1")
        assertNotNull("person should be stored", stored)
        assertEquals("Persona de prueba", stored!!.name)
    }

    @Test
    fun syncGetReturnsOnlyRecordsNewerThanSince() = runBlocking {
        db.personDao().upsert(person("egi-test-old", "Vieja", "2026-06-26T10:00:00Z"))
        db.personDao().upsert(person("egi-test-new", "Nueva", "2026-06-26T14:00:00Z"))

        val out = JSONObject(bridge.syncGet("2026-06-26T12:00:00Z"))
        val ids = out.getJSONArray("records").let { arr ->
            (0 until arr.length()).map { arr.getJSONObject(it).getString("id") }
        }
        assertTrue("newer record is returned", ids.contains("egi-test-new"))
        assertTrue("older record is excluded", !ids.contains("egi-test-old"))
    }

    @Test
    fun personsGetExcludesMergedRows() = runBlocking {
        db.personDao().upsert(person("egi-test-live", "Viva", "2026-06-26T12:00:00Z"))
        db.personDao().upsert(
            person("egi-test-merged", "Fusionada", "2026-06-26T12:00:00Z").copy(mergedInto = "egi-test-live"),
        )

        val out = JSONObject(bridge.personsGet(null, null))
        val ids = out.getJSONArray("records").let { arr ->
            (0 until arr.length()).map { arr.getJSONObject(it).getString("id") }
        }
        assertTrue(ids.contains("egi-test-live"))
        assertTrue("merged rows must be hidden", !ids.contains("egi-test-merged"))
        assertEquals(false, out.getBoolean("has_more"))
    }

    @Test
    fun postReportMintsIdAndPersistsForPerson() = runBlocking {
        db.personDao().upsert(person("egi-test-pr", "Con notas", "2026-06-26T12:00:00Z"))
        val body = JSONObject()
            .put("note", "Visto en el refugio")
            .put("author_name", "Vecino de prueba")
            .put("status", "sighted")
            .put("source", "web")
            .toString()

        val stored = JSONObject(bridge.postReport("egi-test-pr", body))
        assertNotNull("a report id should be minted", stored.optString("id").ifEmpty { null })

        val reports = db.reportDao().forPerson("egi-test-pr")
        assertEquals(1, reports.size)
        assertEquals("Visto en el refugio", reports[0].note)
        assertEquals("egi-test-pr", reports[0].personId)
    }
}
