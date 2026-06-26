package com.egi.app.ble

import com.egi.app.mesh.IndexEntry
import com.egi.app.mesh.RecordEnvelope

/**
 * Bridge from the BLE transport layer (this package) up to the data/orchestration
 * layer (written later). The orchestrator implements this; the advertiser, scanner,
 * GATT server and GATT client only ever *call* it.
 *
 * Threading: the `suspend` members may do disk / DB work and are invoked from the
 * IO dispatchers owned by the transport classes. The plain (non-suspend) callbacks
 * are lightweight notifications and may be invoked from arbitrary BLE callback
 * threads — implementations must not block in them.
 */
interface MeshGattCallbacks {

    /** Our local index of every record we hold, exposed to peers over the Index characteristic. */
    suspend fun localIndex(): List<IndexEntry>

    /** Full envelopes for the requested record IDs (skips any we no longer have). */
    suspend fun envelopesFor(recordIds: List<String>): List<RecordEnvelope>

    /** A peer pushed an envelope to us (server side) or we pulled it (client side); merge it. */
    suspend fun onEnvelopeReceived(envelope: RecordEnvelope)

    /** A sync round with [peerAddress] finished: [received] envelopes in, [sent] envelopes out. */
    fun onPeerSynced(peerAddress: String, received: Int, sent: Int)

    /** Human-readable progress for debugging / a status UI. */
    fun onLog(message: String)
}
