package com.egi.app.mesh

import org.json.JSONArray
import org.json.JSONObject

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
    /** The bare record fields (a PFIF-style person, or a report). */
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

/** JSON (de)serialization helpers for the lists exchanged over GATT. */
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
}

/** `optString` returns the literal "null" / "" too eagerly; this yields a real null. */
internal fun JSONObject.optStringOrNull(key: String): String? =
    if (isNull(key) || !has(key)) null else optString(key, null)
