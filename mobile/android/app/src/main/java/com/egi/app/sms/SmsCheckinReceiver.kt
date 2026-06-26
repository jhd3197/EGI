package com.egi.app.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import com.egi.app.data.EgiDatabase
import com.egi.app.data.MeshRepository
import com.egi.app.data.PersonEntity
import com.egi.app.data.nowIso
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.UUID

/**
 * SMS fallback (Phase 7): receives inbound texts and, when one matches the EGI
 * check-in format, creates a local `safe` self check-in entirely offline —
 * mirroring the server's `POST /sms/webhook` ([server/modules/sms.py]) which
 * stores the same record with source='sms', status='safe', reviewed=0.
 *
 * Trust: these records are UNTRUSTED. [PersonEntity] has no `reviewed` column on
 * the device, so the trust gate is applied server-side: when this row syncs to
 * the cloud it lands as source='sms' and the server keeps it reviewed=0
 * (moderator-only) until a moderator approves it. The on-device store simply
 * mirrors all records; it does not itself filter by trust.
 *
 * Resilience: parsing/DB work is wrapped in try/catch and the receiver never
 * crashes — a malformed text is just ignored.
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
                    val now = nowIso()
                    val person = PersonEntity(
                        id = "egi-sms-${UUID.randomUUID().toString().replace("-", "").take(8)}",
                        name = fields.name.ifBlank { "Check-in SMS" },
                        status = "safe",
                        location = fields.location.ifBlank { null },
                        lastKnownLocation = fields.location.ifBlank { null },
                        cedula = fields.cedula,
                        source = "sms",
                        // Raw text + sender digits for audit (light privacy: digits/+ only).
                        provenance = buildProvenance(sender, body),
                        reporterName = fields.name.ifBlank { "Check-in SMS" },
                        originDevice = MeshRepository.deviceFingerprint(appContext),
                        createdAt = now,
                        updatedAt = now,
                    )
                    EgiDatabase.get(appContext).personDao().upsert(person)
                    Log.i(TAG, "Stored SMS check-in ${person.id} (cedula=${fields.cedula})")
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

    private fun buildProvenance(sender: String?, body: String): String {
        val safeSender = sender?.replace(Regex("[^0-9+]"), "")?.takeIf { it.isNotEmpty() } ?: "unknown"
        return "SMS check-in from $safeSender: ${body.trim().take(160)}"
    }

    companion object {
        private const val TAG = "SmsCheckinReceiver"
    }
}
