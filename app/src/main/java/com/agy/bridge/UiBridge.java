package com.agy.bridge;

import android.util.Log;

import java.io.File;
import java.lang.ref.WeakReference;

import com.agy.ui.MainActivity;
import com.agy.util.SensitiveDataRedactor;

/**
 * Routes UI-ready/error callbacks from JS to the host activity. addJavascriptInterface
 * callbacks land on a WebView thread, so hop to the main thread first.
 */
public final class UiBridge {

    private static final String TAG = "AndroidBridge";

    private volatile WeakReference<MainActivity> activityRef;

    public void setActivity(MainActivity activity) {
        this.activityRef = activity != null ? new WeakReference<MainActivity>(activity) : null;
    }

    public void onUiReady() {
        Log.i(TAG, "onUiReady() received from JavaScript; posting dismissSplash");
        final MainActivity host = this.activityRef != null ? this.activityRef.get() : null;
        if (host == null) {
            return;
        }
        host.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                host.dismissSplash();
            }
        });
    }

    public void onUiError(final String errorMessage) {
        final String safeError = SensitiveDataRedactor.redactLine(errorMessage);
        Log.e(TAG, "onUiError() received from JavaScript: " + safeError);
        final MainActivity host = this.activityRef != null ? this.activityRef.get() : null;
        if (host == null) {
            return;
        }
        host.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                host.showFatalError(safeError);
            }
        });
    }

    public boolean isDesktopMode() {
        final MainActivity host = this.activityRef != null ? this.activityRef.get() : null;
        return host != null ? host.isDesktopMode() : false;
    }

    public void setDesktopMode(final boolean enabled) {
        final MainActivity host = this.activityRef != null ? this.activityRef.get() : null;
        if (host == null) {
            return;
        }
        host.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                host.setDesktopMode(enabled);
            }
        });
    }

    @android.webkit.JavascriptInterface
    public void saveCustomModels(final String json) {
        final MainActivity host = this.activityRef != null ? this.activityRef.get() : null;
        if (host == null || json == null) return;
        try {
            File dir = new File(host.getFilesDir(), ".gemini");
            if (!dir.exists()) dir.mkdirs();
            File file = new File(dir, "custom_models.json");
            com.agy.util.AtomicFileWriter.writeText(file, json);
            Log.i(TAG, "Saved custom models to " + file.getAbsolutePath());
        } catch (Exception e) {
            Log.w(TAG, "Failed to save custom models: " + e.getMessage());
        }
    }

    @android.webkit.JavascriptInterface
    public String getCustomModels() {
        final MainActivity host = this.activityRef != null ? this.activityRef.get() : null;
        if (host == null) return "{}";
        try {
            File file = new File(host.getFilesDir(), ".gemini/custom_models.json");
            if (file.isFile()) {
                return com.agy.util.IoUtil.readAll(new java.io.FileInputStream(file), "UTF-8");
            }
        } catch (Exception ignored) {}
        return "{}";
    }
}
