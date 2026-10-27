package com.agy.bridge;

import android.content.Context;
import android.webkit.JavascriptInterface;

import com.agy.runtime.RuntimeManager;
import com.agy.shell.ShizukuBridge;
import com.agy.theme.ThemeManager;
import com.agy.ui.MainActivity;

import java.lang.ref.WeakReference;
import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.security.SecureRandom;

/**
 * Minimal, low-privilege JavaScript bridge for the app UI. It is visible to
 * embedded frames, so shell, notification, and arbitrary URL capabilities must
 * not be exposed here. Native-only getters below are intentionally unannotated.
 */
public final class AndroidBridge {

    private final Context appContext;
    private final UiBridge ui = new UiBridge();
    private final ThemeBridge themeBridge;
    private final EngineBridge engine;
    private final EngineConfigJson config;
    private final String blobBridgeToken = createBlobBridgeToken();
    private volatile WeakReference<MainActivity> activityRef;

    public AndroidBridge(Context context, RuntimeManager runtime,
                         ShizukuBridge shizuku, ThemeManager theme) {
        this.appContext = context.getApplicationContext();
        this.themeBridge = new ThemeBridge(theme);
        this.engine = new EngineBridge(runtime);
        this.config = new EngineConfigJson(appContext, runtime, engine, shizuku, themeBridge);
    }

    /** Host activity, used to dismiss the native splash once the UI has painted. */
    public void setActivity(MainActivity activity) {
        this.activityRef = activity != null ? new WeakReference<MainActivity>(activity) : null;
        ui.setActivity(activity);
    }

    @JavascriptInterface
    public void onUiReady(String token) {
        if (matchesNativeBridgeToken(token)) {
            ui.onUiReady();
        }
    }

    @JavascriptInterface
    public void openDirectoryPicker() {
        final MainActivity act = activityRef != null ? activityRef.get() : MainActivity.activeActivity;
        if (act != null) {
            act.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    act.launchDirectoryPicker();
                }
            });
        }
    }

    @JavascriptInterface
    public void onUiError(String token, final String errorMessage) {
        if (matchesNativeBridgeToken(token)) {
            ui.onUiError(errorMessage);
        }
    }

    @JavascriptInterface
    public boolean setTheme(String mode) {
        return themeBridge.setTheme(mode);
    }

    @JavascriptInterface
    public boolean setThemeByUser(final String mode) {
        return themeBridge.setThemeByUser(mode);
    }

    @JavascriptInterface
    public void onVisualThemeChanged(String visual) {
        themeBridge.onVisualThemeChanged(visual);
    }

    @JavascriptInterface
    public String getTheme() {
        return themeBridge.getTheme();
    }

    @JavascriptInterface
    public boolean isDesktopMode() {
        return ui.isDesktopMode();
    }

    @JavascriptInterface
    public void setDesktopMode(boolean enabled) {
        ui.setDesktopMode(enabled);
    }

    @JavascriptInterface
    public void saveCustomModels(String json) {
        if (json == null) return;
        try {
            java.io.File dir = new java.io.File(appContext.getFilesDir(), ".gemini");
            if (!dir.exists()) dir.mkdirs();
            java.io.File file = new java.io.File(dir, "custom_models.json");
            com.agy.util.AtomicFileWriter.writeText(file, json);
            android.util.Log.i("AndroidBridge", "Saved custom_models.json (" + json.length() + " bytes) to " + file.getAbsolutePath());
        } catch (Exception e) {
            android.util.Log.w("AndroidBridge", "Failed to save custom_models.json: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public String getCustomModels() {
        try {
            java.io.File file = new java.io.File(appContext.getFilesDir(), ".gemini/custom_models.json");
            if (file.isFile()) {
                return com.agy.util.IoUtil.readAll(new java.io.FileInputStream(file), "UTF-8");
            }
        } catch (Exception ignored) {}
        return "{}";
    }

    @JavascriptInterface
    public String testCustomModel(String baseUrl, String apiKey, String modelName) {
        String endpoint = (baseUrl != null ? baseUrl.trim() : "");
        if (endpoint.isEmpty()) endpoint = "https://aiping.cn/api/v1";
        while (endpoint.endsWith("/")) endpoint = endpoint.substring(0, endpoint.length() - 1);
        if (!endpoint.endsWith("/chat/completions")) {
            endpoint = endpoint + "/chat/completions";
        }
        String model = (modelName != null && !modelName.trim().isEmpty()) ? modelName.trim() : "deepseek-chat";
        String key = (apiKey != null) ? apiKey.trim() : "";
        try {
            java.net.URL url = new java.net.URL(endpoint);
            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(15000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("User-Agent", "Antigravity-Android/2.4");
            if (!key.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + key);
            }
            org.json.JSONObject payload = new org.json.JSONObject();
            payload.put("model", model);
            org.json.JSONArray msgs = new org.json.JSONArray();
            org.json.JSONObject m = new org.json.JSONObject();
            m.put("role", "user");
            m.put("content", "hi");
            msgs.put(m);
            payload.put("messages", msgs);
            payload.put("max_tokens", 8);
            payload.put("stream", false);

            byte[] body = payload.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            try (java.io.OutputStream os = conn.getOutputStream()) {
                os.write(body);
                os.flush();
            }
            int code = conn.getResponseCode();
            if (code >= 200 && code < 300) {
                return "OK:连接成功 (HTTP " + code + ")！端点 [" + endpoint + "] 与模型 [" + model + "] 验证通过。";
            } else {
                java.io.InputStream es = conn.getErrorStream();
                String err = "";
                if (es != null) {
                    err = com.agy.util.IoUtil.readAll(es, "UTF-8");
                }
                if (err.length() > 240) err = err.substring(0, 240) + "...";
                return "ERR:HTTP " + code + " (" + endpoint + "): " + err;
            }
        } catch (Exception e) {
            return "ERR:网络或地址异常 (" + endpoint + "): " + e.getMessage();
        }
    }

    // Native-only helpers used while preparing the trusted app document.
    public boolean isEngineReady() {
        return engine.isReady();
    }

    public int getEnginePort() {
        return engine.getPort();
    }

    public String getEngineBaseUrl() {
        return engine.getBaseUrl();
    }

    public String getCsrfToken() {
        return engine.getCsrfToken();
    }

    public String getConfig() {
        return config.get();
    }

    /** Native-only token inserted into the trusted top-level document. */
    public String getBlobBridgeToken() {
        return blobBridgeToken;
    }

    /** Saves a downloaded blob only for scripts holding the top-level document token. */
    @JavascriptInterface
    public void saveBlob(String token, String base64Data, String filename, String mimeType) {
        if (!matchesNativeBridgeToken(token)) {
            return;
        }
        final MainActivity act = activityRef != null ? activityRef.get() : MainActivity.activeActivity;
        if (act != null) {
            com.agy.ui.download.FileDownloader.handleBlobData(
                    act, base64Data, filename, mimeType);
        }
    }

    private boolean matchesNativeBridgeToken(String candidate) {
        if (candidate == null) {
            return false;
        }
        try {
            byte[] expected = blobBridgeToken.getBytes(Charset.forName("UTF-8"));
            byte[] actual = candidate.getBytes(Charset.forName("UTF-8"));
            return MessageDigest.isEqual(expected, actual);
        } catch (Exception ignored) {
            return false;
        }
    }

    private static String createBlobBridgeToken() {
        byte[] random = new byte[32];
        new SecureRandom().nextBytes(random);
        char[] hex = "0123456789abcdef".toCharArray();
        char[] encoded = new char[random.length * 2];
        for (int i = 0; i < random.length; i++) {
            int value = random[i] & 0xff;
            encoded[i * 2] = hex[value >>> 4];
            encoded[i * 2 + 1] = hex[value & 0x0f];
        }
        return new String(encoded);
    }
}
