package com.egi.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.os.Build
import android.util.Log
import com.egi.app.mesh.BleConstants
import com.egi.app.mesh.EnvelopeCodec
import com.egi.app.mesh.IndexEntry
import com.egi.app.mesh.MeshCrypto
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.security.KeyPair

/**
 * Drives the client side of a sync round against a discovered peer:
 *
 *   connect → requestMtu → discoverServices → enable Records notifications →
 *   read peer Key + write our Key (ECDH → AES-256-GCM session key) → read Index →
 *   compute which peer records we lack/are stale on → write Request →
 *   collect chunked envelopes → onEnvelopeReceived(each) → onPeerSynced → close.
 *
 * Encryption is mandatory: the key exchange runs before the index read, and every
 * Records chunk is decrypted with the per-connection session key.
 *
 * The GATT API is callback-based, so the flow is a small state machine inside the
 * [BluetoothGattCallback]; suspend work (localIndex / onEnvelopeReceived) hops onto
 * the owned IO scope. Completion is detected by an idle timeout after the last
 * chunk, with a hard overall timeout as a safety net.
 *
 * BLE permissions (`BLUETOOTH_CONNECT`) are guaranteed by the caller (MainActivity).
 */
class GattClient(
    private val context: Context,
    private val callbacks: MeshGattCallbacks,
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private var gatt: BluetoothGatt? = null
    private var peerAddress: String = ""

    private var recordsChar: BluetoothGattCharacteristic? = null
    private var requestChar: BluetoothGattCharacteristic? = null
    private var indexChar: BluetoothGattCharacteristic? = null
    private var keyChar: BluetoothGattCharacteristic? = null

    /** Our ephemeral EC key pair for this connection's ECDH exchange. */
    private val keyPair: KeyPair = MeshCrypto.generateKeyPair()

    /** Derived per-connection AES-256 session key (set once the peer's key is read). */
    private var sessionKey: ByteArray? = null

    private var mtu = BleConstants.DEFAULT_CHUNK_SIZE + 3
    private val reassembler = ChunkReassembler()

    private var receivedCount = 0
    private var requestedCount = 0
    private var finished = false

    private var idleTimeoutJob: Job? = null
    private var overallTimeoutJob: Job? = null

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    fun connect(device: BluetoothDevice) {
        peerAddress = device.address
        log("Connecting to $peerAddress")
        gatt = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
        overallTimeoutJob = scope.launch {
            delay(OVERALL_TIMEOUT_MS)
            if (!finished) {
                log("Overall timeout for $peerAddress")
                finish()
            }
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                log("Connected to $peerAddress; negotiating MTU")
                g.requestMtu(BleConstants.PREFERRED_MTU)
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                log("Disconnected from $peerAddress")
                finish()
            }
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onMtuChanged(g: BluetoothGatt, negotiated: Int, status: Int) {
            mtu = if (status == BluetoothGatt.GATT_SUCCESS) negotiated else mtu
            log("MTU for $peerAddress = $mtu; discovering services")
            g.discoverServices()
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            if (status != BluetoothGatt.GATT_SUCCESS) {
                log("Service discovery failed ($status)"); finish(); return
            }
            val service = g.getService(BleConstants.SERVICE_UUID)
            if (service == null) {
                log("Peer $peerAddress has no EGI service"); finish(); return
            }
            indexChar = service.getCharacteristic(BleConstants.INDEX_CHAR_UUID)
            requestChar = service.getCharacteristic(BleConstants.REQUEST_CHAR_UUID)
            recordsChar = service.getCharacteristic(BleConstants.RECORDS_CHAR_UUID)
            keyChar = service.getCharacteristic(BleConstants.KEY_CHAR_UUID)
            if (indexChar == null || requestChar == null || recordsChar == null || keyChar == null) {
                log("Peer $peerAddress missing EGI characteristics"); finish(); return
            }
            // Subscribe to Records notifications first so nothing is missed.
            enableRecordsNotifications(g)
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onDescriptorWrite(
            g: BluetoothGatt,
            descriptor: BluetoothGattDescriptor,
            status: Int,
        ) {
            if (descriptor.uuid == BleConstants.CCC_DESCRIPTOR_UUID) {
                log("Records notifications enabled; reading peer key")
                g.readCharacteristic(keyChar)
            }
        }

        @Suppress("DEPRECATION")
        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onCharacteristicRead(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int,
        ) {
            // Deprecated 3-arg overload: fires on all API levels and the framework
            // has already reassembled long reads into characteristic.value.
            when (characteristic.uuid) {
                BleConstants.KEY_CHAR_UUID -> {
                    if (status != BluetoothGatt.GATT_SUCCESS) {
                        log("Key read failed ($status)"); finish(); return
                    }
                    handlePeerKey(g, characteristic.value ?: ByteArray(0))
                }

                BleConstants.INDEX_CHAR_UUID -> {
                    if (status != BluetoothGatt.GATT_SUCCESS) {
                        log("Index read failed ($status)"); finish(); return
                    }
                    handlePeerIndex(g, characteristic.value ?: ByteArray(0))
                }
            }
        }

        @Suppress("DEPRECATION")
        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
        ) {
            // Deprecated 2-arg overload: value is in characteristic.value across all levels.
            if (characteristic.uuid != BleConstants.RECORDS_CHAR_UUID) return
            val chunk = characteristic.value ?: return
            onRecordsChunk(chunk)
        }

        @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
        override fun onCharacteristicWrite(
            g: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int,
        ) {
            when (characteristic.uuid) {
                BleConstants.KEY_CHAR_UUID -> {
                    // Both sides now hold the session key; safe to read the index.
                    log("Our key written; reading index")
                    g.readCharacteristic(indexChar)
                }

                BleConstants.REQUEST_CHAR_UUID -> {
                    log("Request written; awaiting records")
                    armIdleTimeout()
                }
            }
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    private fun enableRecordsNotifications(g: BluetoothGatt) {
        val records = recordsChar ?: run { finish(); return }
        g.setCharacteristicNotification(records, true)
        val ccc = records.getDescriptor(BleConstants.CCC_DESCRIPTOR_UUID)
        if (ccc == null) {
            log("No CCC descriptor on Records; reading index anyway")
            g.readCharacteristic(indexChar)
            return
        }
        val enable = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeDescriptor(ccc, enable)
        } else {
            @Suppress("DEPRECATION")
            run {
                ccc.value = enable
                g.writeDescriptor(ccc)
            }
        }
    }

    /** Derive the session key from the peer's public bytes, then write our own public key. */
    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    private fun handlePeerKey(g: BluetoothGatt, peerPublicBytes: ByteArray) {
        if (peerPublicBytes.isEmpty()) {
            log("Peer $peerAddress returned no public key"); finish(); return
        }
        sessionKey = runCatching {
            MeshCrypto.deriveSessionKey(keyPair.private, peerPublicBytes)
        }.getOrElse {
            log("Failed to derive session key: ${it.message}"); finish(); return
        }
        log("Session key established with $peerAddress; sending our key")
        writeOurKey(g)
    }

    /** Write our ephemeral public key to the peer's Key characteristic. */
    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    private fun writeOurKey(g: BluetoothGatt) {
        val key = keyChar ?: run { finish(); return }
        val payload = MeshCrypto.publicKeyBytes(keyPair.public)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeCharacteristic(key, payload, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
        } else {
            @Suppress("DEPRECATION")
            run {
                key.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                key.value = payload
                g.writeCharacteristic(key)
            }
        }
    }

    /** Decode the peer index, compute what we need, and write the request. */
    private fun handlePeerIndex(g: BluetoothGatt, bytes: ByteArray) {
        val peerIndex = runCatching { EnvelopeCodec.decodeIndex(bytes) }.getOrElse {
            log("Bad peer index: ${it.message}"); finish(); return
        }
        log("Peer $peerAddress index has ${peerIndex.size} entries")
        scope.launch {
            val localById = runCatching { callbacks.localIndex() }
                .getOrDefault(emptyList())
                .associateBy { it.recordId }
            val wanted = peerIndex.filter { entry -> needs(entry, localById[entry.recordId]) }
                .map { it.recordId }
            requestedCount = wanted.size
            if (wanted.isEmpty()) {
                log("Nothing to request from $peerAddress")
                finish()
                return@launch
            }
            writeRequest(g, wanted)
        }
    }

    /** True if we lack this peer record, or hold an older copy of it. */
    private fun needs(peer: IndexEntry, local: IndexEntry?): Boolean {
        if (local == null) return true
        val peerUpdated = peer.updatedAt ?: return false
        val localUpdated = local.updatedAt ?: return true
        // ISO-8601 UTC strings sort lexicographically by instant.
        return peerUpdated > localUpdated
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    private fun writeRequest(g: BluetoothGatt, recordIds: List<String>) {
        val request = requestChar ?: run { finish(); return }
        val payload = EnvelopeCodec.encodeRequest(recordIds)
        log("Requesting ${recordIds.size} records from $peerAddress")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeCharacteristic(request, payload, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)
        } else {
            @Suppress("DEPRECATION")
            run {
                request.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                request.value = payload
                g.writeCharacteristic(request)
            }
        }
    }

    private fun onRecordsChunk(chunk: ByteArray) {
        // Mandatory encryption: a session key must exist before records arrive.
        val key = sessionKey ?: run {
            log("Dropping records from $peerAddress: no session key")
            return
        }
        val frames = reassembler.offer(chunk)
        if (frames.isNotEmpty()) {
            scope.launch {
                for (frame in frames) {
                    val envelope = runCatching {
                        EnvelopeCodec.decodeEnvelopeEncrypted(frame, key)
                    }.getOrNull() ?: continue
                    receivedCount++
                    runCatching { callbacks.onEnvelopeReceived(envelope) }
                        .onFailure { log("onEnvelopeReceived failed: ${it.message}") }
                }
                log("Received $receivedCount / $requestedCount from $peerAddress")
            }
        }
        // Records still flowing (or just landed) — push the idle deadline out.
        armIdleTimeout()
        if (receivedCount >= requestedCount && requestedCount > 0) finish()
    }

    /** Complete the round if no further chunk arrives within [IDLE_TIMEOUT_MS]. */
    private fun armIdleTimeout() {
        idleTimeoutJob?.cancel()
        idleTimeoutJob = scope.launch {
            delay(IDLE_TIMEOUT_MS)
            if (!finished) {
                log("Idle timeout; finishing $peerAddress")
                finish()
            }
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    private fun finish() {
        if (finished) return
        finished = true
        idleTimeoutJob?.cancel()
        overallTimeoutJob?.cancel()
        callbacks.onPeerSynced(peerAddress, receivedCount, 0)
        log("Sync with $peerAddress done: received=$receivedCount requested=$requestedCount")
        close()
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_CONNECT guaranteed by caller
    fun close() {
        try {
            gatt?.disconnect()
            gatt?.close()
        } catch (e: Exception) {
            log("GATT client close threw: ${e.message}")
        }
        gatt = null
        scope.cancel()
    }

    private fun log(message: String) {
        Log.d(TAG, message)
        callbacks.onLog(message)
    }

    private companion object {
        private const val TAG = "EGI-GattClient"
        private const val IDLE_TIMEOUT_MS = 4_000L
        private const val OVERALL_TIMEOUT_MS = 30_000L
    }
}
