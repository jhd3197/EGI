package com.egi.app.data

import android.content.Context
import android.provider.Settings
import com.egi.app.mesh.BleConstants
import com.egi.app.mesh.IndexEntry
import com.egi.app.mesh.RecordEnvelope
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

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

    /**
     * How many incoming envelopes have been dropped for exceeding [BleConstants.MAX_HOPS].
     * Pure observability (plan-23 Phase 1) — surfaced in the mesh status and never used
     * for any decision. AtomicLong because merges run on the IO dispatcher.
     */
    private val droppedAtMaxHops = AtomicLong(0)

    /** Count of records rejected so far for travelling past the hop limit. */
    fun droppedAtMaxHopsCount(): Long = droppedAtMaxHops.get()

    /**
     * Person index rows still within the relay hop budget. A record whose stored
     * `hop_count` has reached [BleConstants.MAX_HOPS] is kept locally for the user
     * but excluded here so it is no longer advertised or served to peers — that is
     * what stops the mesh from circulating it forever (anti-circulation).
     */
    private suspend fun relayablePersonRows(): List<PersonIndexRow> =
        personDao.indexRows().filter { it.hopCount <= BleConstants.MAX_HOPS }

    /**
     * Index of local records (persons + reports), for advertising what this device
     * holds and how fresh. Persons past the hop limit are withheld from relay;
     * reports don't track hops, so their hopCount is 0.
     */
    suspend fun localRecordIndex(): List<IndexEntry> =
        (relayablePersonRows() + reportDao.indexRows())
            .map { IndexEntry(it.id, it.updatedAt, it.hopCount) }

    /** All relayable record ids (persons within the hop limit + reports) — feeds the advertiser's bloom filter. */
    suspend fun localRecordIds(): List<String> =
        relayablePersonRows().map { it.id } + reportDao.indexRows().map { it.id }

    /**
     * Resolve a set of ids to envelopes, skipping ids we don't hold. Each id maps
     * to a person envelope when a person exists, otherwise to a report envelope.
     */
    suspend fun envelopesFor(ids: List<String>): List<RecordEnvelope> =
        ids.mapNotNull { id ->
            personDao.byId(id)?.toEnvelope() ?: reportDao.byId(id)?.toEnvelope()
        }

    /**
     * Merge an incoming envelope using last-write-wins, dispatching on record type.
     *
     * Returns true if the local store changed (new record, or incoming is newer),
     * false otherwise. For persons, the stored copy's hopCount is the relayed value
     * (env.hopCount + 1) so the next hop sees an accurate distance. Reports don't
     * track hops, so their hopCount stays 0.
     */
    suspend fun mergeEnvelope(env: RecordEnvelope): Boolean =
        when (env.recordType) {
            RecordEnvelope.TYPE_REPORT -> mergeReportEnvelope(env)
            else -> mergePersonEnvelope(env)
        }

    private suspend fun mergePersonEnvelope(env: RecordEnvelope): Boolean {
        // Anti-circulation (plan-23 Phase 1): an envelope that has already travelled
        // past the hop ceiling is rejected outright — the data can't have changed by
        // relaying further, so storing it would only feed the loop. Records arriving
        // AT the limit are still stored (below) but won't be re-advertised.
        if (env.hopCount > BleConstants.MAX_HOPS) {
            droppedAtMaxHops.incrementAndGet()
            return false
        }
        val incoming = personEntityFromEnvelope(env)
        val existing = personDao.byId(incoming.id)
        val changed = existing == null || isNewer(incoming.updatedAt, existing.updatedAt)
        if (!changed) return false
        personDao.upsert(incoming.copy(hopCount = env.hopCount + 1))
        return true
    }

    private suspend fun mergeReportEnvelope(env: RecordEnvelope): Boolean {
        val incoming = reportEntityFromEnvelope(env)
        val existing = reportDao.byId(incoming.id)
        val changed = existing == null || isNewer(incoming.updatedAt, existing.updatedAt)
        if (!changed) return false
        reportDao.upsert(incoming)
        return true
    }

    /** Local persons changed since the last cloud sync — candidates for upload. */
    suspend fun pendingForCloud(since: String): List<PersonEntity> =
        personDao.changedSince(since)

    /** Local reports changed since the last cloud sync — candidates for upload. */
    suspend fun pendingReportsForCloud(since: String): List<ReportEntity> =
        reportDao.changedSince(since)

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

    /**
     * Apply report records pulled from the cloud, last-write-wins per record.
     * Returns the number actually applied (new or newer than the local copy).
     */
    suspend fun applyCloudReports(reports: List<JSONObject>): Int {
        var applied = 0
        for (o in reports) {
            val incoming = reportFromSyncJson(o)
            val existing = reportDao.byId(incoming.id)
            if (existing == null || isNewer(incoming.updatedAt, existing.updatedAt)) {
                reportDao.upsert(incoming)
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
