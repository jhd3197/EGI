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
    private val animalDao get() = db.animalDao()
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
     * Animal index rows still within the relay hop budget. Animals track hops like
     * persons (plan-28), so a record that has reached [BleConstants.MAX_HOPS] is
     * kept locally but withheld from relay (anti-circulation).
     */
    private suspend fun relayableAnimalRows(): List<PersonIndexRow> =
        animalDao.indexRows().filter { it.hopCount <= BleConstants.MAX_HOPS }

    /**
     * Index of local records (persons + reports + animals), for advertising what
     * this device holds and how fresh. Persons and animals past the hop limit are
     * withheld from relay; reports don't track hops, so their hopCount is 0.
     *
     * `disabledCategories` is the set of content categories the user opted OUT of
     * relaying over the mesh (plan-24 Phase 5). Records of a disabled category are
     * excluded here so they never enter the advertised bloom — the device still
     * stores and shows them, it just doesn't carry them onward. Persons + their
     * reports are the `people` category; animals (plan-28) are gated independently
     * behind the `animals` category so a user can opt out of one without the other.
     */
    suspend fun localRecordIndex(disabledCategories: Set<String> = emptySet()): List<IndexEntry> {
        val rows = mutableListOf<PersonIndexRow>()
        if (CATEGORY_PEOPLE !in disabledCategories) {
            rows += relayablePersonRows()
            rows += reportDao.indexRows()
        }
        if (CATEGORY_ANIMALS !in disabledCategories) {
            rows += relayableAnimalRows()
        }
        return rows.map { IndexEntry(it.id, it.updatedAt, it.hopCount) }
    }

    /** All relayable record ids (persons + reports + animals within the hop limit) — feeds the advertiser's bloom filter. */
    suspend fun localRecordIds(disabledCategories: Set<String> = emptySet()): List<String> {
        val ids = mutableListOf<String>()
        if (CATEGORY_PEOPLE !in disabledCategories) {
            ids += relayablePersonRows().map { it.id }
            ids += reportDao.indexRows().map { it.id }
        }
        if (CATEGORY_ANIMALS !in disabledCategories) {
            ids += relayableAnimalRows().map { it.id }
        }
        return ids
    }

    /**
     * Resolve a set of ids to envelopes, skipping ids we don't hold. Each id maps
     * to a person envelope when a person exists, then a report, then an animal.
     */
    suspend fun envelopesFor(ids: List<String>): List<RecordEnvelope> =
        ids.mapNotNull { id ->
            personDao.byId(id)?.toEnvelope()
                ?: reportDao.byId(id)?.toEnvelope()
                ?: animalDao.byId(id)?.toEnvelope()
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
            RecordEnvelope.TYPE_ANIMAL -> mergeAnimalEnvelope(env)
            RecordEnvelope.TYPE_FIELD_REPORT -> mergeFieldReportEnvelope(env)
            else -> mergePersonEnvelope(env)
        }

    private suspend fun mergePersonEnvelope(env: RecordEnvelope): Boolean {
        // Plan-25 (Trust, Safety & Verification): the incoming payload carries the trust
        // signals author_role/org_id/location_id/signature plus the cloud-computed
        // trust_tier. A peer is NOT trusted to assert trust_tier — it is recomputed
        // authoritatively on the next gateway /sync — but offline we relay all five
        // fields verbatim so peers still see provenance. The DIRECT relay path keeps
        // them: envelopes are re-broadcast with their payload JSONObject untouched (see
        // EnvelopeCodec). LIMITATION: the Room PersonEntity mirror has no columns for
        // these fields (adding them needs a Room migration + exported schema, out of
        // scope here), so a record that is persisted and later re-emitted via
        // envelopesFor()/PersonEntity.toEnvelope() loses them. Storing them would
        // require either trust columns on PersonEntity or a generic passthrough column;
        // neither exists today, so we accept that gap and never break Room.
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

    /**
     * Handle an incoming SAR field-report envelope (plan-26 Phase 4) as a
     * relay-passthrough only. The payload is opaque, so the envelope still
     * re-broadcasts verbatim through the existing GATT/codec path (see
     * [com.egi.app.mesh.EnvelopeCodec]); making the dispatch explicit here only
     * keeps a field_report from being mis-routed into the person branch.
     *
     * Anti-circulation (plan-23 Phase 1): mirror [mergePersonEnvelope]'s hop
     * ceiling — an envelope already past [BleConstants.MAX_HOPS] is dropped and
     * counted, since relaying it further can't change the data.
     *
     * LIMITATION (mirrors the plan-25 partial-carry gap): there is no
     * `sar_field_reports` Room table yet (adding one needs a Room migration +
     * exported schema, out of scope here), so a field report is never persisted
     * locally. We always return false (the local store did not change) — the
     * DIRECT relay path is what carries it onward today.
     */
    private fun mergeFieldReportEnvelope(env: RecordEnvelope): Boolean {
        if (env.hopCount > BleConstants.MAX_HOPS) {
            droppedAtMaxHops.incrementAndGet()
            return false
        }
        // No Room store for field reports yet — relay-passthrough only.
        return false
    }

    /**
     * Merge an incoming animal envelope (plan-28) — the parallel track to persons.
     * Mirrors [mergePersonEnvelope]: anti-circulation hop-ceiling drop, last-write-wins
     * by `updated_at`, and the stored copy's hopCount is the relayed value
     * (env.hopCount + 1) so the next hop sees an accurate distance.
     */
    private suspend fun mergeAnimalEnvelope(env: RecordEnvelope): Boolean {
        if (env.hopCount > BleConstants.MAX_HOPS) {
            droppedAtMaxHops.incrementAndGet()
            return false
        }
        val incoming = animalEntityFromEnvelope(env)
        val existing = animalDao.byId(incoming.id)
        val changed = existing == null || isNewer(incoming.updatedAt, existing.updatedAt)
        if (!changed) return false
        animalDao.upsert(incoming.copy(hopCount = env.hopCount + 1))
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

    /**
     * Group local persons that share an *exact* high-confidence dedup key
     * (plan-27 Phase 6 — mesh-aware deduplication). Mirrors the server's
     * `duplicates.exact_clusters`: O(n) bucketing by [DedupNormalize.exactKey]
     * (canonical cédula, else canonical phone + normalized name). Persons whose
     * key is null are skipped, and a person already merged into another
     * (`merged_into` set) is skipped so a survivor isn't re-clustered with its own
     * absorbed duplicate. Returns only buckets of size >= 2, each a list of person
     * ids — the candidate set a future on-device review/merge UI would consume.
     *
     * This is detection only: it never writes. The authoritative merge decision is
     * still made server-side (or by a moderator) and arrives back as a
     * `merged_into` pointer that converges idempotently through the
     * timestamp-guarded last-write-wins in [applyCloudRecords]/[mergePersonEnvelope]
     * — that pointer is carried verbatim by [personFromSyncJson]/[PersonEntity.toSyncJson]
     * (the `merged_into` key), so the cloud's merge decision wins and reapplies
     * without duplicating work.
     */
    suspend fun localExactDuplicates(): List<List<String>> {
        val buckets = LinkedHashMap<String, MutableList<String>>()
        for (p in personDao.all()) {
            if (p.mergedInto != null) continue
            val key = DedupNormalize.exactKey(p.cedula, p.contact, fullName(p)) ?: continue
            buckets.getOrPut(key) { mutableListOf() }.add(p.id)
        }
        return buckets.values.filter { it.size >= 2 }.map { it.toList() }
    }

    /**
     * Record's full name for dedup, mirroring the server's `_full_name`: prefer
     * given + family, falling back to the single `name` field. Normalization is
     * applied later by [DedupNormalize.exactKey].
     */
    private fun fullName(p: PersonEntity): String? {
        val combined = listOfNotNull(p.givenName, p.familyName)
            .joinToString(" ").trim()
        return combined.ifEmpty { p.name }
    }

    /** Local persons changed since the last cloud sync — candidates for upload. */
    suspend fun pendingForCloud(since: String): List<PersonEntity> =
        personDao.changedSince(since)

    /** Local reports changed since the last cloud sync — candidates for upload. */
    suspend fun pendingReportsForCloud(since: String): List<ReportEntity> =
        reportDao.changedSince(since)

    /** Local animals changed since the last cloud sync — candidates for upload. */
    suspend fun pendingAnimalsForCloud(since: String): List<AnimalEntity> =
        animalDao.changedSince(since)

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

    /**
     * Apply animal records pulled from the cloud, last-write-wins per record.
     * Returns the number actually applied (new or newer than the local copy).
     */
    suspend fun applyCloudAnimals(animals: List<JSONObject>): Int {
        var applied = 0
        for (o in animals) {
            val incoming = animalFromSyncJson(o)
            val existing = animalDao.byId(incoming.id)
            if (existing == null || isNewer(incoming.updatedAt, existing.updatedAt)) {
                animalDao.upsert(incoming)
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

        /** The content category persons + their reports carry over the mesh. */
        const val CATEGORY_PEOPLE = "people"

        /** The content category animals (plan-28) carry — gated independently of people. */
        const val CATEGORY_ANIMALS = "animals"

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
