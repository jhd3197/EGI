package com.egi.app.bridge

import android.content.Context
import android.net.Uri
import android.util.Log
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import com.egi.app.data.EgiDatabase
import com.egi.app.data.ReportEntity
import com.egi.app.data.isNewer
import com.egi.app.data.nowIso
import com.egi.app.data.personFromSyncJson
import com.egi.app.data.reportFromSyncJson
import com.egi.app.data.toSyncJson
import com.egi.app.data.MeshRepository
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.util.UUID

/**
 * Serves the PWA's same-origin API calls from the local Room database when the app
 * runs inside the Android WebView. Without this, calls like `fetch('/sync')` resolve
 * to `https://appassets.androidplatform.net/sync` and fail with
 * `ERR_NAME_NOT_RESOLVED` — there is no server at the asset-loader origin.
 *
 * Two halves:
 *  - **Reads** ([handle]) are wired into `MainActivity.shouldInterceptRequest`. GET
 *    requests for `/sync`, `/persons`, and `/persons/{id}/reports` are answered from
 *    Room; `/favicon.ico` returns 204 to silence noise. Anything else returns null so
 *    the [androidx.webkit.WebViewAssetLoader] serves the bundled PWA assets.
 *  - **Writes** ([postSync], [postReport]) are reached through the `window.EgiNative`
 *    JS bridge (a small fetch shim injected at document start routes POSTs here),
 *    because `shouldInterceptRequest` cannot read a request body.
 *
 * The JSON field casing matches the server contract exactly (snake_case except
 * `createdAt`/`updatedAt`) by reusing the shared mappers in `data/RecordMappers.kt`,
 * so a record round-trips PWA ⇄ Room ⇄ cloud without losing fields. Last-write-wins
 * (by `updated_at`) mirrors the server's `/sync` merge.
 *
 * Called on a WebView binder/background thread (never the UI thread), so the suspend
 * DAO calls are driven with [runBlocking]; that is safe off the main thread.
 */
class PwaApiBridge internal constructor(
    private val db: EgiDatabase,
    private val deviceId: String,
) {

    /** Production constructor: the shared file-backed DB + this install's device id. */
    constructor(context: Context) : this(
        EgiDatabase.get(context),
        MeshRepository.deviceFingerprint(context),
    )

    private val personDao get() = db.personDao()
    private val reportDao get() = db.reportDao()

    // ---- Reads (shouldInterceptRequest) -----------------------------------

    /**
     * Answer a PWA API GET from Room, or return null to let the asset loader serve
     * a bundled file. Never throws: any failure degrades to a 500 JSON body so the
     * PWA's `.catch()` paths handle it instead of the WebView surfacing a raw error.
     */
    fun handle(request: WebResourceRequest): WebResourceResponse? {
        val url = request.url
        val path = url.path ?: return null
        val method = (request.method ?: "GET").uppercase()
        return try {
            when {
                path == "/favicon.ico" -> noContent()
                method == "GET" && path == "/sync" -> json(syncGet(url.getQueryParameter("since")))
                method == "GET" && path == "/persons" -> json(
                    personsGet(url.getQueryParameter("disaster_id"), url.getQueryParameter("cedula")),
                )
                method == "GET" && reportPersonId(path) != null -> json(reportsGet(reportPersonId(path)!!))
                else -> null
            }
        } catch (e: Exception) {
            Log.e(TAG, "handle($method $path) failed", e)
            json(JSONObject().put("error", e.message ?: "internal").toString(), status = 500)
        }
    }

    /** GET /sync?since=ISO — person records changed since `since` (LWW newest first). */
    internal fun syncGet(since: String?): String {
        val cutoff = since?.takeIf { it.isNotBlank() } ?: "1970-01-01T00:00:00Z"
        val records = runBlocking { personDao.changedSince(cutoff) }
        val arr = JSONArray()
        for (p in records) if (p.mergedInto == null) arr.put(p.toSyncJson())
        return JSONObject().put("records", arr).toString()
    }

    /** GET /persons?disaster_id=&cedula= — full local registry (no server pagination). */
    internal fun personsGet(disasterIdParam: String?, cedulaParam: String?): String {
        val disasterId = disasterIdParam?.takeIf { it.isNotBlank() }
        val cedula = cedulaParam?.takeIf { it.isNotBlank() }?.let(::normalizeCedula)
        val all = runBlocking { personDao.all() }
        val arr = JSONArray()
        for (p in all) {
            if (p.mergedInto != null) continue
            if (disasterId != null && p.disasterId != null && p.disasterId != disasterId) continue
            if (cedula != null && normalizeCedula(p.cedula ?: "") != cedula) continue
            arr.put(p.toSyncJson())
        }
        // The native store holds the whole registry, so there is never a next page.
        return JSONObject()
            .put("records", arr)
            .put("next_cursor", JSONObject.NULL)
            .put("has_more", false)
            .toString()
    }

    /** GET /persons/{id}/reports — PFIF notes for a person, newest first. */
    private fun reportsGet(personId: String): String {
        val rows = runBlocking { reportDao.forPerson(personId) }
        val arr = JSONArray()
        for (r in rows) arr.put(r.toSyncJson())
        return JSONObject().put("records", arr).toString()
    }

    // ---- Writes (window.EgiNative bridge) ---------------------------------

    /**
     * POST /sync body `{"records":[…]}` — upsert person records, last-write-wins.
     * Returns `{"ok":true,"applied":n,"skipped":m}` (the PWA ignores the body).
     */
    fun postSync(body: String): String {
        return try {
            val records = JSONObject(body).optJSONArray("records") ?: JSONArray()
            var applied = 0
            var skipped = 0
            runBlocking {
                for (i in 0 until records.length()) {
                    val incoming = personFromSyncJson(records.getJSONObject(i))
                        .let { if (it.originDevice == null) it.copy(originDevice = deviceId) else it }
                    val existing = personDao.byId(incoming.id)
                    if (existing == null || isNewer(incoming.updatedAt, existing.updatedAt)) {
                        personDao.upsert(incoming)
                        applied++
                    } else {
                        skipped++
                    }
                }
            }
            Log.d(TAG, "postSync applied=$applied skipped=$skipped")
            JSONObject().put("ok", true).put("applied", applied).put("skipped", skipped).toString()
        } catch (e: Exception) {
            Log.e(TAG, "postSync failed", e)
            JSONObject().put("ok", false).put("error", e.message ?: "internal").toString()
        }
    }

    /**
     * POST /persons/{id}/reports body `{note,author_name,status,source,…}` — append a
     * note. The PWA omits `id` (the server generates one), so we mint a UUID when
     * absent and stamp the `person_id` from the path. Returns the stored record.
     */
    fun postReport(personId: String, body: String): String {
        return try {
            val o = JSONObject(body)
            if (!o.has("id") || o.isNull("id")) o.put("id", "r-" + UUID.randomUUID().toString())
            o.put("person_id", personId)
            val now = nowIso()
            if (!o.has("createdAt")) o.put("createdAt", now)
            if (!o.has("updatedAt")) o.put("updatedAt", now)
            val report: ReportEntity = reportFromSyncJson(o)
            runBlocking { reportDao.upsert(report) }
            Log.d(TAG, "postReport stored ${report.id} for $personId")
            report.toSyncJson().toString()
        } catch (e: Exception) {
            Log.e(TAG, "postReport failed", e)
            JSONObject().put("ok", false).put("error", e.message ?: "internal").toString()
        }
    }

    // ---- helpers ----------------------------------------------------------

    /** Extract `{id}` from `/persons/{id}/reports`, else null. */
    private fun reportPersonId(path: String): String? {
        val m = REPORTS_PATH.matchEntire(path) ?: return null
        return Uri.decode(m.groupValues[1])
    }

    /** Mirror of the PWA's normalizeCedula (frontend/src/lib/person.js). */
    private fun normalizeCedula(value: String): String =
        value.uppercase().replace(Regex("[.\\s-]"), "").replace(Regex("^[VE]"), "")

    private fun json(body: String, status: Int = 200): WebResourceResponse {
        val stream = ByteArrayInputStream(body.toByteArray(Charsets.UTF_8))
        val headers = mapOf(
            "Access-Control-Allow-Origin" to "*",
            "Cache-Control" to "no-store",
        )
        return WebResourceResponse("application/json", "utf-8", status, reasonFor(status), headers, stream)
    }

    private fun noContent(): WebResourceResponse =
        WebResourceResponse(
            "text/plain", "utf-8", 204, "No Content", emptyMap(),
            ByteArrayInputStream(ByteArray(0)),
        )

    private fun reasonFor(status: Int): String = when (status) {
        200 -> "OK"
        500 -> "Internal Server Error"
        else -> "OK"
    }

    companion object {
        private const val TAG = "EGI-PwaApi"
        private val REPORTS_PATH = Regex("^/persons/([^/]+)/reports/?$")

        /**
         * JS injected at document start (before the PWA's scripts run) so:
         *  - `window.isEgiAndroidWebView` lets the PWA know it is embedded.
         *  - `navigator.onLine` reads true: the native bridge IS the always-available
         *    backend, so the PWA should fetch/sync against it instead of short-
         *    circuiting its offline guards.
         *  - `window.fetch` is shimmed so POST `/sync` and POST `/persons/{id}/reports`
         *    route to the native bridge (shouldInterceptRequest cannot read POST
         *    bodies). All other requests fall through to the real fetch, which hits
         *    the native GET interceptor.
         */
        const val DOCUMENT_START_JS = """
(function () {
  try { window.isEgiAndroidWebView = true; } catch (e) {}
  try {
    Object.defineProperty(window.navigator, 'onLine', { get: function () { return true; }, configurable: true });
  } catch (e) {}
  try {
    var origFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
      try {
        var url = (typeof input === 'string') ? input : (input && input.url) || '';
        var method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
        var path = url.replace(/^https?:\/\/[^/]+/, '');
        if (window.EgiNative) {
          if (method === 'POST' && path.indexOf('/sync') === 0) {
            var sbody = (init && init.body) || '{}';
            var sres = window.EgiNative.postSync(typeof sbody === 'string' ? sbody : String(sbody));
            return Promise.resolve(new Response(sres, { status: 200, headers: { 'Content-Type': 'application/json' } }));
          }
          var m = path.match(/^\/persons\/([^/?]+)\/reports/);
          if (method === 'POST' && m) {
            var rbody = (init && init.body) || '{}';
            var rres = window.EgiNative.postReport(decodeURIComponent(m[1]), typeof rbody === 'string' ? rbody : String(rbody));
            return Promise.resolve(new Response(rres, { status: 200, headers: { 'Content-Type': 'application/json' } }));
          }
        }
      } catch (e) { console.error('[EGI] fetch shim error', e); }
      return origFetch(input, init);
    };
  } catch (e) { console.error('[EGI] fetch shim install failed', e); }
})();
"""
    }
}
