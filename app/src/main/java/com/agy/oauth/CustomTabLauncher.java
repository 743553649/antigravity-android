package com.agy.oauth;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
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
import java.util.Map;

/**
 * Opens OAuth URLs as a real Chrome Custom Tab, with no androidx.browser
 * dependency.
 *
 * A plain Chrome tab is opened first because it is synchronous and reliable;
 * this matches the original working behavior. A branded Custom Tab (a normal
 * ACTION_VIEW carrying a SESSION binder from Chrome's CustomTabsService) is
 * only attempted if the plain launch fails, since the service bind is async
 * and a missing/invalid session binder makes Chrome drop the tab. The final
 * fallback is any browser.
 */
public final class CustomTabLauncher {

    private static final String TAG = OAuthConstants.TAG;

    private static final String SERVICE_ACTION =
            "android.support.customtabs.action.CustomTabsService";
    private static final String SERVICE_TOKEN =
            "android.support.customtabs.ICustomTabsService";

    // AIDL transaction codes for ICustomTabsService (FIRST_CALL_TRANSACTION = 1):
    // warmup=1, newSession=2, mayLaunchUrl=3 (see ICustomTabsService.aidl).
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
            "com.microsoft.emmx",
            "com.opera.browser",
            "com.brave.browser",
            "com.sec.android.app.sbrowser"
    };

    /** Session binder per browser package, established on first open. */
    private static final Map<String, IBinder> SESSIONS = new HashMap<>();

    public boolean openInBrowser(Context context, String url) {
        if (context == null || url == null || url.trim().isEmpty()) {
            return false;
        }
        final Uri uri;
        try {
            uri = Uri.parse(url);
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
        // 1. Try system default browser FIRST (implicit Intent, no package lock).
        // This respects the user's preferred browser (Chrome, Mi Browser, Yandex, etc.)
        // and avoids MIUI / OEM explicit-package background launch restrictions.
        if (openDefault(context, uri)) {
            return true;
        }
        // 2. Fallback: try known browsers with direct launch (Chrome, Mi Browser, etc.)
        for (String pkg : CHROME_PACKAGES) {
            if (!PackageInspector.isPackageInstalled(context.getPackageManager(), pkg)) {
                continue;
            }
            if (startPlainChrome(context, pkg, uri)) {
                return true;
            }
        }
        // 3. Fallback: try custom tab bind
        for (String pkg : CHROME_PACKAGES) {
            if (!PackageInspector.isPackageInstalled(context.getPackageManager(), pkg)) {
                continue;
            }
            if (openCustomTab(context, pkg, uri)) {
                return true;
            }
        }
        // 4. Final fallback: system chooser
        return openChooser(context, uri);
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
                    startPlainChrome(context, pkg, uri);
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
                return startPlainChrome(context, pkg, uri);
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
                    // Opaque session handle: acknowledge every callback.
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
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
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

    private boolean startPlainChrome(Context context, String pkg, Uri uri) {
        Intent view = new Intent(Intent.ACTION_VIEW, uri);
        view.addCategory(Intent.CATEGORY_BROWSABLE);
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        view.setPackage(pkg);
        try {
            context.startActivity(view);
            Log.i(TAG, "opened browser pkg=" + pkg + " url=" + uri);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "browser launch failed pkg=" + pkg + ": " + e.getMessage());
            return false;
        }
    }

    private boolean openDefault(Context context, Uri uri) {
        Intent view = new Intent(Intent.ACTION_VIEW, uri);
        view.addCategory(Intent.CATEGORY_BROWSABLE);
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
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
        view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
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
