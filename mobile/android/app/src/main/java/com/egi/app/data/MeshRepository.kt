package com.egi.app.data

import android.content.Context
import android.provider.Settings
import com.egi.app.mesh.IndexEntry
import com.egi.app.mesh.RecordEnvelope
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID

/**
 * Data-layer facade used by the mesh orchestrator and the GATT callbacks. Wraps
 * the Room DAOs, applies last-write-wins merge rules, and bridges entities to the
 * [RecordEnvelope]s exchanged over BLE and the JSON exchanged with the cloud.
 *
 * `deviceId` is this install's stable fingerprint (see [deviceFingerprint]); it
 * is stamped as `origin_device` on records that originate locally.
 */
class MeshRepository(
    private val db: EgiDatabase,
    val deviceId: String,
) {

    private val personDao get() = db.personDao()
    private val reportDao get() = db.reportDao()
    private val syncLogDao get() = db.syncLogDao()

    /** Index of local persons, for advertising what this device holds and how fresh. */
    suspend fun localPersonIndex(): List<IndexEntry> =
        personDao.indexRows().map { IndexEntry(it.id, it.updatedAt, it.hopCount) }

    /** All local person ids — feeds the advertiser's bloom filter. */
    suspend fun localRecordIds(): List<String> =
        personDao.indexRows().map { it.id }

    /** Resolve a set of ids to person envelopes, skipping ids we don't hold. */
    suspend fun envelopesFor(ids: List<String>): List<RecordEnvelope> =
        ids.mapNotNull { id -> personDao.byId(id)?.toEnvelope() }

    /**
     * Merge an incoming person envelope using last-write-wins.
     *
     * Returns true if the local store changed (new record, or incoming is newer),
     * false otherwise. When applied, the stored copy's hopCount is the relayed
     * value (env.hopCount + 1) so the next hop sees an accurate distance.
     */
    suspend fun mergeEnvelope(env: RecordEnvelope): Boolean {
        val incoming = personEntityFromEnvelope(env)
        val existing = personDao.byId(incoming.id)
        val changed = existing == null || isNewer(incoming.updatedAt, existing.updatedAt)
        if (!changed) return false
        personDao.upsert(incoming.copy(hopCount = env.hopCount + 1))
        return true
    }

    /** Local records changed since the last cloud sync — candidates for upload. */
    suspend fun pendingForCloud(since: String): List<PersonEntity> =
        personDao.changedSince(since)

    /**
     * Apply person records pulled from the cloud, last-write-wins per record.
     * Returns the number actually applied (new or newer than the local copy).
     */
    suspend fun applyCloudRecords(records: List<JSONObject>): Int {
        var applied = 0
        for (o in records) {
            val incoming = personFromSyncJson(o)
            val existing = personDao.byId(incoming.id)
            if (existing == null || isNewer(incoming.updatedAt, existing.updatedAt)) {
                personDao.upsert(incoming)
                applied++
            }
        }
        return applied
    }

    /** Append a sync audit row. Never used for decisions — purely observability. */
    suspend fun logSync(direction: String, peer: String?, count: Int, detail: String?) {
        syncLogDao.insert(
            SyncLogEntity(
                direction = direction,
                peer = peer,
                originDevice = deviceId,
                recordCount = count,
                detail = detail,
                createdAt = nowIso(),
            ),
        )
    }

    companion object {

        /**
         * Derive a stable per-install device id.
         *
         * Privacy: ANDROID_ID is a device/app-scoped identifier that should not be
         * transmitted raw, so we never store or broadcast it. Instead we hash it
         * (SHA-256) and keep only the first 16 hex chars — enough entropy to keep
         * mesh provenance ids distinct, but not reversible to the original ANDROID_ID.
         * If ANDROID_ID is unavailable (rare, e.g. some emulators return null), we
         * fall back to a random UUID persisted in SharedPreferences so the id stays
         * stable across launches.
         */
        fun deviceFingerprint(context: Context): String {
            val prefs = context.getSharedPreferences("egi_mesh", Context.MODE_PRIVATE)
            prefs.getString("device_id", null)?.let { return it }

            val androidId = try {
                Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
            } catch (_: Exception) {
                null
            }

            val id = if (!androidId.isNullOrBlank()) {
                sha256Hex(androidId).take(16)
            } else {
                // No stable hardware id available — persist a random one instead.
                UUID.randomUUID().toString().replace("-", "").take(16)
            }

            prefs.edit().putString("device_id", id).apply()
            return id
        }

        private fun sha256Hex(input: String): String {
            val digest = MessageDigest.getInstance("SHA-256")
                .digest(input.toByteArray(Charsets.UTF_8))
            return digest.joinToString("") { "%02x".format(it) }
        }
    }
}
