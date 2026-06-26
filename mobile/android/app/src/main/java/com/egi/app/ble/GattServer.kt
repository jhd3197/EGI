package com.egi.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattServer
import android.bluetooth.BluetoothGattServerCallback
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.os.Build
import android.util.Log
import com.egi.app.mesh.BleConstants
import com.egi.app.mesh.EnvelopeCodec
import com.egi.app.mesh.RecordEnvelope
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.io.ByteArrayOutputStream
import java.util.concurrent.ConcurrentHashMap

/**
 * Hosts the EGI GATT service: Index (read), Request (write), Records (write + notify).
 *
 * The async-read problem: `onCharacteristicReadRequest` must respond synchronously,
 * but building the index is a suspend/DB call. We solve it by caching the encoded
 * index, refreshing it whenever a peer connects, and serving the cached bytes
 * (with offset support for ATT long reads).
 *
 * BLE permissions (`BLUETOOTH_CONNECT`) are guaranteed by the caller (MainActivity).
 */
class GattServer(
    private val context: Context,
    private val callbacks: MeshGattCallbacks,
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val bluetoothManager =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager

    private var gattServer: BluetoothGattServer? = null

    private lateinit var indexChar: BluetoothGattCharacteristic
    private lateinit var recordsChar: BluetoothGattCharacteristic

    /** Cached, pre-encoded local index served on Index reads (refreshed on connect). */
    @Volatile
    private var cachedIndex: ByteArray = "[]".toByteArray(Charsets.UTF_8)

    /** Per-device reassembly buffers for inbound Records writes. */
    private val reassemblers = ConcurrentHashMap<String, ChunkReassembler>()

    /** Per-device outbound notification queues (one in-flight notify at a time). */
    private val sendQueues = ConcurrentHashMap<String, ArrayDeque<ByteArray>>()

    /** Negotiated MTU per device (defaults to the pre-negotiation safe size). */
    private val mtus = ConcurrentHashMap<String, Int>()

    /** Count of envelopes pushed out per device this round (for onPeerSynced). */
    private val sentCounts = ConcurrentHashMap<String, Int>()

    private val serverCallback = object : BluetoothGattServerCallback() {

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onConnectionStateChange(device: BluetoothDevice, status: Int, newState: Int) {
            val address = device.address
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                log("Peer connected: $address")
                mtus[address] = BleConstants.DEFAULT_CHUNK_SIZE + 3
                refreshIndex()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                log("Peer disconnected: $address")
                val sent = sentCounts.remove(address) ?: 0
                val received = reassemblers.remove(address)?.delivered ?: 0
                sendQueues.remove(address)
                mtus.remove(address)
                if (sent > 0 || received > 0) callbacks.onPeerSynced(address, received, sent)
            }
        }

        override fun onMtuChanged(device: BluetoothDevice, mtu: Int) {
            mtus[device.address] = mtu
            log("Server MTU for ${device.address} = $mtu")
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onCharacteristicReadRequest(
            device: BluetoothDevice,
            requestId: Int,
            offset: Int,
            characteristic: BluetoothGattCharacteristic,
        ) {
            if (characteristic.uuid == BleConstants.INDEX_CHAR_UUID) {
                val full = cachedIndex
                val slice = if (offset >= full.size) ByteArray(0)
                else full.copyOfRange(offset, full.size)
                gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, slice)
            } else {
                gattServer?.sendResponse(
                    device, requestId, BluetoothGatt.GATT_FAILURE, offset, ByteArray(0),
                )
            }
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onCharacteristicWriteRequest(
            device: BluetoothDevice,
            requestId: Int,
            characteristic: BluetoothGattCharacteristic,
            preparedWrite: Boolean,
            responseNeeded: Boolean,
            offset: Int,
            value: ByteArray,
        ) {
            when (characteristic.uuid) {
                BleConstants.REQUEST_CHAR_UUID -> {
                    if (responseNeeded) {
                        gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, value)
                    }
                    handleRequestWrite(device, value)
                }

                BleConstants.RECORDS_CHAR_UUID -> {
                    if (responseNeeded) {
                        gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, value)
                    }
                    handleRecordsWrite(device, value)
                }

                else -> {
                    if (responseNeeded) {
                        gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_FAILURE, offset, ByteArray(0))
                    }
                }
            }
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onDescriptorWriteRequest(
            device: BluetoothDevice,
            requestId: Int,
            descriptor: BluetoothGattDescriptor,
            preparedWrite: Boolean,
            responseNeeded: Boolean,
            offset: Int,
            value: ByteArray,
        ) {
            // CCC descriptor toggle (peer subscribing to Records notifications).
            if (responseNeeded) {
                gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, value)
            }
        }

        override fun onNotificationSent(device: BluetoothDevice, status: Int) {
            // Previous notification drained; push the next queued chunk.
            sendNextChunk(device)
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    fun open() {
        val server = bluetoothManager.openGattServer(context, serverCallback)
        if (server == null) {
            log("Failed to open GATT server")
            return
        }
        gattServer = server

        val service = BluetoothGattService(
            BleConstants.SERVICE_UUID,
            BluetoothGattService.SERVICE_TYPE_PRIMARY,
        )

        indexChar = BluetoothGattCharacteristic(
            BleConstants.INDEX_CHAR_UUID,
            BluetoothGattCharacteristic.PROPERTY_READ,
            BluetoothGattCharacteristic.PERMISSION_READ,
        )

        val requestChar = BluetoothGattCharacteristic(
            BleConstants.REQUEST_CHAR_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE,
            BluetoothGattCharacteristic.PERMISSION_WRITE,
        )

        recordsChar = BluetoothGattCharacteristic(
            BleConstants.RECORDS_CHAR_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_WRITE,
        )
        recordsChar.addDescriptor(
            BluetoothGattDescriptor(
                BleConstants.CCC_DESCRIPTOR_UUID,
                BluetoothGattDescriptor.PERMISSION_READ or BluetoothGattDescriptor.PERMISSION_WRITE,
            ),
        )

        service.addCharacteristic(indexChar)
        service.addCharacteristic(requestChar)
        service.addCharacteristic(recordsChar)

        server.addService(service)
        refreshIndex()
        log("GATT server opened")
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    fun close() {
        try {
            gattServer?.close()
        } catch (e: Exception) {
            log("GATT server close threw: ${e.message}")
        }
        gattServer = null
        reassemblers.clear()
        sendQueues.clear()
        mtus.clear()
        sentCounts.clear()
        scope.cancel()
        log("GATT server closed")
    }

    private fun refreshIndex() {
        scope.launch {
            try {
                cachedIndex = EnvelopeCodec.encodeIndex(callbacks.localIndex())
            } catch (e: Exception) {
                log("Index refresh failed: ${e.message}")
            }
        }
    }

    private fun handleRequestWrite(device: BluetoothDevice, value: ByteArray) {
        val ids = runCatching { EnvelopeCodec.decodeRequest(value) }.getOrNull() ?: run {
            log("Bad request payload from ${device.address}")
            return
        }
        log("Peer ${device.address} requested ${ids.size} records")
        scope.launch {
            val envelopes = runCatching { callbacks.envelopesFor(ids) }.getOrElse {
                log("envelopesFor failed: ${it.message}"); emptyList()
            }
            pushEnvelopes(device, envelopes)
        }
    }

    private fun handleRecordsWrite(device: BluetoothDevice, value: ByteArray) {
        val reassembler = reassemblers.getOrPut(device.address) { ChunkReassembler() }
        val frames = reassembler.offer(value)
        if (frames.isEmpty()) return
        scope.launch {
            for (frame in frames) {
                val envelope = runCatching { EnvelopeCodec.decodeEnvelope(frame) }.getOrNull() ?: continue
                runCatching { callbacks.onEnvelopeReceived(envelope) }
                    .onFailure { log("onEnvelopeReceived failed: ${it.message}") }
            }
        }
    }

    /** Length-prefix-frame each envelope, chunk to mtu-3, and queue notifications. */
    private fun pushEnvelopes(device: BluetoothDevice, envelopes: List<RecordEnvelope>) {
        if (envelopes.isEmpty()) return
        val mtu = mtus[device.address] ?: (BleConstants.DEFAULT_CHUNK_SIZE + 3)
        val chunkSize = (mtu - 3).coerceAtLeast(BleConstants.DEFAULT_CHUNK_SIZE)
        val queue = sendQueues.getOrPut(device.address) { ArrayDeque() }

        synchronized(queue) {
            val wasIdle = queue.isEmpty()
            for (envelope in envelopes) {
                val framed = ChunkFraming.frame(EnvelopeCodec.encodeEnvelope(envelope))
                ChunkFraming.split(framed, chunkSize).forEach { queue.addLast(it) }
            }
            sentCounts[device.address] = (sentCounts[device.address] ?: 0) + envelopes.size
            log("Queued ${envelopes.size} envelopes (${queue.size} chunks) to ${device.address}")
            if (wasIdle) sendNextChunk(device)
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    private fun sendNextChunk(device: BluetoothDevice) {
        val queue = sendQueues[device.address] ?: return
        val chunk: ByteArray
        synchronized(queue) {
            chunk = queue.removeFirstOrNull() ?: return
        }
        val server = gattServer ?: return
        val ok = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            server.notifyCharacteristicChanged(device, recordsChar, false, chunk) ==
                BluetoothGatt.GATT_SUCCESS
        } else {
            @Suppress("DEPRECATION")
            run {
                recordsChar.value = chunk
                server.notifyCharacteristicChanged(device, recordsChar, false)
            }
        }
        if (!ok) {
            log("notifyCharacteristicChanged failed for ${device.address}; retrying chunk")
            synchronized(queue) { queue.addFirst(chunk) }
            // No onNotificationSent will fire on failure; nudge once.
            scope.launch { sendNextChunk(device) }
        }
    }

    private fun log(message: String) {
        Log.d(TAG, message)
        callbacks.onLog(message)
    }

    private companion object {
        private const val TAG = "EGI-GattServer"
    }
}

/**
 * Length-prefix framing shared by the server and client: each envelope is sent as
 * a 4-byte big-endian length followed by that many JSON bytes, then split into
 * BLE-sized chunks. The receiver reassembles with [ChunkReassembler].
 */
internal object ChunkFraming {
    const val LENGTH_PREFIX = 4

    fun frame(payload: ByteArray): ByteArray {
        val out = ByteArray(LENGTH_PREFIX + payload.size)
        val len = payload.size
        out[0] = (len ushr 24 and 0xFF).toByte()
        out[1] = (len ushr 16 and 0xFF).toByte()
        out[2] = (len ushr 8 and 0xFF).toByte()
        out[3] = (len and 0xFF).toByte()
        System.arraycopy(payload, 0, out, LENGTH_PREFIX, payload.size)
        return out
    }

    fun split(framed: ByteArray, chunkSize: Int): List<ByteArray> {
        val safe = chunkSize.coerceAtLeast(1)
        val chunks = ArrayList<ByteArray>((framed.size + safe - 1) / safe)
        var offset = 0
        while (offset < framed.size) {
            val end = minOf(offset + safe, framed.size)
            chunks.add(framed.copyOfRange(offset, end))
            offset = end
        }
        return chunks
    }
}

/**
 * Reassembles a stream of BLE chunks back into whole length-prefixed frames.
 * Tolerant of multiple frames arriving across chunk boundaries.
 */
internal class ChunkReassembler {
    private val buffer = ByteArrayOutputStream()

    /** How many complete frames this reassembler has emitted (for sync accounting). */
    var delivered: Int = 0
        private set

    /** Feed one chunk; returns any complete envelope frames now available. */
    fun offer(chunk: ByteArray): List<ByteArray> {
        buffer.write(chunk, 0, chunk.size)
        val frames = ArrayList<ByteArray>()
        var data = buffer.toByteArray()
        var consumed = 0
        while (data.size - consumed >= ChunkFraming.LENGTH_PREFIX) {
            val len = ((data[consumed].toInt() and 0xFF) shl 24) or
                ((data[consumed + 1].toInt() and 0xFF) shl 16) or
                ((data[consumed + 2].toInt() and 0xFF) shl 8) or
                (data[consumed + 3].toInt() and 0xFF)
            if (len < 0) { // corrupt; drop everything to resync
                consumed = data.size
                break
            }
            val frameEnd = consumed + ChunkFraming.LENGTH_PREFIX + len
            if (data.size < frameEnd) break // wait for more chunks
            frames.add(data.copyOfRange(consumed + ChunkFraming.LENGTH_PREFIX, frameEnd))
            consumed = frameEnd
        }
        if (consumed > 0) {
            val remainder = data.copyOfRange(consumed, data.size)
            buffer.reset()
            buffer.write(remainder, 0, remainder.size)
            data = remainder
        }
        delivered += frames.size
        return frames
    }
}
