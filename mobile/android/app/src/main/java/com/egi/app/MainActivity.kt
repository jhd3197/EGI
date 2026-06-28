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
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.egi.app.bridge.EgiBridge
import com.egi.app.bridge.PwaApiBridge
import com.egi.app.push.PushEventBus

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var meshManager: BluetoothMeshManager
    private lateinit var assetLoader: WebViewAssetLoader
    private lateinit var pwaApi: PwaApiBridge

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        // POST_NOTIFICATIONS is optional: without it the foreground notification just
        // won't show, but the mesh (BLE scan/advertise/connect) can still run.
        val requiredGranted = permissions.entries
            .filter { it.key != Manifest.permission.POST_NOTIFICATIONS }
            .all { it.value }
        if (requiredGranted) {
            // onResume already ran (and no-opped) before this grant; re-arm now.
            LocationCache.start(applicationContext)
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
        // Serves the PWA's same-origin API (/sync, /persons, …) from the local Room
        // DB so the embedded app works with no server. Shared by the GET interceptor
        // (reads) and the EgiNative bridge (writes).
        pwaApi = PwaApiBridge(applicationContext)
        // Expose window.EgiNative BEFORE loading the page so the web bridge sees it
        // at startup; forward native→web events onto the UI thread. The bridge gets
        // the application context so it can read/write mesh consent, plus pwaApi so
        // POST /sync and POST /persons/{id}/reports persist to Room.
        webView.addJavascriptInterface(
            EgiBridge(meshManager, applicationContext, pwaApi),
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

    override fun onResume() {
        super.onResume()
        // Battery-aware: only stream location while the app is in the foreground
        // (plan §3.4 "request location only when needed"). Refreshes the cache that
        // EgiNative.getCurrentPosition() reads. No-op without location permission.
        LocationCache.start(applicationContext)
    }

    override fun onPause() {
        // Stop the location stream when backgrounded to save battery; the last fix
        // stays cached in SharedPreferences for the next getCurrentPosition call.
        LocationCache.stop(applicationContext)
        super.onPause()
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
        // Enable Chrome DevTools inspection of the WebView for debuggable builds only,
        // so the automated PWA smoke tests can drive the page over CDP. Gated on the
        // debuggable flag so it never turns on in a release APK.
        if ((applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true)
        }

        assetLoader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        // Inject the PWA bridge shim (window.isEgiAndroidWebView, navigator.onLine,
        // and the fetch() POST router) BEFORE any page script runs, so the PWA's very
        // first /sync and report writes already hit the native backend. Falls back to
        // onPageFinished injection on WebViews too old for document-start scripts.
        val originRules = setOf("https://appassets.androidplatform.net")
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(webView, PwaApiBridge.DOCUMENT_START_JS, originRules)
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView?,
                request: WebResourceRequest?,
            ): WebResourceResponse? {
                val url = request?.url ?: return super.shouldInterceptRequest(view, request)
                // Native API first (Room-backed /sync, /persons, …); fall through to
                // the asset loader for bundled PWA files.
                pwaApi.handle(request)?.let { return it }
                val response = assetLoader.shouldInterceptRequest(url) ?: return null
                // Work around androidx.webkit WebViewAssetLoader versions that serve
                // .js files with a generic MIME type (e.g. application/octet-stream).
                // ES module scripts refuse to execute unless they have a valid JS
                // MIME type, so rewrite it when necessary.
                val path = url.path
                if (path != null && path.endsWith(".js")) {
                    val mt = response.mimeType?.lowercase() ?: ""
                    if (!mt.contains("javascript")) {
                        return WebResourceResponse(
                            "application/javascript",
                            response.encoding,
                            response.statusCode,
                            response.reasonPhrase,
                            response.responseHeaders,
                            response.data,
                        )
                    }
                }
                return response
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Belt-and-suspenders for old WebViews without document-start support.
                if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                    view?.evaluateJavascript(PwaApiBridge.DOCUMENT_START_JS, null)
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

            // Grant the in-WebView navigator.geolocation fallback (plan §3.3). We
            // already hold (or have requested) the runtime ACCESS_*_LOCATION
            // permission, so we approve the page's request without a second prompt.
            // retain=false: don't persist per-origin, the native runtime permission
            // is the real gate. Without this override setGeolocationEnabled(true)
            // alone never resolves the JS geolocation promise.
            override fun onGeolocationPermissionsShowPrompt(
                origin: String?,
                callback: android.webkit.GeolocationPermissions.Callback?,
            ) {
                callback?.invoke(origin, true, false)
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
        // Location powers "my location" + native turn-by-turn (plan-21 §3). On
        // pre-S it's already added above for the BLE scan; request it explicitly on
        // all levels so getCurrentPosition()/navigator.geolocation have a fix.
        if (!permissions.contains(Manifest.permission.ACCESS_FINE_LOCATION)) {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
            permissions.add(Manifest.permission.ACCESS_COARSE_LOCATION)
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
