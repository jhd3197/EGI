package com.egi.app

import android.annotation.SuppressLint
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
import com.egi.app.mesh.DutyCycler
import com.egi.app.mesh.IndexEntry
import com.egi.app.mesh.RecordEnvelope
import com.egi.app.net.CloudSyncClient
import com.egi.app.wifi.WifiDirectManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
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
@SuppressLint("StaticFieldLeak")
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
    private val wifi = WifiDirectManager(context, ::log)

    // Relay duty cycle: staggered advertise/scan windows instead of leaving both
    // radios on continuously. Battery-saver lengthens the idle sleep.
    private val dutyCycler = DutyCycler(
        scope = scope,
        onAdvertiseStart = { advertiser.start(cachedRecordIds) },
        onAdvertiseStop = { advertiser.stop() },
        onScanStart = { scanner.start(::onPeerFound) },
        onScanStop = { scanner.stop() },
        onLog = ::log,
    )

    // Per-peer cooldown so we don't reconnect to the same device in a tight loop.
    private val lastConnectAttempt = HashMap<String, Long>()
    private val connectMutex = Mutex()

    // Most-recently-synced peer addresses (capped), surfaced in the status event so
    // the PWA can render a recent-peers list without inferring it from peer_synced
    // events alone. Guarded by its own lock: written from the IO scope, read from
    // the JS binder thread.
    private val recentPeers = ArrayDeque<String>()
    private val recentPeersLock = Any()

    // Cached status, updated by background work and read synchronously by the JS bridge.
    @Volatile private var running = false
    @Volatile private var peerCount = 0
    @Volatile private var queuedCount = 0
    @Volatile private var lastSyncIso: String? = null

    /** Local record ids fed to the advertiser's bloom; refreshed when records change. */
    @Volatile private var cachedRecordIds: List<String> = emptyList()

    /** Whether the longer battery-saver duty cycle is active (persisted in prefs). */
    @Volatile private var batterySaver: Boolean = readBatterySaver()

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
        wifi.start()
        // Prime the advertised bloom, then run the staggered advertise/scan duty cycle.
        scope.launch {
            cachedRecordIds = repo.localRecordIds()
            // Auto-enable the longer battery-saver duty cycle when the battery is
            // critically low, even if the user hasn't toggled it. Applied live to the
            // cycler only (we don't persist an automatic decision); a manual toggle
            // still wins via setBatterySaver(). Best-effort and never crashes.
            val level = batteryLevelPercent()
            val saver = batterySaver || (level != null && level < LOW_BATTERY_PCT)
            if (saver && !batterySaver) {
                log("Battery low ($level%); enabling battery-saver duty cycle")
            }
            dutyCycler.batterySaver = saver
            dutyCycler.start()
        }
        emitStatus()
        // Opportunistically reconcile with the cloud if we already have connectivity.
        scope.launch { syncCloud() }
    }

    fun stop() {
        if (!running) return
        running = false
        Log.i(tag, "Stopping EGI mesh")
        dutyCycler.stop()
        scanner.stop()
        advertiser.stop()
        wifi.stop()
        gattServer.close()
        gattClient.close()
        emitStatus()
    }

    /**
     * Refresh the advertised bloom source from the current local record set. The
     * duty cycle's next advertise window picks up [cachedRecordIds]; we don't toggle
     * the radio here so we never fight the [DutyCycler]'s scheduling.
     */
    private fun refreshAdvertisement() {
        scope.launch {
            cachedRecordIds = repo.localRecordIds()
        }
    }

    /**
     * Public hook for records written outside the mesh path — e.g. the PWA created a
     * report through the EgiNative bridge straight into Room. Without this, the
     * advertised bloom would stay stale (0 ids) and peers would never learn this
     * device holds the new record, so it would never relay over the mesh.
     */
    fun notifyLocalRecordsChanged() = refreshAdvertisement()

    /** Triggered by the JS bridge: run a cloud reconcile (mesh runs continuously). */
    fun syncMeshRound() {
        scope.launch { syncCloud() }
    }

    /**
     * Prefer the Wi-Fi Direct bulk route when this round's outbound set is large
     * (many records or a photo). Discovery already exists; the WifiP2p group
     * negotiation that yields the group-owner address is still TODO, so for now we
     * compute the outbound set, decide the route, kick off discovery, and always
     * fall back to the BLE/cloud reconcile which keeps working today.
     */
    fun syncBulkRound() {
        scope.launch {
            val ids = repo.localRecordIds()
            val envelopes = runCatching { repo.envelopesFor(ids) }.getOrElse { emptyList() }
            if (WifiDirectManager.shouldUseWifiDirect(envelopes)) {
                log("Bulk set qualifies for Wi-Fi Direct (${envelopes.size} envelopes)")
                wifi.discoverPeers()
                // TODO: complete the WifiP2p group negotiation to obtain the
                // group-owner InetAddress + role, then call:
                //   wifi.sendBulk(envelopes, isGroupOwner, groupOwnerAddress)
                // (receiver side calls wifi.receiveBulk { mergeEnvelope(it) }).
                // Until that is validated on paired devices, BLE remains the path.
            } else {
                log("Bulk set small; using BLE path")
            }
            // BLE mesh keeps running via the duty cycle; reconcile the cloud too.
            syncCloud()
        }
    }

    /** Toggle the longer battery-saver duty cycle; persisted and applied live. */
    fun setBatterySaver(value: Boolean) {
        batterySaver = value
        dutyCycler.batterySaver = value
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_BATTERY_SAVER, value).apply()
        log("Battery saver ${if (value) "enabled" else "disabled"}")
        emitStatus()
    }

    private fun readBatterySaver(): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_BATTERY_SAVER, false)

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
        rememberPeer(peerAddress)
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
        put("batterySaver", batterySaver)
        put("recentPeers", recentPeersJson())
    }.toString()

    /** Record a peer we just synced with, most-recent-first, capped. */
    private fun rememberPeer(address: String) {
        synchronized(recentPeersLock) {
            recentPeers.remove(address)
            recentPeers.addFirst(address)
            while (recentPeers.size > MAX_RECENT_PEERS) recentPeers.removeLast()
        }
    }

    private fun recentPeersJson(): JSONArray = synchronized(recentPeersLock) {
        JSONArray().apply { recentPeers.forEach { put(it) } }
    }

    /**
     * Current battery level as a 0..100 percentage, or null if unavailable. Uses
     * [android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY]; never throws.
     */
    private fun batteryLevelPercent(): Int? = try {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as? android.os.BatteryManager
        val level = bm?.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
        level?.takeIf { it in 0..100 }
    } catch (_: Exception) {
        null
    }

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

    // Single source of truth for the base URL is CloudSyncClient.resolveBaseUrl.
    private fun resolveApiUrl(): String = CloudSyncClient.resolveBaseUrl(context)

    private fun nowIso(): String = java.time.Instant.now().toString()

    companion object {
        private const val EPOCH = "1970-01-01T00:00:00Z"
        private const val PEER_COOLDOWN_MS = 15_000L
        private const val PEER_PULL_INTERVAL_MS = 120_000L
        private const val PREFS = "egi_mesh"
        private const val KEY_BATTERY_SAVER = "battery_saver"

        /** Max recent peer addresses surfaced in the status event. */
        private const val MAX_RECENT_PEERS = 10

        /** Below this battery percentage, the duty cycle auto-switches to saver mode. */
        private const val LOW_BATTERY_PCT = 15

        @Volatile
        private var instance: BluetoothMeshManager? = null

        /**
         * Process-wide singleton so the WebView bridge ([MainActivity]/[EgiBridge])
         * and the [MeshForegroundService] share ONE manager (and therefore one GATT
         * server / one duty cycle). Always backed by the application context.
         */
        fun getInstance(context: Context): BluetoothMeshManager =
            instance ?: synchronized(this) {
                instance ?: BluetoothMeshManager(context.applicationContext).also { instance = it }
            }
    }
}
