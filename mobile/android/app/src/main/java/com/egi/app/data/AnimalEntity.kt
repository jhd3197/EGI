package com.egi.app.data

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Local mirror of the server `animals` table (plan-28 Missing Animals). Column
 * names are kept snake_case to match the server schema 1:1 so mapping to the
 * `/sync` payload stays mechanical. Animals ride the mesh as a PARALLEL track to
 * persons, tagged `record_type="animal"`, and — like persons — carry the mesh
 * provenance columns `origin_device`/`hop_count` so they relay across the human
 * chain with an accurate hop distance.
 */
@Entity(tableName = "animals")
data class AnimalEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "disaster_id") val disasterId: String? = null,
    @ColumnInfo(name = "status") val status: String? = null,
    @ColumnInfo(name = "species") val species: String? = null,
    @ColumnInfo(name = "breed") val breed: String? = null,
    @ColumnInfo(name = "name") val name: String? = null,
    @ColumnInfo(name = "sex") val sex: String? = null,
    @ColumnInfo(name = "size") val size: String? = null,
    @ColumnInfo(name = "color") val color: String? = null,
    @ColumnInfo(name = "distinguishing_marks") val distinguishingMarks: String? = null,
    @ColumnInfo(name = "microchip") val microchip: String? = null,
    @ColumnInfo(name = "photo_url") val photoUrl: String? = null,
    // Raw JSON array string of photo URLs (decoded by the consumer).
    @ColumnInfo(name = "photos") val photos: String? = null,
    @ColumnInfo(name = "last_seen_location") val lastSeenLocation: String? = null,
    @ColumnInfo(name = "last_seen_at") val lastSeenAt: String? = null,
    @ColumnInfo(name = "lat") val lat: Double? = null,
    @ColumnInfo(name = "lon") val lon: Double? = null,
    @ColumnInfo(name = "owner_name") val ownerName: String? = null,
    @ColumnInfo(name = "owner_contact") val ownerContact: String? = null,
    @ColumnInfo(name = "reporter_id") val reporterId: String? = null,
    @ColumnInfo(name = "reporter_name") val reporterName: String? = null,
    @ColumnInfo(name = "notes") val notes: String? = null,
    @ColumnInfo(name = "source") val source: String? = "mesh",
    @ColumnInfo(name = "reviewed") val reviewed: Int? = null,
    @ColumnInfo(name = "shelter_id") val shelterId: String? = null,
    @ColumnInfo(name = "intake_at") val intakeAt: String? = null,
    @ColumnInfo(name = "condition_note") val conditionNote: String? = null,
    // Points at the surviving record's id when this row was merged into another.
    @ColumnInfo(name = "merged_into") val mergedInto: String? = null,
    // Mesh provenance.
    @ColumnInfo(name = "origin_device") val originDevice: String? = null,
    @ColumnInfo(name = "hop_count") val hopCount: Int = 0,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)
