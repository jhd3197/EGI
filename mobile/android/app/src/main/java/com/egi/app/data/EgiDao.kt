package com.egi.app.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PersonDao {

    @Query("SELECT * FROM persons ORDER BY updated_at DESC")
    suspend fun all(): List<PersonEntity>

    @Query("SELECT * FROM persons WHERE id = :id")
    suspend fun byId(id: String): PersonEntity?

    /** Lightweight projection used to build the mesh index without loading full rows. */
    @Query("SELECT id, updated_at, hop_count FROM persons")
    suspend fun indexRows(): List<PersonIndexRow>

    /** Records changed locally since a cloud sync — candidates for upload. */
    @Query("SELECT * FROM persons WHERE updated_at > :since ORDER BY updated_at ASC")
    suspend fun changedSince(since: String): List<PersonEntity>

    /**
     * Last-write-wins upsert. REPLACE keeps the row with whichever copy the caller
     * decided is newer (callers compare `updated_at` before inserting).
     */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(person: PersonEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(persons: List<PersonEntity>)
}

@Dao
interface ReportDao {

    @Query("SELECT * FROM reports WHERE person_id = :personId ORDER BY created_at DESC")
    suspend fun forPerson(personId: String): List<ReportEntity>

    @Query("SELECT * FROM reports")
    suspend fun all(): List<ReportEntity>

    @Query("SELECT id, updated_at, 0 AS hop_count FROM reports")
    suspend fun indexRows(): List<PersonIndexRow>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(report: ReportEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(reports: List<ReportEntity>)
}

@Dao
interface SyncLogDao {

    @Insert
    suspend fun insert(entry: SyncLogEntity)

    @Query("SELECT * FROM sync_log ORDER BY created_at DESC LIMIT :limit")
    suspend fun recent(limit: Int = 50): List<SyncLogEntity>
}

/** Projection for index building. `hopCount` is 0 for reports (they don't track hops yet). */
data class PersonIndexRow(
    @androidx.room.ColumnInfo(name = "id") val id: String,
    @androidx.room.ColumnInfo(name = "updated_at") val updatedAt: String?,
    @androidx.room.ColumnInfo(name = "hop_count") val hopCount: Int,
)
