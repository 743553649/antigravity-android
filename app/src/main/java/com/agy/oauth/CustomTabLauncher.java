package com.agy.oauth;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.util.Log;

import com.agy.ui.MainActivity;

import java.util.List;

/**
 * Opens URLs and OAuth flows in the user's external web browser.
 */
public final class CustomTabLauncher {

    private static final String TAG = OAuthConstants.TAG;

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

        return doOpen(target, uri);
    }

    private boolean doOpen(Context context, Uri uri) {
        String defaultPkg = resolveDefaultBrowserPackage(context);

        // 1. Target resolved default browser explicitly if available
        if (defaultPkg != null) {
            Intent view = new Intent(Intent.ACTION_VIEW, uri);
            view.addCategory(Intent.CATEGORY_BROWSABLE);
            view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            view.setPackage(defaultPkg);
            try {
                context.startActivity(view);
                Log.i(TAG, "opened external browser pkg=" + defaultPkg + " url=" + uri);
                return true;
            } catch (Exception e) {
                Log.w(TAG, "failed to launch default browser pkg=" + defaultPkg + ": " + e.getMessage());
            }
        }

        // 2. Fallback to generic ACTION_VIEW
        Intent fallback = new Intent(Intent.ACTION_VIEW, uri);
        fallback.addCategory(Intent.CATEGORY_BROWSABLE);
        fallback.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            context.startActivity(fallback);
            Log.i(TAG, "opened browser via fallback url=" + uri);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "fallback launch failed: " + e.getMessage());
        }

        // 3. Fallback to system chooser
        try {
            Intent chooser = Intent.createChooser(fallback, "Open in browser");
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(chooser);
            Log.i(TAG, "opened chooser for url=" + uri);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "all browser launch attempts failed for url: " + uri, e);
            return false;
        }
    }
}
