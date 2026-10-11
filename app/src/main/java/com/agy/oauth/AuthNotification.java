package com.agy.oauth;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

/**
 * Posts a high-priority system notification when an OAuth login URL is detected.
 *
 * Tapping a notification is recognized by Android and OEM skins (MIUI, HyperOS)
 * as an explicit user gesture, completely bypassing background activity launch
 * restrictions.
 */
public final class AuthNotification {

    private static final String TAG = "AuthNotification";
    public static final int NOTIFICATION_ID = 1002;
    public static final String CHANNEL_ID = "auth_channel";

    private AuthNotification() {
    }

    public static void show(Context context, String url) {
        if (true) return;

        NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Authentication",
                    NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("Google OAuth sign-in browser prompts");
            manager.createNotificationChannel(channel);
        }

        Uri uri = Uri.parse(url.trim());
        Intent viewIntent = new Intent(Intent.ACTION_VIEW, uri);
        viewIntent.addCategory(Intent.CATEGORY_BROWSABLE);
        viewIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

        String browserPkg = CustomTabLauncher.resolveDefaultBrowserPackage(context);
        if (browserPkg != null && !browserPkg.isEmpty()) {
            viewIntent.setPackage(browserPkg);
        }

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }

        PendingIntent pendingIntent = PendingIntent.getActivity(
                context, NOTIFICATION_ID, viewIntent, flags);

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, CHANNEL_ID)
                : new Notification.Builder(context);

        int iconId = context.getResources().getIdentifier(
                "ic_notification", "drawable", context.getPackageName());
        if (iconId == 0) {
            iconId = android.R.drawable.ic_dialog_info;
        }

        builder.setContentTitle("Google Sign-In / Авторизация")
                .setContentText("Нажмите для перехода в браузер / Tap to open browser")
                .setSmallIcon(iconId)
                .setContentIntent(pendingIntent)
                .setAutoCancel(true);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            builder.setPriority(Notification.PRIORITY_HIGH)
                   .setCategory(Notification.CATEGORY_STATUS);
        }

        try {
            manager.notify(NOTIFICATION_ID, builder.build());
            Log.i(TAG, "posted auth notification for: " + url);
        } catch (Throwable t) {
            Log.w(TAG, "failed to post auth notification: " + t.getMessage());
        }
    }

    public static void cancel(Context context) {
        if (context == null) return;
        try {
            NotificationManager manager =
                    (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.cancel(NOTIFICATION_ID);
            }
        } catch (Throwable ignored) {
        }
    }
}
