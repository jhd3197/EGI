package com.egi.app

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast

/**
 * Placeholder Bluetooth mesh manager.
 *
 * The goal: use Bluetooth Low Energy to discover nearby EGI devices,
 * exchange a compact list of record IDs and timestamps, and request
 * missing records. When a device reaches the internet, it uploads
 * everything to the central server.
 *
 * This file is intentionally a stub. Implementing a robust store-and-forward
 * mesh over BLE requires careful handling of Android permissions, GATT
 * services, connection windows, and battery life. See mobile/shared/protocol.md.
 */
class BluetoothMeshManager(private val context: Context) {

    private val tag = "EGI-Mesh"
    private val handler = Handler(Looper.getMainLooper())

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        val manager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        manager.adapter
    }

    fun start() {
        val adapter = bluetoothAdapter ?: run {
            Log.e(tag, "Bluetooth not supported on this device")
            return
        }
        if (!adapter.isEnabled) {
            Toast.makeText(context, R.string.bluetooth_disabled, Toast.LENGTH_LONG).show()
            return
        }

        Log.i(tag, "Starting Bluetooth mesh placeholder")
        Toast.makeText(context, "Bluetooth mesh started (placeholder)", Toast.LENGTH_SHORT).show()

        // TODO: start BLE advertisement and scan here
        // adapter.bluetoothLeAdvertiser?.startAdvertising(...)
        // adapter.bluetoothLeScanner?.startScan(...)
    }

    fun stop() {
        Log.i(tag, "Stopping Bluetooth mesh placeholder")
        // TODO: stop BLE advertisement and scan
    }

    /**
     * Called when a nearby peer is discovered.
     */
    fun onPeerDiscovered(deviceAddress: String) {
        Log.i(tag, "Discovered peer: $deviceAddress")
        // TODO: connect, exchange metadata, request missing records
    }

    /**
     * Called when records are received from a peer.
     */
    fun onRecordsReceived(recordsJson: String) {
        Log.i(tag, "Received records: $recordsJson")
        // TODO: validate, merge into local database, mark for server upload
    }
}
