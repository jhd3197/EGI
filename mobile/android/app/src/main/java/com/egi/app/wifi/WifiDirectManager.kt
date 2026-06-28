package com.egi.app.wifi

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.p2p.WifiP2pConfig
import android.net.wifi.p2p.WifiP2pDevice
import android.net.wifi.p2p.WifiP2pInfo
import android.net.wifi.p2p.WifiP2pManager
import android.util.Log
import com.egi.app.ble.ChunkFraming
import com.egi.app.ble.ChunkReassembler
import com.egi.app.mesh.EnvelopeCodec
import com.egi.app.mesh.RecordEnvelope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket

/**
 * Wi-Fi Direct bulk-transfer fallback (plan §3 Layer 1, step 9).
 *
 * BLE/GATT is great for discovery and small payloads, but pushing many records
 * or photos over GATT is slow. When a peer signals it has a large batch, devices
 * form a Wi-Fi Direct group and stream length-prefixed envelopes over a TCP
 * socket (group owner listens, client connects). The envelope wire format is
 * identical to the BLE path — the SAME [ChunkFraming]/[ChunkReassembler] framing
 * the GATT layer uses — so the merge/dedup logic is reused unchanged.
 *
 * Framing reuse: [ChunkFraming] and [ChunkReassembler] live in `com.egi.app.ble`
 * as `internal` types. Because the wifi package is in the same Gradle module they
 * are visible here via import, so we reuse them directly rather than moving them
 * to a shared package (lower-risk: no edits to GattServer's call sites).
 *
 * This class wires up real peer discovery and the socket transfer. The WifiP2p
 * group negotiation that yields the group-owner [InetAddress] still needs a paired
 * on-device run to validate (see [com.egi.app.BluetoothMeshManager.syncBulkRound]),
 * and BLE remains the primary path for the v1 success criteria.
 *
 * Permissions: NEARBY_WIFI_DEVICES (API 33+) or ACCESS_FINE_LOCATION (older),
 * plus ACCESS_WIFI_STATE / CHANGE_WIFI_STATE — obtained by MainActivity.
 */
class WifiDirectManager(
    private val context: Context,
    private val onLog: (String) -> Unit = {},
) {
    private val tag = "EGI-WifiDirect"

    private val manager: WifiP2pManager? by lazy {
        context.getSystemService(Context.WIFI_P2P_SERVICE) as? WifiP2pManager
    }
    private var channel: WifiP2pManager.Channel? = null
    private var receiver: BroadcastReceiver? = null

    /** Latest Wi-Fi Direct connection info (group owner role + address), or null. */
    @Volatile
    private var connectionInfo: WifiP2pInfo? = null

    private val intentFilter = IntentFilter().apply {
        addAction(WifiP2pManager.WIFI_P2P_STATE_CHANGED_ACTION)
        addAction(WifiP2pManager.WIFI_P2P_PEERS_CHANGED_ACTION)
        addAction(WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION)
        addAction(WifiP2pManager.WIFI_P2P_THIS_DEVICE_CHANGED_ACTION)
    }

    fun start() {
        val mgr = manager ?: run {
            log("Wi-Fi Direct not supported on this device")
            return
        }
        channel = mgr.initialize(context, context.mainLooper, null)
        receiver = WifiDirectReceiver()
        context.registerReceiver(receiver, intentFilter)
        log("Wi-Fi Direct initialized")
    }

    @SuppressLint("MissingPermission")
    fun discoverPeers() {
        val mgr = manager ?: return
        val ch = channel ?: return
        mgr.discoverPeers(ch, object : WifiP2pManager.ActionListener {
            override fun onSuccess() = log("Wi-Fi Direct peer discovery started")
            override fun onFailure(reason: Int) = log("Wi-Fi Direct discovery failed: $reason")
        })
    }

    fun stop() {
        receiver?.let {
            try {
                context.unregisterReceiver(it)
            } catch (e: IllegalArgumentException) {
                // Receiver was not registered; ignore.
            }
        }
        receiver = null
        channel = null
        connectionInfo = null
        log("Wi-Fi Direct stopped")
    }

    /**
     * Connect to a discovered peer to form a Wi-Fi Direct group (plan-23 Phase 5).
     * The group-owner role + address arrive asynchronously via the connection-changed
     * broadcast; [awaitConnectionInfo] waits for them.
     */
    @SuppressLint("MissingPermission")
    fun connect(peer: WifiP2pDevice) {
        val mgr = manager ?: return
        val ch = channel ?: return
        val config = WifiP2pConfig().apply { deviceAddress = peer.deviceAddress }
        mgr.connect(ch, config, object : WifiP2pManager.ActionListener {
            override fun onSuccess() = log("Wi-Fi Direct connect to ${peer.deviceAddress} requested")
            override fun onFailure(reason: Int) = log("Wi-Fi Direct connect failed: $reason")
        })
    }

    /**
     * Suspend until a Wi-Fi Direct group is formed (connection info with
     * `groupFormed == true`) or [timeoutMs] elapses. Polls the cached
     * [connectionInfo] the connection-changed receiver keeps fresh, so it works
     * whether the group formed before or after the call. Returns null on timeout.
     */
    suspend fun awaitConnectionInfo(timeoutMs: Long = GROUP_FORM_TIMEOUT_MS): WifiP2pInfo? {
        val deadline = System.nanoTime() + timeoutMs * 1_000_000
        while (System.nanoTime() < deadline) {
            val info = connectionInfo
            if (info != null && info.groupFormed) return info
            requestConnectionInfo()
            delay(POLL_INTERVAL_MS)
        }
        return null
    }

    /**
     * Run one bulk exchange over an already-formed Wi-Fi Direct group (plan-23
     * Phase 5). Role is decided by group ownership to avoid a port clash: the group
     * owner listens and RECEIVES (merging each envelope via [onEnvelope]); the client
     * connects and SENDS its [envelopes]. Returns the number of envelopes transferred,
     * or -1 if no group is formed (caller falls back to BLE). The reverse direction
     * and anything not covered here keep flowing over the BLE mesh.
     */
    suspend fun runBulkExchange(
        envelopes: List<RecordEnvelope>,
        onEnvelope: suspend (RecordEnvelope) -> Unit,
    ): Int {
        val info = awaitConnectionInfo() ?: run {
            log("Wi-Fi Direct: no group formed; falling back to BLE")
            return -1
        }
        return if (info.isGroupOwner) {
            receiveBulk(onEnvelope)
        } else {
            sendBulk(envelopes, isGroupOwner = false, groupOwnerAddress = info.groupOwnerAddress)
        }
    }

    @SuppressLint("MissingPermission")
    private fun requestConnectionInfo() {
        val mgr = manager ?: return
        val ch = channel ?: return
        mgr.requestConnectionInfo(ch) { info -> connectionInfo = info }
    }

    /**
     * Stream [envelopes] to a connected Wi-Fi Direct peer over a TCP socket.
     *
     * Socket role is decided by [isGroupOwner] (orthogonal to data direction):
     * - group owner: opens a [ServerSocket] on [TRANSFER_PORT], accepts one client,
     *   then writes the frames to it.
     * - client: connects to [groupOwnerAddress]:[TRANSFER_PORT] and writes the frames.
     *
     * Each envelope is sent as `ChunkFraming.frame(EnvelopeCodec.encodeEnvelope(env))`
     * — a 4-byte big-endian length prefix followed by the envelope JSON — exactly the
     * frame layout the BLE path produces, so [receiveBulk] (and the GATT reassembler)
     * can decode it. Returns the number of envelopes written. All IO runs on
     * [Dispatchers.IO] with connect/accept/read timeouts and try/finally socket close.
     *
     * Note: this streams the PLAINTEXT envelope codec ([EnvelopeCodec.encodeEnvelope]).
     * Wi-Fi Direct group membership is the trust boundary here; the BLE path's
     * per-connection AES session does not apply to the WFD socket.
     */
    suspend fun sendBulk(
        envelopes: List<RecordEnvelope>,
        isGroupOwner: Boolean,
        groupOwnerAddress: InetAddress?,
    ): Int = withContext(Dispatchers.IO) {
        if (envelopes.isEmpty()) return@withContext 0
        if (isGroupOwner) {
            var serverSocket: ServerSocket? = null
            var client: Socket? = null
            try {
                serverSocket = ServerSocket().apply {
                    reuseAddress = true
                    bind(InetSocketAddress(TRANSFER_PORT), 1)
                    soTimeout = ACCEPT_TIMEOUT_MS
                }
                log("Wi-Fi Direct: awaiting client on port $TRANSFER_PORT (owner send)")
                client = serverSocket.accept()
                client.soTimeout = IO_TIMEOUT_MS
                writeFrames(client.getOutputStream(), envelopes).also {
                    log("Wi-Fi Direct: sent $it envelopes (owner)")
                }
            } catch (e: Exception) {
                log("Wi-Fi Direct owner send failed: ${e.message}")
                0
            } finally {
                runCatching { client?.close() }
                runCatching { serverSocket?.close() }
            }
        } else {
            val addr = groupOwnerAddress ?: run {
                log("Wi-Fi Direct client send skipped: no group-owner address")
                return@withContext 0
            }
            var socket: Socket? = null
            try {
                socket = Socket()
                socket.connect(InetSocketAddress(addr, TRANSFER_PORT), CONNECT_TIMEOUT_MS)
                socket.soTimeout = IO_TIMEOUT_MS
                writeFrames(socket.getOutputStream(), envelopes).also {
                    log("Wi-Fi Direct: sent $it envelopes (client → ${addr.hostAddress})")
                }
            } catch (e: Exception) {
                log("Wi-Fi Direct client send failed: ${e.message}")
                0
            } finally {
                runCatching { socket?.close() }
            }
        }
    }

    /**
     * Receive a bulk stream as the Wi-Fi Direct group owner: open a [ServerSocket]
     * on [TRANSFER_PORT], accept one client, and read length-prefixed envelope
     * frames until EOF, reassembling them with the SAME [ChunkReassembler] the BLE
     * path uses and decoding each via [EnvelopeCodec.decodeEnvelope]. [onEnvelope]
     * is invoked per decoded envelope. Returns the count received. Runs on
     * [Dispatchers.IO] with accept/read timeouts and try/finally socket close.
     */
    suspend fun receiveBulk(onEnvelope: suspend (RecordEnvelope) -> Unit): Int =
        withContext(Dispatchers.IO) {
            var serverSocket: ServerSocket? = null
            var client: Socket? = null
            try {
                serverSocket = ServerSocket().apply {
                    reuseAddress = true
                    bind(InetSocketAddress(TRANSFER_PORT), 1)
                    soTimeout = ACCEPT_TIMEOUT_MS
                }
                log("Wi-Fi Direct: listening for bulk transfer on port $TRANSFER_PORT")
                client = serverSocket.accept()
                client.soTimeout = IO_TIMEOUT_MS
                readFrames(client.getInputStream(), onEnvelope).also {
                    log("Wi-Fi Direct: received $it envelopes")
                }
            } catch (e: Exception) {
                log("Wi-Fi Direct receive failed: ${e.message}")
                0
            } finally {
                runCatching { client?.close() }
                runCatching { serverSocket?.close() }
            }
        }

    /** Write each envelope as a framed (length-prefixed) blob; returns the count. */
    private fun writeFrames(output: OutputStream, envelopes: List<RecordEnvelope>): Int {
        var count = 0
        for (env in envelopes) {
            val framed = ChunkFraming.frame(EnvelopeCodec.encodeEnvelope(env))
            output.write(framed)
            count++
        }
        output.flush()
        return count
    }

    /** Read the socket to EOF, reassembling frames and dispatching decoded envelopes. */
    private suspend fun readFrames(
        input: InputStream,
        onEnvelope: suspend (RecordEnvelope) -> Unit,
    ): Int {
        val reassembler = ChunkReassembler()
        val buffer = ByteArray(READ_BUFFER_BYTES)
        var count = 0
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break // EOF
            if (read == 0) continue
            val frames = reassembler.offer(buffer.copyOfRange(0, read))
            for (frame in frames) {
                val envelope = runCatching { EnvelopeCodec.decodeEnvelope(frame) }.getOrNull()
                    ?: continue
                onEnvelope(envelope)
                count++
            }
        }
        return count
    }

    /** Instance shortcut for [shouldUseWifiDirect]. */
    fun shouldUseWifiDirect(envelopes: List<RecordEnvelope>): Boolean =
        Companion.shouldUseWifiDirect(envelopes)

    private inner class WifiDirectReceiver : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.action) {
                WifiP2pManager.WIFI_P2P_STATE_CHANGED_ACTION -> {
                    val enabled = intent.getIntExtra(WifiP2pManager.EXTRA_WIFI_STATE, -1) ==
                        WifiP2pManager.WIFI_P2P_STATE_ENABLED
                    log("Wi-Fi Direct state: ${if (enabled) "enabled" else "disabled"}")
                }
                WifiP2pManager.WIFI_P2P_PEERS_CHANGED_ACTION ->
                    log("Wi-Fi Direct peers changed")
                WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION -> {
                    // Group membership changed: refresh the cached connection info so
                    // awaitConnectionInfo() sees the group-owner role + address.
                    log("Wi-Fi Direct connection changed")
                    requestConnectionInfo()
                }
            }
        }
    }

    private fun log(message: String) {
        Log.i(tag, message)
        onLog(message)
    }

    companion object {
        /** TCP port the group owner listens on for bulk envelope streaming. */
        const val TRANSFER_PORT = 8988

        /**
         * Outbound payload size (bytes) at/over which Wi-Fi Direct is preferred over
         * BLE. ~20 KB: above this, GATT's MTU-sized notifications get slow enough that
         * the WFD setup cost pays off. Any payload carrying a photo also forces WFD.
         */
        const val BULK_THRESHOLD_BYTES = 20 * 1024

        /** Connect timeout for the client socket (ms). */
        private const val CONNECT_TIMEOUT_MS = 10_000

        /** Accept timeout for the owner's server socket (ms). */
        private const val ACCEPT_TIMEOUT_MS = 30_000

        /** Per-read/write socket timeout once connected (ms). */
        private const val IO_TIMEOUT_MS = 30_000

        /** Stream read buffer size (bytes). */
        private const val READ_BUFFER_BYTES = 8 * 1024

        /** Max time to wait for a Wi-Fi Direct group to form before falling back to BLE (ms). */
        private const val GROUP_FORM_TIMEOUT_MS = 15_000L

        /** Connection-info poll interval while awaiting group formation (ms). */
        private const val POLL_INTERVAL_MS = 500L

        /**
         * True when [envelopes] should go over Wi-Fi Direct instead of BLE: when the
         * total serialized size exceeds [BULK_THRESHOLD_BYTES], OR any payload carries
         * a photo (non-empty `photo_url` or `image_path`). Pure function (no Android
         * deps beyond org.json) so it is JVM-unit-testable.
         */
        fun shouldUseWifiDirect(envelopes: List<RecordEnvelope>): Boolean {
            if (envelopes.isEmpty()) return false
            var total = 0
            for (env in envelopes) {
                if (hasPhoto(env, "photo_url") || hasPhoto(env, "image_path")) return true
                total += EnvelopeCodec.encodeEnvelope(env).size
                if (total > BULK_THRESHOLD_BYTES) return true
            }
            return total > BULK_THRESHOLD_BYTES
        }

        private fun hasPhoto(env: RecordEnvelope, key: String): Boolean {
            val payload = env.payload
            return payload.has(key) && !payload.isNull(key) &&
                payload.optString(key, "").isNotEmpty()
        }
    }
}
