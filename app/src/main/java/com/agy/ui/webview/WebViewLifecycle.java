package com.agy.ui.webview;

import android.util.Log;
import android.webkit.WebView;

/** WebView resume/timer/memory lifecycle, kept out of the activity. */
public final class WebViewLifecycle {

    private static final String TAG = "WebViewHost";

    private WebViewLifecycle() {
    }

    /** Resume the page and tell it the host is back in front. */
    public static void resume(WebView webView) {
        if (webView == null) {
            return;
        }
        try {
            webView.onResume();
            webView.resumeTimers();
            webView.evaluateJavascript(
                    "(function(){ try { window.dispatchEvent(new CustomEvent('agy:host-resume')); } catch(e){} })();",
                    null);
        } catch (Exception e) {
            Log.w(TAG, "failed to resume webView", e);
        }
    }

    /**
     * Called when host activity moves to background.
     * We deliberately do NOT call webView.pauseTimers() or webView.onPause()
     * so that JavaScript execution, network requests, streaming SSE, and AI agent
     * tasks continue running smoothly in the background when the user switches apps
     * or turns off the screen.
     */
    public static void pause(WebView webView) {
        if (webView == null) {
            return;
        }
        try {
            webView.evaluateJavascript(
                    "(function(){ try { window.dispatchEvent(new CustomEvent('agy:host-pause')); } catch(e){} })();",
                    null);
        } catch (Exception e) {
            Log.w(TAG, "failed to notify webView on pause", e);
        }
    }

    public static void freeMemory(WebView webView) {
        if (webView == null) {
            return;
        }
        try {
            webView.freeMemory();
        } catch (Exception e) {
            Log.w(TAG, "freeMemory failed", e);
        }
    }
}
