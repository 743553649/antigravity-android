package com.agy.ui.splash;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebView;
import android.widget.FrameLayout;

import com.agy.theme.ThemeManager;
import com.agy.util.ViewParams;

/**
 * Controls the splash screen overlay.
 *
 * Uses a lightweight native View (NativeSplashDotsView) for the initial loading
 * screen, saving ~40 MB RAM compared to initializing a dedicated Chromium WebView.
 *
 * If a fatal error or restart transient overlay needs to be displayed, an error
 * WebView is lazily initialized on demand to render HTML diagnostic logs and retry buttons.
 */
public final class SplashController {

    public static final int MODE_LOADING = 0;
    public static final int MODE_TRANSIENT = 1;
    public static final int MODE_ERROR = 2;

    private final Context context;
    private final FrameLayout container;
    private final NativeSplashDotsView nativeDotsView;
    private final ThemeManager theme;
    private final FrameLayout root;

    private WebView errorWebView;
    private SplashRetryListener retryListener;
    private boolean dismissed = false;
    private boolean fatalShown = false;
    private int mode = MODE_LOADING;

    public SplashController(Context context, ThemeManager theme, FrameLayout root) {
        this.context = context;
        this.theme = theme;
        this.root = root;

        this.container = new FrameLayout(context);
        this.container.setBackgroundColor(theme != null ? theme.getBackgroundColor() : Color.TRANSPARENT);

        this.nativeDotsView = new NativeSplashDotsView(context);
        if (theme != null) {
            this.nativeDotsView.setDotColor(theme.isDark() ? Color.WHITE : Color.BLACK);
        }

        FrameLayout.LayoutParams dotParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER
        );
        this.container.addView(this.nativeDotsView, dotParams);
    }

    /** Returns the root View of this splash controller to be added into the Activity's layout hierarchy. */
    public View view() {
        return container;
    }

    public int mode() {
        return mode;
    }

    public boolean isFatalShown() {
        return fatalShown;
    }

    public void setRetryListener(SplashRetryListener listener) {
        this.retryListener = listener;
        if (errorWebView != null) {
            SplashRetryBridge.bind(errorWebView, context, listener);
        }
    }

    private WebView getOrCreateErrorWebView() {
        if (errorWebView == null) {
            errorWebView = new WebView(context);
            errorWebView.setBackgroundColor(Color.TRANSPARENT);
            android.webkit.WebSettings settings = errorWebView.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            container.addView(errorWebView, ViewParams.full());
        }
        return errorWebView;
    }

    /** First render of the loading splash (before any show* call). */
    public void loadInitial() {
        mode = MODE_LOADING;
        showNativeLoading();
    }

    /** Show the animated loading splash again (startup or post-restart ready). */
    public void showLoading() {
        setVisible();
        if (mode != MODE_LOADING) {
            mode = MODE_LOADING;
            showNativeLoading();
        }
    }

    private void showNativeLoading() {
        if (errorWebView != null) {
            errorWebView.setVisibility(View.GONE);
        }
        nativeDotsView.setVisibility(View.VISIBLE);
        if (theme != null) {
            container.setBackgroundColor(theme.getBackgroundColor());
            nativeDotsView.setDotColor(theme.isDark() ? Color.WHITE : Color.BLACK);
        }
        nativeDotsView.startAnimation();
    }

    /** Non-fatal status (auto-restart running): overlay without a Retry button. */
    public void showTransient(String message) {
        if (fatalShown) {
            return;
        }
        setVisible();
        if (mode != MODE_TRANSIENT) {
            mode = MODE_TRANSIENT;
            nativeDotsView.stopAnimation();
            nativeDotsView.setVisibility(View.GONE);

            WebView errView = getOrCreateErrorWebView();
            errView.setVisibility(View.VISIBLE);
            SplashOverlayHtml.show(errView, "Restarting Antigravity", message,
                    foreground(), background(), false);
        }
    }

    /** Fail-closed startup failure: readable message with a Retry action. */
    public void showFatalError(String message) {
        if (fatalShown) {
            return;
        }
        fatalShown = true;
        mode = MODE_ERROR;
        setVisible();

        nativeDotsView.stopAnimation();
        nativeDotsView.setVisibility(View.GONE);

        WebView errView = getOrCreateErrorWebView();
        errView.setVisibility(View.VISIBLE);
        SplashRetryBridge.bind(errView, context, retryListener);
        SplashOverlayHtml.show(errView, "Antigravity failed to start", message,
                foreground(), background(), retryListener != null);
    }

    /** Called when a fresh ready generation begins; errors can be shown again. */
    public void clearFatal() {
        fatalShown = false;
        if (errorWebView != null) {
            errorWebView.setVisibility(View.GONE);
        }
    }

    public void setVisible() {
        dismissed = false;
        container.setAlpha(1f);
        if (container.getVisibility() != View.VISIBLE) {
            container.setVisibility(View.VISIBLE);
        }
        if (mode == MODE_LOADING) {
            nativeDotsView.startAnimation();
        }
        if (root != null) {
            root.bringChildToFront(container);
        }
    }

    /** Idempotent; called by AndroidBridge.onUiReady() on the main thread. */
    public void dismiss() {
        if (dismissed) {
            return;
        }
        dismissed = true;
        nativeDotsView.stopAnimation();
        container.animate()
                .alpha(0f)
                .setDuration(280)
                .withEndAction(new Runnable() {
                    @Override
                    public void run() {
                        container.setVisibility(View.GONE);
                        if (errorWebView != null) {
                            try {
                                errorWebView.stopLoading();
                                errorWebView.destroy();
                            } catch (Exception ignored) {
                            }
                            container.removeView(errorWebView);
                            errorWebView = null;
                        }
                    }
                })
                .start();
    }

    /** Re-render the splash after a theme/configuration change. */
    public void refresh() {
        if (theme != null) {
            container.setBackgroundColor(theme.getBackgroundColor());
            nativeDotsView.setDotColor(theme.isDark() ? Color.WHITE : Color.BLACK);
        }
    }

    /** API31+: cross-fade the system splash into this overlay. */
    public void installExitAnimation(Activity activity) {
        SplashExitInstaller.install(activity, container);
    }

    private String foreground() {
        return theme != null ? theme.getForegroundHex() : "#ffffff";
    }

    private String background() {
        return theme != null ? theme.getBackgroundHex() : "#101010";
    }
}
