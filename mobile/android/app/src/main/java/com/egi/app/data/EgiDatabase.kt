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
    entities = [PersonEntity::class, ReportEntity::class, AnimalEntity::class, SyncLogEntity::class],
    version = 3,
    exportSchema = true,
)
abstract class EgiDatabase : RoomDatabase() {

    abstract fun personDao(): PersonDao
    abstract fun reportDao(): ReportDao
    abstract fun animalDao(): AnimalDao
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

        /**
         * v2 -> v3: additive `animals` table (plan-28 Missing Animals — a parallel
         * mesh/cloud track to persons). New table only, so no existing data is
         * touched. The column list and NOT NULL constraints must match
         * [AnimalEntity] exactly or Room's schema validation will fail at open.
         */
        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `animals` (" +
                        "`id` TEXT NOT NULL, " +
                        "`disaster_id` TEXT, " +
                        "`status` TEXT, " +
                        "`species` TEXT, " +
                        "`breed` TEXT, " +
                        "`name` TEXT, " +
                        "`sex` TEXT, " +
                        "`size` TEXT, " +
                        "`color` TEXT, " +
                        "`distinguishing_marks` TEXT, " +
                        "`microchip` TEXT, " +
                        "`photo_url` TEXT, " +
                        "`photos` TEXT, " +
                        "`last_seen_location` TEXT, " +
                        "`last_seen_at` TEXT, " +
                        "`lat` REAL, " +
                        "`lon` REAL, " +
                        "`owner_name` TEXT, " +
                        "`owner_contact` TEXT, " +
                        "`reporter_id` TEXT, " +
                        "`reporter_name` TEXT, " +
                        "`notes` TEXT, " +
                        "`source` TEXT, " +
                        "`reviewed` INTEGER, " +
                        "`shelter_id` TEXT, " +
                        "`intake_at` TEXT, " +
                        "`condition_note` TEXT, " +
                        "`merged_into` TEXT, " +
                        "`origin_device` TEXT, " +
                        "`hop_count` INTEGER NOT NULL, " +
                        "`created_at` TEXT NOT NULL, " +
                        "`updated_at` TEXT NOT NULL, " +
                        "PRIMARY KEY(`id`))",
                )
            }
        }

        fun get(context: Context): EgiDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    EgiDatabase::class.java,
                    "egi.db",
                ).addMigrations(MIGRATION_1_2, MIGRATION_2_3).build().also { instance = it }
            }
    }
}
