package com.egi.app

import android.app.Notification
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Focused instrumented test for [MeshForegroundService]'s notification logic.
 *
 * Driving the full service lifecycle (startForeground) from a test is heavy and
 * flaky — it needs notification permission and a real foreground-service slot — so
 * instead we test the seam the service depends on: the companion notification
 * builder (extracted to take a [Context]). This proves the ongoing mesh notification
 * is constructed correctly and the channel registers without crashing, which is the
 * part most likely to regress. The start/stop intent contract is also asserted.
 */
@RunWith(AndroidJUnit4::class)
class MeshForegroundServiceTest {

    private val context: Context
        get() = ApplicationProvider.getApplicationContext()

    @Test
    fun buildsOngoingForegroundNotification() {
        val notification = MeshForegroundService.buildNotification(context)

        assertNotNull(notification)
        // The mesh notification must be ongoing (non-dismissable) so the service
        // stays visible while relaying in the background.
        assertTrue(
            "notification should carry FLAG_ONGOING_EVENT",
            (notification.flags and Notification.FLAG_ONGOING_EVENT) != 0,
        )
        assertEquals(MeshForegroundService.CHANNEL_ID, notification.channelId)
    }

    @Test
    fun ensureChannelIsIdempotent() {
        // Calling twice must not throw (createNotificationChannel is upsert-like).
        MeshForegroundService.ensureChannel(context)
        MeshForegroundService.ensureChannel(context)
    }

    @Test
    fun stopActionConstantIsStable() {
        // The notification's stop action and MeshForegroundService.stop() rely on this
        // exact action string; pin it so a rename can't silently break the stop path.
        assertEquals("com.egi.app.action.STOP_MESH", MeshForegroundService.ACTION_STOP)
    }
}
