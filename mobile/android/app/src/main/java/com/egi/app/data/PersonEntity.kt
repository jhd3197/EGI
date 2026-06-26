package com.egi.app.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Local mirror of the server `persons` table (see `server/db.py`). Column names
 * are kept snake_case to match the server schema 1:1 so mapping to the `/sync`
 * payload stays mechanical. The mesh provenance columns `origin_device` and
 * `hop_count` mirror the same additive columns added server-side.
 */
@Entity(tableName = "persons")
data class PersonEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "disaster_id") val disasterId: String? = null,
    @ColumnInfo(name = "name") val name: String? = null,
    @ColumnInfo(name = "status") val status: String? = null,
    @ColumnInfo(name = "gender") val gender: String? = null,
    @ColumnInfo(name = "age") val age: Int? = null,
    @ColumnInfo(name = "location") val location: String? = null,
    @ColumnInfo(name = "last_seen_date") val lastSeenDate: String? = null,
    @ColumnInfo(name = "clothes") val clothes: String? = null,
    @ColumnInfo(name = "notes") val notes: String? = null,
    @ColumnInfo(name = "contact") val contact: String? = null,
    @ColumnInfo(name = "reporter_name") val reporterName: String? = null,
    @ColumnInfo(name = "reporter_relation") val reporterRelation: String? = null,
    @ColumnInfo(name = "reporter_country") val reporterCountry: String? = null,
    @ColumnInfo(name = "reported_by") val reportedBy: String? = null,
    @ColumnInfo(name = "source") val source: String? = "mesh",
    @ColumnInfo(name = "provenance") val provenance: String? = null,
    @ColumnInfo(name = "image_path") val imagePath: String? = null,
    @ColumnInfo(name = "given_name") val givenName: String? = null,
    @ColumnInfo(name = "family_name") val familyName: String? = null,
    @ColumnInfo(name = "cedula") val cedula: String? = null,
    @ColumnInfo(name = "sex") val sex: String? = null,
    @ColumnInfo(name = "photo_url") val photoUrl: String? = null,
    @ColumnInfo(name = "last_known_location") val lastKnownLocation: String? = null,
    // Mesh provenance.
    @ColumnInfo(name = "origin_device") val originDevice: String? = null,
    @ColumnInfo(name = "hop_count") val hopCount: Int = 0,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)
