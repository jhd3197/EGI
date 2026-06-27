package com.egi.app.mesh

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Battery-friendly relay duty cycle for the mesh.
 *
 * Continuous advertise + scan drains the battery fast, so instead of leaving both
 * radios on we run a staggered cycle: advertise for a short window, stop, scan for
 * a window, stop, then sleep before repeating. Advertising and scanning windows do
 * not fully overlap, which lowers radio contention and power draw while still
 * letting two nearby phones discover each other within a few cycles.
 *
 * Battery-saver mode lengthens the idle sleep (and slightly the scan gap) to trade
 * discovery latency for runtime. Durations are constants in the companion object.
 *
 * The cycle runs on the caller-supplied [scope]; [stop] cancels it cleanly and
 * fires the stop callbacks so neither radio is left on.
 */
class DutyCycler(
    private val scope: CoroutineScope,
    private val onAdvertiseStart: () -> Unit,
    private val onAdvertiseStop: () -> Unit,
    private val onScanStart: () -> Unit,
    private val onScanStop: () -> Unit,
    private val onLog: (String) -> Unit = {},
) {
    /** When true, the idle sleep is lengthened to conserve battery. */
    @Volatile
    var batterySaver: Boolean = false

    private var job: Job? = null

    /** Start the duty cycle (idempotent — a running cycle is left untouched). */
    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            onLog("Duty cycle started (batterySaver=$batterySaver)")
            var cycle = 0L
            try {
                while (isActive) {
                    // Snapshot the timings for THIS cycle (batterySaver may flip live).
                    val saver = batterySaver
                    val scanMs = if (saver) BATTERY_SAVER_SCAN_MS else SCAN_MS
                    val sleepMs = if (saver) BATTERY_SAVER_SLEEP_MS else SLEEP_MS

                    // Advertise window.
                    onAdvertiseStart()
                    delay(ADVERTISE_MS)
                    onAdvertiseStop()

                    // Scan window (staggered after advertising, never fully overlapping).
                    onScanStart()
                    delay(scanMs)
                    onScanStop()

                    // Idle sleep — the bulk of the power saving.
                    delay(sleepMs)

                    // Lightweight power/duty-cycle observability (plan §7.3): periodically
                    // log the cycle timings so field battery measurement is possible without
                    // a profiler. Throttled to every LOG_EVERY_N_CYCLES so logcat stays quiet.
                    cycle++
                    if (cycle % LOG_EVERY_N_CYCLES == 0L) {
                        val period = ADVERTISE_MS + scanMs + sleepMs
                        onLog(
                            "Duty cycle #$cycle: advertise=${ADVERTISE_MS}ms scan=${scanMs}ms " +
                                "sleep=${sleepMs}ms period=${period}ms batterySaver=$saver",
                        )
                    }
                }
            } finally {
                // Whether cancelled or completed, leave both radios off.
                onAdvertiseStop()
                onScanStop()
            }
        }
    }

    /** Cancel the cycle and ensure advertising/scanning are stopped. */
    fun stop() {
        job?.cancel()
        job = null
        onAdvertiseStop()
        onScanStop()
        onLog("Duty cycle stopped")
    }

    companion object {
        /** Advertise window length (ms). */
        const val ADVERTISE_MS = 200L

        /** Scan window length in normal mode (ms). */
        const val SCAN_MS = 400L

        /** Idle sleep between cycles in normal mode (ms). */
        const val SLEEP_MS = 800L

        /** Scan window length in battery-saver mode (ms). */
        const val BATTERY_SAVER_SCAN_MS = 300L

        /** Idle sleep between cycles in battery-saver mode (ms). */
        const val BATTERY_SAVER_SLEEP_MS = 3_000L

        /** Log a summary once every N complete cycles. */
        const val LOG_EVERY_N_CYCLES = 30L
    }
}
