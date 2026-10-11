package com.agy.oauth;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Parcel;
import android.util.Log;

import com.agy.ui.MainActivity;
import com.agy.util.PackageInspector;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Opens OAuth URLs in an external web browser.
 *
 * Direct browser launch with an explicit package is attempted first because:
 * 1. Implicit intents for accounts.google.com are hijacked by com.google.android.gms
 *    (Google Play Services) which silently swallows desktop OAuth redirect URIs.
 * 2. Explicit package launches bypass GMS domain verification and force the real
 *    web browser (Chrome, Mi Browser, Firefox, Yandex, etc.) to handle the URL.
 * 3. Custom Tab service binding is attempted as a secondary enhancement.
 */
public final class CustomTabLauncher {

    private static final String TAG = OAuthConstants.TAG;

    private static final String SERVICE_ACTION =
            "android.support.customtabs.action.CustomTabsService";
    private static final String SERVICE_TOKEN =
            "android.support.customtabs.ICustomTabsService";

    // AIDL transaction codes for ICustomTabsService:
    private static final int TX_WARMUP = 1;
    private static final int TX_NEW_SESSION = 2;

    private static final String[] CHROME_PACKAGES = {
            "com.android.chrome",
            "com.chrome.beta",
            "com.chrome.dev",
            "com.chrome.canary",
            "com.mi.globalbrowser",
            "com.android.browser",
            "org.mozilla.firefox",
            "org.mozilla.fenix",
            "com.microsoft.emmx",
            "com.opera.browser",
            "com.opera.mini.native",
            "com.opera.gx",
            "com.brave.browser",
            "com.sec.android.app.sbrowser",
            "com.yandex.browser",
            "com.yandex.browser.beta",
            "com.duckduckgo.mobile.android",
            "com.huawei.browser",
            "com.vivaldi.browser"
    };

    /** Session binder per browser package, established on first open. */
    private static final Map<String, IBinder> SESSIONS = new HashMap<>();

    /**
     * Resolves the user's default web browser package using a neutral HTTPS URL,
     * specifically filtering out Google Play Services and system disambiguation.
     */
    public static String resolveDefaultBrowserPackage(Context context) {
        if (context == null) return null;
        PackageManager pm = context.getPackageManager();
        if (pm == null) return null;

        Intent testIntent = new Intent(Intent.ACTION_VIEW, Uri.parse("https://example.com"));
        testIntent.addCategory(Intent.CATEGORY_BROWSABLE);

        // 1. Check user's explicitly chosen default browser
        try {
            ResolveInfo defaultResolve = pm.resolveActivity(testIntent, PackageManager.MATCH_DEFAULT_ONLY);
            if (defaultResolve != null && defaultResolve.activityInfo != null) {
                String pkg = defaultResolve.activityInfo.packageName;
                if (isRealBrowserPackage(pkg)) {
                    return pkg;
                }
            }
        } catch (Throwable t) {
            Log.w(TAG, "resolveActivity failed: " + t.getMessage());
        }

        // 2. Query all activities capable of browsing web URLs
        try {
            List<ResolveInfo> candidates = pm.queryIntentActivities(testIntent, 0);
            if (candidates != null) {
                for (ResolveInfo info : candidates) {
                    if (info != null && info.activityInfo != null) {
                        String pkg = info.activityInfo.packageName;
                        if (isRealBrowserPackage(pkg)) {
                            return pkg;
                        }
                    }
                }
            }
        } catch (Throwable t) {
            Log.w(TAG, "queryIntentActivities failed: " + t.getMessage());
        }

        return null;
    }

    private static boolean isRealBrowserPackage(String pkg) {
        if (pkg == null || pkg.isEmpty()) return false;
        if ("android".equals(pkg)) return false;
        if ("com.google.android.gms".equals(pkg)) return false;
        if ("com.google.android.googlequicksearchbox".equals(pkg)) return false;
        return true;
    }

    public boolean openInBrowser(Context context, String url) {
        if (context == null || url == null || url.trim().isEmpty()) {
            return false;
        }
        final Uri uri;
        try {
            uri = Uri.parse(url.trim());
        } catch (Exception e) {
            Log.e(TAG, "bad url: " + url, e);
            return false;
        }

        final Context target = (MainActivity.activeActivity != null)
                ? MainActivity.activeActivity
                : context;

        if (Looper.myLooper() == Looper.getMainLooper()) {
            return doOpen(target, uri);
        } else {
            final boolean[] success = new boolean[1];
            final java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
            new Handler(Looper.getMainLooper()).post(new Runnable() {
                @Override
                public void run() {
                    try {
                        success[0] = doOpen(target, uri);
                    } finally {
                        latch.countDown();
                    }
                }
            });
            try {
                latch.await(3, java.util.concurrent.TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
            }
            return success[0];
        }
    }

    private boolean doOpen(Context context, Uri uri) {
        // 1. Resolve and target the user's actual default browser explicitly.
        // Explicit package lock prevents com.google.android.gms from hijacking accounts.google.com!
        String defaultPkg = resolveDefaultBrowserPackage(context);
        if (defaultPkg != null) {
            Log.i(TAG, "targeting resolved default browser: " + defaultPkg);
            if (startPlainBrowser(context, defaultPkg, uri)) {
                return true;
            }
            if (openCustomTab(context, defaultPkg, uri)) {
                return true;
            }
        }

        // 2. Iterate known browser packages with explicit package targeting
        for (String pkg : CHROME_PACKAGES) {
            if (pkg.equals(defaultPkg)) continue;
            if (!PackageInspector.isPackageInstalled(context.getPackageManager(), pkg)) {
                continue;
            }
            if (startPlainBrowser(context, pkg, uri)) {
                return true;
            }
        }

        // 3. Try custom tab bind on installed packages
        for (String pkg : CHROME_PACKAGES) {
            if (pkg.equals(defaultPkg)) continue;
            if (!PackageInspector.isPackageInstalled(context.getPackageManager(), pkg)) {
                continue;
            }
            if (openCustomTab(context, pkg, uri)) {
                return true;
            }
        }

        // 4. Try system chooser
        if (openChooser(context, uri)) {
            return true;
        }

        // 5. Final fallback: implicit intent
        return openDefault(context, uri);
    }

    private boolean startPlainBrowser(Context context, String pkg, Uri uri) {
        Intent view = new Intent(Intent.ACTION_VIEW, uri);
        view.addCategory(Intent.CATEGORY_BROWSABLE);
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TOP
                | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (pkg != null && !pkg.isEmpty()) {
            view.setPackage(pkg);
        }
        try {
            context.startActivity(view);
            Log.i(TAG, "opened browser pkg=" + pkg + " url=" + uri);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "browser launch failed pkg=" + pkg + ": " + e.getMessage());
            return false;
        }
    }

    /** Opens as a Custom Tab in {@code pkg}; falls back to a plain tab there. */
    private boolean openCustomTab(Context context, String pkg, Uri uri) {
        IBinder session = SESSIONS.get(pkg);
        if (session != null) {
            return startView(context, pkg, uri, session);
        }
        Intent service = new Intent(SERVICE_ACTION).setPackage(pkg);
        ServiceConnection connection = new ServiceConnection() {
            @Override
            public void onServiceConnected(ComponentName name, IBinder binder) {
                IBinder s = newSession(binder);
                if (s != null) {
                    synchronized (SESSIONS) {
                        SESSIONS.put(pkg, s);
                    }
                    startView(context, pkg, uri, s);
                } else {
                    startPlainBrowser(context, pkg, uri);
                }
            }

            @Override
            public void onServiceDisconnected(ComponentName name) {
                synchronized (SESSIONS) {
                    SESSIONS.remove(pkg);
                }
            }
        };
        try {
            boolean bound = context.bindService(service, connection, Context.BIND_AUTO_CREATE);
            Log.i(TAG, "bind CustomTabsService pkg=" + pkg + " bound=" + bound);
            if (!bound) {
                return startPlainBrowser(context, pkg, uri);
            }
            return true;
        } catch (Exception e) {
            Log.w(TAG, "bind CustomTabsService failed pkg=" + pkg, e);
            return false;
        }
    }

    /** warmup + newSession over raw binder; returns the session binder or null. */
    private static IBinder newSession(IBinder service) {
        try {
            Parcel warm = Parcel.obtain();
            Parcel warmReply = Parcel.obtain();
            try {
                warm.writeInterfaceToken(SERVICE_TOKEN);
                warm.writeLong(0L);
                service.transact(TX_WARMUP, warm, warmReply, 0);
                warmReply.readInt();
            } finally {
                warm.recycle();
                warmReply.recycle();
            }
            Binder callback = new Binder() {
                @Override
                protected boolean onTransact(int code, Parcel data, Parcel reply, int flags) {
                    return true;
                }
            };
            Parcel data = Parcel.obtain();
            Parcel reply = Parcel.obtain();
            try {
                data.writeInterfaceToken(SERVICE_TOKEN);
                data.writeStrongBinder(callback);
                service.transact(TX_NEW_SESSION, data, reply, 0);
                reply.readInt();
            } finally {
                data.recycle();
                reply.recycle();
            }
            return callback;
        } catch (Exception e) {
            Log.w(TAG, "newSession failed", e);
            return null;
        }
    }

    private boolean startView(Context context, String pkg, Uri uri, IBinder session) {
        Intent view = new Intent(Intent.ACTION_VIEW, uri);
        Bundle extras = new Bundle();
        extras.putBinder(OAuthConstants.EXTRA_SESSION, session);
        extras.putInt(OAuthConstants.EXTRA_TOOLBAR_COLOR, OAuthConstants.TOOLBAR_COLOR_DARK);
        view.putExtras(extras);
        view.putExtra(OAuthConstants.EXTRA_APP_ID, context.getPackageName());
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        view.setPackage(pkg);
        try {
            context.startActivity(view);
            Log.i(TAG, "opened Custom Tab pkg=" + pkg + " url=" + uri);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "Custom Tab start failed pkg=" + pkg, e);
            return false;
        }
    }

    private boolean openDefault(Context context, Uri uri) {
        Intent view = new Intent(Intent.ACTION_VIEW, uri);
        view.addCategory(Intent.CATEGORY_BROWSABLE);
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        try {
            context.startActivity(view);
            Log.i(TAG, "opened default browser url=" + uri);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "openDefault failed: " + e.getMessage());
            return false;
        }
    }

    private boolean openChooser(Context context, Uri uri) {
        Intent view = new Intent(Intent.ACTION_VIEW, uri);
        view.addCategory(Intent.CATEGORY_BROWSABLE);
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        Intent chooser = Intent.createChooser(view, "Open in browser");
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            context.startActivity(chooser);
            Log.i(TAG, "opened browser chooser url=" + uri);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "no browser available for url: " + uri, e);
            return false;
        }
    }
}
