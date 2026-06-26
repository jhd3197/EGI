package com.egi.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.content.Context
import android.os.ParcelUuid
import android.util.Log
import com.egi.app.mesh.BleConstants
import com.egi.app.mesh.BloomFilter

/**
 * Broadcasts the EGI service UUID plus a compact bloom filter of our local record
 * IDs as service data, so a passing peer can cheaply decide whether to connect.
 *
 * BLE permissions (`BLUETOOTH_ADVERTISE`) are guaranteed by the caller
 * (MainActivity requests them); methods are annotated accordingly.
 */
class BleAdvertiser(
    context: Context,
    private val onLog: (String) -> Unit = {},
) {
    private val bluetoothManager =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager

    private val advertiser: BluetoothLeAdvertiser?
        get() = bluetoothManager.adapter?.bluetoothLeAdvertiser

    private var advertising = false

    private val callback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
            advertising = true
            log("Advertising started")
        }

        override fun onStartFailure(errorCode: Int) {
            advertising = false
            log("Advertising failed: error=$errorCode")
        }
    }

    /**
     * Build a bloom filter from [localRecordIds] and start advertising it under
     * [BleConstants.SERVICE_UUID]. Service data is prefixed with the protocol
     * version byte so peers can reject incompatible advertisements.
     */
    @SuppressLint("MissingPermission") // BLUETOOTH_ADVERTISE guaranteed by caller
    fun start(localRecordIds: Collection<String>) {
        val adv = advertiser
        if (adv == null) {
            // Many devices simply do not support BLE peripheral mode; degrade gracefully.
            log("BLE advertising unsupported on this device; skipping advertise")
            return
        }
        if (advertising) stop()

        val bloom = BloomFilter.of(localRecordIds).toBytes()
        // Prefix the protocol version so the 16-byte bloom payload is self-describing.
        val serviceData = ByteArray(1 + bloom.size).also {
            it[0] = BleConstants.PROTOCOL_VERSION
            System.arraycopy(bloom, 0, it, 1, bloom.size)
        }

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_BALANCED)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_MEDIUM)
            .setConnectable(true)
            .setTimeout(0)
            .build()

        val parcelUuid = ParcelUuid(BleConstants.SERVICE_UUID)
        // The 128-bit service UUID alone nearly fills the 31-byte legacy advert, so
        // carry the bloom service data in the scan response to stay within budget.
        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .addServiceUuid(parcelUuid)
            .build()
        val scanResponse = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .addServiceData(parcelUuid, serviceData)
            .build()

        try {
            adv.startAdvertising(settings, data, scanResponse, callback)
            log("Advertising request submitted (${localRecordIds.size} ids in bloom)")
        } catch (e: Exception) {
            log("Advertising start threw: ${e.message}")
        }
    }

    @SuppressLint("MissingPermission") // BLUETOOTH_ADVERTISE guaranteed by caller
    fun stop() {
        if (!advertising && advertiser == null) return
        try {
            advertiser?.stopAdvertising(callback)
        } catch (e: Exception) {
            log("Advertising stop threw: ${e.message}")
        }
        advertising = false
        log("Advertising stopped")
    }

    private fun log(message: String) {
        Log.d(TAG, message)
        onLog(message)
    }

    private companion object {
        private const val TAG = "EGI-Advertiser"
    }
}
