package com.egi.app.data

import androidx.room.testing.MigrationTestHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Validates the v1 -> v2 Room migration ([EgiDatabase.MIGRATION_1_2]) does not lose
 * data: a person row inserted under the v1 schema must survive the migration, and the
 * additive `merged_into` column must exist and default to null afterward.
 *
 * Instrumented test: it runs on a device/emulator (not the JVM `test` source set) and
 * relies on the exported schema JSON in `app/schemas/`, which is generated on the first
 * build with `exportSchema = true`. It therefore cannot run in a headless/SDK-less
 * environment — it is here so the migration is covered once an emulator is available.
 */
@RunWith(AndroidJUnit4::class)
class MigrationTest {

    private val testDb = "egi-migration-test.db"

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        EgiDatabase::class.java,
        emptyList(),
        FrameworkSQLiteOpenHelperFactory(),
    )

    @Test
    fun migrate1To2PreservesDataAndAddsMergedIntoColumn() {
        val personId = "egi-test-migrate-0001" // TEST DATA — NOT REAL

        // Create the DB at v1 and insert a person with raw SQL (the v1 schema has no
        // merged_into column).
        helper.createDatabase(testDb, 1).apply {
            execSQL(
                "INSERT INTO persons (id, hop_count, created_at, updated_at) " +
                    "VALUES ('$personId', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            )
            close()
        }

        // Run the migration and let Room validate the resulting schema matches v2.
        val db = helper.runMigrationsAndValidate(testDb, 2, true, EgiDatabase.MIGRATION_1_2)

        db.query("SELECT id, merged_into FROM persons WHERE id = '$personId'").use { cursor ->
            assertTrue("person row should survive the migration", cursor.moveToFirst())
            assertEquals(personId, cursor.getString(cursor.getColumnIndexOrThrow("id")))
            // The new column exists and is null for the pre-existing row.
            val mergedIdx = cursor.getColumnIndexOrThrow("merged_into")
            assertTrue("merged_into should default to null", cursor.isNull(mergedIdx))
        }
    }
}
