package com.egi.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.ParcelUuid
import android.util.Log
import com.egi.app.mesh.BleConstants
import com.egi.app.mesh.BloomFilter

/**
 * A peer discovered in a scan, with its advertised bloom filter (if parseable) and
 * whether it advertised the gateway flag (recent cloud reachability, plan-23 Phase 2).
 */
data class PeerDevice(
    val address: String,
    val device: BluetoothDevice,
    val bloom: BloomFilter?,
    val rssi: Int,
    val isGateway: Boolean = false,
)

/**
 * Scans for EGI peers (filtered to [BleConstants.SERVICE_UUID]) in low-latency mode
 * and reports each result, parsing the bloom filter out of the service data.
 *
 * BLE permissions (`BLUETOOTH_SCAN`) are guaranteed by the caller (MainActivity).
 */
class BleScanner(
    context: Context,
    private val onLog: (String) -> Unit = {},
) {
    private val bluetoothManager =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager

    private val scanner: BluetoothLeScanner?
        get() = bluetoothManager.adapter?.bluetoothLeScanner

    private var scanning = false
    private var listener: ((PeerDevice) -> Unit)? = null

    private val callback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult?) {
            result ?: return
            handleResult(result)
        }

        override fun onBatchScanResults(results: MutableList<ScanResult>?) {
            results?.forEach { handleResult(it) }
        }

        override fun onScanFailed(errorCode: Int) {
            scanning = false
            log("Scan failed: error=$errorCode")
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_SCAN guaranteed by caller
    fun start(onPeerFound: (PeerDevice) -> Unit) {
        val s = scanner
        if (s == null) {
            log("BLE scanning unavailable (no scanner); skipping scan")
            return
        }
        if (scanning) stop()
        listener = onPeerFound

        val filter = ScanFilter.Builder()
            .setServiceUuid(ParcelUuid(BleConstants.SERVICE_UUID))
            .build()
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()

        try {
            s.startScan(listOf(filter), settings, callback)
            scanning = true
            log("Scanning started")
        } catch (e: Exception) {
            log("Scan start threw: ${e.message}")
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_SCAN guaranteed by caller
    fun stop() {
        if (!scanning) return
        try {
            scanner?.stopScan(callback)
        } catch (e: Exception) {
            log("Scan stop threw: ${e.message}")
        }
        scanning = false
        listener = null
        log("Scanning stopped")
    }

    /** Parsed EGI service data: the advertised bloom plus the gateway flag. */
    private data class ServiceData(val bloom: BloomFilter?, val isGateway: Boolean)

    private fun handleResult(result: ScanResult) {
        val device = result.device ?: return
        val parsed = parseServiceData(result)
        val peer = PeerDevice(
            address = device.address,
            device = device,
            bloom = parsed?.bloom,
            rssi = result.rssi,
            isGateway = parsed?.isGateway ?: false,
        )
        listener?.invoke(peer)
    }

    /**
     * Extract the bloom filter and gateway flag from the version-prefixed service
     * data. Two layouts are accepted for backward compatibility (plan-23 Phase 2):
     *  - new:    `[version][flags][bloom(16)]` — flags bit 0 = gateway.
     *  - legacy: `[version][bloom(16)]`        — no flags byte, treated as non-gateway.
     */
    private fun parseServiceData(result: ScanResult): ServiceData? {
        val record = result.scanRecord ?: return null
        val raw = record.getServiceData(ParcelUuid(BleConstants.SERVICE_UUID)) ?: return null
        if (raw.isEmpty()) return null
        if (raw[0] != BleConstants.PROTOCOL_VERSION) {
            log("Ignoring peer ${result.device?.address}: protocol v${raw[0]}")
            return null
        }
        val n = BleConstants.ADVERT_BLOOM_BYTES
        val (flags, bloomBytes) = when (raw.size) {
            2 + n -> raw[1].toInt() to raw.copyOfRange(2, raw.size) // new format
            1 + n -> 0 to raw.copyOfRange(1, raw.size)              // legacy, no flags
            else -> return null
        }
        if (bloomBytes.size != n) return null
        val bloom = runCatching { BloomFilter.fromBytes(bloomBytes) }.getOrNull()
        val isGateway = (flags and BleConstants.GATEWAY_FLAG) != 0
        return ServiceData(bloom, isGateway)
    }

    private fun log(message: String) {
        Log.d(TAG, message)
        onLog(message)
    }

    private companion object {
        private const val TAG = "EGI-Scanner"
    }
}
