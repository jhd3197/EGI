package com.egi.app.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Local mirror of the server `reports` table — a PFIF "note" attached to a person.
 * Carries `origin_device` for the same mesh provenance reason as [PersonEntity].
 */
@Entity(tableName = "reports")
data class ReportEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "person_id") val personId: String? = null,
    @ColumnInfo(name = "author_name") val authorName: String? = null,
    @ColumnInfo(name = "author_relation") val authorRelation: String? = null,
    @ColumnInfo(name = "status") val status: String? = null,
    @ColumnInfo(name = "note") val note: String? = null,
    @ColumnInfo(name = "location") val location: String? = null,
    @ColumnInfo(name = "source") val source: String? = "mesh",
    @ColumnInfo(name = "origin_device") val originDevice: String? = null,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)
