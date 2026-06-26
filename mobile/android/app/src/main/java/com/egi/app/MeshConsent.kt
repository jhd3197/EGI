package com.egi.app

import android.content.Context

/**
 * Stores whether the user has consented to mesh sync. Mesh activation broadcasts
 * emergency records to nearby devices over Bluetooth, so it must stay gated behind
 * an explicit, informed opt-in (see the `mesh_privacy_warning` dialog). The flag
 * lives in the same `egi_mesh` SharedPreferences file as the device fingerprint.
 */
object MeshConsent {

    private const val PREFS = "egi_mesh"
    private const val KEY_CONSENT = "mesh_consent"

    /** True once the user has accepted the privacy warning. Defaults to false. */
    fun hasConsented(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_CONSENT, false)

    /** Persist the user's consent decision. */
    fun setConsented(context: Context, value: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_CONSENT, value)
            .apply()
    }
}
