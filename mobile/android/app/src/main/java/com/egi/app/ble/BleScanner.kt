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

/** A peer discovered in a scan, with its advertised bloom filter (if parseable). */
data class PeerDevice(
    val address: String,
    val device: BluetoothDevice,
    val bloom: BloomFilter?,
    val rssi: Int,
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

    private fun handleResult(result: ScanResult) {
        val device = result.device ?: return
        val bloom = parseBloom(result)
        val peer = PeerDevice(
            address = device.address,
            device = device,
            bloom = bloom,
            rssi = result.rssi,
        )
        listener?.invoke(peer)
    }

    /** Extract and validate the version-prefixed bloom filter from the service data. */
    private fun parseBloom(result: ScanResult): BloomFilter? {
        val record = result.scanRecord ?: return null
        val raw = record.getServiceData(ParcelUuid(BleConstants.SERVICE_UUID)) ?: return null
        if (raw.isEmpty()) return null
        if (raw[0] != BleConstants.PROTOCOL_VERSION) {
            log("Ignoring peer ${result.device?.address}: protocol v${raw[0]}")
            return null
        }
        val bloomBytes = raw.copyOfRange(1, raw.size)
        if (bloomBytes.size != BleConstants.ADVERT_BLOOM_BYTES) return null
        return runCatching { BloomFilter.fromBytes(bloomBytes) }.getOrNull()
    }

    private fun log(message: String) {
        Log.d(TAG, message)
        onLog(message)
    }

    private companion object {
        private const val TAG = "EGI-Scanner"
    }
}
