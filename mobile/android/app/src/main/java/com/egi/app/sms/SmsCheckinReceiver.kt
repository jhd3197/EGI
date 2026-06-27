package com.egi.app.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import com.egi.app.BluetoothMeshManager
import com.egi.app.data.EgiDatabase
import com.egi.app.data.MeshRepository
import com.egi.app.data.PersonEntity
import com.egi.app.data.ReportEntity
import com.egi.app.data.nowIso
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.UUID

/**
 * SMS fallback (Phase 5): receives inbound texts and, when one matches the EGI
 * check-in format, creates a local `safe` self check-in entirely offline —
 * mirroring the server's `POST /sms/webhook` ([server/modules/sms.py]) which
 * stores the same record with source='sms', status='safe', reviewed=0 AND a
 * companion report ("note") so the check-in shows up on the person's timeline.
 *
 * Trust: these records are UNTRUSTED. [PersonEntity] has no `reviewed` column on
 * the device, so the trust gate is applied server-side: when this row syncs to
 * the cloud it lands as source='sms' and the server keeps it reviewed=0
 * (moderator-only) until a moderator approves it. The on-device store simply
 * mirrors all records; it does not itself filter by trust.
 *
 * Resilience: parsing/DB work is wrapped in try/catch and the receiver never
 * crashes — a malformed text is just ignored. The report upsert has its own
 * guard so a report failure can never lose the (already stored) person.
 */
class SmsCheckinReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        try {
            // Concatenate all PDUs so multipart (long) messages reassemble into one body.
            val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
            if (messages.isEmpty()) return
            val body = messages.joinToString("") { it.displayMessageBody ?: it.messageBody ?: "" }
            val sender = messages.firstOrNull()?.displayOriginatingAddress

            val fields = SmsCheckin.parse(body) ?: return

            // Keep the receiver process alive while the DB write runs off the main thread.
            val pending = goAsync()
            val appContext = context.applicationContext
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val records = buildCheckinRecords(
                        fields = fields,
                        deviceId = MeshRepository.deviceFingerprint(appContext),
                        sender = sender,
                        body = body,
                    )
                    val db = EgiDatabase.get(appContext)
                    db.personDao().upsert(records.person)
                    Log.i(TAG, "Stored SMS check-in ${records.person.id} (cedula=${fields.cedula})")
                    // The person is already persisted; a report failure must not lose it.
                    try {
                        db.reportDao().upsert(records.report)
                        Log.i(TAG, "Stored SMS check-in report ${records.report.id}")
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to store SMS check-in report", e)
                    }
                    // Best-effort: nudge a cloud reconcile so this check-in uploads as
                    // soon as we have connectivity. If the mesh singleton isn't reachable
                    // from here, the record is still picked up by
                    // MeshRepository.pendingForCloud()/pendingReportsForCloud() on the
                    // next sync round, so this is purely an optimization.
                    runCatching { BluetoothMeshManager.getInstance(appContext).syncMeshRound() }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to store SMS check-in", e)
                } finally {
                    pending.finish()
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error handling inbound SMS", e)
        }
    }

    companion object {
        private const val TAG = "SmsCheckinReceiver"
    }
}

/** A parsed SMS check-in materialized as the two local rows it creates. */
data class CheckinRecords(
    val person: PersonEntity,
    val report: ReportEntity,
)

/**
 * Pure builder (no Android/DB deps beyond the entity types) that turns parsed
 * [SmsCheckin.CheckinFields] into the person + companion report a check-in
 * creates. Factored out of the receiver so the record-creation path is unit/
 * instrumented-testable without faking an SMS PDU intent.
 *
 * Mirrors the server check-in→report behavior: the person is `safe`/source='sms'
 * and the report is a text-only note ("Auto check-in vía SMS" + location) linked
 * back to the person by `person_id`, also source='sms'.
 */
fun buildCheckinRecords(
    fields: SmsCheckin.CheckinFields,
    deviceId: String,
    sender: String?,
    body: String,
    now: String = nowIso(),
): CheckinRecords {
    val personId = "egi-sms-${UUID.randomUUID().toString().replace("-", "").take(8)}"
    val location = fields.location.ifBlank { null }
    val displayName = fields.name.ifBlank { "Check-in SMS" }

    val person = PersonEntity(
        id = personId,
        name = displayName,
        status = "safe",
        location = location,
        lastKnownLocation = location,
        cedula = fields.cedula,
        source = "sms",
        // Raw text + sender digits for audit (light privacy: digits/+ only).
        provenance = buildProvenance(sender, body),
        reporterName = displayName,
        originDevice = deviceId,
        createdAt = now,
        updatedAt = now,
    )

    val note = buildString {
        append("Auto check-in vía SMS")
        if (!location.isNullOrBlank()) append(" — $location")
    }
    val report = ReportEntity(
        id = "egi-sms-rpt-${UUID.randomUUID().toString().replace("-", "").take(8)}",
        personId = personId,
        authorName = fields.name.ifBlank { null },
        status = "safe",
        note = note,
        location = location,
        source = "sms",
        originDevice = deviceId,
        createdAt = now,
        updatedAt = now,
    )

    return CheckinRecords(person, report)
}

private fun buildProvenance(sender: String?, body: String): String {
    val safeSender = sender?.replace(Regex("[^0-9+]"), "")?.takeIf { it.isNotEmpty() } ?: "unknown"
    return "SMS check-in from $safeSender: ${body.trim().take(160)}"
}
