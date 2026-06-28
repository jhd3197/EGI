package com.egi.app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.webkit.WebViewAssetLoader
import com.egi.app.bridge.EgiBridge
import com.egi.app.push.PushEventBus

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var meshManager: BluetoothMeshManager
    private lateinit var assetLoader: WebViewAssetLoader

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        // POST_NOTIFICATIONS is optional: without it the foreground notification just
        // won't show, but the mesh (BLE scan/advertise/connect) can still run.
        val requiredGranted = permissions.entries
            .filter { it.key != Manifest.permission.POST_NOTIFICATIONS }
            .all { it.value }
        if (requiredGranted) {
            startMeshWithConsent()
        } else {
            Toast.makeText(this, getString(R.string.nearby_devices_permission_needed), Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        setupWebView()

        // Shared singleton so the WebView bridge and MeshForegroundService drive the
        // same mesh instance (one GATT server / one duty cycle).
        meshManager = BluetoothMeshManager.getInstance(applicationContext)
        // Expose window.EgiNative BEFORE loading the page so the web bridge sees it
        // at startup; forward native→web events onto the UI thread. The bridge gets
        // the application context so it can read/write mesh consent.
        webView.addJavascriptInterface(
            EgiBridge(meshManager, applicationContext),
            EgiBridge.INTERFACE_NAME,
        )
        meshManager.eventSink = { json -> runOnUiThread { dispatchMeshEvent(json) } }
        // Forward native FCM push alerts to the same window.EgiMesh.onEvent(...) path.
        // The bus buffers events that arrived while no Activity was attached and
        // flushes them on attach. Detached in onDestroy to avoid leaking the WebView.
        PushEventBus.setSink { json -> runOnUiThread { dispatchMeshEvent(json) } }

        // Route the system Back gesture through the WebView history first, falling
        // back to default Activity behavior. Uses the AndroidX OnBackPressedDispatcher
        // (the deprecated onBackPressed() override has been removed). When the WebView
        // has no history left, we disable this callback and re-dispatch so the default
        // handler (finish the Activity) runs.
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        // Load the PWA through the local HTTPS asset loader instead of file:// so
        // ES module scripts and CSS load without CORS errors.
        webView.loadUrl("https://appassets.androidplatform.net/assets/www/index.html")
        requestNeededPermissions()
    }

    override fun onDestroy() {
        // Stop forwarding push events into a WebView that's about to be destroyed.
        PushEventBus.setSink(null)
        assetLoader?.let { /* no explicit teardown needed */ }
        super.onDestroy()
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
        assetLoader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView?,
                request: WebResourceRequest?,
            ): WebResourceResponse? {
                val url = request?.url ?: return super.shouldInterceptRequest(view, request)
                Log.d("EGI-AssetLoader", "intercept request: $url")
                return assetLoader.shouldInterceptRequest(url).also {
                    Log.d("EGI-AssetLoader", "response for $url: ${it != null}")
                }
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?,
            ) {
                Log.e(
                    "EGI-AssetLoader",
                    "onReceivedError: ${error?.errorCode} ${error?.description} for ${request?.url}",
                )
                super.onReceivedError(view, request, error)
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(message: android.webkit.ConsoleMessage?): Boolean {
                Log.d(
                    "EGI-WebView",
                    "[${message?.sourceId()}:${message?.lineNumber()}] ${message?.message()}",
                )
                return true
            }
        }
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowContentAccess = true
            allowFileAccess = false
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
        // Needed to show the ongoing foreground-service notification on API 33+.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            permissionLauncher.launch(missing.toTypedArray())
        } else {
            startMeshWithConsent()
        }
    }

    /**
     * Start the mesh, but gate the very first activation behind an explicit Spanish
     * privacy-consent dialog. Once consented, future launches start directly.
     */
    private fun startMeshWithConsent() {
        if (MeshConsent.hasConsented(this)) {
            startMeshService()
            return
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.mesh_privacy_title)
            .setMessage(R.string.mesh_privacy_warning)
            .setCancelable(false)
            .setPositiveButton(R.string.mesh_privacy_continue) { _, _ ->
                MeshConsent.setConsented(this, true)
                startMeshService()
            }
            .setNegativeButton(R.string.mesh_privacy_cancel) { _, _ -> /* do nothing */ }
            .show()
    }

    /**
     * Start the mesh inside a foreground service so it survives backgrounding. The
     * service drives the same singleton manager exposed to the WebView bridge.
     */
    private fun startMeshService() {
        MeshForegroundService.start(this)
    }

    /** Stop the mesh foreground service (and the mesh). */
    fun stopMeshService() {
        MeshForegroundService.stop(this)
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
}
