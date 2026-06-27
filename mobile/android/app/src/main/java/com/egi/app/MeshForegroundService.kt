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
        if (intent?.action == ACTION_STOP) {
            stopMesh()
            return START_NOT_STICKY
        }
        // Post the ongoing notification and enter the foreground first, then start
        // the mesh. On API 34+ the connectedDevice type must be supplied here.
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(this),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            } else {
                0
            },
        )
        BluetoothMeshManager.getInstance(this).start()
        // Re-deliver so a killed service resumes the mesh when resources free up.
        return START_STICKY
    }

    private fun stopMesh() {
        BluetoothMeshManager.getInstance(this).stop()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        BluetoothMeshManager.getInstance(this).stop()
        super.onDestroy()
    }

    companion object {
        /** NotificationChannel id (also the SharedPreferences mesh file name, by spec). */
        const val CHANNEL_ID = "egi_mesh"

        /** Notification action that stops the mesh + service. */
        const val ACTION_STOP = "com.egi.app.action.STOP_MESH"

        private const val NOTIFICATION_ID = 4711

        /**
         * Build the ongoing mesh notification. Extracted to the companion (taking a
         * [Context]) so it has no hidden dependency on Service lifecycle state and can
         * be exercised by an instrumented test with an application context.
         */
        fun buildNotification(context: Context): Notification {
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

            return NotificationCompat.Builder(context, CHANNEL_ID)
                .setContentTitle(context.getString(R.string.mesh_service_title))
                .setContentText(context.getString(R.string.mesh_service_text))
                .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
                .setOngoing(true)
                .setContentIntent(openIntent)
                .addAction(0, context.getString(R.string.mesh_service_stop), stopIntent)
                .build()
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
