package com.egi.app.wifi

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.egi.app.mesh.RecordEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.net.InetAddress
import java.util.Collections

/**
 * Exercises the REAL Wi-Fi Direct bulk socket path (plan-23 Phase 5) over loopback,
 * without forming an actual Wi-Fi Direct group: the group-owner side runs
 * [WifiDirectManager.receiveBulk] (binds the transfer port, accepts, reads framed
 * envelopes) while the client side runs [WifiDirectManager.sendBulk] against
 * 127.0.0.1. This proves the ServerSocket/Socket framing + reassembly transfers the
 * envelopes intact end-to-end — the same merge inputs the BLE path produces.
 *
 * Instrumented (not a JVM unit test) because [WifiDirectManager] touches Android
 * system services in its constructor; the sockets themselves are plain java.net.
 */
@RunWith(AndroidJUnit4::class)
class WifiDirectBulkTransferTest {

    // TEST DATA — NOT REAL
    private fun envelope(id: String, name: String): RecordEnvelope {
        val payload = JSONObject().apply {
            put("id", id)
            put("name", name)
            put("status", "missing")
        }
        return RecordEnvelope(
            recordType = RecordEnvelope.TYPE_PERSON,
            recordId = id,
            originDevice = "device-test-01",
            hopCount = 1,
            createdAt = "2026-06-26T12:00:00.000Z",
            updatedAt = "2026-06-26T12:30:00.000Z",
            payload = payload,
        )
    }

    @Test
    fun bulkEnvelopesTransferOverLoopbackSocket() = runBlocking {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val owner = WifiDirectManager(ctx)
        val client = WifiDirectManager(ctx)

        // TEST DATA — NOT REAL
        val sent = listOf(
            envelope("egi-test-wd-0001", "Ana de prueba"),
            envelope("egi-test-wd-0002", "Beto de prueba"),
            envelope("egi-test-wd-0003", "Carla de prueba"),
        )
        val received = Collections.synchronizedList(mutableListOf<RecordEnvelope>())

        // Group owner listens + receives on a background coroutine.
        val receiver = async(Dispatchers.IO) {
            owner.receiveBulk { env -> received.add(env) }
        }
        // Give the ServerSocket a moment to bind before the client connects.
        delay(500)
        val sentCount = withContext(Dispatchers.IO) {
            client.sendBulk(sent, isGroupOwner = false, groupOwnerAddress = InetAddress.getByName("127.0.0.1"))
        }
        val receivedCount = receiver.await()

        assertEquals("client should report sending every envelope", sent.size, sentCount)
        assertEquals("owner should receive every envelope", sent.size, receivedCount)
        assertEquals(sent.size, received.size)
        assertEquals(
            sent.map { it.recordId }.toSet(),
            received.map { it.recordId }.toSet(),
        )
        // Payload integrity survived the socket round-trip.
        val byId = received.associateBy { it.recordId }
        assertEquals("Ana de prueba", byId["egi-test-wd-0001"]!!.payload.getString("name"))
        assertTrue(received.all { it.hopCount == 1 })
    }
}
