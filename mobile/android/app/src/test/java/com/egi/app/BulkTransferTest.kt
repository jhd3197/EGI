package com.egi.app

import com.egi.app.ble.ChunkFraming
import com.egi.app.ble.ChunkReassembler
import com.egi.app.mesh.EnvelopeCodec
import com.egi.app.mesh.RecordEnvelope
import com.egi.app.wifi.WifiDirectManager
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Exercises the Wi-Fi Direct bulk-transfer streaming codec WITHOUT real sockets:
 * a list of envelopes is framed exactly as [WifiDirectManager.sendBulk] would write
 * them, the concatenated bytes are sliced into arbitrary "socket read" chunks, and
 * fed through the same [ChunkReassembler] the receive side uses. This proves the
 * stream reassembles into the original envelopes across chunk boundaries.
 *
 * Also covers the [WifiDirectManager.shouldUseWifiDirect] threshold logic.
 */
class BulkTransferTest {

    // TEST DATA — NOT REAL
    private fun envelope(id: String, name: String, extra: JSONObject.() -> Unit = {}): RecordEnvelope {
        val payload = JSONObject().apply {
            put("id", id)
            put("name", name)
            put("status", "missing")
            extra()
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

    /** Simulate the receiver: slice the stream into [chunkSize] reads, reassemble, decode. */
    private fun roundTripThroughStream(
        envelopes: List<RecordEnvelope>,
        chunkSize: Int,
    ): List<RecordEnvelope> {
        // Sender side: frame each envelope and concatenate (one continuous TCP stream).
        val stream = ArrayList<Byte>()
        for (env in envelopes) {
            ChunkFraming.frame(EnvelopeCodec.encodeEnvelope(env)).forEach { stream.add(it) }
        }
        val bytes = stream.toByteArray()

        // Receiver side: feed arbitrary-sized reads through the reassembler.
        val reassembler = ChunkReassembler()
        val out = ArrayList<RecordEnvelope>()
        var offset = 0
        while (offset < bytes.size) {
            val end = minOf(offset + chunkSize, bytes.size)
            reassembler.offer(bytes.copyOfRange(offset, end)).forEach {
                out.add(EnvelopeCodec.decodeEnvelope(it))
            }
            offset = end
        }
        return out
    }

    @Test
    fun bulkStreamRoundTripsAcrossSmallChunkBoundaries() {
        // TEST DATA — NOT REAL
        val envelopes = listOf(
            envelope("egi-test-0001", "Ana de prueba"),
            envelope("egi-test-0002", "Beto de prueba"),
            envelope("egi-test-0003", "Carla de prueba"),
        )

        // Tiny reads force frames to split across many chunk boundaries.
        val decoded = roundTripThroughStream(envelopes, chunkSize = 7)

        assertEquals(envelopes.size, decoded.size)
        for (i in envelopes.indices) {
            assertEquals(envelopes[i].recordId, decoded[i].recordId)
            assertEquals(envelopes[i].hopCount, decoded[i].hopCount)
            assertEquals(
                envelopes[i].payload.getString("name"),
                decoded[i].payload.getString("name"),
            )
        }
    }

    @Test
    fun bulkStreamRoundTripsWithLargeChunks() {
        // TEST DATA — NOT REAL: a single read big enough to hold every frame at once.
        val envelopes = listOf(
            envelope("egi-test-0010", "Diana de prueba"),
            envelope("egi-test-0011", "Emilio de prueba"),
        )

        val decoded = roundTripThroughStream(envelopes, chunkSize = 64 * 1024)

        assertEquals(envelopes.map { it.recordId }, decoded.map { it.recordId })
    }

    @Test
    fun shouldUseWifiDirectFalseForSmallSet() {
        // TEST DATA — NOT REAL: well under the 20 KB threshold.
        val envelopes = listOf(
            envelope("egi-test-0100", "Fede de prueba"),
            envelope("egi-test-0101", "Gabi de prueba"),
        )
        assertFalse(WifiDirectManager.shouldUseWifiDirect(envelopes))
    }

    @Test
    fun shouldUseWifiDirectTrueWhenPayloadExceedsThreshold() {
        // TEST DATA — NOT REAL: a single oversized payload (> 20 KB).
        val big = "x".repeat(WifiDirectManager.BULK_THRESHOLD_BYTES + 1_000)
        val envelopes = listOf(envelope("egi-test-0200", "Hugo de prueba") { put("notes", big) })
        assertTrue(WifiDirectManager.shouldUseWifiDirect(envelopes))
    }

    @Test
    fun shouldUseWifiDirectTrueJustOverThresholdAcrossManyEnvelopes() {
        // TEST DATA — NOT REAL: each ~2 KB; enough of them to cross 20 KB combined.
        val chunk = "y".repeat(2_000)
        val envelopes = (0 until 12).map { envelope("egi-test-03$it", "Ivo de prueba") { put("notes", chunk) } }
        assertTrue(WifiDirectManager.shouldUseWifiDirect(envelopes))
    }

    @Test
    fun shouldUseWifiDirectTrueWhenPhotoPresentEvenIfSmall() {
        // TEST DATA — NOT REAL: tiny payload but carries a photo reference.
        val withUrl = listOf(
            envelope("egi-test-0400", "Juli de prueba") { put("photo_url", "https://example.test/p.jpg") },
        )
        val withPath = listOf(
            envelope("egi-test-0401", "Kira de prueba") { put("image_path", "/data/egi/p.jpg") },
        )
        assertTrue(WifiDirectManager.shouldUseWifiDirect(withUrl))
        assertTrue(WifiDirectManager.shouldUseWifiDirect(withPath))
    }

    @Test
    fun shouldUseWifiDirectFalseForEmptyList() {
        assertFalse(WifiDirectManager.shouldUseWifiDirect(emptyList()))
    }
}
