package com.egi.app.net

import com.egi.app.data.PersonEntity
import com.egi.app.data.ReportEntity
import com.egi.app.data.toSyncJson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

/**
 * OkHttp client for the FastAPI `/sync` endpoint.
 *
 * The WebView talks to the API same-origin, but a native client needs an absolute
 * URL. The orchestrator passes [baseUrl] (e.g. from a stored setting); the default
 * for the Android emulator reaching a host-machine server is "http://10.0.2.2:3000".
 *
 * All network calls run on [Dispatchers.IO].
 */
class CloudSyncClient(
    baseUrl: String,
    private val client: OkHttpClient = OkHttpClient(),
) {

    // Normalize so we can always append "sync" cleanly regardless of trailing slash.
    private val root: String = baseUrl.trimEnd('/')

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    /**
     * POST persons (and optional reports) to `/sync`.
     * Body: `{"records": [...persons], "reports": [...reports]}`.
     * Returns the server's `saved` count.
     */
    suspend fun upload(
        persons: List<PersonEntity>,
        reports: List<ReportEntity> = emptyList(),
    ): Int = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            put("records", JSONArray().apply { persons.forEach { put(it.toSyncJson()) } })
            put("reports", JSONArray().apply { reports.forEach { put(it.toSyncJson()) } })
        }

        val request = Request.Builder()
            .url("$root/sync")
            .post(body.toString().toRequestBody(jsonMedia))
            .build()

        client.newCall(request).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                throw IOException("POST /sync failed: HTTP ${resp.code} $text")
            }
            JSONObject(text).optInt("saved", 0)
        }
    }

    /**
     * GET `/sync?since=…` and return both `records` (persons) and `reports` as
     * lists of JSONObjects. `reports` defaults to empty when the server omits it,
     * keeping backward compatibility with older servers. Callers map them via
     * personFromSyncJson / reportFromSyncJson.
     */
    suspend fun download(since: String): CloudPull = withContext(Dispatchers.IO) {
        val url = "$root/sync?since=${encode(since)}"
        val request = Request.Builder().url(url).get().build()

        client.newCall(request).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                throw IOException("GET /sync failed: HTTP ${resp.code} $text")
            }
            val obj = JSONObject(text)
            CloudPull(
                persons = obj.optJSONArray("records").toJsonObjectList(),
                reports = obj.optJSONArray("reports").toJsonObjectList(),
            )
        }
    }

    private fun JSONArray?.toJsonObjectList(): List<JSONObject> {
        val arr = this ?: JSONArray()
        return (0 until arr.length()).map { arr.getJSONObject(it) }
    }

    private fun encode(value: String): String =
        java.net.URLEncoder.encode(value, "UTF-8")

    /** Result of a `/sync` download: persons (`records`) and `reports`. */
    data class CloudPull(
        val persons: List<JSONObject>,
        val reports: List<JSONObject>,
    )
}
