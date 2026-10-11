package com.agy.ui;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;
import android.widget.Toast;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;

import com.agy.bridge.AndroidBridge;
import com.agy.core.CoreRuntimeState;
import com.agy.core.CoreServiceLauncher;
import com.agy.oauth.AuthNotification;
import com.agy.oauth.OAuthManager;
import com.agy.oauth.OAuthTokenStore;
import com.agy.runtime.RuntimeManager;
import com.agy.shell.ShizukuBridge;
import com.agy.theme.ThemeManager;
import com.agy.ui.lifecycle.AppLifecycle;
import com.agy.ui.lifecycle.BackNavigator;
import com.agy.ui.lifecycle.ThemeRefresher;
import com.agy.ui.splash.SplashController;
import com.agy.ui.webview.AgyWebChromeClient;
import com.agy.ui.webview.DesktopModePrefs;
import com.agy.ui.webview.WebViewHost;
import com.agy.util.ViewParams;

/**
 * Activity host: builds the WebView, starts CoreServerService, shows the
 * three-dot splash until the core UI has rendered, and wires theming/OAuth.
 * All logic lives in the helper classes; this only wires them and polls.
 */
public class MainActivity extends Activity
        implements WebViewHost.Listener, AgyWebChromeClient.FileChooserCallback {

    private static final String TAG = "MainActivity";
    private static final int REQUEST_STORAGE = 100;
    private static final int REQUEST_FILE_CHOOSER = 1002;
    private static final long SPLASH_TIMEOUT_MS = 45000;
    private static final long POLL_INTERVAL_MS = 50;

    public static volatile MainActivity activeActivity;

    private ValueCallback<Uri[]> filePathCallback;

    private ThemeManager themeManager;
    private OAuthManager oauthManager;
    private RuntimeManager runtimeManager;
    private ShizukuBridge shizukuBridge;
    private AndroidBridge androidBridge;
    private WebViewHost webViewHost;
    private SplashController splash;
    private FrameLayout rootLayout;
    private View authBannerView;

    private boolean appLoaded = false;
    private int loadedGeneration = -1;
    private long splashDeadline;

    private final Handler handler = new Handler(Looper.getMainLooper());

    /**
     * Runs for the whole activity life: it drives the splash, loads the app on
     * ready, and keeps watching for a post-ready core death.
     */
    private final Runnable pollServer = new Runnable() {
        @Override
        public void run() {
            watchCore();
            handler.postDelayed(this, POLL_INTERVAL_MS);
        }
    };

    private void watchCore() {
        String error = CoreRuntimeState.lastError;
        if (error != null) {
            if (CoreRuntimeState.restarting) {
                splash.showTransient(error);
            } else {
                splash.showFatalError(error);
            }
            return;
        }
        if (CoreRuntimeState.serverUrl != null && webViewHost != null) {
            int generation = CoreRuntimeState.readyGeneration;
            if (!appLoaded || (loadedGeneration > 0 && generation != loadedGeneration)) {
                appLoaded = true;
                loadedGeneration = generation;
                splash.clearFatal();
                if (generation > 1) {
                    splash.showLoading();
                }
                webViewHost.loadApp();
                handler.postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        if (appLoaded && !splash.isFatalShown()) {
                            Log.w(TAG, "watchdog: auto-dismissing splash after timeout");
                            dismissSplash();
                        }
                    }
                }, 10000);
            }
            return;
        }
        if (CoreRuntimeState.serverUrl == null && !splash.isFatalShown()
                && System.currentTimeMillis() > splashDeadline) {
            splash.showFatalError("core did not start within " + (SPLASH_TIMEOUT_MS / 1000) + "s");
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        activeActivity = this;
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);

        themeManager = new ThemeManager(this);
        themeManager.applyToActivity(this);


        oauthManager = new OAuthManager();
        runtimeManager = new RuntimeManager(this);
        shizukuBridge = new ShizukuBridge(this);
        androidBridge = new AndroidBridge(this, runtimeManager, shizukuBridge, oauthManager, themeManager);
        androidBridge.setActivity(this);
        webViewHost = new WebViewHost(this, themeManager, oauthManager, androidBridge, this);
        webViewHost.setListener(this);

        rootLayout = new FrameLayout(this);
        rootLayout.setBackgroundColor(themeManager.getBackgroundColor());
        setContentView(rootLayout);

        rootLayout.addView(webViewHost.getWebView(), ViewParams.full());

        splash = new SplashController(this, themeManager, rootLayout);
        splash.setRetryListener(this::retryCore);
        rootLayout.addView(splash.view(), ViewParams.full());
        splash.loadInitial();

        splash.installExitAnimation(this);

        splashDeadline = System.currentTimeMillis() + SPLASH_TIMEOUT_MS;
        requestStoragePermissions();
        startCoreService();

        handler.postDelayed(pollServer, 30);
    }

    private void startCoreService() {
        try {
            CoreServiceLauncher.start(this);
        } catch (Exception e) {
            showFatalError("cannot start core service: "
                    + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
        }
    }

    /** Keep the splash visible and replace it with a readable failure message. */
    public void showFatalError(String message) {
        splash.showFatalError(message);
    }

    /** Retry re-runs install + start: stop the service, then start it again. */
    private void retryCore() {
        splash.clearFatal();
        appLoaded = false;
        loadedGeneration = -1;
        splashDeadline = System.currentTimeMillis() + SPLASH_TIMEOUT_MS;
        splash.showLoading();
        CoreServiceLauncher.stop(this);
        try {
            java.io.File marker = new java.io.File(runtimeManager.getRuntimeDir(), com.agy.runtime.RuntimePaths.RUNTIME_MARKER);
            if (marker.exists()) {
                marker.delete();
            }
        } catch (Exception ignored) {
        }
        handler.postDelayed(this::startCoreService, 400);
    }

    /**
     * Page load finished, but the Web UI has NOT necessarily painted yet (the
     * app bundle is large), so the splash is NOT dismissed here. Dismissal is
     * driven by web/patches/startup_ready.js -> AndroidBridge.onUiReady().
     */
    @Override
    public void onPageFinished(String url) {
        Log.i(TAG, "onPageFinished " + url);
    }

    /** Idempotent; called by AndroidBridge.onUiReady() on the main thread. */
    public void dismissSplash() {
        Log.i(TAG, "dismissSplash: fading out splashView (280ms)");
        splash.dismiss();
    }

    public boolean isDesktopMode() {
        return webViewHost != null ? webViewHost.isDesktopMode() : DesktopModePrefs.isDesktopMode(this);
    }

    public void setDesktopMode(boolean enabled) {
        if (webViewHost != null) {
            webViewHost.setDesktopMode(enabled);
        } else {
            DesktopModePrefs.setDesktopMode(this, enabled);
        }
    }

    @Override
    protected void onDestroy() {
        if (activeActivity == this) {
            activeActivity = null;
        }
        dismissAuthBanner();
        AppLifecycle.destroy(handler);
        super.onDestroy();
    }

    @Override
    public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        AppLifecycle.trimMemory(level, handler, webViewHost);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        refreshTheme();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (webViewHost != null) {
            AppLifecycle.pauseTimers(webViewHost.getWebView());
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        com.agy.theme.LauncherIconSwitcher.onAppBackgrounded(this);
        if (webViewHost != null) {
            AppLifecycle.pauseTimers(webViewHost.getWebView());
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        activeActivity = this;
        if (OAuthTokenStore.hasToken(this)) {
            dismissAuthBanner();
        }
        if (webViewHost != null) {
            AppLifecycle.resume(webViewHost.getWebView());
        }
        refreshTheme();
    }

    private void refreshTheme() {
        ThemeRefresher.refresh(this, themeManager, rootLayout, splash, webViewHost);
        if (webViewHost != null && webViewHost.getWebView() != null) {
            String resolved = themeManager != null ? themeManager.getTheme() : "light";
            webViewHost.getWebView().evaluateJavascript(
                    "window.__AG_RESOLVED_THEME__='" + resolved + "'; window.__agOnSystemThemeChanged && window.__agOnSystemThemeChanged();", null);
        }
    }

    @Override
    public void onBackPressed() {
        if (!BackNavigator.handle(webViewHost != null ? webViewHost.getWebView() : null)) {
            super.onBackPressed();
        }
    }

    private void requestStoragePermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                if (!android.os.Environment.isExternalStorageManager()) {
                    Intent intent = new Intent(
                            android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                }
            } catch (Exception e) {
                try {
                    startActivity(new Intent(
                            android.provider.Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
                } catch (Exception ignored) {
                }
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE)
                    != PackageManager.PERMISSION_GRANTED
                    || checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{
                        android.Manifest.permission.READ_EXTERNAL_STORAGE,
                        android.Manifest.permission.WRITE_EXTERNAL_STORAGE
                }, REQUEST_STORAGE);
            }
        }
    }

    @Override
    public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> callback,
                                      WebChromeClient.FileChooserParams fileChooserParams) {
        if (filePathCallback != null) {
            filePathCallback.onReceiveValue(null);
            filePathCallback = null;
        }
        this.filePathCallback = callback;

        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");

        if (fileChooserParams != null
                && fileChooserParams.getMode() == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE) {
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        }

        try {
            startActivityForResult(intent, REQUEST_FILE_CHOOSER);
            return true;
        } catch (ActivityNotFoundException e) {
            try {
                Intent fallback = new Intent(Intent.ACTION_GET_CONTENT);
                fallback.addCategory(Intent.CATEGORY_OPENABLE);
                fallback.setType("*/*");
                if (fileChooserParams != null
                        && fileChooserParams.getMode() == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE) {
                    fallback.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                }
                startActivityForResult(Intent.createChooser(fallback, "Select File"), REQUEST_FILE_CHOOSER);
                return true;
            } catch (Exception ex) {
                Log.e(TAG, "Cannot launch file chooser: " + ex.getMessage());
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                    filePathCallback = null;
                }
                return false;
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_FILE_CHOOSER) {
            if (filePathCallback != null) {
                Uri[] results = null;
                if (resultCode == RESULT_OK && data != null) {
                    ClipData clipData = data.getClipData();
                    if (clipData != null && clipData.getItemCount() > 0) {
                        results = new Uri[clipData.getItemCount()];
                        for (int i = 0; i < clipData.getItemCount(); i++) {
                            results[i] = clipData.getItemAt(i).getUri();
                        }
                    } else if (data.getData() != null) {
                        results = new Uri[]{data.getData()};
                    } else if (data.getDataString() != null) {
                        results = new Uri[]{Uri.parse(data.getDataString())};
                    }
                }
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == com.agy.ui.download.FileDownloader.REQUEST_STORAGE_DOWNLOAD) {
            WebView wv = (webViewHost != null) ? webViewHost.getWebView() : null;
            com.agy.ui.download.FileDownloader.onPermissionResult(this, wv, requestCode, grantResults);
        }
    }

    public void showAuthBanner(final String url) {
        if (url == null || url.trim().isEmpty()) return;
        handler.post(new Runnable() {
            @Override
            public void run() {
                if (isFinishing() || isDestroyed()) return;
                final String targetUrl = url.trim();
                if (authBannerView != null) {
                    authBannerView.setTag(targetUrl);
                    authBannerView.setVisibility(View.VISIBLE);
                    authBannerView.bringToFront();
                    return;
                }
                if (rootLayout == null) return;

                final LinearLayout banner = new LinearLayout(MainActivity.this);
                authBannerView = banner;
                banner.setTag(targetUrl);
                banner.setOrientation(LinearLayout.VERTICAL);

                float density = getResources().getDisplayMetrics().density;
                int pad = (int) (16 * density);
                banner.setPadding(pad, pad, pad, pad);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                    banner.setElevation(24f * density);
                }

                // Background drawable: modern dark rounded card with Google blue accent border
                GradientDrawable bg = new GradientDrawable();
                bg.setColor(0xFF1E1F26);
                bg.setCornerRadius(16f * density);
                bg.setStroke((int) (1.5f * density), 0xFF4285F4);
                banner.setBackground(bg);

                // Row with title and close button
                LinearLayout header = new LinearLayout(MainActivity.this);
                header.setOrientation(LinearLayout.HORIZONTAL);
                header.setGravity(Gravity.CENTER_VERTICAL);

                TextView title = new TextView(MainActivity.this);
                title.setText("Google Sign-In / Вход в Google");
                title.setTextColor(0xFFFFFFFF);
                title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
                title.setTypeface(Typeface.DEFAULT_BOLD);
                LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
                header.addView(title, titleLp);

                TextView closeBtn = new TextView(MainActivity.this);
                closeBtn.setText("✕");
                closeBtn.setTextColor(0xFF9E9E9E);
                closeBtn.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
                closeBtn.setPadding(pad / 2, 0, pad / 2, 0);
                closeBtn.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        dismissAuthBanner();
                    }
                });
                header.addView(closeBtn);
                banner.addView(header);

                TextView subtitle = new TextView(MainActivity.this);
                subtitle.setText("Нажмите кнопку ниже для перехода в браузер:");
                subtitle.setTextColor(0xFFB0B0B0);
                subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
                subtitle.setPadding(0, pad / 3, 0, pad / 2);
                banner.addView(subtitle);

                // Buttons row
                LinearLayout btnRow = new LinearLayout(MainActivity.this);
                btnRow.setOrientation(LinearLayout.HORIZONTAL);
                btnRow.setGravity(Gravity.CENTER_VERTICAL);

                // Open Browser button (primary blue)
                Button openBtn = new Button(MainActivity.this);
                openBtn.setText("Открыть браузер");
                openBtn.setTextColor(0xFFFFFFFF);
                openBtn.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
                GradientDrawable btnBg = new GradientDrawable();
                btnBg.setColor(0xFF1A73E8);
                btnBg.setCornerRadius(8f * density);
                openBtn.setBackground(btnBg);
                openBtn.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        String currentUrl = (String) banner.getTag();
                        if (currentUrl != null && oauthManager != null) {
                            oauthManager.openInBrowser(MainActivity.this, currentUrl);
                        }
                    }
                });
                LinearLayout.LayoutParams openLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.3f);
                openLp.rightMargin = (int) (8 * density);
                btnRow.addView(openBtn, openLp);

                // Copy Link button (secondary dark gray)
                Button copyBtn = new Button(MainActivity.this);
                copyBtn.setText("Копировать");
                copyBtn.setTextColor(0xFFE0E0E0);
                copyBtn.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
                GradientDrawable copyBg = new GradientDrawable();
                copyBg.setColor(0xFF2E313D);
                copyBg.setCornerRadius(8f * density);
                copyBtn.setBackground(copyBg);
                copyBtn.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        String currentUrl = (String) banner.getTag();
                        if (currentUrl != null) {
                            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                            if (cm != null) {
                                cm.setPrimaryClip(ClipData.newPlainText("Google Sign-In URL", currentUrl));
                                Toast.makeText(MainActivity.this, "Ссылка скопирована в буфер", Toast.LENGTH_SHORT).show();
                            }
                        }
                    }
                });
                LinearLayout.LayoutParams copyLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
                btnRow.addView(copyBtn, copyLp);

                banner.addView(btnRow);

                FrameLayout.LayoutParams flp = new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        Gravity.TOP | Gravity.CENTER_HORIZONTAL);
                int margin = (int) (16 * density);
                flp.setMargins(margin, margin + (int) (32 * density), margin, margin);
                rootLayout.addView(banner, flp);
                banner.bringToFront();
            }
        });
    }

    public void dismissAuthBanner() {
        handler.post(new Runnable() {
            @Override
            public void run() {
                if (authBannerView != null && rootLayout != null) {
                    rootLayout.removeView(authBannerView);
                    authBannerView = null;
                }
                AuthNotification.cancel(MainActivity.this);
            }
        });
    }
}
