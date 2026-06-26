package com.egi.app.data

import com.egi.app.mesh.RecordEnvelope
import org.json.JSONObject
import java.time.Instant

/**
 * Pure mapping functions between the Room entities, the mesh [RecordEnvelope]
 * transport wrapper, and the JSON shape the server `/sync` endpoint accepts.
 *
 * Field casing rule (must match `server/main.py` PersonRecord/ReportRecord):
 * everything is snake_case EXCEPT `createdAt` / `updatedAt`, which stay camelCase.
 *
 * Null policy: to keep mesh/cloud payloads small we omit keys whose value is null
 * rather than emitting JSONObject.NULL. The inverse parsers tolerate missing keys.
 */
/** ISO-8601 UTC timestamp (e.g. "2026-06-26T12:34:56.789Z"). API 26+ has java.time. */
fun nowIso(): String = Instant.now().toString()

/**
 * Newer-than over ISO-8601 UTC timestamps. A null is treated as the oldest
 * possible value, so any real timestamp beats it.
 *
 * Parses both sides to [Instant] and compares by absolute instant rather than by
 * raw string. This normalizes equivalent-but-differently-spelled offsets (e.g.
 * "...T00:00:00Z" vs "...T00:00:00+00:00"), which a naive lexicographic compare
 * would misorder even though they denote the same moment. If either value is
 * malformed and cannot be parsed, we fall back to the original lexicographic
 * comparison so the function never throws.
 */
fun isNewer(a: String?, b: String?): Boolean {
    if (a == null) return false
    if (b == null) return true
    return try {
        Instant.parse(a) > Instant.parse(b)
    } catch (_: Exception) {
        a > b
    }
}

// --- Small JSON helpers ----------------------------------------------------

/** Put a value only when it is non-null, keeping payloads compact. */
private fun JSONObject.putIfNotNull(key: String, value: Any?): JSONObject {
    if (value != null) put(key, value)
    return this
}

/** Real null instead of optString's eager "" / "null". */
private fun JSONObject.strOrNull(key: String): String? =
    if (!has(key) || isNull(key)) null else optString(key, null)

private fun JSONObject.intOrNull(key: String): Int? =
    if (!has(key) || isNull(key)) null else optInt(key)

// --- PersonEntity <-> /sync JSON -------------------------------------------

/** Snake_case fields + camelCase createdAt/updatedAt, matching server PersonRecord. */
fun PersonEntity.toSyncJson(): JSONObject = JSONObject().apply {
    put("id", id)
    putIfNotNull("disaster_id", disasterId)
    putIfNotNull("name", name)
    putIfNotNull("status", status)
    putIfNotNull("gender", gender)
    putIfNotNull("age", age)
    putIfNotNull("location", location)
    putIfNotNull("last_seen_date", lastSeenDate)
    putIfNotNull("clothes", clothes)
    putIfNotNull("notes", notes)
    putIfNotNull("contact", contact)
    putIfNotNull("reporter_name", reporterName)
    putIfNotNull("reporter_relation", reporterRelation)
    putIfNotNull("reporter_country", reporterCountry)
    putIfNotNull("reported_by", reportedBy)
    putIfNotNull("source", source)
    putIfNotNull("provenance", provenance)
    putIfNotNull("image_path", imagePath)
    putIfNotNull("given_name", givenName)
    putIfNotNull("family_name", familyName)
    putIfNotNull("cedula", cedula)
    putIfNotNull("sex", sex)
    putIfNotNull("photo_url", photoUrl)
    putIfNotNull("last_known_location", lastKnownLocation)
    putIfNotNull("merged_into", mergedInto)
    putIfNotNull("origin_device", originDevice)
    put("hop_count", hopCount)
    // camelCase by contract:
    put("createdAt", createdAt)
    put("updatedAt", updatedAt)
}

/**
 * Inverse of [toSyncJson]. Tolerates missing keys. Requires `id`. `hopCount`
 * defaults to 0, `source` defaults to "web" (server default) when absent, and
 * createdAt/updatedAt fall back to now if absent.
 */
fun personFromSyncJson(o: JSONObject): PersonEntity {
    val now = nowIso()
    return PersonEntity(
        id = o.getString("id"),
        disasterId = o.strOrNull("disaster_id"),
        name = o.strOrNull("name"),
        status = o.strOrNull("status"),
        gender = o.strOrNull("gender"),
        age = o.intOrNull("age"),
        location = o.strOrNull("location"),
        lastSeenDate = o.strOrNull("last_seen_date"),
        clothes = o.strOrNull("clothes"),
        notes = o.strOrNull("notes"),
        contact = o.strOrNull("contact"),
        reporterName = o.strOrNull("reporter_name"),
        reporterRelation = o.strOrNull("reporter_relation"),
        reporterCountry = o.strOrNull("reporter_country"),
        reportedBy = o.strOrNull("reported_by"),
        source = o.strOrNull("source") ?: "web",
        provenance = o.strOrNull("provenance"),
        imagePath = o.strOrNull("image_path"),
        givenName = o.strOrNull("given_name"),
        familyName = o.strOrNull("family_name"),
        cedula = o.strOrNull("cedula"),
        sex = o.strOrNull("sex"),
        photoUrl = o.strOrNull("photo_url"),
        lastKnownLocation = o.strOrNull("last_known_location"),
        mergedInto = o.strOrNull("merged_into"),
        originDevice = o.strOrNull("origin_device"),
        hopCount = o.intOrNull("hop_count") ?: 0,
        createdAt = o.strOrNull("createdAt") ?: now,
        updatedAt = o.strOrNull("updatedAt") ?: now,
    )
}

/** Wrap a person as a mesh envelope; payload is the exact /sync JSON. */
fun PersonEntity.toEnvelope(): RecordEnvelope = RecordEnvelope(
    recordType = RecordEnvelope.TYPE_PERSON,
    recordId = id,
    originDevice = originDevice,
    hopCount = hopCount,
    createdAt = createdAt,
    updatedAt = updatedAt,
    payload = toSyncJson(),
)

/**
 * Parse an envelope's payload into a PersonEntity, overlaying the envelope's
 * provenance: keep the payload's originDevice when present, otherwise use the
 * envelope's; the envelope's hopCount is authoritative for transport.
 */
fun personEntityFromEnvelope(env: RecordEnvelope): PersonEntity {
    val base = personFromSyncJson(env.payload)
    return base.copy(
        originDevice = base.originDevice ?: env.originDevice,
        hopCount = env.hopCount,
    )
}

// --- ReportEntity <-> /sync JSON -------------------------------------------

fun ReportEntity.toSyncJson(): JSONObject = JSONObject().apply {
    put("id", id)
    putIfNotNull("person_id", personId)
    putIfNotNull("author_name", authorName)
    putIfNotNull("author_relation", authorRelation)
    putIfNotNull("status", status)
    putIfNotNull("note", note)
    putIfNotNull("location", location)
    putIfNotNull("source", source)
    putIfNotNull("origin_device", originDevice)
    put("createdAt", createdAt)
    put("updatedAt", updatedAt)
}

/** Inverse of [toSyncJson] for reports. Requires `id`. Reports have no hop_count. */
fun reportFromSyncJson(o: JSONObject): ReportEntity {
    val now = nowIso()
    return ReportEntity(
        id = o.getString("id"),
        personId = o.strOrNull("person_id"),
        authorName = o.strOrNull("author_name"),
        authorRelation = o.strOrNull("author_relation"),
        status = o.strOrNull("status"),
        note = o.strOrNull("note"),
        location = o.strOrNull("location"),
        source = o.strOrNull("source") ?: "web",
        originDevice = o.strOrNull("origin_device"),
        createdAt = o.strOrNull("createdAt") ?: now,
        updatedAt = o.strOrNull("updatedAt") ?: now,
    )
}

/** Wrap a report as a mesh envelope. Reports don't track hops, so hopCount is 0. */
fun ReportEntity.toEnvelope(): RecordEnvelope = RecordEnvelope(
    recordType = RecordEnvelope.TYPE_REPORT,
    recordId = id,
    originDevice = originDevice,
    hopCount = 0,
    createdAt = createdAt,
    updatedAt = updatedAt,
    payload = toSyncJson(),
)

/** Parse an envelope payload into a ReportEntity, overlaying envelope originDevice. */
fun reportEntityFromEnvelope(env: RecordEnvelope): ReportEntity {
    val base = reportFromSyncJson(env.payload)
    return base.copy(originDevice = base.originDevice ?: env.originDevice)
}
