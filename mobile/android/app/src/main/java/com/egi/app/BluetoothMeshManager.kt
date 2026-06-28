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
        onAdvertiseStart = { advertiser.start(cachedRecordIds, isGateway()) },
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

    // Gateway state (plan-23 Phase 2): this device is a "gateway" — has recently
    // confirmed it can reach the EGI cloud — until `gatewayUntilMs`. Set after every
    // successful cloud sync, cleared after repeated failures or when the mesh stops,
    // and read by isGateway() to drive the advertised gateway flag.
    @Volatile private var gatewayUntilMs = 0L
    @Volatile private var consecutiveCloudFailures = 0

    // Last gateway peer we saw advertised nearby (plan-23 Phase 2/3/6): its address
    // and when, so peers with pending uploads can prefer it and the PWA can show a
    // "gateway nearby" hint. Guarded by the volatile pair; cleared on stop.
    @Volatile private var lastGatewayPeer: String? = null
    @Volatile private var lastGatewaySeenMs = 0L

    /** Local record ids fed to the advertiser's bloom; refreshed when records change. */
    @Volatile private var cachedRecordIds: List<String> = emptyList()

    /** Whether the longer battery-saver duty cycle is active (persisted in prefs). */
    @Volatile private var batterySaver: Boolean = readBatterySaver()

    /** Set by MainActivity to forward native→web events on the UI thread. */
    var eventSink: ((String) -> Unit)? = null

    /**
     * Set by [MeshForegroundService] so it can refresh its live notification whenever
     * the mesh status changes (peers found, gateway detected, cloud synced, queue
     * drained). Invoked from [emitStatus]; the service does the UI-thread hop itself.
     */
    var onStatusChanged: (() -> Unit)? = null

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
            cachedRecordIds = repo.localRecordIds(relayDisabledCategories())
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
        // Stop claiming gateway status the moment the mesh is off (plan-23 Phase 2).
        gatewayUntilMs = 0L
        consecutiveCloudFailures = 0
        lastGatewayPeer = null
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
            cachedRecordIds = repo.localRecordIds(relayDisabledCategories())
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
     * (many records or a photo). We compute the outbound set, decide the route, and
     * — when Wi-Fi Direct qualifies — kick off discovery and run a group exchange
     * (group owner receives, client sends; plan-23 Phase 5). Any failure or the
     * absence of a formed group degrades to the BLE mesh + cloud reconcile, which
     * keep working regardless, so a bulk round never gets stuck.
     */
    fun syncBulkRound() {
        scope.launch {
            val ids = repo.localRecordIds(relayDisabledCategories())
            val envelopes = runCatching { repo.envelopesFor(ids) }.getOrElse { emptyList() }
            if (WifiDirectManager.shouldUseWifiDirect(envelopes)) {
                log("Bulk set qualifies for Wi-Fi Direct (${envelopes.size} envelopes)")
                val transferred = runCatching {
                    wifi.discoverPeers()
                    wifi.runBulkExchange(envelopes) { env -> onEnvelopeReceived(env) }
                }.getOrElse { e ->
                    log("Wi-Fi Direct bulk failed: ${e.message}; falling back to BLE")
                    -1
                }
                if (transferred >= 0) {
                    log("Wi-Fi Direct bulk transferred $transferred envelopes")
                    repo.logSync("wifi_direct", peer = null, count = transferred, detail = "bulk")
                } else {
                    log("Wi-Fi Direct group unavailable; BLE mesh + cloud handle this round")
                }
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

    /**
     * Set whether this device relays a content category over the mesh (plan-24
     * Phase 5). Persisted in SharedPreferences and applied live: refreshing the
     * advertised bloom drops (or restores) that category's records immediately.
     * A disabled category is still stored and shown — only relay is suppressed.
     */
    fun setRelayCategory(category: String, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_RELAY_PREFIX + category, enabled).apply()
        log("Relay $category ${if (enabled) "enabled" else "disabled"}")
        refreshAdvertisement()
        emitStatus()
    }

    /** Content categories the user opted OUT of relaying (default: all enabled). */
    private fun relayDisabledCategories(): Set<String> {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return RELAY_CATEGORIES.filterNot { prefs.getBoolean(KEY_RELAY_PREFIX + it, true) }.toSet()
    }

    private fun onPeerFound(peer: PeerDevice) {
        // Remember a nearby gateway regardless of whether we connect this round, so
        // the prioritization heuristic and the PWA hint can see it (plan-23 Phase 2/3).
        if (peer.isGateway) {
            lastGatewayPeer = peer.address
            lastGatewaySeenMs = System.currentTimeMillis()
        }
        scope.launch {
            if (!shouldConnect(peer)) return@launch
            connectMutex.withLock {
                log("Connecting to peer ${peer.address} (rssi ${peer.rssi})")
                gattClient.connect(peer.device)
            }
        }
    }

    /**
     * Decide whether a discovered peer is worth a GATT connection.
     *
     * Gateway-aware routing (plan-23 Phase 3): if this peer is a gateway and we hold
     * records the cloud hasn't seen, we preferentially connect — pushing toward the
     * cloud is the whole point of the human chain — using a much shorter cooldown so
     * the upload happens fast. Otherwise we fall back to the bloom-filter need check:
     * connect when the peer is missing at least one record we hold (so we can push),
     * has no bloom, or we hold nothing yet (so we can pull) — all gated by a per-peer
     * cooldown to spare the battery.
     */
    private suspend fun shouldConnect(peer: PeerDevice): Boolean {
        val now = System.currentTimeMillis()
        val last = lastConnectAttempt[peer.address] ?: 0L

        // Fast path toward a gateway when we have something to upload.
        if (peer.isGateway && hasPendingForCloud()) {
            if (now - last < GATEWAY_PEER_COOLDOWN_MS) return false
            lastConnectAttempt[peer.address] = now
            log("Prioritizing gateway peer ${peer.address} (local records pending for cloud)")
            return true
        }

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

    /** True when local persons, reports or animals have changed since the last cloud sync. */
    private suspend fun hasPendingForCloud(): Boolean {
        val since = lastSyncIso ?: EPOCH
        return repo.pendingForCloud(since).isNotEmpty() ||
            repo.pendingReportsForCloud(since).isNotEmpty() ||
            repo.pendingAnimalsForCloud(since).isNotEmpty()
    }

    /** Upload locally-changed records, then pull anything newer from the cloud. */
    private suspend fun syncCloud() {
        try {
            val since = lastSyncIso ?: EPOCH
            val pending = repo.pendingForCloud(since)
            val pendingReports = repo.pendingReportsForCloud(since)
            val pendingAnimals = repo.pendingAnimalsForCloud(since)
            queuedCount = pending.size + pendingReports.size + pendingAnimals.size
            if (pending.isNotEmpty() || pendingReports.isNotEmpty() || pendingAnimals.isNotEmpty()) {
                val saved = cloud.upload(pending, pendingReports, pendingAnimals)
                repo.logSync("cloud_out", peer = null, count = saved, detail = "upload")
                log("Uploaded $saved records to cloud")
            }
            val pull = cloud.download(since)
            if (pull.persons.isNotEmpty() || pull.reports.isNotEmpty() || pull.animals.isNotEmpty()) {
                val applied = repo.applyCloudRecords(pull.persons) +
                    repo.applyCloudReports(pull.reports) +
                    repo.applyCloudAnimals(pull.animals)
                repo.logSync("cloud_in", peer = null, count = applied, detail = "download")
                log("Applied $applied records from cloud")
            }
            lastSyncIso = nowIso()
            queuedCount = 0
            // Reaching here means the cloud was reachable: become/refresh a gateway so
            // peers with pending uploads prefer us (plan-23 Phase 2).
            gatewayUntilMs = System.currentTimeMillis() + GATEWAY_VALIDITY_MS
            consecutiveCloudFailures = 0
            refreshAdvertisement()
            emitStatus()
        } catch (e: Exception) {
            // Offline or server unreachable: keep local data, retry on the next trigger.
            // After a couple of consecutive failures, stop advertising as a gateway so
            // we don't mislead peers into routing toward an unreachable cloud.
            consecutiveCloudFailures += 1
            if (consecutiveCloudFailures >= MAX_CLOUD_FAILURES_BEFORE_DEMOTE && isGateway()) {
                gatewayUntilMs = 0L
                log("Cloud unreachable ($consecutiveCloudFailures failures); no longer a gateway")
                emitStatus()
            }
            Log.d(tag, "Cloud sync skipped: ${e.message}")
        }
    }

    /**
     * Whether this device is currently a mesh gateway: the mesh is running and the
     * last successful cloud sync is still within the validity window. Drives the
     * advertised gateway flag and the PWA badge (plan-23 Phase 2).
     */
    fun isGateway(): Boolean = running && System.currentTimeMillis() < gatewayUntilMs

    /**
     * Address of a gateway peer seen within [GATEWAY_PEER_FRESH_MS], or null. Lets
     * the UI show a "gateway nearby" hint and peers preferentially route toward it.
     */
    private fun gatewayPeerNearby(): String? {
        val peer = lastGatewayPeer ?: return null
        return if (System.currentTimeMillis() - lastGatewaySeenMs < GATEWAY_PEER_FRESH_MS) peer else null
    }

    // ----- MeshGattCallbacks (driven by the GATT server/client) -----

    // Served to peers when they pull our index — respects relay preferences so
    // categories the user opted out of are never offered onward (plan-24 Phase 5).
    override suspend fun localIndex(): List<IndexEntry> = repo.localRecordIndex(relayDisabledCategories())

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
        // Refresh the live notification with the new peer count even while offline
        // (syncCloud() won't emit a status update when the cloud is unreachable).
        emitStatus()
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
        // Gateway / chain awareness for the PWA mesh screen (plan-23 Phase 6).
        put("isGateway", isGateway())
        put("gatewayPeer", gatewayPeerNearby() ?: JSONObject.NULL)
        put("maxHops", com.egi.app.mesh.BleConstants.MAX_HOPS)
        put("droppedAtMaxHops", repo.droppedAtMaxHopsCount())
        // Per-category relay opt-outs so the PWA can render its current state
        // (plan-24 Phase 5): { category: true|false } where false = not relayed.
        put("relay", relayCategoriesJson())
    }.toString()

    /** Current relay-enabled state per category (true = relayed over the mesh). */
    private fun relayCategoriesJson(): JSONObject {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return JSONObject().apply {
            for (c in RELAY_CATEGORIES) put(c, prefs.getBoolean(KEY_RELAY_PREFIX + c, true))
        }
    }

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

    /** Snapshot of mesh status for the foreground-service notification (plan-23 Phase 4). */
    data class NotificationStatus(
        val running: Boolean,
        val peers: Int,
        val queued: Int,
        val isGateway: Boolean,
        val gatewayNearby: Boolean,
        val online: Boolean,
    )

    fun notificationStatus(): NotificationStatus = NotificationStatus(
        running = running,
        peers = peerCount,
        queued = queuedCount,
        isGateway = isGateway(),
        gatewayNearby = gatewayPeerNearby() != null,
        online = isOnline(),
    )

    /** Best-effort current internet reachability (the notification's online dot). */
    private fun isOnline(): Boolean = try {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE)
            as? android.net.ConnectivityManager
        val network = cm?.activeNetwork
        val caps = network?.let { cm.getNetworkCapabilities(it) }
        caps?.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
    } catch (_: Exception) {
        false
    }

    private fun emitStatus() {
        emit("status", JSONObject(statusJson()))
        // Let the foreground service repaint its live notification.
        onStatusChanged?.invoke()
    }

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

        /** How long a successful cloud sync keeps this device flagged as a gateway. */
        private const val GATEWAY_VALIDITY_MS = 5 * 60_000L

        /** Consecutive cloud-sync failures before we drop our gateway claim. */
        private const val MAX_CLOUD_FAILURES_BEFORE_DEMOTE = 2

        /** A gateway peer sighting older than this is considered stale. */
        private const val GATEWAY_PEER_FRESH_MS = 60_000L

        /** Shorter cooldown for a gateway peer when we have records to push (Phase 3). */
        private const val GATEWAY_PEER_COOLDOWN_MS = 4_000L
        private const val PREFS = "egi_mesh"
        private const val KEY_BATTERY_SAVER = "battery_saver"

        /** SharedPreferences key prefix for per-category relay opt-outs (plan-24 Phase 5). */
        private const val KEY_RELAY_PREFIX = "relay_"

        /** Content categories the PWA can toggle for mesh relay. All default ON. */
        private val RELAY_CATEGORIES = listOf(
            "people", "animals", "shelters", "hazards", "supplies", "operations", "broadcasts",
        )

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
