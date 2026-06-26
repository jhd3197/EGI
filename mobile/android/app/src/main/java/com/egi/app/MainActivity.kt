package com.egi.app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.egi.app.bridge.EgiBridge

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var meshManager: BluetoothMeshManager

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.entries.all { it.value }
        if (allGranted) {
            meshManager.start()
        } else {
            Toast.makeText(this, getString(R.string.nearby_devices_permission_needed), Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        setupWebView()

        meshManager = BluetoothMeshManager(this)
        // Expose window.EgiNative BEFORE loading the page so the web bridge sees it
        // at startup; forward native→web events onto the UI thread.
        webView.addJavascriptInterface(EgiBridge(meshManager), EgiBridge.INTERFACE_NAME)
        meshManager.eventSink = { json -> runOnUiThread { dispatchMeshEvent(json) } }

        webView.loadUrl("file:///android_asset/www/index.html")
        requestNeededPermissions()
    }

    /** Deliver a native mesh event to the web side via window.EgiMesh.onEvent(...). */
    private fun dispatchMeshEvent(json: String) {
        val escaped = json.replace("\\", "\\\\").replace("'", "\\'")
        webView.evaluateJavascript(
            "window.EgiMesh && window.EgiMesh.onEvent(JSON.parse('$escaped'))",
            null,
        )
    }

    private fun setupWebView() {
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            setGeolocationEnabled(true)
        }
    }

    private fun requestNeededPermissions() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_ADVERTISE)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            permissions.add(Manifest.permission.BLUETOOTH)
            permissions.add(Manifest.permission.BLUETOOTH_ADMIN)
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        }

        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            permissionLauncher.launch(missing.toTypedArray())
        } else {
            meshManager.start()
        }
    }

    fun ensureBluetoothEnabled(): Boolean {
        val bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        val adapter = bluetoothManager.adapter ?: return false
        if (!adapter.isEnabled) {
            Toast.makeText(this, getString(R.string.bluetooth_disabled), Toast.LENGTH_LONG).show()
            return false
        }
        return true
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
