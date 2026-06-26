package com.egi.app.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

/**
 * The on-device store. Mirrors the server's SQLite schema closely enough that a
 * row can round-trip to `/sync` and back without losing fields. Bumped when any
 * entity changes; uses destructive migration for now since the canonical copy
 * always lives in the cloud and the mesh can re-fill a wiped device.
 */
@Database(
    entities = [PersonEntity::class, ReportEntity::class, SyncLogEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class EgiDatabase : RoomDatabase() {

    abstract fun personDao(): PersonDao
    abstract fun reportDao(): ReportDao
    abstract fun syncLogDao(): SyncLogDao

    companion object {
        @Volatile
        private var instance: EgiDatabase? = null

        fun get(context: Context): EgiDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    EgiDatabase::class.java,
                    "egi.db",
                ).fallbackToDestructiveMigration().build().also { instance = it }
            }
    }
}
