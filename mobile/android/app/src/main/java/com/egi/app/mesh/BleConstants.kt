package com.egi.app.mesh

import java.util.UUID

/**
 * Shared BLE identifiers and tuning constants for the EGI mesh.
 *
 * The service + characteristic UUIDs are derived from the 16-bit alias `0xE91x`
 * placed in the Bluetooth SIG base UUID, so they are stable across builds and
 * documented in `mobile/shared/protocol.md`.
 */
object BleConstants {

    /** Advertised EGI service. Peers scan for exactly this UUID. */
    val SERVICE_UUID: UUID = UUID.fromString("0000e91f-0000-1000-8000-00805f9b34fb")

    /** Peer reads this to learn our local index: `[{record_id, updated_at, hop_count}, …]`. */
    val INDEX_CHAR_UUID: UUID = UUID.fromString("0000e911-0000-1000-8000-00805f9b34fb")

    /** Peer writes the record IDs it wants here: `[record_id, …]`. */
    val REQUEST_CHAR_UUID: UUID = UUID.fromString("0000e912-0000-1000-8000-00805f9b34fb")

    /** Records flow here as length-prefixed envelope chunks. Supports notify + write. */
    val RECORDS_CHAR_UUID: UUID = UUID.fromString("0000e913-0000-1000-8000-00805f9b34fb")

    /** ECDH public-key exchange: peer reads our ephemeral public key and writes its own to establish a per-connection AES-256-GCM session key. */
    val KEY_CHAR_UUID: UUID = UUID.fromString("0000e914-0000-1000-8000-00805f9b34fb")

    /** Standard Client Characteristic Configuration descriptor (enables notifications). */
    val CCC_DESCRIPTOR_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

    /**
     * Service-data byte tacked onto the advertisement holds a compact bloom filter
     * of local record IDs. Kept tiny so it fits the 31-byte legacy advert budget.
     */
    const val ADVERT_BLOOM_BYTES = 16

    /** Conservative default payload per GATT write before MTU negotiation (23 - 3 ATT header). */
    const val DEFAULT_CHUNK_SIZE = 20

    /** Requested ATT MTU. Most modern phones grant 247; transfers chunk to `mtu - 3`. */
    const val PREFERRED_MTU = 247

    /** Manufacturer-style tag prefixing the bloom filter service data, identifies protocol v1. */
    const val PROTOCOL_VERSION: Byte = 1

    /**
     * Maximum number of relay hops a record may travel before the mesh stops
     * forwarding it (plan-23 Phase 1, anti-circulation). A record arriving with a
     * hop_count greater than this is rejected outright; a record whose *stored*
     * hop_count reaches this ceiling is kept locally for the user to see but is no
     * longer advertised/relayed, so it cannot circulate forever and waste battery.
     *
     * Default 10 — tune after field density + battery benchmarks (plan §10).
     */
    const val MAX_HOPS = 10

    /**
     * Bit 0 of the advertisement `flags` byte: this device has recently confirmed
     * cloud reachability and is therefore a mesh "gateway" peers should prefer when
     * they have records pending for the cloud (plan-23 Phase 2).
     */
    const val GATEWAY_FLAG: Int = 0x01
}
