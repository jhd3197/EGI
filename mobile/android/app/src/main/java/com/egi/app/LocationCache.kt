package com.egi.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat

/**
 * Battery-aware last-known-position cache (plan-21 §3.4).
 *
 * The PWA's "my location" needs an *instant*, synchronous answer when the web UI
 * asks `window.EgiNative.getCurrentPosition()` on a binder thread — it must not
 * block on a GPS round-trip. So we keep a continuously-refreshed best fix in
 * [android.content.SharedPreferences] and serve that immediately.
 *
 * Lifecycle: [start] registers a single low-frequency location update stream
 * (NETWORK + GPS, min 30s / 50m) on the main looper; [stop] tears it down so we
 * don't drain the battery while backgrounded. MainActivity wires these to
 * `onResume`/`onPause`. Everything is permission- and exception-guarded — a
 * revoked location permission must never crash the host app.
 *
 * This is intentionally built on the platform [LocationManager] (no Google Play
 * Services FusedLocationProvider) to keep the APK dependency-free and installable
 * on de-Googled handsets, consistent with EGI's offline-first stance.
 */
object LocationCache {

    private const val TAG = "EGI-Location"
    private const val PREFS = "egi_location_cache"
    private const val KEY_LAT = "lat"
    private const val KEY_LON = "lon"
    private const val KEY_AT = "at"
    private const val KEY_ACC = "accuracy"

    /** ~30s between updates is plenty for "where am I"; trades freshness for battery. */
    private const val MIN_TIME_MS = 30_000L

    /** Skip updates under 50m of movement — same battery rationale. */
    private const val MIN_DISTANCE_M = 50f

    @Volatile
    private var listener: LocationListener? = null

    private fun hasPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED

    /**
     * Begin (or re-arm) the low-frequency location stream. Idempotent: calling it
     * twice keeps a single listener. No-op without permission. Must be called from
     * a thread with a Looper (MainActivity's onResume satisfies this; we also pass
     * the main looper explicitly so the callback lands on the UI thread).
     */
    @Synchronized
    fun start(context: Context) {
        if (listener != null) return
        if (!hasPermission(context)) {
            Log.i(TAG, "start skipped: no location permission")
            return
        }
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return
        val l = object : LocationListener {
            override fun onLocationChanged(location: Location) = save(context, location)

            // Empty overrides keep us compatible with older API levels that still
            // declare these as abstract/required on the interface.
            override fun onProviderEnabled(provider: String) {}
            override fun onProviderDisabled(provider: String) {}

            @Deprecated("Deprecated in API 29, still abstract on older levels")
            override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
        }
        listener = l
        try {
            val app = context.applicationContext
            // Register both providers when present so we get a fix indoors (NETWORK)
            // and an accurate one outdoors (GPS); seed the cache from any last-known
            // fix so the very first getCurrentPosition is non-empty.
            for (provider in listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)) {
                if (!lm.allProviders.contains(provider)) continue
                lm.requestLocationUpdates(provider, MIN_TIME_MS, MIN_DISTANCE_M, l, Looper.getMainLooper())
                lm.getLastKnownLocation(provider)?.let { save(app, it) }
            }
            Log.i(TAG, "location updates started")
        } catch (e: SecurityException) {
            // Permission revoked between the check and the call — degrade silently.
            Log.w(TAG, "start: permission revoked", e)
            listener = null
        } catch (e: Exception) {
            Log.w(TAG, "start failed", e)
            listener = null
        }
    }

    /** Stop the location stream to save battery (called from onPause). Idempotent. */
    @Synchronized
    fun stop(context: Context) {
        val l = listener ?: return
        listener = null
        try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
            lm?.removeUpdates(l)
            Log.i(TAG, "location updates stopped")
        } catch (e: Exception) {
            Log.w(TAG, "stop failed", e)
        }
    }

    private fun save(context: Context, location: Location) {
        try {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(KEY_LAT, location.latitude.toString())
                .putString(KEY_LON, location.longitude.toString())
                .putLong(KEY_AT, if (location.time > 0) location.time else System.currentTimeMillis())
                .putFloat(KEY_ACC, if (location.hasAccuracy()) location.accuracy else 0f)
                .apply()
        } catch (e: Exception) {
            Log.w(TAG, "save failed", e)
        }
    }

    /**
     * Return the best available fix as a JSON string
     * `{"lat":..,"lon":..,"at":<epochMillis>,"accuracy":..}`, or `""` when there is
     * no cached fix, no last-known fix, or no permission. Never throws.
     *
     * Order: cached SharedPreferences fix first (instant), then a direct
     * [LocationManager.getLastKnownLocation] over GPS then NETWORK as a fallback.
     */
    fun currentPositionJson(context: Context): String {
        if (!hasPermission(context)) return ""
        try {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val lat = prefs.getString(KEY_LAT, null)
            val lon = prefs.getString(KEY_LON, null)
            if (lat != null && lon != null) {
                val at = prefs.getLong(KEY_AT, System.currentTimeMillis())
                val acc = prefs.getFloat(KEY_ACC, 0f)
                return """{"lat":$lat,"lon":$lon,"at":$at,"accuracy":$acc}"""
            }
            // Cache empty — try a direct last-known read before giving up.
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
                ?: return ""
            for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
                if (!lm.allProviders.contains(provider)) continue
                val loc = lm.getLastKnownLocation(provider) ?: continue
                save(context, loc)
                val at = if (loc.time > 0) loc.time else System.currentTimeMillis()
                val acc = if (loc.hasAccuracy()) loc.accuracy else 0f
                return """{"lat":${loc.latitude},"lon":${loc.longitude},"at":$at,"accuracy":$acc}"""
            }
            return ""
        } catch (e: SecurityException) {
            Log.w(TAG, "currentPositionJson: permission revoked", e)
            return ""
        } catch (e: Exception) {
            Log.w(TAG, "currentPositionJson failed", e)
            return ""
        }
    }
}
