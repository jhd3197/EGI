package com.egi.app.sms

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.egi.app.data.EgiDatabase
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test for the SMS check-in record-creation path.
 *
 * Faking a real SMS_RECEIVED PDU intent is impractical (the platform builds
 * SmsMessage from raw PDUs), so we test the seam the receiver actually uses:
 * [SmsCheckin.parse] → [buildCheckinRecords] → Room upsert. This asserts that an
 * "EGI CHECKIN ..." body produces the expected person AND the linked companion
 * report, and that both persist into the (in-memory) database.
 */
@RunWith(AndroidJUnit4::class)
class SmsCheckinReceiverTest {

    private lateinit var db: EgiDatabase

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, EgiDatabase::class.java)
            .allowMainThreadQueries()
            .build()
    }

    @After
    fun tearDown() {
        db.close()
    }

    @Test
    fun checkinBodyCreatesLinkedPersonAndReport() = runBlocking {
        // TEST DATA — NOT REAL
        val fields = SmsCheckin.parse("EGI CHECKIN V-12345678, Juan Pérez, Refugio Norte")
        assertNotNull("body should parse", fields)

        val records = buildCheckinRecords(
            fields = fields!!,
            deviceId = "device-test-0001",
            sender = "+58-414-1234567",
            body = "EGI CHECKIN V-12345678, Juan Pérez, Refugio Norte",
        )

        // Person: safe self check-in, source='sms', cédula carried through.
        val person = records.person
        assertEquals("safe", person.status)
        assertEquals("sms", person.source)
        assertEquals("V-12345678", person.cedula)
        assertEquals("Juan Pérez", person.name)
        assertEquals("Refugio Norte", person.location)

        // Report: linked to the person, source='sms', note mentions the check-in + location.
        val report = records.report
        assertEquals(person.id, report.personId)
        assertEquals("sms", report.source)
        assertEquals("safe", report.status)
        assertTrue(report.note!!.contains("Auto check-in vía SMS"))
        assertTrue(report.note!!.contains("Refugio Norte"))

        // Both rows persist and the report resolves back to the person.
        db.personDao().upsert(person)
        db.reportDao().upsert(report)

        assertNotNull(db.personDao().byId(person.id))
        val storedReports = db.reportDao().forPerson(person.id)
        assertEquals(1, storedReports.size)
        assertEquals(report.id, storedReports[0].id)
    }

    @Test
    fun nonCheckinBodyParsesToNull() {
        assertEquals(null, SmsCheckin.parse("hola, estoy bien")) // TEST DATA — NOT REAL
    }
}
