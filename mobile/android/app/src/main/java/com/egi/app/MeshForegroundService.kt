package com.egi.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat

/**
 * Keeps the EGI mesh alive while the app is backgrounded.
 *
 * A bare [BluetoothMeshManager] started from the Activity would be torn down (or
 * heavily throttled) once the app leaves the foreground. Running the mesh inside a
 * foreground service with an ongoing notification lets relaying continue so records
 * keep propagating to nearby devices during a disaster.
 *
 * The service drives the SAME singleton manager the WebView bridge uses
 * ([BluetoothMeshManager.getInstance]), so there is exactly one GATT server / duty
 * cycle regardless of who started it. A STOP notification action (and onDestroy)
 * stops the mesh and removes the foreground notification.
 *
 * Permissions/manifest: declared with `foregroundServiceType="connectedDevice"`;
 * needs FOREGROUND_SERVICE, FOREGROUND_SERVICE_CONNECTED_DEVICE (API 34+), and
 * POST_NOTIFICATIONS (API 33+, requested by MainActivity).
 */
class MeshForegroundService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopMesh()
                return START_NOT_STICKY
            }
            ACTION_SYNC -> {
                // Manual "Sincronizar ahora" from the notification: nudge a sync round
                // (no foreground transition needed — the service is already running).
                BluetoothMeshManager.getInstance(this).syncMeshRound()
                return START_STICKY
            }
        }
        val manager = BluetoothMeshManager.getInstance(this)
        // Post the ongoing notification and enter the foreground first, then start
        // the mesh. On API 34+ the connectedDevice type must be supplied here.
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(this, manager.notificationStatus()),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            } else {
                0
            },
        )
        // Repaint the notification live as mesh status changes (peers, gateway, queue).
        manager.onStatusChanged = { refreshNotification() }
        manager.start()
        // Re-deliver so a killed service resumes the mesh when resources free up.
        return START_STICKY
    }

    /** Rebuild the ongoing notification from the latest mesh status snapshot. */
    private fun refreshNotification() {
        val status = BluetoothMeshManager.getInstance(this).notificationStatus()
        getSystemService(NotificationManager::class.java)
            ?.notify(NOTIFICATION_ID, buildNotification(this, status))
    }

    private fun stopMesh() {
        val manager = BluetoothMeshManager.getInstance(this)
        manager.onStatusChanged = null
        manager.stop()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        val manager = BluetoothMeshManager.getInstance(this)
        manager.onStatusChanged = null
        manager.stop()
        super.onDestroy()
    }

    companion object {
        /** NotificationChannel id (also the SharedPreferences mesh file name, by spec). */
        const val CHANNEL_ID = "egi_mesh"

        /** Notification action that stops the mesh + service. */
        const val ACTION_STOP = "com.egi.app.action.STOP_MESH"

        /** Notification action that triggers an immediate sync round ("Sincronizar ahora"). */
        const val ACTION_SYNC = "com.egi.app.action.SYNC_MESH"

        private const val NOTIFICATION_ID = 4711

        /**
         * Build the ongoing mesh notification, reflecting the current mesh [status]
         * (plan-23 Phase 4): peer + queued counts, a gateway badge when this device is
         * a gateway or one is nearby, and the online/offline state — the same signals
         * the PWA TopBar shows. A glance tells the user whether they are a gateway,
         * whether a gateway is nearby, and whether records are waiting to upload.
         *
         * Extracted to the companion (taking a [Context]) so it has no hidden
         * dependency on Service lifecycle state and can be exercised by an instrumented
         * test with an application context. A null [status] renders the neutral
         * "starting" notification used before the manager has any state.
         */
        fun buildNotification(
            context: Context,
            status: BluetoothMeshManager.NotificationStatus? = null,
        ): Notification {
            ensureChannel(context)

            val openIntent = PendingIntent.getActivity(
                context,
                0,
                Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_IMMUTABLE,
            )
            val stopIntent = PendingIntent.getService(
                context,
                1,
                Intent(context, MeshForegroundService::class.java).apply { action = ACTION_STOP },
                PendingIntent.FLAG_IMMUTABLE,
            )
            val syncIntent = PendingIntent.getService(
                context,
                2,
                Intent(context, MeshForegroundService::class.java).apply { action = ACTION_SYNC },
                PendingIntent.FLAG_IMMUTABLE,
            )

            val title = notificationTitle(context, status)
            val text = notificationText(context, status)

            return NotificationCompat.Builder(context, CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(NotificationCompat.BigTextStyle().bigText(text))
                .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(openIntent)
                .addAction(0, context.getString(R.string.mesh_service_sync), syncIntent)
                .addAction(0, context.getString(R.string.mesh_service_stop), stopIntent)
                .build()
        }

        /** Title line: the gateway state is the headline when relevant. */
        private fun notificationTitle(
            context: Context,
            status: BluetoothMeshManager.NotificationStatus?,
        ): String = when {
            status?.isGateway == true -> context.getString(R.string.mesh_service_title) +
                " · " + context.getString(R.string.mesh_notif_online)
            else -> context.getString(R.string.mesh_service_title)
        }

        /**
         * Body line, prioritised: gateway-self > gateway-nearby > peers/queue summary,
         * with an online/offline suffix. Falls back to the static "starting" text.
         */
        private fun notificationText(
            context: Context,
            status: BluetoothMeshManager.NotificationStatus?,
        ): String {
            if (status == null || !status.running) {
                return context.getString(R.string.mesh_notif_starting)
            }
            val lead = when {
                status.isGateway -> context.getString(R.string.mesh_notif_gateway_self)
                status.gatewayNearby -> context.getString(R.string.mesh_notif_gateway_near)
                else -> context.getString(R.string.mesh_notif_peers, status.peers, status.queued)
            }
            val conn = if (status.online) {
                context.getString(R.string.mesh_notif_online)
            } else {
                context.getString(R.string.mesh_notif_offline)
            }
            return "$lead\n$conn"
        }

        /** Register the (low-importance) mesh notification channel. Idempotent. */
        fun ensureChannel(context: Context) {
            // minSdk is 26 (O), so NotificationChannel is always available.
            val channel = NotificationChannel(
                CHANNEL_ID,
                context.getString(R.string.mesh_service_channel),
                NotificationManager.IMPORTANCE_LOW,
            )
            context.getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }

        /** Start the mesh foreground service (caller must hold mesh consent + perms). */
        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, MeshForegroundService::class.java),
            )
        }

        /** Ask the service to stop the mesh and leave the foreground. */
        fun stop(context: Context) {
            context.startService(
                Intent(context, MeshForegroundService::class.java).apply { action = ACTION_STOP },
            )
        }
    }
}
