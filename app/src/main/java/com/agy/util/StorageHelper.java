package com.agy.util;

import android.os.Environment;
import android.system.Os;
import android.util.Log;

import java.io.File;

/**
 * Manages symlinks between the app's internal home directory and
 * Android shared external storage (/storage/emulated/0).
 */
public final class StorageHelper {

    private static final String TAG = "StorageHelper";

    private StorageHelper() {
    }

    public static void setupSharedStorageLinks(File homeDir) {
        if (homeDir == null) return;
        try {
            File sharedStorage = new File("/storage/emulated/0");
            if (!sharedStorage.exists()) {
                sharedStorage = Environment.getExternalStorageDirectory();
            }
            if (sharedStorage != null && sharedStorage.isDirectory()) {
                linkSafe(sharedStorage, new File(homeDir, "storage"));
                linkSafe(sharedStorage, new File(homeDir, "sdcard"));

                File docs = new File(sharedStorage, "Documents");
                if (docs.isDirectory() || docs.mkdirs()) {
                    linkSafe(docs, new File(homeDir, "Documents"));

                    File agDir = new File(docs, "Antigravity");
                    if (!agDir.exists()) {
                        agDir.mkdirs();
                    }
                    linkSafe(agDir, new File(homeDir, "Projects"));
                }
                Log.i(TAG, "Shared storage symlinks created in " + homeDir.getAbsolutePath());
            }
        } catch (Exception e) {
            Log.w(TAG, "Failed to setup shared storage links: " + e.getMessage());
        }
    }

    private static void linkSafe(File target, File link) {
        try {
            if (link.exists() || isSymlink(link)) {
                link.delete();
            }
            Os.symlink(target.getAbsolutePath(), link.getAbsolutePath());
        } catch (Exception ignored) {
        }
    }

    private static boolean isSymlink(File file) {
        try {
            return !file.getAbsolutePath().equals(file.getCanonicalPath());
        } catch (Exception e) {
            return false;
        }
    }
}
