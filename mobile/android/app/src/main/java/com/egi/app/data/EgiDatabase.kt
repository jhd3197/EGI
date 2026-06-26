package com.egi.app.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * The on-device store. Mirrors the server's SQLite schema closely enough that a
 * row can round-trip to `/sync` and back without losing fields.
 *
 * Migrations are explicit (never destructive): a device may hold records that
 * have not yet synced anywhere, so a schema bump must preserve user data. Each
 * version bump adds a [Migration] to the builder and (with `exportSchema = true`)
 * a JSON schema under `app/schemas/` that the migration tests validate against.
 */
@Database(
    entities = [PersonEntity::class, ReportEntity::class, SyncLogEntity::class],
    version = 2,
    exportSchema = true,
)
abstract class EgiDatabase : RoomDatabase() {

    abstract fun personDao(): PersonDao
    abstract fun reportDao(): ReportDao
    abstract fun syncLogDao(): SyncLogDao

    companion object {
        @Volatile
        private var instance: EgiDatabase? = null

        /**
         * v1 -> v2: additive `merged_into` column on `persons` (fuzzy-dedup support).
         * Additive-only, so no data is touched.
         */
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE persons ADD COLUMN merged_into TEXT")
            }
        }

        fun get(context: Context): EgiDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    EgiDatabase::class.java,
                    "egi.db",
                ).addMigrations(MIGRATION_1_2).build().also { instance = it }
            }
    }
}
