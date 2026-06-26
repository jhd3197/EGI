package com.egi.app.wifi

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.wifi.p2p.WifiP2pManager
import android.util.Log

/**
 * Wi-Fi Direct bulk-transfer fallback (plan §3 Layer 1, step 9).
 *
 * BLE/GATT is great for discovery and small payloads, but pushing many records
 * or photos over GATT is slow. When a peer signals it has a large batch, devices
 * can form a Wi-Fi Direct group and stream length-prefixed envelopes over a TCP
 * socket (group owner listens, client connects). The envelope wire format is
 * identical to the BLE path, so the merge/dedup logic is reused unchanged.
 *
 * This class wires up real peer discovery; the socket transfer is scaffolded with
 * a clear contract and TODOs, because it needs a paired on-device run to validate
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
        log("Wi-Fi Direct stopped")
    }

    /**
     * Stream the given envelopes (already serialized) to a connected peer.
     *
     * Contract: the group owner opens a [java.net.ServerSocket] on [TRANSFER_PORT]
     * and reads length-prefixed (4-byte BE) envelope JSON frames until EOF; the
     * client connects to the owner's address and writes the same frames. Reuses
     * `com.egi.app.mesh.EnvelopeCodec` for (de)serialization.
     *
     * TODO: implement the socket transfer once paired-device testing is available.
     * Until then, callers fall back to the BLE/GATT path which satisfies the v1
     * success criteria for small record sets.
     */
    fun sendBulk(serializedEnvelopes: List<ByteArray>, isGroupOwner: Boolean, ownerAddress: String?) {
        log("Wi-Fi Direct bulk transfer requested (${serializedEnvelopes.size} envelopes) — not yet wired")
    }

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
                WifiP2pManager.WIFI_P2P_CONNECTION_CHANGED_ACTION ->
                    log("Wi-Fi Direct connection changed")
            }
        }
    }

    private fun log(message: String) {
        Log.i(tag, message)
        onLog(message)
    }

    companion object {
        const val TRANSFER_PORT = 8988
    }
}
