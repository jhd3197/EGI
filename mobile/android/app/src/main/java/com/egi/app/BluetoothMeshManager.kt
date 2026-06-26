package com.egi.app

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.util.Log
import com.egi.app.ble.BleAdvertiser
import com.egi.app.ble.BleScanner
import com.egi.app.ble.GattClient
import com.egi.app.ble.GattServer
import com.egi.app.ble.MeshGattCallbacks
import com.egi.app.ble.PeerDevice
import com.egi.app.data.EgiDatabase
import com.egi.app.data.MeshRepository
import com.egi.app.mesh.IndexEntry
import com.egi.app.mesh.RecordEnvelope
import com.egi.app.net.CloudSyncClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject

/**
 * Orchestrates the EGI store-and-forward mesh: BLE advertise + scan, GATT
 * server/client record exchange, and the bridge/cloud sync to FastAPI `/sync`.
 *
 * It implements [MeshGattCallbacks] so the GATT layer can read our local index,
 * fetch envelopes, and hand us records peers pushed — all routed through
 * [MeshRepository] (last-write-wins, deduped by `record_id`). See
 * `mobile/shared/protocol.md` for the wire protocol.
 *
 * Permissions (BLUETOOTH_SCAN/ADVERTISE/CONNECT) are obtained by [MainActivity]
 * before [start] is called; the BLE classes are annotated accordingly.
 */
class BluetoothMeshManager(private val context: Context) : MeshGattCallbacks {

    private val tag = "EGI-Mesh"
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val db = EgiDatabase.get(context)
    val deviceId: String = MeshRepository.deviceFingerprint(context)
    private val repo = MeshRepository(db, deviceId)
    private val cloud = CloudSyncClient(resolveApiUrl())

    private val advertiser = BleAdvertiser(context, ::log)
    private val scanner = BleScanner(context, ::log)
    private val gattServer = GattServer(context, this)
    private val gattClient = GattClient(context, this)

    // Per-peer cooldown so we don't reconnect to the same device in a tight loop.
    private val lastConnectAttempt = HashMap<String, Long>()
    private val connectMutex = Mutex()

    // Cached status, updated by background work and read synchronously by the JS bridge.
    @Volatile private var running = false
    @Volatile private var peerCount = 0
    @Volatile private var queuedCount = 0
    @Volatile private var lastSyncIso: String? = null

    /** Set by MainActivity to forward native→web events on the UI thread. */
    var eventSink: ((String) -> Unit)? = null

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    }

    fun start() {
        val adapter = bluetoothAdapter
        if (adapter == null) {
            log("Bluetooth not supported on this device")
            return
        }
        if (!adapter.isEnabled) {
            log("Bluetooth is disabled; mesh cannot start")
            return
        }
        if (running) return
        running = true
        Log.i(tag, "Starting EGI mesh as device $deviceId")

        gattServer.open()
        refreshAdvertisement()
        scanner.start(::onPeerFound)
        emitStatus()
        // Opportunistically reconcile with the cloud if we already have connectivity.
        scope.launch { syncCloud() }
    }

    fun stop() {
        if (!running) return
        running = false
        Log.i(tag, "Stopping EGI mesh")
        scanner.stop()
        advertiser.stop()
        gattServer.close()
        gattClient.close()
        emitStatus()
    }

    /** Rebuilds the advertisement bloom from the current local record set. */
    private fun refreshAdvertisement() {
        scope.launch {
            val ids = repo.localRecordIds()
            advertiser.stop()
            advertiser.start(ids)
        }
    }

    /** Triggered by the JS bridge: run a cloud reconcile (mesh runs continuously). */
    fun syncMeshRound() {
        scope.launch { syncCloud() }
    }

    private fun onPeerFound(peer: PeerDevice) {
        scope.launch {
            if (!shouldConnect(peer)) return@launch
            connectMutex.withLock {
                log("Connecting to peer ${peer.address} (rssi ${peer.rssi})")
                gattClient.connect(peer.device)
            }
        }
    }

    /**
     * Decide whether a discovered peer is worth a GATT connection. We connect when
     * the peer's advertised bloom shows it is missing at least one record we hold
     * (so we can push), when it has no bloom, or when we hold nothing yet (so we
     * can pull) — all gated by a per-peer cooldown to spare the battery.
     */
    private suspend fun shouldConnect(peer: PeerDevice): Boolean {
        val now = System.currentTimeMillis()
        val last = lastConnectAttempt[peer.address] ?: 0L
        if (now - last < PEER_COOLDOWN_MS) return false

        val localIds = repo.localRecordIds()
        val bloom = peer.bloom
        val peerMissingSomething = bloom == null || localIds.isEmpty() ||
            localIds.any { !bloom.mightContain(it) }
        if (!peerMissingSomething) {
            // Peer likely already has everything we hold; pull occasionally anyway.
            if (now - last < PEER_PULL_INTERVAL_MS) return false
        }
        lastConnectAttempt[peer.address] = now
        return true
    }

    /** Upload locally-changed records, then pull anything newer from the cloud. */
    private suspend fun syncCloud() {
        try {
            val since = lastSyncIso ?: EPOCH
            val pending = repo.pendingForCloud(since)
            val pendingReports = repo.pendingReportsForCloud(since)
            queuedCount = pending.size + pendingReports.size
            if (pending.isNotEmpty() || pendingReports.isNotEmpty()) {
                val saved = cloud.upload(pending, pendingReports)
                repo.logSync("cloud_out", peer = null, count = saved, detail = "upload")
                log("Uploaded $saved records to cloud")
            }
            val pull = cloud.download(since)
            if (pull.persons.isNotEmpty() || pull.reports.isNotEmpty()) {
                val applied = repo.applyCloudRecords(pull.persons) +
                    repo.applyCloudReports(pull.reports)
                repo.logSync("cloud_in", peer = null, count = applied, detail = "download")
                log("Applied $applied records from cloud")
            }
            lastSyncIso = nowIso()
            queuedCount = 0
            refreshAdvertisement()
            emitStatus()
        } catch (e: Exception) {
            // Offline or server unreachable: keep local data, retry on the next trigger.
            Log.d(tag, "Cloud sync skipped: ${e.message}")
        }
    }

    // ----- MeshGattCallbacks (driven by the GATT server/client) -----

    override suspend fun localIndex(): List<IndexEntry> = repo.localRecordIndex()

    override suspend fun envelopesFor(recordIds: List<String>): List<RecordEnvelope> =
        repo.envelopesFor(recordIds)

    override suspend fun onEnvelopeReceived(envelope: RecordEnvelope) {
        val changed = repo.mergeEnvelope(envelope)
        if (changed) {
            queuedCount += 1 // a freshly merged record is now pending for the cloud
            refreshAdvertisement()
        }
    }

    override fun onPeerSynced(peerAddress: String, received: Int, sent: Int) {
        peerCount += 1
        log("Synced with $peerAddress: received $received, sent $sent")
        scope.launch {
            repo.logSync("mesh_in", peer = peerAddress, count = received, detail = "sent=$sent")
            // A mesh exchange may have produced records the cloud hasn't seen.
            syncCloud()
        }
        emitPeerSynced(peerAddress, received, sent)
    }

    override fun onLog(message: String) = log(message)

    // ----- JS bridge support (synchronous reads of cached status) -----

    fun statusJson(): String = JSONObject().apply {
        put("running", running)
        put("peers", peerCount)
        put("queued", queuedCount)
        put("lastSync", lastSyncIso ?: JSONObject.NULL)
        put("deviceId", deviceId)
    }.toString()

    private fun emitStatus() = emit("status", JSONObject(statusJson()))

    private fun emitPeerSynced(peer: String, received: Int, sent: Int) =
        emit("peer_synced", JSONObject().apply {
            put("peer", peer); put("received", received); put("sent", sent)
        })

    private fun emit(type: String, data: JSONObject) {
        val event = JSONObject().apply { put("type", type); put("data", data) }
        eventSink?.invoke(event.toString())
    }

    private fun log(message: String) {
        Log.i(tag, message)
        emit("log", JSONObject().apply { put("message", message) })
    }

    private fun resolveApiUrl(): String {
        val prefs = context.getSharedPreferences("egi_mesh", Context.MODE_PRIVATE)
        // 10.0.2.2 is the host loopback as seen from the Android emulator.
        return prefs.getString("api_url", "http://10.0.2.2:3000") ?: "http://10.0.2.2:3000"
    }

    private fun nowIso(): String = java.time.Instant.now().toString()

    companion object {
        private const val EPOCH = "1970-01-01T00:00:00Z"
        private const val PEER_COOLDOWN_MS = 15_000L
        private const val PEER_PULL_INTERVAL_MS = 120_000L
    }
}
