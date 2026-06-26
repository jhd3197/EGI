package com.egi.app.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Local mirror of the server `sync_log` table. Records every mesh/cloud exchange
 * so the UI can show "last synced with N peers" and so duty-cycling can back off.
 *
 * `direction` is one of: "mesh_in", "mesh_out", "cloud_in", "cloud_out".
 */
@Entity(tableName = "sync_log")
data class SyncLogEntity(
    @PrimaryKey(autoGenerate = true) @ColumnInfo(name = "id") val id: Long = 0,
    @ColumnInfo(name = "direction") val direction: String,
    @ColumnInfo(name = "peer") val peer: String? = null,
    @ColumnInfo(name = "origin_device") val originDevice: String? = null,
    @ColumnInfo(name = "record_count") val recordCount: Int = 0,
    @ColumnInfo(name = "detail") val detail: String? = null,
    @ColumnInfo(name = "created_at") val createdAt: String,
)
