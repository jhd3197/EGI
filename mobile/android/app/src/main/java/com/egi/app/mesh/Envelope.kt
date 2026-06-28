package com.egi.app.mesh

import org.json.JSONArray
import org.json.JSONObject
import java.util.Base64

/**
 * Record envelope exchanged over the mesh. A thin transport wrapper around the
 * exact JSON the server `/sync` endpoint accepts (`payload`). See
 * `mobile/shared/protocol.md` for the wire format and rules.
 */
data class RecordEnvelope(
    val recordType: String,
    val recordId: String,
    val originDevice: String?,
    val hopCount: Int,
    val createdAt: String?,
    val updatedAt: String?,
    /**
     * The bare record fields (a PFIF-style person, or a report).
     *
     * Plan-25 (Trust, Safety & Verification): the server-carried trust signals
     * `author_role`, `org_id`, `location_id`, `signature` and the server-computed
     * `trust_tier` ride INSIDE this payload as ordinary keys. Because the whole
     * payload is relayed verbatim (see [EnvelopeCodec]), these provenance fields
     * survive every mesh hop so offline peers still see who vouched for a record.
     * They must never be stripped from the payload on relay.
     */
    val payload: JSONObject,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("record_type", recordType)
        put("record_id", recordId)
        put("origin_device", originDevice ?: JSONObject.NULL)
        put("hop_count", hopCount)
        put("created_at", createdAt ?: JSONObject.NULL)
        put("updated_at", updatedAt ?: JSONObject.NULL)
        put("payload", payload)
    }

    /** Returns a copy with `hop_count` incremented — used when relaying a peer's record. */
    fun relayed(): RecordEnvelope = copy(hopCount = hopCount + 1)

    companion object {
        const val TYPE_PERSON = "person"
        const val TYPE_REPORT = "report"

        fun fromJson(obj: JSONObject): RecordEnvelope = RecordEnvelope(
            recordType = obj.optString("record_type", TYPE_PERSON),
            recordId = obj.getString("record_id"),
            originDevice = obj.optStringOrNull("origin_device"),
            hopCount = obj.optInt("hop_count", 0),
            createdAt = obj.optStringOrNull("created_at"),
            updatedAt = obj.optStringOrNull("updated_at"),
            payload = obj.getJSONObject("payload"),
        )
    }
}

/**
 * One entry in the index a device exposes/reads to decide which records a peer
 * is missing or holds in a staler form.
 */
data class IndexEntry(
    val recordId: String,
    val updatedAt: String?,
    val hopCount: Int,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("record_id", recordId)
        put("updated_at", updatedAt ?: JSONObject.NULL)
        put("hop_count", hopCount)
    }

    companion object {
        fun fromJson(obj: JSONObject): IndexEntry = IndexEntry(
            recordId = obj.getString("record_id"),
            updatedAt = obj.optStringOrNull("updated_at"),
            hopCount = obj.optInt("hop_count", 0),
        )
    }
}

/**
 * JSON (de)serialization helpers for the lists exchanged over GATT.
 *
 * Payload-passthrough invariant: the codec treats [RecordEnvelope.payload] as an
 * opaque [JSONObject] and serializes it whole (`payload.toString()`), so arbitrary
 * keys — including the plan-25 trust fields `author_role`/`org_id`/`location_id`/
 * `signature`/`trust_tier` — round-trip unchanged through both the plaintext and the
 * encrypted variants. No key is ever whitelisted or dropped here; do not add such a
 * filter or the offline trust provenance would be lost on relay.
 */
object EnvelopeCodec {

    fun encodeIndex(entries: List<IndexEntry>): ByteArray {
        val arr = JSONArray()
        entries.forEach { arr.put(it.toJson()) }
        return arr.toString().toByteArray(Charsets.UTF_8)
    }

    fun decodeIndex(bytes: ByteArray): List<IndexEntry> {
        val arr = JSONArray(String(bytes, Charsets.UTF_8))
        return (0 until arr.length()).map { IndexEntry.fromJson(arr.getJSONObject(it)) }
    }

    fun encodeRequest(recordIds: List<String>): ByteArray {
        val arr = JSONArray()
        recordIds.forEach { arr.put(it) }
        return arr.toString().toByteArray(Charsets.UTF_8)
    }

    fun decodeRequest(bytes: ByteArray): List<String> {
        val arr = JSONArray(String(bytes, Charsets.UTF_8))
        return (0 until arr.length()).map { arr.getString(it) }
    }

    fun encodeEnvelope(envelope: RecordEnvelope): ByteArray =
        envelope.toJson().toString().toByteArray(Charsets.UTF_8)

    fun decodeEnvelope(bytes: ByteArray): RecordEnvelope =
        RecordEnvelope.fromJson(JSONObject(String(bytes, Charsets.UTF_8)))

    /**
     * Encode an envelope with the [payload] encrypted under the per-connection
     * [sessionKey]. The header fields (record_type, record_id, origin_device,
     * hop_count, created_at, updated_at) stay in plaintext JSON so a relay can still
     * apply last-write-wins without decrypting; only the PII-bearing `payload` is
     * replaced by an `enc` field holding base64(AES-256-GCM(payload)).
     *
     * `java.util.Base64` (not `android.util.Base64`) keeps this JVM-testable.
     */
    fun encodeEnvelopeEncrypted(envelope: RecordEnvelope, sessionKey: ByteArray): ByteArray {
        val cipherBytes = MeshCrypto.encrypt(
            sessionKey,
            envelope.payload.toString().toByteArray(Charsets.UTF_8),
        )
        val obj = JSONObject().apply {
            put("record_type", envelope.recordType)
            put("record_id", envelope.recordId)
            put("origin_device", envelope.originDevice ?: JSONObject.NULL)
            put("hop_count", envelope.hopCount)
            put("created_at", envelope.createdAt ?: JSONObject.NULL)
            put("updated_at", envelope.updatedAt ?: JSONObject.NULL)
            put("enc", Base64.getEncoder().encodeToString(cipherBytes))
        }
        return obj.toString().toByteArray(Charsets.UTF_8)
    }

    /**
     * Inverse of [encodeEnvelopeEncrypted]: parse the plaintext header, base64-decode
     * the `enc` field, AES-256-GCM decrypt it with [sessionKey], and rebuild the
     * payload JSON. Throws if the key is wrong or the ciphertext is tampered with.
     */
    fun decodeEnvelopeEncrypted(bytes: ByteArray, sessionKey: ByteArray): RecordEnvelope {
        val obj = JSONObject(String(bytes, Charsets.UTF_8))
        val cipherBytes = Base64.getDecoder().decode(obj.getString("enc"))
        val payloadBytes = MeshCrypto.decrypt(sessionKey, cipherBytes)
        val payload = JSONObject(String(payloadBytes, Charsets.UTF_8))
        return RecordEnvelope(
            recordType = obj.optString("record_type", RecordEnvelope.TYPE_PERSON),
            recordId = obj.getString("record_id"),
            originDevice = obj.optStringOrNull("origin_device"),
            hopCount = obj.optInt("hop_count", 0),
            createdAt = obj.optStringOrNull("created_at"),
            updatedAt = obj.optStringOrNull("updated_at"),
            payload = payload,
        )
    }
}

/** `optString` returns the literal "null" / "" too eagerly; this yields a real null. */
internal fun JSONObject.optStringOrNull(key: String): String? =
    if (isNull(key) || !has(key)) null else optString(key)
