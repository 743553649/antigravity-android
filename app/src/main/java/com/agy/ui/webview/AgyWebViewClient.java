package com.agy.ui.webview;

import android.content.Context;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.util.Log;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.agy.bridge.AndroidBridge;
import com.agy.oauth.OAuthManager;
import com.agy.util.LoopbackHost;

/** WebView client: OAuth interception, loopback TLS, and static asset serving. */
public final class AgyWebViewClient extends WebViewClient {

    private static final String TAG = "WebViewHost";

    private final Context context;
    private final OAuthManager oauth;
    private final LocalAssetServer assetServer;
    private final AndroidBridge bridge;
    private final WebViewHost.Listener listener;

    public AgyWebViewClient(Context context, OAuthManager oauth, LocalAssetServer assetServer,
                            AndroidBridge bridge, WebViewHost.Listener listener) {
        this.context = context;
        this.oauth = oauth;
        this.assetServer = assetServer;
        this.bridge = bridge;
        this.listener = listener;
    }

    @Override
    public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
        if (req != null && req.getUrl() != null) {
            Log.w(TAG, "Resource load error: " + req.getUrl() + " err="
                    + (err != null ? err.getDescription() : "unknown"));
        }
    }

    @Override
    public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) {
        String url = request != null && request.getUrl() != null
                ? request.getUrl().toString() : null;
        Log.i(TAG, "shouldOverrideUrlLoading url=" + url);
        return handleNavigation(v, url);
    }

    @Override
    @SuppressWarnings("deprecation")
    public boolean shouldOverrideUrlLoading(WebView v, String url) {
        Log.i(TAG, "shouldOverrideUrlLoading(deprecated) url=" + url);
        return handleNavigation(v, url);
    }

    private boolean handleNavigation(WebView v, String url) {
        if (url == null || url.isEmpty() || url.equals("about:blank")) {
            return false;
        }
        try {
            Uri uri = Uri.parse(url);
            if (!LoopbackHost.isLoopback(uri)) {
                Log.i(TAG, "non-loopback navigation -> external browser: " + url);
                return oauth.openInBrowser(context, url);
            }
        } catch (Exception e) {
            Log.w(TAG, "cannot parse uri: " + url, e);
        }
        return oauth.intercept(context, url);
    }

    /**
     * Server-side (3xx) redirects do not always reach shouldOverrideUrlLoading;
     * catch non-loopback URLs here and stop the WebView from rendering them.
     */
    @Override
    public void onPageStarted(WebView v, String url, Bitmap favicon) {
        if (url != null && !url.equals("about:blank")) {
            try {
                Uri uri = Uri.parse(url);
                if (!LoopbackHost.isLoopback(uri)) {
                    Log.i(TAG, "onPageStarted intercepted non-loopback url: " + url);
                    v.stopLoading();
                    oauth.openInBrowser(context, url);
                    return;
                }
            } catch (Exception ignored) {
            }
        }
        if (oauth.intercept(context, url)) {
            Log.i(TAG, "onPageStarted stopped auth url=" + url);
            v.stopLoading();
        }
    }

    @Override
    public void onReceivedSslError(WebView v, SslErrorHandler handler, SslError error) {
        if (LoopbackSslPolicy.proceed(error)) {
            handler.proceed();
        } else {
            handler.cancel();
        }
    }

    @Override
    public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest request) {
        if (request == null || request.getUrl() == null) {
            return null;
        }
        return assetServer.intercept(context, request.getUrl(), request.getMethod(),
                bridge.getEnginePort());
    }

    @Override
    @SuppressWarnings("deprecation")
    public WebResourceResponse shouldInterceptRequest(WebView v, String url) {
        if (url == null) {
            return null;
        }
        try {
            return assetServer.intercept(context, Uri.parse(url), "GET", bridge.getEnginePort());
        } catch (Exception e) {
            return null;
        }
    }

    @Override
    public void onPageFinished(WebView v, String url) {
        if (listener != null) {
            listener.onPageFinished(url);
        }
    }
}
